from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
import os

import yt_dlp
from youtubesearchpython import (
    ChannelsSearch,
    CustomSearch,
    PlaylistsSearch,
    Search as AllSearch,
    ShortsSearch,
    VideosSearch,
)
from youtubesearchpython.core.constants import *

from youtube_browser.ytdlp_collections import NO_RESULTS_TEXT


SEARCH_FILTERS = [
    {"label": "All results", "mode": "all"},
    {"label": "Videos", "mode": "videos"},
    {"label": "Shorts", "mode": "shorts_search"},
    {"label": "Live", "mode": "live"},
    {"label": "Channels", "mode": "channels"},
    {"label": "Playlists", "mode": "playlists"},
    {"label": "Movies", "mode": "movies"},
    {"label": "Sort by upload date", "mode": "sort_upload"},
    {"label": "Sort by view count", "mode": "sort_views"},
    {"label": "Sort by rating", "mode": "sort_rating"},
    {"label": "Uploaded today", "mode": "upload_today"},
    {"label": "Uploaded this week", "mode": "upload_week"},
    {"label": "Uploaded this month", "mode": "upload_month"},
    {"label": "Uploaded this year", "mode": "upload_year"},
    {"label": "Short duration (< 4 min)", "mode": "short_duration"},
    {"label": "Medium duration (4-20 min)", "mode": "medium_duration"},
    {"label": "Long duration (> 20 min)", "mode": "long_duration"},
]


