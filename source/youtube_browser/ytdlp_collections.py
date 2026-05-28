import os
from concurrent.futures import ThreadPoolExecutor

import yt_dlp


NO_RESULTS_TEXT = "No search results found..."


def _project_file(name):
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), name)


def _ydl_options(flat=True, start=None, end=None):
    options = {
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": True,
        "extract_flat": "in_playlist" if flat else False,
        "lazy_playlist": True,
        "playlist_items": f"{start or 1}:{end}" if end is not None else None,
        "js_runtimes": {"deno": {"executable": _project_file("deno.exe")}},
        "extractor_args": {
            "youtubetab": {
                "approximate_date": ["1"],
            },
        },
    }
    if options["playlist_items"] is None:
        options.pop("playlist_items")
    return options


def _extract_info(url, flat=True, start=None, end=None):
    with yt_dlp.YoutubeDL(_ydl_options(flat=flat, start=start, end=end)) as ydl:
        return ydl.extract_info(url, download=False)


def _first_non_empty(*values):
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return ""


def _normalize_count_text(value, suffix):
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, dict):
        for key in ("label", "text", "short", "simpleText", "simple", "precise", "approximate"):
            nested = value.get(key)
            if nested not in (None, "", [], {}):
                return _normalize_count_text(nested, suffix)
        return ""
    if isinstance(value, (int, float)):
        text = str(int(value))
    else:
        text = str(value).strip()
    if not text:
        return ""
    if suffix.lower() not in text.lower():
        text = f"{text} {suffix}"
    return text.strip()


def _normalize_views(value):
    return _normalize_count_text(value, "views")


def _normalize_subscribers(value):
    return _normalize_count_text(value, "subscribers")


def _normalize_videos(value):
    return _normalize_count_text(value, "videos")


