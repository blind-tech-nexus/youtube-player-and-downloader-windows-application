import wx
import os
import threading
import traceback
from settings_handler import config_get
import yt_dlp

class Downloader:
    def __init__(self, url, path, downloading_format, gui_frame, convert=False, channel_or_playlist=False):
        self.url = url
        self.path = path
        self.downloading_format = downloading_format
        self.gui_frame = gui_frame
        self.convert = convert
        self.channel_or_playlist = channel_or_playlist
        self.cancelled = False
        self.is_finished = False
        self.current_filename = None

    @staticmethod
    def get_proper_count(number):
        if number is None:
            return "0 Bytes"
        length = len(str(int(number)))
        if length <= 3:
            return "{} Bytes".format(number)
        elif 4 <= length < 7:
            return "{} KB".format(round(number / 1024, 2))
        elif 7 <= length < 10:
            return "{} MB".format(round(number / 1024 ** 2, 2))
        elif 10 <= length < 13:
            return "{} GB".format(round(number / 1024 ** 3, 2))
        else:
            return "{} TB".format(round(number / 1024 ** 4, 2))

    def get_quality(self):
        qualities = {
            0: '96',
            1: '128',
            2: '192'
        }
        return qualities.get(int(config_get("conversion")), '192')

    def my_hook(self, data):
        if self.cancelled:
            raise Exception("Download stopped by user")
        
        if 'filename' in data:
            self.current_filename = data['filename']
            
        if data.get('status') == 'downloading':
            total_bytes = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            if total_bytes == 0:
                return
            downloaded_bytes = data.get("downloaded_bytes", 0)
            percent = int((downloaded_bytes / total_bytes) * 100)
            
            total = self.get_proper_count(total_bytes)
            downloaded = self.get_proper_count(downloaded_bytes)
            remaining = self.get_proper_count(total_bytes - downloaded_bytes)
            speed = "{}/s".format(self.get_proper_count(data.get('speed', 0)))
            
            wx.CallAfter(self.gui_frame.update_status, "Downloading...")
            wx.CallAfter(self.gui_frame.update_stats, percent, total, downloaded, remaining, speed)
        elif data.get('status') == 'finished':
            wx.CallAfter(self.gui_frame.update_status, "Download finished, processing...")

    def pp_hook(self, data):
        if self.cancelled:
            raise Exception("Download stopped by user")
        if data.get('status') == 'started':
            wx.CallAfter(self.gui_frame.update_status, "Converting your audio...")
        elif data.get('status') == 'finished':
            wx.CallAfter(self.gui_frame.update_status, "Conversion completed.")

    def download(self):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        deno_path = os.path.join(project_root, "deno.exe")
        cookies_path = os.path.join(project_root, "cookies.txt")

        if self.channel_or_playlist:
            out_tmpl = os.path.join(self.path, "%(playlist_title|%(uploader)s)s", "%(title)s.%(ext)s")
        else:
            out_tmpl = os.path.join(self.path, "%(title)s.%(ext)s")

        download_options = {
            'outtmpl': out_tmpl,
            'quiet': True,
            'format': self.downloading_format,
            'continuedl': True,
            'youtube_include_dash_manifest': False,
            'concurrent_fragment_downloads': 4,
            'progress_hooks': [self.my_hook],
            'postprocessor_hooks': [self.pp_hook],
            'noplaylist': not self.channel_or_playlist,
            'ffmpeg_location': project_root,
            'ignoreerrors': True,
        }

        if os.path.exists(cookies_path):
            download_options['cookiefile'] = cookies_path

        if os.path.exists(deno_path):
            download_options['js_runtimes'] = {'deno': {'executable': deno_path}}

        if self.convert:
            download_options['postprocessors'] = [{
                "key": "FFmpegExtractAudio",
                'preferredcodec': 'mp3',
                'preferredquality': self.get_quality(),
            }]

        with yt_dlp.YoutubeDL(download_options) as ydl:
            ydl.download([self.url])

def downloadAction(url, path, dlg, downloading_format, convert=False, channel_or_playlist=False):
    downloader = Downloader(url, path, downloading_format, dlg, convert=convert, channel_or_playlist=channel_or_playlist)
    dlg.downloader = downloader
    wx.CallAfter(dlg.Show)

    def attempt(at):
        try:
            downloader.download()
            return True
        except Exception as e:
            traceback.print_exc()
            if downloader.cancelled:
                if downloader.current_filename:
                    for ext in ['', '.part', '.ytdl']:
                        f = downloader.current_filename + ext
                        if os.path.exists(f):
                            try:
                                os.remove(f)
                            except:
                                pass
                wx.CallAfter(dlg.Destroy)
                return False
            if at < 3:
                return attempt(at + 1)
            else:
                def show_error():
                    wx.MessageBox(
                        "Download failed. Please try another link, or check your network connection.",
                        "Error",
                        style=wx.ICON_ERROR,
                        parent=dlg
                    )
                    dlg.Destroy()
                wx.CallAfter(show_error)
                return False

    def worker():
        if attempt(0):
            if not downloader.cancelled:
                downloader.is_finished = True
                def show_success():
                    dlg.is_completed = True
                    dlg.update_status("Completed Successfully!")
                    wx.MessageBox("Action completed successfully!", "Success", parent=dlg, style=wx.ICON_INFORMATION)
                    dlg.Destroy()
                wx.CallAfter(show_success)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
