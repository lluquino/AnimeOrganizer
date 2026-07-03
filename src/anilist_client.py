import logging
import time
import requests
from typing import Optional
from .models import AniListMedia, Relation

ANILIST_ENDPOINT = "https://graphql.anilist.co"

SEARCH_QUERY = """
query ($search: String!) {
  Page(page: 1, perPage: 10) {
    media(search: $search, type: ANIME) {
      id
      idMal
      title { romaji english native }
      format
      status
      episodes
      season
      seasonYear
      synonyms
      relations {
        edges {
          relationType
          node {
            id
            title { romaji }
            format
          }
        }
      }
    }
  }
}
"""

MEDIA_BY_ID_QUERY = """
query ($id: Int!) {
  Media(id: $id) {
    id
    idMal
    title { romaji english native }
    format
    status
    episodes
    season
    seasonYear
    synonyms
    relations {
      edges {
        relationType
        node {
          id
          title { romaji }
          format
        }
      }
    }
  }
}
"""

STREAMING_EPISODES_QUERY = """
query ($id: Int!) {
  Media(id: $id) {
    streamingEpisodes {
      title
    }
  }
}
"""


def _parse_relations(media_data: dict) -> list[Relation]:
    relations = []
    for edge in media_data.get("relations", {}).get("edges", []):
        node = edge.get("node", {})
        relations.append(
            Relation(
                media_id=node.get("id", 0),
                relation_type=edge.get("relationType", ""),
                title_romaji=node.get("title", {}).get("romaji", ""),
                format=node.get("format", ""),
            )
        )
    return relations


def _parse_media(data: dict) -> AniListMedia:
    title = data.get("title", {})
    return AniListMedia(
        id=data.get("id", 0),
        id_mal=data.get("idMal"),
        title_romaji=title.get("romaji", ""),
        title_english=title.get("english"),
        title_native=title.get("native"),
        episodes=data.get("episodes"),
        format=data.get("format", ""),
        status=data.get("status", ""),
        season=data.get("season"),
        season_year=data.get("seasonYear"),
        synonyms=data.get("synonyms", []),
        relations=_parse_relations(data),
    )


class AniListClient:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.last_request = 0.0
        self.min_interval = 2.0
        self._session = requests.Session()

    def _rate_limit(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request = time.time()

    def _post(self, query: str, variables: dict, retries: int = 3) -> Optional[dict]:
        for attempt in range(retries):
            self._rate_limit()
            try:
                resp = self._session.post(
                    ANILIST_ENDPOINT,
                    json={"query": query, "variables": variables},
                    timeout=10,
                )
                if resp.status_code == 429 and attempt < retries - 1:
                    wait = 4 ** (attempt + 1)
                    self.logger.warning(
                        f"Rate limited, retrying in {wait}s (attempt {attempt + 1}/{retries})"
                    )
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as e:
                if attempt < retries - 1:
                    wait = 4 ** (attempt + 1)
                    self.logger.warning(
                        f"AniList request failed: {e}, retrying in {wait}s"
                    )
                    time.sleep(wait)
                    continue
                self.logger.warning(f"AniList request failed: {e}")
                return None
        return None

    def search_media(self, query: str) -> list[AniListMedia]:
        result = self._post(SEARCH_QUERY, {"search": query})
        if not result:
            return []
        media_list = result.get("data", {}).get("Page", {}).get("media", [])
        return [_parse_media(m) for m in media_list]

    def get_media_by_id(self, media_id: int) -> Optional[AniListMedia]:
        result = self._post(MEDIA_BY_ID_QUERY, {"id": media_id})
        if not result:
            return None
        media_data = result.get("data", {}).get("Media")
        if not media_data:
            return None
        return _parse_media(media_data)

    def get_streaming_episodes(self, media_id: int) -> list[str]:
        result = self._post(STREAMING_EPISODES_QUERY, {"id": media_id})
        if not result:
            return []
        episodes = result.get("data", {}).get("Media", {}).get("streamingEpisodes", [])
        return [ep.get("title", "") or "" for ep in episodes]
