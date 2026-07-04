# AnimeOrganizer

Docker service that monitors a download folder, identifies anime episodes via the **AniList API**, and organizes them into a clean, standardized library structure.

```
/downloads                          /anime-library
  [Erai-raws] Dr. Stone S3E10.mkv   Dr. STONE/
  [Erai-raws] Frieren - 01.mkv        Season 2/
  [Erai-raws] Bocchi! - 05.mkv          Dr. STONE S02E01 - Episode 16 - Medusa Mechanism.mkv
                                       Season 3/
                                         Dr. STONE S03E10 - Episode 7 - The Two Scientists.mkv
                                     Frieren/
                                       Season 1/
                                         Frieren S01E01 - Episode 1 - The Journey's End.mkv
                                     Bocchi the Rock!/
                                       Season 1/
                                         Bocchi the Rock! S01E05.mkv
```

## Features

- **Automatic AniList matching** — resolves series, seasons, arcs, and episode titles via GraphQL
- **Franchise-aware folder grouping** — sequel series (e.g. *Dr. Stone: Stone Wars*) are placed under the root franchise folder (`Dr. STONE/Season 2/`)
- **Season resolution** — follows SEQUEL/PREQUEL relations on AniList to determine the correct season number
- **Batch torrent support** — expands `Title - 01 ~ 12 [BATCH]` folders; processes files individually
- **Specials handling** — folder mode, sequential numbering, or skip (configurable per series)
- **Arc mappings for long-runners** — maps absolute episode ranges to seasons (One Piece, Detective Conan)
- **Collision resolution** — `keep_both`, `keep_largest`, or `keep_best` when duplicates are detected
- **Configurable title formatting** — `original` or `title_case` capitalization
- **Real-time monitoring** — uses `watchdog` to detect new files instantly
- **Title mappings** — override titles that are hard to match on AniList
- **Docker-native** — stateless, config-driven, easy to deploy

## Quick Start

### 1. Clone

```bash
git clone https://github.com/lluquino/AnimeOrganizer.git
cd AnimeOrganizer
```

### 2. Configure

Edit `config.yaml` to set your watch and output directories:

```yaml
watch_dir: /downloads
output_dir: /anime-library
```

### 3. Run

```bash
docker compose up --build -d
```

Place `.mkv` / `.mp4` / `.avi` files in the mounted `downloads` folder. They will be automatically matched, renamed, and moved to the library.

## Configuration

All options in `config.yaml`:

```yaml
watch_dir: /downloads
output_dir: /anime-library
log_level: INFO
collision_mode: keep_both
title_format: original
specials:
  default_mode: "folder"
  folder: "Extras"
specials_overrides:
  "Lord of Mysteries":
    mode: "sequential"
title_mappings:
  "Spy x Family":
    title: "SPY×FAMILY"
  "Mushoku Tensei S2":
    title: "Mushoku Tensei II: Isekai Ittara Honki Dasu"
    season: 2
  "Spy x Family - Movie":
    title: "SPY×FAMILY CODE: White"
arc_mappings:
  "One Piece":
    1: [1, 61]
    2: [62, 135]
    11: [1087]
```

### Field Reference

#### `collision_mode`
Controls what happens when two files would end up with the same destination path.

| Mode | Behavior |
|------|----------|
| `keep_both` (default) | Appends `(1)`, `(2)`, etc. to the new file: `Show S01E01.mkv` → `Show S01E01 (1).mkv` |
| `keep_largest` | Compares file sizes; keeps the larger one, removes the smaller |
| `keep_best` | Scores by quality heuristics: 1080p > 720p > 480p, HEVC > AVC, WEB > others, then falls back to size |

#### `title_format`
How the anime title is capitalized in folder/file names.

| Mode | Input (`best_title`) | Output |
|------|--------------------|--------|
| `original` (default) | `Dr. STONE: STONE WARS` | `Dr. STONE - STONE WARS` |
| `title_case` | `Dr. STONE: STONE WARS` | `Dr. Stone - Stone Wars` |

