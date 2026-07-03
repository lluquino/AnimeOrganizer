import yaml
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SpecialsConfig:
    default_mode: str = "folder"
    folder: str = "Extras"


@dataclass
class AnimeConfig:
    watch_dir: str = "/downloads"
    output_dir: str = "/anime-library"
    log_level: str = "INFO"
    collision_mode: str = "keep_both"
    title_format: str = "original"
    output_pattern: str = "{title}/Season {season}/{title} S{season:02d}E{episode:02d}{ep_name}{ext}"
    special_pattern: str = "{title}/{special}/{title} - Special {episode:02d}{ep_name}{ext}"
    specials: SpecialsConfig = field(default_factory=SpecialsConfig)
    specials_overrides: dict = field(default_factory=dict)
    title_mappings: dict = field(default_factory=dict)
    arc_mappings: dict = field(default_factory=dict)


def load_config(path: str) -> AnimeConfig:
    config = AnimeConfig()

    if not os.path.exists(path):
        return config

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data:
        return config

    if "watch_dir" in data:
        config.watch_dir = data["watch_dir"]
    if "output_dir" in data:
        config.output_dir = data["output_dir"]
    if "log_level" in data:
        config.log_level = data["log_level"]
    if "collision_mode" in data:
        config.collision_mode = data["collision_mode"]
    if "title_format" in data:
        config.title_format = data["title_format"]
    if "output_pattern" in data:
        config.output_pattern = data["output_pattern"]
    if "special_pattern" in data:
        config.special_pattern = data["special_pattern"]

    if "specials" in data:
        s = data["specials"]
        if "default_mode" in s:
            config.specials.default_mode = s["default_mode"]
        if "folder" in s:
            config.specials.folder = s["folder"]

    if "specials_overrides" in data:
        config.specials_overrides = data["specials_overrides"]
    if "title_mappings" in data:
        config.title_mappings = data["title_mappings"]
    if "arc_mappings" in data:
        config.arc_mappings = data["arc_mappings"]

    return config
