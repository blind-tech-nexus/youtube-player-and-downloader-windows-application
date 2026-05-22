import re
from threading import Thread
from settings_handler import config_get
from download_handler.downloader import downloadAction
import json
import requests
import wx
import application
import os
import sys

import yt_dlp

resolution = "640x360"

def get_audio_stream(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'format': 'bestaudio',
        'skip_download': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if 'url' not in info:
            raise Exception("No audio stream found")
        return info

def get_video_stream(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'format': 'best',
        'skip_download': True
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        stream_url = info.get('url')
        if not stream_url:
            raise Exception("No playable stream URL found")
        return {
            'url': stream_url,
            'title': info.get('title'),
            'thumbnail': info.get('thumbnail'),
            'duration': info.get('duration')
        }

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
        elif 3 <= m <= 10:
            return "{} minutes".format(m)
        else:
            return "{} minutes".format(m)

    def second(s):
        if s == 1:
            return "one second"
        elif s == 2:
            return "two seconds"
        elif 3 <= s <= 10:
            return "{} seconds".format(s)
        else:
            return "{} seconds".format(s)

    def hour(h):
        if h == 1:
            return "one hour"
        elif h == 2:
            return "two hours"
        elif 3 <= h <= 10:
            return "{} hours".format(h)
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

def direct_download(option, url, dlg, download_type="video", path=config_get("path")):
    os.makedirs(path, exist_ok=True)
    if option == 0:
        format_str = "bestvideo+bestaudio/best"
    else:
        format_str = "bestaudio[ext=m4a]"
    convert = True if option == 2 else False
    folder = False if download_type == "video" else True
    trd = Thread(target=downloadAction, args=[url, path, dlg, format_str, dlg.gaugeProgress, dlg.textProgress, convert, folder], daemon=True)
    trd.start()

def check_for_updates(quiet=False):
    url = "https://raw.githubusercontent.com/rai369770-ship-it/youtube-player-and-downloader-windows-application/main/update_info.json"
    try:
        r = requests.get(url)
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
            print(info)
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
    except requests.ConnectionError:
        if not quiet:
            wx.MessageBox(
                "An error occurred while connecting to the update service. Please ensure a stable internet connection and try again.",
                "Error",
                parent=wx.GetApp().GetTopWindow(),
                style=wx.ICON_ERROR
            )