Uses Python's `str.capitalize()` on each word: first letter uppercase, rest lowercase.

#### `specials`
Controls how special episodes (detected as `Special N` in filenames) are handled.

| Mode | Description | Example |
|------|------------|---------|
| `folder` | Places the special in a subfolder (default: `Extras`) under the series root | `{Anime}/Extras/{Anime} - Special 01.mkv` |
| `sequential` | Numbers the special as a continuation of the regular season: `episode = total_episodes + special_number`. Requires AniList to report the episode count. | If `total_episodes = 12`, `Special 01` becomes `S01E13` |
| `skip` | Ignores the file entirely; it stays in the watch folder | — |

The `folder` key sets the subdirectory name when mode is `folder` (default: `Extras`).

Per-series overrides in `specials_overrides` take precedence over `default_mode`:

```yaml
specials_overrides:
  "Lord of Mysteries":
    mode: "sequential"   # insert as regular episodes
  "One Piece":
    mode: "folder"
    folder: "Películas y Especiales"  # custom folder name
```

#### `title_mappings`
Redirects a parsed title to an AniList entry that would not be found by search alone. This is useful for:

- **Titles AniList doesn't find** — e.g., `Mahou no Shimai Lulutto Lilly` → `Mahou no Shimai LuluttoLilly`
- **Wrong season resolution** — e.g., `Spy x Family` season 2 gets misidentified as season 3 due to a movie in the franchise chain; the mapping forces it to the correct AniList entry
- **Mismatched naming** — e.g., `Hokuto no Ken (2026)` → `Hokuto no Ken` (forcing season 2 since the 2026 series is actually a sequel)
- **Mapping to a different season entry** — optionally include `season: N` to skip SEQUEL traversal and use that season number directly

```yaml
title_mappings:
  # Simple: just redirect the search
  "Mahou no Shimai Lulutto Lilly":
    title: "Mahou no Shimai LuluttoLilly"

  # Redirect + force season (no SEQUEL traversal)
  "Hokuto no Ken (2026)":
    title: "Hokuto no Ken"
    season: 2

  # Fix franchise traversal
  "Spy x Family":
    title: "SPY×FAMILY"

  # Map to correct sequel entry
  "Jidouhanbaiki ni Umarekawatta Ore wa Meikyuu o Samayou":
    title: "Jidou Hanbaiki ni Umarekawatta Ore wa Meikyuu wo Samayou 3rd Season"
    season: 3
```

**Priority**: title_mappings are checked **before** any AniList search. If matched, the mapped title is used directly and SEQUEL traversal is skipped (only used if `season` is not provided in the mapping).

#### `arc_mappings`
For long-running series (One Piece, Detective Conan) where AniList stores the entire series as a single media entry with absolute episode numbering. Maps absolute episode ranges to season numbers.

```yaml
arc_mappings:
  "One Piece":
    1: [1, 61]         # episodes 1-61 → Season 1 (East Blue)
    2: [62, 135]       # episodes 62-135 → Season 2 (Alabasta)
    11: [1087]         # episodes 1087+ → Season 11 (Egghead, open-ended)
```

- `[start, end]` — closed range
- `[start]` or a bare integer — from start to infinity (for ongoing arcs)
- Evaluated in ascending order of start; first match wins

#### `output_pattern` / `special_pattern`

Controls the directory structure and filename for organized files. Both are Python format strings with these placeholders:

| Placeholder | Description | Example output |
|-------------|-------------|----------------|
| `{title}` | Anime title (sanitized, formatted) | `Dr. STONE` |
| `{season}` | Season number | `2` |
| `{episode}` | Episode number | `1` |
| `{ep_name}` | Episode title with leading ` - `, or empty | ` - Episode 16 - Medusa Mechanism` |
| `{ext}` | File extension with dot | `.mkv` |
| `{special}` | Specials folder name (only in `special_pattern`) | `Extras` |

