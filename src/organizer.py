import os
import re
import shutil
import logging
from .models import MatchResult, ParseResult
from .config import AnimeConfig

INVALID_PATH_CHARS = re.compile(r'[<>"|?*]')
COLON_RE = re.compile(r":")
SLASH_RE = re.compile(r"[/\\]+")


def _sanitize(name: str) -> str:
    name = COLON_RE.sub(" -", name)
    name = INVALID_PATH_CHARS.sub("", name)
    name = SLASH_RE.sub(" - ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _strip_season_suffix(title: str, season: int) -> str:
    title = re.sub(
        r"\s+\d+(?:st|nd|rd|th)\s+[Ss]eason\s*$", "", title
    ).strip()
    title = re.sub(
        r"\s+[Ss]eason\s+\d+\s*$", "", title
    ).strip()
    if re.search(rf"\s+{re.escape(str(season))}\s*$", title):
        if not re.search(r"\b(?:Part|Cour)\s+\d+\s*$", title, re.IGNORECASE):
            title = re.sub(
                rf"\s+{re.escape(str(season))}\s*$", "", title
            ).strip()
    return title


def _quality_score(filename: str) -> int:
    f = filename.lower()
    score = 0
    if "1080" in f:
        score += 100
    if "720" in f:
        score += 50
    if "480" in f:
        score += 20
    if "hevc" in f or "x265" in f or "h265" in f:
        score += 30
    if "avc" in f or "x264" in f or "h264" in f:
        score += 10
    if "web" in f:
        score += 20
    if "bluray" in f or "bd" in f:
        score += 15
    if "10bit" in f:
        score += 5
    return score


def _resolve_collision(path: str, src_path: str = None, mode: str = "keep_both") -> str:
    if not os.path.exists(path):
        return path

    if mode == "keep_both":
        base, ext = os.path.splitext(path)
        counter = 1
        while os.path.exists(f"{base} ({counter}){ext}"):
            counter += 1
        return f"{base} ({counter}){ext}"

    if src_path is None or not os.path.exists(src_path):
        return path

    src_size = os.path.getsize(src_path)
    dst_size = os.path.getsize(path)

    src_wins = False
    if mode == "keep_largest":
        src_wins = src_size > dst_size
    elif mode == "keep_best":
        src_score = _quality_score(os.path.basename(src_path))
        dst_score = _quality_score(os.path.basename(path))
        if src_score > dst_score:
            src_wins = True
        elif src_score < dst_score:
            src_wins = False
        else:
            src_wins = src_size > dst_size
    else:
        return path

    if src_wins:
        os.remove(path)
        return path
    else:
        return None


def _format_title(title: str, mode: str) -> str:
    if mode != "title_case":
        return title
    return " ".join(w.capitalize() for w in title.split())


def _remove_empty_parent_dirs(path: str, stop_dir: str) -> None:
    parent = os.path.dirname(path)
    while parent and os.path.isdir(parent) and parent != stop_dir:
        if os.listdir(parent):
            break
        try:
            os.rmdir(parent)
        except OSError:
            break
        parent = os.path.dirname(parent)


class FileOrganizer:
    def __init__(self, config: AnimeConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)

    def organize(
        self, src_path: str, match: MatchResult, parse: ParseResult
    ) -> None:
        root = match.root_media or match.media
        official_title = _sanitize(root.best_title)
        official_title = _strip_season_suffix(official_title, match.season)
        official_title = _format_title(official_title, self.config.title_format)

        ep_name = (
            f" - {_sanitize(match.episode_title)}"
            if match.episode_title
            else ""
        )

        if match.is_special:
            special_folder = _sanitize(
                match.special_folder or self.config.specials.folder
            )
            relative = self.config.special_pattern.format(
                title=official_title,
                season=match.season,
                episode=match.episode,
                ep_name=ep_name,
                ext=parse.file_ext,
                special=special_folder,
            )
        else:
            relative = self.config.output_pattern.format(
                title=official_title,
                season=match.season,
                episode=match.episode,
                ep_name=ep_name,
                ext=parse.file_ext,
            )

        dest_path = os.path.join(self.config.output_dir, relative)
        dest_dir = os.path.dirname(dest_path)
        dest_path = _resolve_collision(dest_path, src_path, self.config.collision_mode)

        if dest_path is None:
            existing_path = os.path.join(dest_dir, dest_name)
            self.logger.info(
                "Kept existing: %s, removed source: %s",
                os.path.relpath(existing_path, self.config.output_dir),
                os.path.basename(src_path),
            )
            os.remove(src_path)
            _remove_empty_parent_dirs(src_path, self.config.watch_dir)
            return

        os.makedirs(dest_dir, exist_ok=True)

        try:
            shutil.move(src_path, dest_path)
            self.logger.info(
                "Moved: %s -> %s",
                os.path.basename(src_path),
                os.path.relpath(dest_path, self.config.output_dir),
            )
            _remove_empty_parent_dirs(src_path, self.config.watch_dir)
        except OSError as e:
            self.logger.error("Failed to move '%s': %s", src_path, e)