def _duration_to_text(value):
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        value = int(value)
        hours, remainder = divmod(value, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    return str(value).strip()


def _published_from_entry(entry):
    published = _first_non_empty(
        entry.get("relative_date"),
        entry.get("release_date"),
        entry.get("modified_date"),
    )
    if published:
        return str(published).strip()
    upload_date = str(entry.get("upload_date") or "").strip()
    if len(upload_date) == 8 and upload_date.isdigit():
        return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
    return upload_date


def _entry_url(entry):
    url = entry.get("webpage_url") or entry.get("url") or entry.get("original_url") or ""
    if url.startswith("http"):
        return url
    webpage_url_basename = entry.get("webpage_url_basename")
    if webpage_url_basename:
        return f"https://www.youtube.com/{webpage_url_basename.lstrip('/')}"
    video_id = entry.get("id")
    if not video_id:
        return url
    if entry.get("_type") == "playlist":
        return f"https://www.youtube.com/playlist?list={video_id}"
    return f"https://www.youtube.com/watch?v={video_id}"


def _channel_url(entry, fallback=""):
    url = (
        entry.get("channel_url")
        or entry.get("uploader_url")
        or entry.get("playlist_channel_url")
        or entry.get("playlist_uploader_url")
        or fallback
        or ""
    )
    channel_id = entry.get("channel_id") or entry.get("uploader_id")
    if not url and channel_id:
        url = f"https://www.youtube.com/channel/{channel_id}"
    return url


def _video_from_entry(entry, fallback_channel_name="", fallback_channel_url=""):
    channel_name = _first_non_empty(
        entry.get("channel"),
        entry.get("uploader"),
        entry.get("playlist_channel"),
        entry.get("playlist_uploader"),
        entry.get("uploader_id"),
        entry.get("channel_id"),
        fallback_channel_name,
    )
    channel_url = _channel_url(entry, fallback_channel_url)
    duration = _duration_to_text(entry.get("duration_string") or entry.get("duration"))
    view_count = _normalize_views(entry.get("view_count"))
    video_url = _entry_url(entry)
    video_type = "shorts" if "/shorts/" in video_url else "video"
    live_status = entry.get("live_status")
    if live_status in ("is_live", "is_upcoming"):
        video_type = "live"
    return {
        "type": video_type,
        "title": entry.get("title") or "Untitled video",
        "url": video_url,
        "duration": duration,
        "published": _published_from_entry(entry),
        "views": view_count,
        "channel": {
            "name": channel_name,
            "url": channel_url,
        },
    }


class YtdlpVideoCollection:
    metadata_workers = 100

    def __init__(self, url, kind="playlist", page_size=50):
        self.url = url
        self.kind = kind
        self.page_size = page_size
        self.loaded = 0
        self.videos = []
        self.count = 0
        self.new_videos = 0
        self.info = {}
        self.title = ""
        self.channel_name = ""
        self.channel_url = ""
        self.subscribers = ""
        self.upload_count = ""
        self.view_count = ""
        self.description = ""
        self._seen_urls = set()
        self._sources = self._collection_urls()
        self._source_offsets = {source: 0 for source in self._sources}
        self._next_source_index = 0
        self._load_initial()

    def _collection_urls(self):
        if self.kind != "channel":
            return [self.url]
        base = self.url.rstrip("/")
        sources = []
        for suffix in ("/videos", "/shorts", "/streams"):
            candidate = f"{base}{suffix}"
            if candidate not in sources:
                sources.append(candidate)
        return sources

    def _load_initial(self):
        initial_sources = self._sources[:1] if self.kind == "channel" else self._sources
        with ThreadPoolExecutor(max_workers=min(self.metadata_workers, len(initial_sources) + 1)) as executor:
            meta_future = executor.submit(_extract_info, self.url, True, 1, 1)
            item_futures = {
                source: executor.submit(_extract_info, source, True, 1, self.page_size)
                for source in initial_sources
            }
            self.info = meta_future.result() or {}
            source_items = {source: future.result() or {} for source, future in item_futures.items()}
        merged_items = {}
        for items in source_items.values():
            for key, value in items.items():
                if value not in (None, "", [], {}):
                    merged_items[key] = value
        self._set_metadata(self.info, merged_items)
        for source, items in source_items.items():
            self._append_entries(items.get("entries") or [])
            self._source_offsets[source] = self.page_size
        self._next_source_index = 1 if self.kind == "channel" and len(self._sources) > 1 else 0

    def _set_metadata(self, info, items=None):
        items = items or {}
        merged = dict(info or {})
        for key, value in items.items():
            if value not in (None, "", [], {}):
                merged[key] = value

        self.title = _first_non_empty(
            merged.get("title"),
            merged.get("playlist_title"),
            merged.get("channel"),
            merged.get("uploader"),
            "YouTube collection",
        )
        self.channel_name = _first_non_empty(
            merged.get("channel"),
            merged.get("uploader"),
            merged.get("playlist_channel"),
            merged.get("playlist_uploader"),
            self.title,
        )
        self.channel_url = _first_non_empty(
            merged.get("channel_url"),
            merged.get("uploader_url"),
            merged.get("playlist_channel_url"),
            merged.get("playlist_uploader_url"),
            self.url if self.kind == "channel" else "",
        )
        self.subscribers = _normalize_subscribers(_first_non_empty(
            merged.get("channel_follower_count"),
            merged.get("subscriber_count"),
        ))
        self.upload_count = _normalize_videos(_first_non_empty(
            merged.get("playlist_count"),
            merged.get("n_entries"),
            merged.get("video_count"),
            merged.get("channel_count"),
            merged.get("entries") and len([entry for entry in merged.get("entries") if entry]),
        ))
        self.view_count = _normalize_views(_first_non_empty(
            merged.get("view_count"),
            merged.get("playlist_view_count"),
        ))
        self.description = _first_non_empty(merged.get("description"), "")

    def _append_entries(self, entries):
        current = len(self.videos)
        for entry in entries:
            if not entry:
                continue
            video = _video_from_entry(entry, self.channel_name, self.channel_url)
            if not video["url"] or video["url"] in self._seen_urls:
                continue
            self._seen_urls.add(video["url"])
            self.videos.append(video)
        self.loaded = len(self.videos)
        self.count = self.loaded
        self.new_videos = self.loaded - current

    def next(self):
        current = len(self.videos)
        if not self._sources:
            self.new_videos = 0
            return False
        source = self._sources[self._next_source_index]
        start = self._source_offsets[source] + 1
        end = self._source_offsets[source] + self.page_size
        info = _extract_info(source, True, start, end) or {}
        entries = info.get("entries") or []
        if entries:
            self._append_entries(entries)
            self._source_offsets[source] = end
        self._next_source_index = (self._next_source_index + 1) % len(self._sources)
        self.new_videos = len(self.videos) - current
        self.loaded = len(self.videos)
        self.count = self.loaded
        return self.new_videos > 0

    def get_new_titles(self):
        if self.new_videos <= 0:
            return []
        return self.get_display_titles()[-self.new_videos :]

    def get_title(self, n):
        return self.videos[n]["title"]

    def get_type(self, n):
        return self.videos[n]["type"]

    def get_views(self, n):
        return self.videos[n]["views"]

    def get_published(self, n):
        return self.videos[n]["published"]

    def get_display_titles(self):
        if not self.videos:
            return [NO_RESULTS_TEXT]
        titles = []
        for video in self.videos:
            parts = [video["title"]]
            if video["duration"]:
                parts.append(f"duration: {video['duration']}")
            uploader = video["channel"]["name"]
            published = video["published"]
            if uploader and published:
                parts.append(f"uploaded by: {uploader} - {published}")
            elif uploader:
                parts.append(f"uploaded by: {uploader}")
            elif published:
                parts.append(published)
            if video["views"]:
                parts.append(video["views"])
            elif video["type"] == "live":
                parts.append("Live")
            titles.append(", ".join([part for part in parts if part]))
        return titles

    def get_url(self, n):
        return self.videos[n]["url"]

    def get_channel(self, n):
        return self.videos[n]["channel"]

    def has_results(self):
        return bool(self.videos)


class PlaylistResult(YtdlpVideoCollection):
    def __init__(self, url):
        super().__init__(url, kind="playlist")


class ChannelResult(YtdlpVideoCollection):
    def __init__(self, url):
        super().__init__(url, kind="channel")