Standard Python format specifiers are supported (e.g. `{season:02d}` for zero-padding).

**Defaults:**

```yaml
# Regular episode → "Dr. STONE/Season 2/Dr. STONE S02E01 - Episode 16 - Medusa Mechanism.mkv"
output_pattern: "{title}/Season {season}/{title} S{season:02d}E{episode:02d}{ep_name}{ext}"

# Special → "Dr. STONE/Extras/Dr. STONE - Special 01.mkv"
special_pattern: "{title}/{special}/{title} - Special {episode:02d}{ep_name}{ext}"
```

**Custom examples:**

```yaml
# Plex-style: /TV/Dr. STONE/Season 02/Dr. STONE - 02x01 - Episode Title.mkv
output_pattern: "{title}/Season {season:02d}/{title} - {season}x{episode:02d}{ep_name}{ext}"

# Minimal: /Anime/Dr. STONE/S02E01.mkv
output_pattern: "{title}/S{season:02d}E{episode:02d}{ep_name}{ext}"

# No season folder, flat structure: /Dr. STONE/Dr. STONE E01.mkv
output_pattern: "{title}/{title} E{episode:02d}{ep_name}{ext}"
```

## How It Works

```
New .mkv/.mp4/.avi file
        │
        ▼
  ┌──────────┐
  │  Parser  │  Extracts: group, title, season?, episode, special?, batch?
  └────┬─────┘
        │
        ▼
  ┌──────────┐
  │  Matcher │  1. Checks title_mappings for overrides
  │          │  2. Searches AniList by title
  │          │  3. Follows SEQUEL relations to find correct season
  │          │  4. Follows PREQUEL relations to find root franchise
  │          │  5. Applies arc_mappings for long-runners
  │          │  6. Handles specials per config
  └────┬─────┘
        │
        ▼
  ┌───────────┐
  │ Organizer │  Builds destination path, resolves collisions, moves file
  └───────────┘
```

### Season Resolution

Each anime season is a separate AniList entry linked by `SEQUEL`/`PREQUEL` relations:

```
Dr. Stone (S1) ──SEQUEL──▶ Dr. Stone: Stone Wars (S2) ──SEQUEL──▶ Dr. Stone: New World (S3)
```

The matcher traverses this chain to assign the correct season number and groups related entries under the root franchise title.

### Batch Folders

Folders matching patterns like `Title - 01 ~ 12 [tags]` or containing `[BATCH]` are not moved themselves. Their contents are processed individually when files appear inside them (watchdog is recursive).

## Output Structure

```
/anime-library/
├── Dr. STONE/                        # Root franchise title
│   ├── Season 2/
│   │   └── Dr. STONE S02E01 - Episode 16 - Medusa Mechanism.mkv
│   └── Season 3/
│       └── Dr. STONE S03E10 - Episode 7 - The Two Scientists.mkv
├── Frieren/
│   └── Season 1/
│       └── Frieren S01E01 - The Journey's End.mkv
├── ONE PIECE/
│   ├── Season 1/
│   │   ├── ONE PIECE S01E01.mkv
│   │   └── ...
│   └── Season 11/
│       └── ONE PIECE S11E1087.mkv
├── SPY×FAMILY/
│   └── Season 3/
│       └── SPY×FAMILY S03E01 - OPERATION STRIX.mp4
└── Full Metal Panic!/
    └── Season 3/
        ├── Full Metal Panic! S03E01 - Zero Hour.mkv
        └── Full Metal Panic! S03E12 - Onward, Onward.mkv
```

Specials (folder mode):
```
└── Extras/
    └── Anime Title - Special 01.mkv
```

## Requirements

- Python 3.12+
- Docker (optional, for containerized deployment)

## Development

```bash
# Create venv and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
pip install pytest
pytest tests/

# Test data generation
python tests/create_test_data.py

# Manual run (without Docker)
python -m src.main
```

## License

GNU General Public License v3.0. See [LICENSE](LICENSE).
