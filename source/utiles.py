import re
from threading import Thread
from settings_handler import config_get
import wx
import application
import os
import sys
from download_handler.formats import (
    PLAYABLE_AUDIO_FORMAT,
    PLAYABLE_VIDEO_FORMAT,
    FALLBACK_AUDIO_FORMAT,
    FALLBACK_VIDEO_FORMAT,
    format_from_option,
)

resolution = "640x360"


def _build_stream_opts(fmt):
    opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'skip_download': True,
        'extractor_retries': 3,
        'format': fmt,
    }
    try:
        from paths import resolve_runtime_path
        deno_path = resolve_runtime_path("deno.exe")
        if deno_path and os.path.exists(deno_path):
            opts['js_runtimes'] = {'deno': {'executable': deno_path}}
    except Exception:
        pass
    return opts


def _resolve_stream_url(info):
    if info.get('url'):
        return info['url']
    requested = info.get('requested_formats') or []
    for fmt in requested:
        if fmt.get('url'):
            return fmt['url']
    formats = info.get('formats') or []
    for fmt in reversed(formats):
        if fmt.get('url') and fmt.get('protocol') in ('https', 'http') and fmt.get('vcodec') != 'none':
            return fmt['url']
    for fmt in reversed(formats):
        if fmt.get('url') and fmt.get('protocol') in ('https', 'http'):
            return fmt['url']
    for fmt in reversed(formats):
        if fmt.get('url'):
            return fmt['url']
    return None


def _pick_audio_url(info):
    formats = info.get('formats') or []
    audio_formats = [
        f for f in formats
        if f.get('url') and f.get('acodec') not in (None, 'none')
        and f.get('vcodec') in (None, 'none')
        and f.get('protocol') in ('https', 'http')
    ]
    if audio_formats:
        audio_formats.sort(key=lambda f: f.get('abr') or f.get('tbr') or 0)
        return audio_formats[-1]['url']
    progressive = [
        f for f in formats
        if f.get('url') and f.get('acodec') not in (None, 'none')
        and f.get('protocol') in ('https', 'http')
    ]
    if progressive:
        progressive.sort(key=lambda f: f.get('tbr') or 0)
        return progressive[-1]['url']
    return None


def _extract_info(url, fmt):
    import yt_dlp
    with yt_dlp.YoutubeDL(_build_stream_opts(fmt)) as ydl:
        return ydl.extract_info(url, download=False)


def _extract_with_fallback(url, primary_format, fallback_format):
    import yt_dlp
    try:
        return _extract_info(url, primary_format)
    except yt_dlp.utils.DownloadError as e:
        if "Requested format is not available" not in str(e):
            raise
    try:
        return _extract_info(url, fallback_format)
    except yt_dlp.utils.DownloadError as e:
        if "Requested format is not available" not in str(e):
            raise
    with yt_dlp.YoutubeDL(_build_stream_opts(None)) as ydl:
        return ydl.extract_info(url, download=False)


def _stream_result(info, stream_url):
    return {
        'url': stream_url,
        'title': info.get('title'),
        'thumbnail': info.get('thumbnail'),
        'duration': info.get('duration'),
    }


def get_audio_stream(url):
    info = _extract_with_fallback(url, PLAYABLE_AUDIO_FORMAT, FALLBACK_AUDIO_FORMAT)
    stream_url = _resolve_stream_url(info) or _pick_audio_url(info)
    if not stream_url:
        raise Exception("No audio stream found")
    return _stream_result(info, stream_url)


def get_video_stream(url):
    info = _extract_with_fallback(url, PLAYABLE_VIDEO_FORMAT, FALLBACK_VIDEO_FORMAT)
    stream_url = _resolve_stream_url(info)
    if not stream_url:
        raise Exception("No playable stream URL found")
    return _stream_result(info, stream_url)


def time_formatting(t):
    t = t.split(":")
    t = [int(i) for i in t]
    if t[0] == 0:
        t.pop(0)

    def minute(m):
        if m == 1:
            return "one minute"
        elif m == 2:
            return "two minutes"
        else:
            return "{} minutes".format(m)

    def second(s):
        if s == 1:
            return "one second"
        elif s == 2:
            return "two seconds"
        else:
            return "{} seconds".format(s)

    def hour(h):
        if h == 1:
            return "one hour"
        elif h == 2:
            return "two hours"
        else:
            return "{} hours".format(h)

    if len(t) == 1:
        return second(t[0])
    elif len(t) == 2:
        return "{} and {}".format(minute(t[0]), second(t[1]))
    elif len(t) == 3:
        return "{}, {} and {}".format(hour(t[0]), minute(t[1]), second(t[2]))


def youtube_regexp(string):
    pattern = re.compile(
        r"^((?:https?:)?//)?((?:www|m)\.)?((?:youtube\.com|youtu.be))(/(?:[\w\-]+\?v=|embed/|v/)?)([\w\-]+)(\S+)?$")
    return pattern.search(string)


def direct_download(option, url, dlg, download_type="video", path=None):
    from download_handler.downloader import downloadAction
    if path is None:
        path = config_get("path")
    os.makedirs(path, exist_ok=True)
    format_str, convert = format_from_option(option)
    folder = False if download_type == "video" else True
    trd = Thread(
        target=downloadAction,
        kwargs={
            "url": url,
            "path": path,
            "dlg": dlg,
            "downloading_format": format_str,
            "convert": convert,
            "channel_or_playlist": folder,
        },
        daemon=True,
    )
    trd.start()


def check_for_updates(quiet=False):
    import requests
    url = "https://raw.githubusercontent.com/blind-tech-nexus/youtube-player-and-downloader-windows-application/master/update_info.json"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            if not quiet:
                wx.MessageBox(
                    "An error occurred while connecting to the update service. Please ensure a stable internet connection and try again.",
                    "Error",
                    parent=wx.GetApp().GetTopWindow(),
                    style=wx.ICON_ERROR
                )
            return
        info = r.json()
        if application.version != info["version"]:
            message = wx.MessageBox(
                "A new update is available. Would you like to download it now?",
                "New Update",
                parent=wx.GetApp().GetTopWindow(),
                style=wx.YES_NO
            )
            url = info["url"]
            if message == wx.YES:
                from gui.update_dialog import UpdateDialog
                wx.CallAfter(UpdateDialog, wx.GetApp().GetTopWindow(), url)
            return
        if not quiet:
            wx.MessageBox(
                "You are already running the latest version of the application.",
                "No Update",
                parent=wx.GetApp().GetTopWindow()
            )
    except (requests.ConnectionError, requests.Timeout):
        if not quiet:
            wx.MessageBox(
                "An error occurred while connecting to the update service. Please ensure a stable internet connection and try again.",
                "Error",
                parent=wx.GetApp().GetTopWindow(),
                style=wx.ICON_ERROR
            )
