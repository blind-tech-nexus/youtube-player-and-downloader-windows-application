# favorites.py
import wx
import application
from database import Favorite
from nvda_client.client import speak
from .activity_dialog import AsyncLoadingDialog, LoadingDialog
from settings_handler import config_get
import webbrowser


class Favorites(wx.Frame):
    def __init__(self, parent):
        super().__init__(parent, title=application.name)
        self.Centre()
        self.SetSize(wx.DisplaySize())
        self.Maximize(True)
        p = wx.Panel(self)
        l1 = wx.StaticText(p, -1, "Favorites: ")
        self.favList = wx.ListBox(p, -1)
        self.playButton = wx.Button(p, -1, "Play", name="control")
        self.openChannelButton = wx.Button(p, -1, "Open channel", name="control")
        self.downloadButton = wx.Button(p, -1, "Download", name="control")
        self.deleteButton = wx.Button(p, -1, "Remove from favorites", name="control")
        backButton = wx.Button(p, -1, "Back to main window", name="control")
        self.favorites = Favorite()
        self.rows = self.favorites.get_all()
        self.refresh_list()
        if self.rows:
            self.favList.Selection = 0
            self.contextSetup()
            hotkeys = wx.AcceleratorTable([
                (0, wx.WXK_RETURN, self.videoPlayItemId),
                (wx.ACCEL_CTRL, wx.WXK_RETURN, self.audioPlayItemId),
                (wx.ACCEL_CTRL, ord("D"), self.directDownloadId),
                (wx.ACCEL_CTRL, ord("L"), self.copyItemId),
            ])
            self.favList.SetAcceleratorTable(hotkeys)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(l1, 1)
        sizer.Add(self.favList, 1, wx.EXPAND)
        ctrlSizer = wx.BoxSizer(wx.HORIZONTAL)
        for control in p.GetChildren():
            if control.Name == "control":
                ctrlSizer.Add(control, 1)
        sizer.Add(ctrlSizer)
        self.togleControls()

        self.playButton.Bind(wx.EVT_BUTTON, lambda e: self.playVideo())
        self.openChannelButton.Bind(wx.EVT_BUTTON, self.onOpenChannel)
        self.downloadButton.Bind(wx.EVT_BUTTON, self.onDownload)
        self.deleteButton.Bind(wx.EVT_BUTTON, self.onDelete)
        self.favList.Bind(wx.EVT_LISTBOX, lambda e: self.togleControls())
        backButton.Bind(wx.EVT_BUTTON, self.onBack)
        self.Bind(wx.EVT_CLOSE, lambda e: wx.Exit())
        self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
        p.SetSizer(sizer)
        sizer.Fit(p)
        self.Show()

    def refresh_list(self):
        if self.rows:
            self.favList.Set([row["display_title"] for row in self.rows])
        else:
            self.favList.Set(["No favorites..."])

    def onDelete(self, event):
        n = self.favList.Selection
        if n == -1 or not self.rows:
            return
        url = self.rows[n]["url"]
        self.favorites.remove_favorite(url)
        self.rows.pop(n)
        self.refresh_list()
        self.togleControls()
        if self.rows:
            self.favList.Selection = min(n, len(self.rows) - 1)
        else:
            self.favList.Selection = 0
        self.favList.SetFocus()
        speak("Removed from favorites")

    def playVideo(self):
        n = self.favList.Selection
        if n == -1 or not self.rows:
            return
        item_type = self.rows[n].get("item_type", "video")
        if item_type == "playlist":
            from gui.playlist_dialog import PlaylistDialog
            PlaylistDialog(self, self.rows[n]["url"])
            return
        if item_type == "channel":
            from gui.channel_dialog import ChannelDialog
            ChannelDialog(self, self.rows[n]["url"])
            return
        url = self.rows[n]["url"]
        title = self.rows[n]["title"]
        from utiles import get_video_stream

        def open_player(stream):
            from media_player.media_gui import MediaGui
            MediaGui(self, title, stream, url, True if not self.rows[n]["live"] else False, self.rows)
            self.Hide()

        AsyncLoadingDialog(self, "Fetching streaming URL...", get_video_stream, open_player, url)

    def playAudio(self):
        n = self.favList.Selection
        if n == -1 or not self.rows or self.rows[n].get("item_type", "video") in ("playlist", "channel"):
            return
        url = self.rows[n]["url"]
        title = self.rows[n]["title"]
        from utiles import get_audio_stream

        def open_player(stream):
            from media_player.media_gui import MediaGui
            MediaGui(self, title, stream, url, audio_mode=True, results=self.rows)
            self.Hide()

        AsyncLoadingDialog(self, "Fetching streaming URL...", get_audio_stream, open_player, url)

    def togleControls(self):
        for control in (self.playButton, self.openChannelButton, self.downloadButton, self.deleteButton):
            if self.rows == []:
                control.Disable()
            else:
                control.Enable()
        self.toglePlayLabel()

    def toglePlayLabel(self):
        n = self.favList.Selection
        if n == -1 or self.rows == []:
            self.playButton.Label = "Play"
            self.openChannelButton.Label = "Open channel"
            self.openChannelButton.Enabled = False
            return
        item_type = self.rows[n].get("item_type", "video")
        if item_type == "playlist":
            self.playButton.Label = "Open playlist"
            self.openChannelButton.Label = "Open channel"
            self.openChannelButton.Enabled = False
        elif item_type == "channel":
            self.playButton.Label = "Open channel"
            self.openChannelButton.Label = "Open channel"
            self.openChannelButton.Enabled = False
        else:
            self.playButton.Label = "Play"
            channel_name = self.rows[n].get("channel_name") or "channel"
            self.openChannelButton.Label = f"Open {channel_name}"
            self.openChannelButton.Enabled = bool(self.rows[n].get("channel_url"))

    def contextSetup(self):
        self.contextMenu = wx.Menu()
        videoPlayItem = self.contextMenu.Append(-1, "Play")
        self.videoPlayItemId = videoPlayItem.GetId()
        audioPlayItem = self.contextMenu.Append(-1, "Play as audio")
        self.audioPlayItemId = audioPlayItem.GetId()
        self.downloadMenu = wx.Menu()
        videoItem = self.downloadMenu.Append(-1, "Video")
        audioMenu = wx.Menu()
        m4aItem = audioMenu.Append(-1, "m4a")
        mp3Item = audioMenu.Append(-1, "mp3")
        self.downloadMenu.AppendSubMenu(audioMenu, "Audio")
        self.downloadId = self.contextMenu.AppendSubMenu(self.downloadMenu, "Download").GetId()
        directDownloadItem = self.contextMenu.Append(-1, "Direct download...\tctrl+d")
        self.directDownloadId = directDownloadItem.GetId()
        openChannelItem = self.contextMenu.Append(-1, "Open channel")
        downloadChannelItem = self.contextMenu.Append(-1, "Download channel")
        copyItem = self.contextMenu.Append(-1, "Copy Video link")
        self.copyItemId = copyItem.GetId()
        webbrowserItem = self.contextMenu.Append(-1, "Open in web browser")
        def popup():
            if self.rows != []:
                self.favList.PopupMenu(self.contextMenu)
        self.favList.Bind(wx.EVT_CONTEXT_MENU, lambda event: popup())
        self.favList.Bind(wx.EVT_MENU, lambda e: self.playVideo(), id=self.videoPlayItemId)
        self.favList.Bind(wx.EVT_MENU, lambda e: self.playAudio(), id=self.audioPlayItemId)
        self.favList.Bind(wx.EVT_MENU, self.onCopy, id=self.copyItemId)
        self.favList.Bind(wx.EVT_MENU, lambda e: self.directDownload(), id=self.directDownloadId)
        self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
        self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
        self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
        self.favList.Bind(wx.EVT_MENU, self.onOpenChannel, openChannelItem)
        self.favList.Bind(wx.EVT_MENU, self.onDownloadChannel, downloadChannelItem)
        self.Bind(wx.EVT_MENU, self.onOpenInBrowser, webbrowserItem)

    def onOpenInBrowser(self, event):
        n = self.favList.Selection
        if n == -1 or not self.rows:
            return
        webbrowser.open(self.rows[n]["url"])

    def onOpenChannel(self, event):
        n = self.favList.Selection
        if n == -1 or not self.rows:
            return
        item_type = self.rows[n].get("item_type", "video")
        if item_type == "channel":
            from gui.channel_dialog import ChannelDialog
            ChannelDialog(self, self.rows[n]["url"])
        elif self.rows[n]["channel_url"]:
            from gui.channel_dialog import ChannelDialog
            ChannelDialog(self, self.rows[n]["channel_url"])

    def onDownloadChannel(self, event):
        n = self.favList.Selection
        if n == -1 or not self.rows:
            return
        title = self.rows[n]["channel_name"]
        url = self.rows[n]["channel_url"]
        if self.rows[n].get("item_type", "video") == "channel":
            title = self.rows[n]["title"]
            url = self.rows[n]["url"]
        if not url:
            return
        from gui.download_progress import DownloadProgress
        from download_handler.downloader import downloadAction

        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        option = int(config_get('defaultformat'))
        fmt, conv = self._format_from_option(option)
        downloadAction(url, config_get('path'), dlg, fmt, convert=conv, channel_or_playlist=True)

    def onCopy(self, event):
        if self.favList.Selection == -1 or not self.rows:
            return
        import pyperclip
        pyperclip.copy(self.rows[self.favList.Selection]["url"])
        wx.MessageBox("Link copied successfully", "Done", parent=self)

    def _format_from_option(self, option):
        from download_handler.formats import format_from_option
        return format_from_option(option)

    def directDownload(self):
        n = self.favList.Selection
        if n == -1 or not self.rows:
            return
        url = self.rows[n]["url"]
        title = self.rows[n]["title"]
        item_type = self.rows[n].get("item_type", "video")
        option = int(config_get('defaultformat'))
        fmt, conv = self._format_from_option(option)
        from gui.download_progress import DownloadProgress
        from download_handler.downloader import downloadAction

        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        is_channel_or_playlist = item_type in ("channel", "playlist")
        downloadAction(url, config_get('path'), dlg, fmt, convert=conv, channel_or_playlist=is_channel_or_playlist)

    def onM4aDownload(self, event):
        n = self.favList.Selection
        if n == -1 or not self.rows or self.rows[n].get("item_type", "video") in ("playlist", "channel"):
            self.directDownload()
            return
        url = self.rows[n]["url"]
        title = self.rows[n]["title"]
        from gui.download_progress import DownloadProgress
        from download_handler.downloader import downloadAction
        from download_handler.formats import AUDIO_M4A_FORMAT

        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        downloadAction(url, config_get('path'), dlg, AUDIO_M4A_FORMAT, convert=False, channel_or_playlist=False)

    def onMp3Download(self, event):
        n = self.favList.Selection
        if n == -1 or not self.rows or self.rows[n].get("item_type", "video") in ("playlist", "channel"):
            self.directDownload()
            return
        url = self.rows[n]["url"]
        title = self.rows[n]["title"]
        from gui.download_progress import DownloadProgress
        from download_handler.downloader import downloadAction
        from download_handler.formats import AUDIO_DOWNLOAD_FORMAT

        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        downloadAction(url, config_get('path'), dlg, AUDIO_DOWNLOAD_FORMAT, convert=True, channel_or_playlist=False)

    def onVideoDownload(self, event):
        n = self.favList.Selection
        if n == -1 or not self.rows:
            return
        url = self.rows[n]["url"]
        title = self.rows[n]["title"]
        item_type = self.rows[n].get("item_type", "video")
        from gui.download_progress import DownloadProgress
        from download_handler.downloader import downloadAction
        from download_handler.formats import VIDEO_DOWNLOAD_FORMAT

        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        downloadAction(url, config_get('path'), dlg, VIDEO_DOWNLOAD_FORMAT, convert=False, channel_or_playlist=(item_type in ("channel", "playlist")))

    def onDownload(self, event):
        n = self.favList.Selection
        if n == -1 or not self.rows:
            return
        if self.rows[n].get("item_type", "video") in ("playlist", "channel"):
            self.directDownload()
            return
        downloadMenu = wx.Menu()
        videoItem = downloadMenu.Append(-1, "Video")
        audioMenu = wx.Menu()
        m4aItem = audioMenu.Append(-1, "m4a")
        mp3Item = audioMenu.Append(-1, "mp3")
        downloadMenu.AppendSubMenu(audioMenu, "Audio")
        self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
        self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
        self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
        self.PopupMenu(downloadMenu)

    def onHook(self, event):
        if event.KeyCode in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE) and self.FindFocus() == self.favList:
            self.onDelete(None)
        elif event.KeyCode == wx.WXK_BACK:
            self.onBack(None)
        else:
            event.Skip()

    def onBack(self, event):
        self.Parent.Show()
        self.Destroy()
