import os
import time
import logging
from typing import Callable
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".mov"}


class AnimeFileHandler(FileSystemEventHandler):
    def __init__(
        self,
        callback: Callable[[str], None],
        cooldown: int = 5,
    ):
        self.callback = callback
        self.cooldown = cooldown
        self._last_processed: dict[str, float] = {}
        self.logger = logging.getLogger(__name__)

    def on_created(self, event):
        if event.is_directory:
            return
        if self._is_video(event.src_path):
            self._debounce(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        if self._is_video(event.dest_path):
            self._debounce(event.dest_path)

    def _is_video(self, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS

    def _debounce(self, path: str):
        now = time.time()
        last = self._last_processed.get(path, 0.0)
        if now - last < self.cooldown:
            return
        self._last_processed[path] = now
        self._wait_for_file(path)
        self.callback(path)

    @staticmethod
    def _wait_for_file(path: str, max_wait: int = 10):
        stable = 0.0
        last_size = -1
        start = time.time()
        while time.time() - start < max_wait:
            try:
                size = os.path.getsize(path)
                if size == last_size and size > 0:
                    stable += 0.5
                    if stable >= 1.0:
                        return
                else:
                    stable = 0.0
                last_size = size
            except OSError:
                pass
            time.sleep(0.5)


def start_watchdog(
    watch_dir: str,
    callback: Callable[[str], None],
    recursive: bool = True,
) -> Observer:
    logger = logging.getLogger(__name__)
    event_handler = AnimeFileHandler(callback)
    observer = Observer()

    os.makedirs(watch_dir, exist_ok=True)

    observer.schedule(event_handler, watch_dir, recursive=recursive)
    observer.start()
    logger.info("Watchdog started on %s (recursive=%s)", watch_dir, recursive)
    return observer
