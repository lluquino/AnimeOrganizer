import re
from typing import Optional
from .models import ParseResult

KNOWN_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".mov"}

ANNOTATIONS_PATTERN = re.compile(
    r"\s*\((?:REPACK|PROPER|CA|UNCENSORED|UNC|v\d+)\)"
)

SXXEYY_PATTERN = re.compile(r"\bS(\d{1,2})[Ee](\d{1,3})\b")

SEASON_EPISODE_PATTERN = re.compile(
    r"\b[Ss]eason\s+(\d+)\s+[Ee]pisode\s+(\d+)\b"
)

SEASON_ORDINAL_PATTERN = re.compile(
    r"\b(\d+)(?:st|nd|rd|th)\s+[Ss]eason\b"
)

TRAILING_S_PATTERN = re.compile(
    r"\b[Ss](\d+)\s*(?=-\s*\d|$)"
)


def _split_extension(filename: str) -> tuple[str, str]:
    idx = filename.rfind(".")
    if idx == -1:
        return filename, ""
    ext = filename[idx:]
    if ext.lower() in KNOWN_EXTENSIONS:
        return filename[:idx], ext
    return filename, ""


def strip_trailing_brackets(text: str) -> str:
    while True:
        new_text = re.sub(r"\s*\[[^\]]*\]\s*$", "", text).strip()
        if new_text == text:
            break
        text = new_text
    return text


def _clean_title(raw: str) -> str:
    return raw.strip().rstrip("-").strip()


def parse_filename(filename: str) -> Optional[ParseResult]:
    name, ext = _split_extension(filename)

    group = None
    text = name

    m = re.match(r"^\[([^\]]+)\]\s*(.*)", text)
    if m:
        group = m.group(1)
        text = m.group(2)

    text = strip_trailing_brackets(text)

    m = SXXEYY_PATTERN.search(text)
    if m:
        title = _clean_title(text[: m.start()])
        season = int(m.group(1))
        episode = int(m.group(2))
        return ParseResult(
            title=title,
            episode=episode,
            season=season,
            file_ext=ext,
        )

    m = SEASON_EPISODE_PATTERN.search(text)
    if m:
        title = _clean_title(text[: m.start()])
        season = int(m.group(1))
        episode = int(m.group(2))
        return ParseResult(
            title=title,
            episode=episode,
            season=season,
            file_ext=ext,
        )

    nth_season = SEASON_ORDINAL_PATTERN.search(text)
    extracted_season = None
    if nth_season:
        extracted_season = int(nth_season.group(1))
        text = (text[: nth_season.start()] + text[nth_season.end() :]).strip()
        text = re.sub(r"\s+", " ", text)

    trailing_s = TRAILING_S_PATTERN.search(text)
    if trailing_s:
        extracted_season = int(trailing_s.group(1))
        text = (text[: trailing_s.start()] + text[trailing_s.end() :]).strip()
        text = re.sub(r"\s+", " ", text)

    dash_pattern = re.compile(r"\s*-\s*")
    dashes = list(dash_pattern.finditer(text))

    for match in reversed(dashes):
        after = text[match.end() :].strip()
        after_clean = ANNOTATIONS_PATTERN.sub("", after).strip()

        bm = re.match(r"^(\d+)\s*~\s*(\d+)", after_clean)
        if bm:
            title = text[: match.start()].strip()
            return ParseResult(
                title=title,
                episode=int(bm.group(1)),
                ep_end=int(bm.group(2)),
                is_batch=True,
                file_ext=ext,
                season=extracted_season,
            )

        sm = re.match(r"^[Ss]pecial\s+(\d+)", after_clean)
        if sm:
            title = text[: match.start()].strip()
            return ParseResult(
                title=title,
                episode=int(sm.group(1)),
                is_special=True,
                file_ext=ext,
                season=extracted_season,
            )

        em = re.match(r"^(\d+)\b", after_clean)
        if em:
            title = text[: match.start()].strip()
            return ParseResult(
                title=title,
                episode=int(em.group(1)),
                file_ext=ext,
                season=extracted_season,
            )

    return None
