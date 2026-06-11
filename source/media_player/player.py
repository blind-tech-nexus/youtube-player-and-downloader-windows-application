from datetime import timedelta
from threading import Thread
from settings_handler import config_get

_instance = None


def get_vlc_instance():
	global _instance
	if _instance is None:
		import vlc
		_instance = vlc.Instance("--quiet", "--no-video-title-show", "--network-caching=1000")
	return _instance


class Player:
	def __init__(self, filename, hwnd, window=None):
		import vlc
		self.do_reset = False
		self.closed = False
		self.window = window
		self.filename = filename
		self.hwnd = hwnd
		self.pending_position = None
		self.instance = get_vlc_instance()
		self.media = self.instance.media_player_new()
		self.media.set_hwnd(self.hwnd)
		self.manager = self.media.event_manager()
		self.manager.event_attach(vlc.EventType.MediaPlayerEndReached, self.onEnd)
		self.manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.onPlaying)
		self.volume = int(config_get("volume"))
		self.media.audio_set_volume(self.volume)
		self.set_media(self.filename)

	def onEnd(self, event):
		if self.closed:
			return
		self.do_reset = True
		Thread(target=self.reset, daemon=True).start()

	def onPlaying(self, event):
		if self.closed:
			return
		position = self.pending_position
		self.pending_position = None

		def apply():
			try:
				self.media.audio_set_volume(self.volume)
				if position is not None:
					self.media.set_position(position)
			except Exception:
				pass

		Thread(target=apply, daemon=True).start()

	def seek(self, seconds):
		length = self.media.get_length()
		if length == -1:
			return 0.03
		try:
			return seconds / (length / 1000)
		except ZeroDivisionError:
			return 0.03

	def get_duration(self):
		from utiles import time_formatting
		duration = self.media.get_length()
		if duration == -1 or not isinstance(duration, int):
			return ""
		return time_formatting(str(timedelta(seconds=duration // 1000)))

	def get_elapsed(self):
		from utiles import time_formatting
		elapsed = self.media.get_time()
		if elapsed == -1 or not isinstance(elapsed, int):
			return ""
		return time_formatting(str(timedelta(seconds=elapsed // 1000)))

	def get_remaining(self):
		from utiles import time_formatting
		duration = self.media.get_length()
		elapsed = self.media.get_time()
		if duration == -1 or elapsed == -1 or not isinstance(duration, int) or not isinstance(elapsed, int):
			return ""
		remaining = max((duration - elapsed) // 1000, 0)
		return time_formatting(str(timedelta(seconds=remaining)))

	def close(self):
		import vlc
		self.closed = True
		self.pending_position = None
		try:
			self.manager.event_detach(vlc.EventType.MediaPlayerEndReached)
			self.manager.event_detach(vlc.EventType.MediaPlayerPlaying)
		except Exception:
			pass

		def _stop():
			try:
				self.media.stop()
				self.media.set_media(None)
				self.media.release()
			except Exception:
				pass

		Thread(target=_stop, daemon=True).start()

	def reset(self):
		import wx
		self.do_reset = False
		if self.closed:
			return
		self.media.set_media(self.media.get_media())
		if config_get("repeatetracks") and not config_get('autonext'):
			self.media.play()
		elif config_get('autonext') and not config_get('repeatetracks'):
			if self.window is not None:
				wx.CallAfter(self.window.next)

	def set_media(self, m):
		media = self.instance.media_new(m)
		self.media.set_media(media)
		media.release()

	def resume_from(self, position):
		if position is not None and 0.0 < position < 1.0:
			self.pending_position = position

	def start(self):
		self.media.play()
		self.media.audio_set_volume(self.volume)

	def play_url(self, url):
		if self.closed:
			return
		self.filename = url
		self.set_media(url)
		self.media.play()
		self.media.audio_set_volume(self.volume)

	def stop_async(self):
		def _stop():
			try:
				self.media.stop()
			except Exception:
				pass

		Thread(target=_stop, daemon=True).start()
