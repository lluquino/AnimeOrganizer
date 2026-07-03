import logging
import os
import sys
from .config import load_config
from .parser import parse_filename
from .matcher import AnimeMatcher
from .organizer import FileOrganizer
from .anilist_client import AniListClient
from .watcher import start_watchdog, VIDEO_EXTENSIONS


def process_file(path, matcher, organizer, config):
    logger = logging.getLogger(__name__)
    basename = os.path.basename(path)

    parse_result = parse_filename(basename)
    if not parse_result:
        logger.warning("Cannot parse filename: %s", basename)
        return

    if parse_result.is_batch:
        logger.info("Skipping batch file/folder: %s", basename)
        return

    match_result = matcher.match(parse_result)
    if not match_result:
        logger.warning(
            "Cannot identify anime in '%s' (title: %s)",
            basename,
            parse_result.title,
        )
        return

    organizer.organize(path, match_result, parse_result)


def main():
    config_path = os.environ.get("ANIME_CONFIG", "config.yaml")
    config = load_config(config_path)

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info("Starting AnimeOrganizer")
    logger.info("Watch dir: %s", config.watch_dir)
    logger.info("Output dir: %s", config.output_dir)

    client = AniListClient()
    matcher = AnimeMatcher(config, client)
    organizer = FileOrganizer(config)

    # Process any existing files before starting watchdog
    logger.info("Scanning for existing files in %s ...", config.watch_dir)
    for root, _, files in os.walk(config.watch_dir):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in VIDEO_EXTENSIONS:
                process_file(
                    os.path.join(root, fname), matcher, organizer, config
                )

    observer = start_watchdog(config.watch_dir, lambda p: process_file(
        p, matcher, organizer, config
    ))

    try:
        observer.join()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
