import os
import sys

settings_path = os.path.join(os.getenv("appdata"), "YouTube player and downloader")
update_path = os.path.join(settings_path, "updates")
db_path = os.path.join(settings_path, "youtube_player_and_downloader.db")


def get_bundle_dir():
    return getattr(sys, "_MEIPASS", None)


def get_app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_runtime_search_dirs():
    dirs = []
    for path in (
        get_bundle_dir(),
        get_app_base_dir(),
        os.getcwd(),
    ):
        if path and path not in dirs:
            dirs.append(path)
    return dirs


def resolve_runtime_path(*relative_parts):
    for base_dir in get_runtime_search_dirs():
        candidate = os.path.join(base_dir, *relative_parts)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(get_app_base_dir(), *relative_parts)