def _duration_to_text(value):
    if value in (None, "", "No duration"):
        return ""
    if isinstance(value, (int, float)):
        value = int(value)
        hours, remainder = divmod(value, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"
    return str(value).strip()


def _strip_suffix(value, suffix):
    text = str(value).strip()
    lowered = text.lower()
    suffix = suffix.lower()
    if lowered.endswith(suffix):
        return text[: len(text) - len(suffix)].strip()
    return text


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
        text = f"{_strip_suffix(text, suffix)} {suffix}"
    return text.strip()


def _normalize_view_text(value):
    return _normalize_count_text(value, "views")


def _normalize_subscriber_text(value):
    return _normalize_count_text(value, "subscribers")


def _normalize_video_count(value):
    return _normalize_count_text(value, "videos")


def _normalize_result_type(value):
    if value == "short":
        return "shorts"
    return value or "video"


def _published_from_upload_date(value):
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


class Search:
    page_size = 20
    ytdlp_prefetch_limit = 240
    ytdlp_enrich_workers = 100

    def __init__(self, query, filter=0):
        self.query = query
        self.filter = filter
        self.results = {}
        self.count = 1
        self.new_videos = 0
        self.using_ytdlp = False
        self.ytdlp_entries = []
        self.ytdlp_index = 0
        self.filter_config = SEARCH_FILTERS[self.filter]
        self.search = None

        if self.should_prefer_ytdlp():
            self.parse_ytdlp_results()
            return

        self.search = self.create_search()
        if self.search:
            self.parse_results()
            if not self.results:
                self.parse_ytdlp_results()
        else:
            self.parse_ytdlp_results()

    def create_search(self):
        mode = self.filter_config["mode"]
        if mode == "all":
            return AllSearch(self.query, limit=self.page_size)
        if mode == "videos":
            return VideosSearch(self.query, limit=self.page_size)
        if mode == "channels":
            return ChannelsSearch(self.query, limit=self.page_size)
        if mode == "playlists":
            return PlaylistsSearch(self.query, limit=self.page_size)
        if mode == "shorts_search":
            return ShortsSearch(self.query, limit=self.page_size)
        if mode == "live":
            return CustomSearch(self.query, VideoSortOrder.uploadDate, limit=self.page_size)
        if mode == "movies":
            return CustomSearch(self.query, VideoSortOrder.uploadDate, limit=self.page_size)
        if mode == "sort_upload":
            return CustomSearch(self.query, VideoSortOrder.uploadDate, limit=self.page_size)
        if mode == "sort_views":
            return CustomSearch(self.query, VideoSortOrder.viewCount, limit=self.page_size)
        if mode == "sort_rating":
            return CustomSearch(self.query, VideoSortOrder.rating, limit=self.page_size)
        if mode == "upload_today":
            return CustomSearch(self.query, VideoUploadDateFilter.today, limit=self.page_size)
        if mode == "upload_week":
            return CustomSearch(self.query, VideoUploadDateFilter.thisWeek, limit=self.page_size)
        if mode == "upload_month":
            return CustomSearch(self.query, VideoUploadDateFilter.thisMonth, limit=self.page_size)
        if mode == "upload_year":
            return CustomSearch(self.query, VideoUploadDateFilter.thisYear, limit=self.page_size)
        if mode == "short_duration":
            return CustomSearch(self.query, VideoDurationFilter.short, limit=self.page_size)
        if mode == "medium_duration":
            return CustomSearch(self.query, VideoDurationFilter.medium, limit=self.page_size)
        if mode == "long_duration":
            return CustomSearch(self.query, VideoDurationFilter.long, limit=self.page_size)
        return VideosSearch(self.query, limit=self.page_size)

    def should_prefer_ytdlp(self):
        return False

    def ytdlp_options(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return {
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "extract_flat": "in_playlist",
            "lazy_playlist": True,
            "playlist_items": f"1:{self.ytdlp_prefetch_limit}",
            "js_runtimes": {"deno": {"executable": os.path.join(project_root, "deno.exe")}},
            "extractor_args": {
                "youtubetab": {
                    "approximate_date": ["1"],
                },
            },
        }

    def ytdlp_detail_options(self):
        options = self.ytdlp_options().copy()
        options.update({
            "lazy_playlist": False,
            "playlist_items": "1",
        })
        return options

    def ytdlp_search_url(self):
        url = f"https://www.youtube.com/results?search_query={quote_plus(self.query)}"
        mode = self.filter_config["mode"]
        if mode == "live":
            url += "&sp=EgJAAQ%3D%3D"
        elif mode == "movies":
            url += "&sp=EgIQBA%3D%3D"
        elif mode == "upload_today":
            url += "&sp=EgIIAg%3D%3D"
        elif mode == "upload_week":
            url += "&sp=EgIIAw%3D%3D"
        elif mode == "upload_month":
            url += "&sp=EgIIBA%3D%3D"
        elif mode == "upload_year":
            url += "&sp=EgIIBQ%3D%3D"
        return url

    def parse_ytdlp_results(self):
        self.using_ytdlp = True
        with yt_dlp.YoutubeDL(self.ytdlp_options()) as ydl:
            info = ydl.extract_info(self.ytdlp_search_url(), download=False) or {}
        self.ytdlp_entries = [entry for entry in info.get("entries") or [] if entry]
        self.enrich_ytdlp_entries()
        self.append_ytdlp_entries()

    def enrich_ytdlp_entries(self):
        candidates = []
        for entry in self.ytdlp_entries:
            url = self.entry_webpage_url(entry)
            if not url:
                continue
            if self.filter_config["mode"] == "playlists" and self.needs_playlist_enrichment(entry):
                candidates.append((entry, url))
            elif self.filter_config["mode"] == "channels" and self.needs_channel_enrichment(entry):
                candidates.append((entry, url))
        if not candidates:
            return
        with ThreadPoolExecutor(max_workers=min(self.ytdlp_enrich_workers, len(candidates))) as executor:
            urls = [url for _, url in candidates]
            for original, enriched in zip(candidates, executor.map(self.fetch_ytdlp_detail, urls)):
                if enriched:
                    original[0].update(self.merge_ytdlp_entry(original[0], enriched))

    def fetch_ytdlp_detail(self, url):
        try:
            with yt_dlp.YoutubeDL(self.ytdlp_detail_options()) as ydl:
                return ydl.extract_info(url, download=False) or {}
        except Exception:
            return {}

    def merge_ytdlp_entry(self, base, enriched):
        merged = dict(base)
        for key, value in enriched.items():
            if value not in (None, "", [], {}):
                merged[key] = value
        return merged

    def needs_playlist_enrichment(self, entry):
        return not any((
            entry.get("playlist_channel"),
            entry.get("playlist_uploader"),
            entry.get("channel"),
            entry.get("uploader"),
            entry.get("playlist_count"),
            entry.get("view_count"),
        ))

    def needs_channel_enrichment(self, entry):
        return not any((
            entry.get("channel_follower_count"),
            entry.get("subscriber_count"),
            entry.get("playlist_count"),
            entry.get("channel_url"),
            entry.get("uploader_url"),
        ))

    def entry_webpage_url(self, entry):
        url = entry.get("webpage_url") or entry.get("url") or entry.get("original_url") or ""
        if url.startswith("http"):
            return url
        webpage_url_basename = entry.get("webpage_url_basename")
        if webpage_url_basename:
            return f"https://www.youtube.com/{webpage_url_basename.lstrip('/')}"
        entry_id = entry.get("id")
        if not entry_id:
            return ""
        if entry.get("_type") == "playlist":
            return f"https://www.youtube.com/playlist?list={entry_id}"
        return f"https://www.youtube.com/watch?v={entry_id}"

    def append_ytdlp_entries(self):
        current = self.count
        while self.ytdlp_index < len(self.ytdlp_entries) and self.count - current < self.page_size:
            entry = self.ytdlp_entries[self.ytdlp_index]
            self.ytdlp_index += 1
            data = self.normalize_ytdlp_entry(entry)
            if not data or not self.matches_filter(data):
                continue
            self.results[self.count] = data
            self.count += 1
        self.new_videos = self.count - current

    def normalize_ytdlp_entry(self, entry):
        url = self.entry_webpage_url(entry)
        if not url:
            return None
        result_type = self.infer_ytdlp_type(url, entry)
        channel_url = (
            entry.get("channel_url")
            or entry.get("uploader_url")
            or entry.get("playlist_channel_url")
            or entry.get("playlist_uploader_url")
            or ""
        )
        channel_id = entry.get("channel_id") or entry.get("uploader_id")
        if not channel_url and channel_id:
            channel_url = f"https://www.youtube.com/channel/{channel_id}"
        channel_name = (
            entry.get("playlist_channel")
            or entry.get("playlist_uploader")
            or entry.get("channel")
            or entry.get("uploader")
            or entry.get("uploader_id")
            or entry.get("channel_id")
            or ""
        )
        elements = (
            entry.get("playlist_count")
            or entry.get("channel_count")
            or entry.get("n_entries")
            or entry.get("video_count")
        )
        subscribers = entry.get("channel_follower_count") or entry.get("subscriber_count")
        published = (
            entry.get("relative_date")
            or entry.get("release_date")
            or _published_from_upload_date(entry.get("upload_date"))
        )
        return {
            "type": result_type,
            "title": entry.get("title") or "Untitled",
            "url": url,
            "duration": _duration_to_text(entry.get("duration_string") or entry.get("duration")),
            "elements": _normalize_video_count(elements),
            "channel": {
                "name": channel_name,
                "url": channel_url,
            },
            "published": published or "",
            "views": _normalize_view_text(entry.get("view_count")),
            "subscribers": _normalize_subscriber_text(subscribers),
        }

    def infer_ytdlp_type(self, url, entry):
        if "/playlist?" in url or ("list=" in url and "/watch?" not in url):
            return "playlist"
        if "/channel/" in url or "/@" in url or "/c/" in url or "/user/" in url:
            return "channel"
        if "/shorts/" in url:
            return "shorts"
        return _normalize_result_type(entry.get("_type"))

    def parse_results(self):
        try:
            result_data = self.search.result()
            results = (result_data or {}).get("result") or []
        except Exception:
            return

        for result in results:
            if not self.matches_filter(result):
                continue

            result_type = _normalize_result_type(result.get("type"))
            channel = result.get("channel") or {}
            if result_type == "channel":
                channel = {"name": result.get("title", ""), "link": result.get("link", "")}

            data = {
                "type": result_type,
                "title": result.get("title", "Untitled"),
                "url": result.get("link", ""),
                "duration": _duration_to_text(result.get("duration")),
                "published": result.get("publishedTime", "") or "",
                "elements": "",
                "channel": {
                    "name": channel.get("name", ""),
                    "url": channel.get("link") or (
                        f"https://www.youtube.com/channel/{channel.get('id', '')}" if channel.get("id") else ""
                    ),
                },
                "views": None,
                "subscribers": "",
            }

            if result_type in ("video", "shorts", "movie", "live"):
                data["views"] = _normalize_view_text(result.get("viewCount"))
            elif result_type == "playlist":
                data["views"] = _normalize_view_text(result.get("viewCount"))
                data["elements"] = _normalize_video_count(result.get("videoCount"))
            elif result_type == "channel":
                data["subscribers"] = _normalize_subscriber_text(
                    result.get("subscribersCount") or result.get("subscribers")
                )
                data["elements"] = _normalize_video_count(result.get("videoCount"))

            self.results[self.count] = data
            self.count += 1

    def matches_filter(self, result):
        mode = self.filter_config["mode"]
        result_type = _normalize_result_type(result.get("type", ""))
        if mode == "channels":
            return result_type == "channel"
        if mode == "playlists":
            return result_type == "playlist"
        if mode == "shorts_search":
            if result_type == "shorts":
                return True
            duration = result.get("duration")
            if not duration:
                return False
            seconds = self.duration_to_seconds(duration)
            return seconds is not None and seconds <= 60
        return True

    def duration_to_seconds(self, duration):
        if isinstance(duration, (int, float)):
            return int(duration)
        if not duration:
            return None
        parts = str(duration).split(":")
        try:
            values = [int(part) for part in parts]
        except ValueError:
            return None
        total = 0
        for value in values:
            total = total * 60 + value
        return total

    def get_titles(self):
        if not self.results:
            return [NO_RESULTS_TEXT]
        titles = []
        for data in self.results.values():
            title = [data["title"]]
            if data["type"] in ("video", "shorts", "movie", "live"):
                if data["duration"]:
                    title.append(f"duration: {data['duration']}")
                uploader = data["channel"]["name"]
                published = data.get("published", "")
                if uploader and published:
                    title.append(f"uploaded by: {uploader} - {published}")
                elif uploader:
                    title.append(f"uploaded by: {uploader}")
                elif published:
                    title.append(published)
                if data["views"]:
                    title.append(data["views"])
                elif data["type"] == "live":
                    title.append("Live")
            elif data["type"] == "playlist":
                if data["elements"]:
                    title.append(data["elements"])
                if data["channel"]["name"]:
                    title.append(f"uploaded by: {data['channel']['name']}")
            elif data["type"] == "channel":
                if data.get("elements"):
                    title.append(data["elements"])
                if data.get("subscribers"):
                    title.append(data["subscribers"])
            titles.append(", ".join([element for element in title if element]))
        return titles

    def get_last_titles(self):
        if self.new_videos <= 0:
            return []
        titles = self.get_titles()
        return titles[len(titles) - self.new_videos : len(titles)]

    def get_title(self, number):
        if not self.has_results():
            return ""
        return self.results[number + 1]["title"]

    def get_url(self, number):
        if not self.has_results():
            return ""
        return self.results[number + 1]["url"]

    def get_type(self, number):
        if not self.has_results():
            return "none"
        return self.results[number + 1]["type"]

    def get_channel(self, number):
        if not self.has_results():
            return {"name": "", "url": ""}
        return self.results[number + 1]["channel"]

    def load_more(self):
        if self.using_ytdlp:
            if self.ytdlp_index >= len(self.ytdlp_entries):
                self.new_videos = 0
                return False
            self.append_ytdlp_entries()
            return self.new_videos > 0
        try:
            if not self.search.next():
                self.new_videos = 0
                return False
        except Exception:
            return False
        current = self.count
        self.parse_results()
        self.new_videos = self.count - current
        return self.new_videos > 0

    def get_views(self, number):
        if not self.has_results():
            return None
        return self.results[number + 1].get("views")

    def get_subscribers(self, number):
        if not self.has_results():
            return ""
        return self.results[number + 1].get("subscribers", "")

    def get_elements(self, number):
        if not self.has_results():
            return ""
        return self.results[number + 1].get("elements", "")

    def get_published(self, number):
        if not self.has_results():
            return ""
        return self.results[number + 1].get("published", "")

    def has_results(self):
        return bool(self.results)
