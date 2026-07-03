import logging
import re
from difflib import SequenceMatcher
from typing import Optional
from .models import ParseResult, MatchResult, AniListMedia
from .anilist_client import AniListClient
from .config import AnimeConfig


def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


class AnimeMatcher:
    def __init__(self, config: AnimeConfig, client: AniListClient):
        self.config = config
        self.client = client
        self.logger = logging.getLogger(__name__)
        self._search_cache: dict[str, Optional[AniListMedia]] = {}
        self._media_cache: dict[int, Optional[AniListMedia]] = {}
        self._streaming_cache: dict[int, list[str]] = {}

    def _title_similarity(self, query: str, media: AniListMedia) -> float:
        q = _normalize(query)
        candidates = [
            _normalize(media.title_romaji or ""),
            _normalize(media.title_english or ""),
            _normalize(media.title_native or ""),
        ] + [_normalize(s) for s in media.synonyms]

        for c in candidates:
            if not c:
                continue
            if c == q:
                return 1.0
            if c in q or q in c:
                return 0.9
            ratio = SequenceMatcher(None, q, c).ratio()
            if ratio > 0.75:
                return ratio

        return 0.0

    def _search_best_match(self, query: str) -> Optional[AniListMedia]:
        if query in self._search_cache:
            return self._search_cache[query]

        results = self.client.search_media(query)
        if not results:
            clean = re.sub(r"\s+[Ss]\d+\s*$", "", query).strip()
            if clean != query:
                result = self._search_best_match(clean)
                self._search_cache[query] = result
                return result
            clean = re.sub(r"\s+(?:Season|Cour|Part)\s+\d+", "", query).strip()
            if clean != query:
                result = self._search_best_match(clean)
                self._search_cache[query] = result
                return result
            clean = re.sub(r"\s*\([^)]*\)\s*$", "", query).strip()
            if clean != query:
                result = self._search_best_match(clean)
                self._search_cache[query] = result
                return result
            self._search_cache[query] = None
            return None

        best = None
        best_score = 0.0

        for media in results:
            score = self._title_similarity(query, media)
            if score > best_score:
                best_score = score
                best = media

        if best_score < 0.5:
            clean = re.sub(r"\s+(?:Season|Cour|Part)\s+\d+", "", query).strip()
            if clean != query:
                result = self._search_best_match(clean)
                self._search_cache[query] = result
                return result
            clean2 = re.sub(r"\s*\([^)]*\)\s*$", "", query).strip()
            if clean2 != query:
                result = self._search_best_match(clean2)
                self._search_cache[query] = result
                return result
            self._search_cache[query] = None
            return None

        self._search_cache[query] = best
        return best

    def _get_media(self, media_id: int) -> Optional[AniListMedia]:
        if media_id not in self._media_cache:
            self._media_cache[media_id] = self.client.get_media_by_id(media_id)
        return self._media_cache[media_id]

    def _resolve_root(self, media: AniListMedia) -> AniListMedia:
        visited = set()
        current = media
        while current.id not in visited:
            visited.add(current.id)
            prequels = [
                r
                for r in current.relations
                if r.relation_type == "PREQUEL" and r.format == "TV"
            ]
            if not prequels:
                break
            next_media = self._get_media(prequels[0].media_id)
            if not next_media:
                break
            current = next_media
        return current

    def _resolve_season(self, media: AniListMedia) -> int:
        season = 1
        visited = set()
        current = media

        while current.id not in visited:
            visited.add(current.id)
            prequels = [
                r
                for r in current.relations
                if r.relation_type == "PREQUEL" and r.format == "TV"
            ]
            if not prequels:
                break
            current = self._get_media(prequels[0].media_id)
            if not current:
                season += 1
                break
            season += 1

        return season

    def _follow_sequels(self, media: AniListMedia, target_season: int) -> AniListMedia:
        current = media
        current_season = self._resolve_season(current)

        while current_season < target_season:
            sequels = [
                r
                for r in current.relations
                if r.relation_type == "SEQUEL" and r.format == "TV"
            ]
            if not sequels:
                self.logger.warning(
                    f"No SEQUEL found for {current.best_title} to reach season {target_season}"
                )
                break
            next_id = sequels[0].media_id
            next_media = self._get_media(next_id)
            if not next_media:
                break
            current = next_media
            current_season = self._resolve_season(current)

        return current

    def _is_long_runner(self, media: AniListMedia) -> bool:
        if media.format != "TV":
            return False
        if media.episodes is None:
            return True
        return media.episodes > 100

    def _apply_arc_mapping(
        self, media: AniListMedia, episode: int
    ) -> Optional[int]:
        title = media.best_title
        if title not in self.config.arc_mappings:
            return None

        arcs = self.config.arc_mappings[title]
        for arc_num in sorted(arcs.keys()):
            bounds = arcs[arc_num]
            if isinstance(bounds, list):
                if len(bounds) == 2:
                    start, end = bounds
                    if start <= episode <= end:
                        return arc_num
                elif len(bounds) == 1:
                    if episode >= bounds[0]:
                        return arc_num
            elif isinstance(bounds, (int, float)):
                if episode >= bounds:
                    return arc_num
        return None

    def _apply_title_mapping(self, title: str) -> Optional[dict]:
        if title in self.config.title_mappings:
            mapping = self.config.title_mappings[title]
            if isinstance(mapping, str):
                return {"title": mapping}
            if isinstance(mapping, dict):
                return mapping
        return None

    def _get_episode_title(
        self, media_id: int, episode: int, is_special: bool = False
    ) -> Optional[str]:
        if is_special:
            return None
        if media_id not in self._streaming_cache:
            self._streaming_cache[media_id] = self.client.get_streaming_episodes(
                media_id
            )
        episodes = self._streaming_cache[media_id]
        if episodes and 0 <= episode - 1 < len(episodes):
            title = episodes[episode - 1]
            return title if title else None
        return None

    def _handle_special(
        self, media: AniListMedia, season: int, special_num: int, original_title: str
    ) -> Optional[MatchResult]:
        title = media.best_title
        override = self.config.specials_overrides.get(original_title) or \
                   self.config.specials_overrides.get(title)

        mode = self.config.specials.default_mode
        folder = self.config.specials.folder

        if override:
            mode = override.get("mode", mode)
            folder = override.get("folder", folder)

        if mode == "skip":
            self.logger.info(f"Skipping special {special_num} for {title}")
            return None

        if mode == "sequential":
            total = media.episodes
            if total is None:
                self.logger.warning(
                    f"Cannot use sequential for {title}: episode count unknown, "
                    f"falling back to folder mode"
                )
                mode = "folder"
            else:
                ep_num = total + special_num
                ep_title = self._get_episode_title(media.id, ep_num)
                return MatchResult(
                    media=media,
                    season=season,
                    episode=ep_num,
                    episode_title=ep_title,
                    is_special=False,
                    special_folder=None,
                    original_title=original_title,
                )

        ep_title = self._get_episode_title(media.id, special_num, is_special=True)
        return MatchResult(
            media=media,
            season=season,
            episode=special_num,
            episode_title=ep_title,
            is_special=True,
            special_folder=folder,
            original_title=original_title,
        )

    def match(self, parse_result: ParseResult) -> Optional[MatchResult]:
        mapped = self._apply_title_mapping(parse_result.title)

        if mapped:
            search_title = mapped["title"]
            media = self._search_best_match(search_title)
            if not media:
                self.logger.warning(
                    f"title_mapping '{parse_result.title}' -> "
                    f"'{search_title}' not found on AniList"
                )
                return None
            season = mapped.get("season") or self._resolve_season(media)
        else:
            media = self._search_best_match(parse_result.title)
            if not media:
                self.logger.warning(
                    f"No match found for '{parse_result.title}' on AniList"
                )
                return None
            season = self._resolve_season(media)

        if parse_result.season is not None and not mapped:
            media = self._follow_sequels(media, parse_result.season)
            resolved = self._resolve_season(media)
            season = max(parse_result.season, resolved)

        root = self._resolve_root(media)

        if self._is_long_runner(media):
            arc_season = self._apply_arc_mapping(media, parse_result.episode)
            if arc_season is not None:
                season = arc_season

        if parse_result.is_special:
            result = self._handle_special(
                media, season, parse_result.episode, parse_result.title
            )
            if result is not None:
                result.root_media = root
            return result

        ep_title = self._get_episode_title(media.id, parse_result.episode)

        return MatchResult(
            media=media,
            season=season,
            episode=parse_result.episode,
            episode_title=ep_title,
            is_special=False,
            special_folder=None,
            original_title=parse_result.title,
            root_media=root,
        )
