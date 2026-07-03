from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ParseResult:
    title: str
    episode: int
    group: Optional[str] = None
    season: Optional[int] = None
    ep_end: Optional[int] = None
    is_special: bool = False
    is_batch: bool = False
    file_ext: str = ""


@dataclass
class Relation:
    media_id: int
    relation_type: str
    title_romaji: str
    format: str


@dataclass
class AniListMedia:
    id: int
    id_mal: Optional[int]
    title_romaji: str
    title_english: Optional[str]
    title_native: Optional[str]
    episodes: Optional[int]
    format: str
    status: str
    season: Optional[str]
    season_year: Optional[int]
    synonyms: list = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)

    @property
    def best_title(self) -> str:
        return self.title_romaji or self.title_english or self.title_native or "Unknown"


@dataclass
class MatchResult:
    media: AniListMedia
    season: int
    episode: int
    episode_title: Optional[str]
    is_special: bool
    special_folder: Optional[str]
    original_title: str
    root_media: Optional[AniListMedia] = None
