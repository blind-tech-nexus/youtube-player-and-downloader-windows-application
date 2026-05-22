import os
from concurrent.futures import ThreadPoolExecutor

import yt_dlp

from utiles import time_formatting


NO_RESULTS_TEXT = "No search results found..."


def _project_file(name):
	return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), name)


def _ydl_options(flat=True, start=None, end=None):
	options = {
		"quiet": True,
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
	if start is not None:
		options["playliststart"] = start
	if end is not None:
		options["playlistend"] = end
	return options


def _extract_info(url, flat=True, start=None, end=None):
	with yt_dlp.YoutubeDL(_ydl_options(flat=flat, start=start, end=end)) as ydl:
		return ydl.extract_info(url, download=False)


def _format_duration(value):
	if value in (None, ""):
		return ""
	if isinstance(value, (int, float)):
		value = int(value)
		hours, remainder = divmod(value, 3600)
		minutes, seconds = divmod(remainder, 60)
		if hours:
			value = f"{hours}:{minutes:02d}:{seconds:02d}"
		else:
			value = f"{minutes}:{seconds:02d}"
	try:
		return time_formatting(str(value))
	except Exception:
		return str(value)


def _clean_count(value):
	if value in (None, ""):
		return ""
	return str(value)


def _first_non_empty(*values):
	for value in values:
		if value not in (None, "", [], {}):
			return value
	return ""


def _entry_url(entry):
	url = entry.get("webpage_url") or entry.get("url") or entry.get("original_url") or ""
	if url.startswith("http"):
		return url
	webpage_url_basename = entry.get("webpage_url_basename")
	if webpage_url_basename:
		return f"https://www.youtube.com/{webpage_url_basename.lstrip('/')}"
	video_id = entry.get("id")
	if video_id:
		return f"https://www.youtube.com/watch?v={video_id}"
	return url


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
	channel_name = (
		entry.get("channel")
		or entry.get("uploader")
		or entry.get("playlist_channel")
		or entry.get("playlist_uploader")
		or entry.get("uploader_id")
		or entry.get("channel_id")
		or fallback_channel_name
		or ""
	)
	channel_url = _channel_url(entry, fallback_channel_url)
	duration = entry.get("duration_string") or entry.get("duration")
	view_count = entry.get("view_count")
	video_url = _entry_url(entry)
	video_type = "video"
	if "/shorts/" in video_url:
		video_type = "short"
	live_status = entry.get("live_status")
	if live_status in ("is_live", "is_upcoming"):
		video_type = "live"
	return {
		"type": video_type,
		"title": entry.get("title") or "Untitled video",
		"url": video_url,
		"duration": duration,
		"duration_text": _format_duration(duration),
		"views": _clean_count(view_count),
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
		self._load_initial()

	def _collection_url(self):
		if self.kind != "channel":
			return self.url
		url = self.url.rstrip("/")
		if not url.endswith("/videos"):
			url = f"{url}/videos"
		return url

	def _load_initial(self):
		with ThreadPoolExecutor(max_workers=self.metadata_workers) as executor:
			meta_future = executor.submit(_extract_info, self.url, True, 1, 1)
			items_future = executor.submit(_extract_info, self._collection_url(), True, 1, self.page_size)
			self.info = meta_future.result() or {}
			items = items_future.result() or {}
		self._set_metadata(self.info, items)
		self._append_entries(items.get("entries") or [])

	def _set_metadata(self, info, items=None):
		items = items or {}
		merged = dict(info or {})
		for key, value in (items or {}).items():
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
		self.subscribers = _clean_count(_first_non_empty(
			merged.get("channel_follower_count"),
			merged.get("subscriber_count"),
		))
		self.upload_count = _clean_count(_first_non_empty(
			merged.get("playlist_count"),
			merged.get("n_entries"),
			merged.get("video_count"),
			merged.get("channel_count"),
			merged.get("entries") and len([entry for entry in merged.get("entries") if entry]),
		))
		self.view_count = _clean_count(_first_non_empty(
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
		self.new_videos = self.loaded - current

	def next(self):
		start = self.loaded + 1
		end = self.loaded + self.page_size
		info = _extract_info(self._collection_url(), True, start, end) or {}
		entries = info.get("entries") or []
		if not entries:
			self.new_videos = 0
			return False
		self._append_entries(entries)
		return self.new_videos > 0

	def get_new_titles(self):
		if self.new_videos <= 0:
			return []
		return self.get_display_titles()[-self.new_videos:]

	def get_title(self, n):
		return self.videos[n]["title"]

	def get_display_titles(self):
		if not self.videos:
			return [NO_RESULTS_TEXT]
		titles = []
		for video in self.videos:
			parts = [video["title"]]
			if video["duration_text"]:
				parts.append(f"Duration: {video['duration_text']}")
			if video["channel"]["name"]:
				parts.append(f"By {video['channel']['name']}")
			if video["views"]:
				parts.append(f"{video['views']} views")
			if video["type"] == "short":
				parts.append("Shorts")
			elif video["type"] == "live":
				parts.append("Live")
			titles.append(", ".join(parts))
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
