import wx

def link_type(url):
	cases = ("list", "channel", "playlist", "/user/")
	if cases[0] in url or cases[2] in url:
		return "Playlist"
	elif cases[1] in url or cases[3] in url:
		return "Channel"
	else:
		return "Video"

class AutoDetectDialog(wx.Dialog):
	def __init__(self, parent, url):
		wx.Dialog.__init__(self, parent, title=parent.Title)
		self.url  = url
		self.Centre()
		panel = wx.Panel(self)
		msg = wx.StaticText(panel, -1, "A YouTube {} link was detected in the clipboard. Choose what you want to do.".format(link_type(url)))
		downloadButton = wx.Button(panel, -1, "Download")
		playButton = wx.Button(panel, -1, "Play")

		if link_type(self.url) == "Playlist":
			playButton.Label = "Open..."
		elif link_type(url) != "Video":
			playButton.Disable() 
		cancelButton = wx.Button(panel, wx.ID_CANCEL, "Cancel")
		downloadButton.Bind(wx.EVT_BUTTON, self.onDownload)
		playButton.Bind(wx.EVT_BUTTON, self.onPlay)
		self.ShowModal()
	def onDownload(self, event):
		from .download_dialog import DownloadDialog
		dlg = DownloadDialog(wx.GetApp().GetTopWindow(), self.url)
		dlg.Show()
		self.Destroy()
	def onPlay(self, event):
		if link_type(self.url) == "Playlist":
			from .playlist_dialog import PlaylistDialog
			PlaylistDialog(self.Parent, self.url)
			self.Destroy()
			return
		from .activity_dialog import AsyncLoadingDialog
		from utiles import get_audio_stream
		parent = self.Parent
		url = self.url
		self.Destroy()
		def open_player(stream):
			from media_player.media_gui import MediaGui
			MediaGui(parent, stream.get("title") or url, stream, url, audio_mode=True)
		AsyncLoadingDialog(parent, "Fetching streaming URL...", get_audio_stream, open_player, url)
