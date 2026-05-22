from concurrent.futures import ThreadPoolExecutor
from youtubesearchpython import Search as AllSearch, VideosSearch, ChannelsSearch, CustomSearch, PlaylistsSearch, ShortsSearch
from youtubesearchpython.core.constants import *
from utiles import time_formatting
from youtube_browser.ytdlp_collections import NO_RESULTS_TEXT, PlaylistResult
from urllib.parse import quote_plus
import os
import yt_dlp

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

class Search:
    page_size = 20
    ytdlp_prefetch_limit = 240
    ytdlp_enrich_workers = 100

    def __init__(self, query, filter=0):
        self.query = query
        self.filter = filter
        self.results = {}
        self.count = 1
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
        elif mode == "videos":
            return VideosSearch(self.query, limit=self.page_size)
        elif mode == "channels":
            return ChannelsSearch(self.query, limit=self.page_size)
        elif mode == "playlists":
            return PlaylistsSearch(self.query, limit=self.page_size)
        elif mode == "shorts_search":
            return ShortsSearch(self.query, limit=self.page_size)
        elif mode == "live":
            return CustomSearch(self.query, VideoSortOrder.uploadDate, limit=self.page_size)
        elif mode == "movies":
            return CustomSearch(self.query, VideoSortOrder.uploadDate, limit=self.page_size)
        elif mode == "sort_upload":
            return CustomSearch(self.query, VideoSortOrder.uploadDate, limit=self.page_size)
        elif mode == "sort_views":
            return CustomSearch(self.query, VideoSortOrder.viewCount, limit=self.page_size)
        elif mode == "sort_rating":
            return CustomSearch(self.query, VideoSortOrder.rating, limit=self.page_size)
        elif mode == "upload_today":
            return CustomSearch(self.query, VideoUploadDateFilter.today, limit=self.page_size)
        elif mode == "upload_week":
            return CustomSearch(self.query, VideoUploadDateFilter.thisWeek, limit=self.page_size)
        elif mode == "upload_month":
            return CustomSearch(self.query, VideoUploadDateFilter.thisMonth, limit=self.page_size)
        elif mode == "upload_year":
            return CustomSearch(self.query, VideoUploadDateFilter.thisYear, limit=self.page_size)
        elif mode == "short_duration":
            return CustomSearch(self.query, VideoDurationFilter.short, limit=self.page_size)
        elif mode == "medium_duration":
            return CustomSearch(self.query, VideoDurationFilter.medium, limit=self.page_size)
        elif mode == "long_duration":
            return CustomSearch(self.query, VideoDurationFilter.long, limit=self.page_size)
        else:
            return VideosSearch(self.query, limit=self.page_size)

    def should_prefer_ytdlp(self):
        return self.filter_config["mode"] in ("channels", "playlists")

    def ytdlp_options(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return {
            "quiet": True,
            "ignoreerrors": True,
            "extract_flat": "in_playlist",
            "lazy_playlist": True,
            "playlist_items": f"1:{self.ytdlp_prefetch_limit}",
            "playlistend": self.ytdlp_prefetch_limit,
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
            "playlistend": 1,
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
            for original, enriched in zip(candidates, executor.map(self.fetch_ytdlp_detail, [url for _, url in candidates])):
                if not enriched:
                    continue
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
            if self.filter_config["mode"] == "shorts_search" and data["type"] == "video":
                data["type"] = "shorts"
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
        return {
            "type": result_type,
            "title": entry.get("title") or "Untitled",
            "url": url,
            "duration": entry.get("duration_string") or entry.get("duration"),
            "elements": self.parse_count(elements),
            "channel": {
                "name": channel_name,
                "url": channel_url,
            },
            "views": self.parse_views(entry.get("view_count")),
            "subscribers": self.parse_count(subscribers),
        }

    def infer_ytdlp_type(self, url, entry):
        if "/playlist?" in url or "list=" in url and "/watch?" not in url:
            return "playlist"
        if "/channel/" in url or "/@" in url or "/c/" in url or "/user/" in url:
            return "channel"
        if "/shorts/" in url:
            return "shorts"
        return "video"

    def parse_results(self):
        try:
            result_data = self.search.result()
            if not result_data or "result" not in result_data:
                return
            results = result_data["result"]
        except Exception:
            return
            
        for result in results:
            if not self.matches_filter(result):
                continue
            channel = result.get("channel") or {}
            result_type = result.get("type", "video")
            
            if self.filter_config["mode"] == "shorts_search" and result_type == "video":
                result_type = "shorts"
                
            if result_type == "channel":
                channel = {"name": result.get("title", ""), "link": result.get("link", "")}
                
            self.results[self.count] = {
                "type": result_type,
                "title": result.get("title", "Untitled"),
                "url": result.get("link", ""),
                "duration": result.get("duration"),
                "elements": result.get("videoCount"),
                "channel": {
                    "name": channel.get("name", ""),
                    "url": channel.get("link") or (f"https://www.youtube.com/channel/{channel.get('id', '')}" if channel.get("id") else ""),
                },
            }
            
            if result_type in ("video", "shorts", "movie"):
                view_count = result.get("viewCount") or {}
                self.results[self.count]["views"] = self.parse_views(view_count.get("text") or view_count.get("short"))
            else:
                self.results[self.count]["views"] = None
                
            if result_type == "channel":
                subscribers = result.get("subscribersCount") or {}
                self.results[self.count]["subscribers"] = subscribers.get("label", subscribers.get("text", ""))
                
            self.count += 1

    def matches_filter(self, result):
        mode = self.filter_config["mode"]
        result_type = result.get("type", "")
        
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
        for result, data in self.results.items():
            title = [data["title"]]
            if data["type"] in ("video", "short"):
                title += [self.get_duration(data["duration"]), f"By {data['channel']['name']}", self.views_part(data["views"])]
                if data["type"] == "short":
                    title.append("Shorts")
            elif data["type"] == "playlist":
                title += ["Playlist"]
                if data["channel"]["name"]:
                    title.append(f"By {data['channel']['name']}")
                if data["elements"]:
                    elements_str = str(data["elements"])
                    if "video" not in elements_str.lower():
                        title.append(f"Contains {data['elements']} videos")
                    else:
                        title.append(f"Contains {data['elements']}")
            elif data["type"] == "channel":
                title += ["Channel"]
                if data.get("subscribers"):
                    title.append(data['subscribers'])
                if data.get("elements"):
                    title.append(data["elements"])
            elif data["type"] == "movie":
                title += ["Movie"]
            titles.append(", ".join([element for element in title if element != ""]))
        return titles

    def get_last_titles(self):
        if self.new_videos <= 0:
            return []
        titles = self.get_titles()
        return titles[len(titles)-self.new_videos:len(titles)]

    def get_title(self, number):
        if not self.has_results():
            return ""
        return self.results[number+1]["title"]

    def get_url(self, number):
        if not self.has_results():
            return ""
        return self.results[number+1]["url"]

    def get_type(self, number):
        if not self.has_results():
            return "none"
        return self.results[number+1]["type"]

    def get_channel(self, number):
        if not self.has_results():
            return {"name": "", "url": ""}
        return self.results[number+1]["channel"]

    def load_more(self):
        if self.using_ytdlp:
            if self.ytdlp_index >= len(self.ytdlp_entries):
                self.new_videos = 0
                return False
            self.append_ytdlp_entries()
            return self.new_videos > 0
        try:
            self.search.next()
        except:
            return False
        current = self.count
        self.parse_results()
        self.new_videos = self.count-current
        return self.new_videos > 0

    def parse_views(self, string):
        if string is None:
            return None
        if isinstance(string, (int, float)):
            return str(string)
        try:
            string = str(string).replace(",", "")
        except AttributeError:
            return None
        return string.replace("views", "").strip()

    def parse_count(self, value):
        if isinstance(value, (int, float)):
            return str(int(value))
        if value in (None, ""):
            return ""
        return str(value).strip()

    def get_views(self, number):
        if not self.has_results():
            return None
        return self.results[number+1].get("views")

    def get_subscribers(self, number):
        if not self.has_results():
            return ""
        return self.results[number+1].get("subscribers", "")

    def get_elements(self, number):
        if not self.has_results():
            return ""
        return self.results[number+1].get("elements", "")

    def has_results(self):
        return bool(self.results)

    def views_part(self, data):
        if data is not None:
            return f"{data} views"
        return "Live"

    def get_duration(self, data):
        if data is not None and data != "No duration":
            if isinstance(data, (int, float)):
                data = int(data)
                hours, remainder = divmod(data, 3600)
                minutes, seconds = divmod(remainder, 60)
                data = f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
            return f"Duration: {time_formatting(data)}"
        return ""
