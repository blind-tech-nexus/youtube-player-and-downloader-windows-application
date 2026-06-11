import wx
import os
import threading
import traceback
from settings_handler import config_get
from paths import get_runtime_search_dirs, resolve_runtime_path
from download_handler.formats import FALLBACK_AUDIO_FORMAT, FALLBACK_VIDEO_FORMAT


def _call_dialog(dialog, method_name, *args):
    def caller():
        try:
            if dialog is None or getattr(dialog, 'is_closing', False):
                return
            getattr(dialog, method_name)(*args)
        except (RuntimeError, AttributeError):
            pass

    wx.CallAfter(caller)


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
        self.download_started = False
        self.download_finished = False
        self.postprocess_started = False
        self.postprocess_finished = False

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
            self.download_started = True
            total_bytes = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            if total_bytes == 0:
                return
            downloaded_bytes = data.get("downloaded_bytes", 0)
            percent = int((downloaded_bytes / total_bytes) * 100)

            total = self.get_proper_count(total_bytes)
            downloaded = self.get_proper_count(downloaded_bytes)
            remaining = self.get_proper_count(total_bytes - downloaded_bytes)
            speed = "{}/s".format(self.get_proper_count(data.get('speed', 0)))

            _call_dialog(self.gui_frame, "update_status", "Downloading...")
            _call_dialog(self.gui_frame, "update_stats", percent, total, downloaded, remaining, speed)
        elif data.get('status') == 'finished':
            self.download_finished = True
            _call_dialog(self.gui_frame, "update_status", "Download finished, processing...")

    def pp_hook(self, data):
        if self.cancelled:
            raise Exception("Download stopped by user")
        if data.get('status') == 'started':
            self.postprocess_started = True
            _call_dialog(self.gui_frame, "update_status", "Converting your audio...")
        elif data.get('status') == 'finished':
            self.postprocess_finished = True
            _call_dialog(self.gui_frame, "update_status", "Conversion completed.")

    def completed_enough_to_finish(self):
        if self.convert:
            return self.postprocess_finished
        return self.download_finished

    def _fallback_format(self):
        fmt = self.downloading_format or ""
        if "bestvideo" in fmt or fmt.startswith("best["):
            return FALLBACK_VIDEO_FORMAT
        return FALLBACK_AUDIO_FORMAT

    def _build_options(self, downloading_format):
        deno_path = resolve_runtime_path("deno.exe")
        ffmpeg_dir = None
        for candidate_dir in get_runtime_search_dirs():
            if os.path.exists(os.path.join(candidate_dir, "ffmpeg.exe")):
                ffmpeg_dir = candidate_dir
                break
        if ffmpeg_dir is None:
            ffmpeg_dir = os.path.dirname(deno_path)

        if self.channel_or_playlist:
            out_tmpl = os.path.join(self.path, "%(playlist_title|%(uploader)s)s", "%(title)s.%(ext)s")
        else:
            out_tmpl = os.path.join(self.path, "%(title)s.%(ext)s")

        download_options = {
            'outtmpl': out_tmpl,
            'quiet': True,
            'no_warnings': True,
            'format': downloading_format,
            'continuedl': True,
            'concurrent_fragment_downloads': 4,
            'progress_hooks': [self.my_hook],
            'postprocessor_hooks': [self.pp_hook],
            'noplaylist': not self.channel_or_playlist,
            'ffmpeg_location': ffmpeg_dir,
            'ignoreerrors': True if self.channel_or_playlist else False,
            'extractor_retries': 3,
            'retries': 5,
            'fragment_retries': 5,
        }

        if os.path.exists(deno_path):
            download_options['js_runtimes'] = {'deno': {'executable': deno_path}}

        if self.convert:
            download_options['postprocessors'] = [{
                "key": "FFmpegExtractAudio",
                'preferredcodec': 'mp3',
                'preferredquality': self.get_quality(),
            }]
        return download_options

    def _run(self, downloading_format):
        import yt_dlp
        with yt_dlp.YoutubeDL(self._build_options(downloading_format)) as ydl:
            retcode = ydl.download([self.url])
        if retcode != 0 and not self.completed_enough_to_finish():
            raise Exception("Download failed")

    def download(self):
        import yt_dlp
        try:
            self._run(self.downloading_format)
        except yt_dlp.utils.DownloadError as e:
            if self.cancelled or "Requested format is not available" not in str(e):
                raise
            self._run(self._fallback_format())


def downloadAction(url, path, dlg, downloading_format, convert=False, channel_or_playlist=False):
    downloader = Downloader(url, path, downloading_format, dlg, convert=convert, channel_or_playlist=channel_or_playlist)
    dlg.downloader = downloader
    _call_dialog(dlg, "Show")

    def attempt(at):
        try:
            downloader.download()
            return True
        except Exception:
            if downloader.completed_enough_to_finish():
                return True
            if downloader.cancelled:
                if downloader.current_filename:
                    for ext in ['', '.part', '.ytdl']:
                        f = downloader.current_filename + ext
                        if os.path.exists(f):
                            try:
                                os.remove(f)
                            except Exception:
                                pass
                _call_dialog(dlg, "finish_cancelled")
                return False
            traceback.print_exc()
            if downloader.download_finished or downloader.postprocess_started:
                show_retry_error = True
            else:
                show_retry_error = at >= 3
            if not show_retry_error:
                return attempt(at + 1)

            def show_error():
                try:
                    if getattr(dlg, 'is_closing', False):
                        return
                    wx.MessageBox(
                        "Download failed. Please try another link, or check your network connection.",
                        "Error",
                        style=wx.OK | wx.ICON_ERROR,
                        parent=dlg
                    )
                    dlg.close_immediately()
                except (RuntimeError, AttributeError):
                    pass
            wx.CallAfter(show_error)
            return False

    def worker():
        if attempt(0):
            if not downloader.cancelled:
                downloader.is_finished = True
                success_message = "Download and conversion completed successfully!" if downloader.convert else "Download completed successfully!"
                _call_dialog(dlg, "finish_download", success_message)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
