# playlist_dialog.py
import wx
from youtube_browser.ytdlp_collections import PlaylistResult
from download_handler.downloader import downloadAction
from download_handler.formats import AUDIO_DOWNLOAD_FORMAT, AUDIO_M4A_FORMAT, VIDEO_DOWNLOAD_FORMAT, format_from_option
from media_player.media_gui import MediaGui
from nvda_client.client import speak
import pyperclip
from gui.download_progress import DownloadProgress
from settings_handler import config_get
import webbrowser
from threading import Thread
import os
from .activity_dialog import LoadingDialog
import application
from database import Favorite
from gui.channel_dialog import ChannelDialog
from utiles import get_audio_stream, get_video_stream

class PlaylistDialog(wx.Dialog):
    def __init__(self, parent, url, views="", elements=""):
        super().__init__(parent, title=application.name)
        self.CenterOnParent()
        self.url = url
        self.Maximize(True)
        self.prefetched_views = views
        self.prefetched_elements = elements
        
        p = wx.Panel(self)
        self.infoText = wx.StaticText(p, -1, "")
        self.infoText.Wrap(900)
        l1 = wx.StaticText(p, -1, "Videos: ")
        self.videosBox = wx.ListBox(p, -1)
        self.playButton = wx.Button(p, -1, "Play", name="control")
        self.downloadButton = wx.Button(p, -1, "Download video", name="control")
        self.downloadPlaylistButton = wx.Button(p, -1, "Download playlist", name="control")
        self.favCheck = wx.CheckBox(p, -1, "Favorite playlist", name="control")
        backButton = wx.Button(p, -1, "Back", name="control")
        self.favorites = Favorite()
        self.contextSetup()

        hotkeys = wx.AcceleratorTable([
            (0, wx.WXK_RETURN, self.videoPlayItemId),
            (wx.ACCEL_CTRL, wx.WXK_RETURN, self.audioPlayItemId),
            (wx.ACCEL_CTRL, ord("D"), self.directDownloadId),
            (wx.ACCEL_CTRL, ord("L"), self.copyItemId),
        ])
        self.videosBox.SetAcceleratorTable(hotkeys)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.infoText, 0, wx.TOP | wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL, 8)
        sizer.Add(l1, 0, wx.ALL, 4)
        sizer.Add(self.videosBox, 1, wx.EXPAND)
        ctrlSizer = wx.BoxSizer(wx.HORIZONTAL)
        for control in p.GetChildren():
            if control.Name == "control":
                ctrlSizer.Add(control, 1)
        sizer.Add(ctrlSizer)
        p.SetSizer(sizer)
        self.videosBox.Bind(wx.EVT_LISTBOX, self.onListBox)
        self.playButton.Bind(wx.EVT_BUTTON, lambda e: self.playVideo())
        self.downloadButton.Bind(wx.EVT_BUTTON, self.onDownload)
        self.downloadPlaylistButton.Bind(wx.EVT_BUTTON, self.onDownloadPlaylist)
        self.favCheck.Bind(wx.EVT_CHECKBOX, self.onFavoritePlaylist)
        backButton.Bind(wx.EVT_BUTTON, lambda e: self.back())
        self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
        self.Bind(wx.EVT_CLOSE, lambda e: wx.Exit())
        
        try:
            self.result = LoadingDialog(self.Parent, "Loading playlist", PlaylistResult, self.url).res
            self.title = self.result.title
            self.SetTitle(self.title)
            self.infoText.Label = self.get_info_text()
            self.videosBox.Set(self.result.get_display_titles())
        except Exception as e:
            wx.MessageBox(f"An error occurred while opening the playlist.\n\n{e}", "Error", style=wx.ICON_ERROR, parent=self)
            self.Destroy()
            return
            
        self.Parent.Hide()
        self.Show()
        if self.videosBox.Count:
            self.videosBox.Selection = 0
        self.togleControls()
        self.togleFavorite()

    def get_info_text(self):
        parts = [f"Playlist: {self.result.title}"]
        if self.result.channel_name:
            parts.append(f"By {self.result.channel_name}")
            
        elements = self.result.upload_count or self.prefetched_elements
        if elements:
            parts.append(f"Videos: {elements}")
            
        views = self.result.view_count or self.prefetched_views
        if views:
            parts.append(f"Views: {views}")
            
        return ". ".join(parts)

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
        downloadPlaylistItem = self.contextMenu.Append(-1, "Download playlist")
        openChannelItem = self.contextMenu.Append(-1, "Open channel")
        downloadChannelItem = self.contextMenu.Append(-1, "Download channel")
        copyItem = self.contextMenu.Append(-1, "Copy Video link")
        self.copyItemId = copyItem.GetId()
        webbrowserItem = self.contextMenu.Append(-1, "Open in web browser")
        
        def popup():
            if self.result and self.result.has_results():
                self.videosBox.PopupMenu(self.contextMenu)
                
        self.videosBox.Bind(wx.EVT_CONTEXT_MENU, lambda event: popup())
        self.videosBox.Bind(wx.EVT_MENU, lambda e: self.playVideo(), id=self.videoPlayItemId)
        self.videosBox.Bind(wx.EVT_MENU, lambda e: self.playAudio(), id=self.audioPlayItemId)
        self.videosBox.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
        self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
        self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
        self.videosBox.Bind(wx.EVT_MENU, lambda e: self.directDownload(), id=self.directDownloadId)
        self.videosBox.Bind(wx.EVT_MENU, self.onDownloadPlaylist, downloadPlaylistItem)
        self.videosBox.Bind(wx.EVT_MENU, self.onCopy, id=self.copyItemId)
        self.videosBox.Bind(wx.EVT_MENU, self.onOpenChannel, openChannelItem)
        self.videosBox.Bind(wx.EVT_MENU, self.onDownloadChannel, downloadChannelItem)
        self.Bind(wx.EVT_MENU, self.onOpenInBrowser, webbrowserItem)

    def onOpenInBrowser(self, event):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        webbrowser.open(self.result.get_url(n))

    def onCopy(self, event):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        pyperclip.copy(self.result.get_url(n))
        wx.MessageBox("Video link copied successfully", "Done", parent=self)

    def onOpenChannel(self, event):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        url = self.result.videos[n]['channel']['url']
        if url:
            ChannelDialog(self, url)

    def onDownloadChannel(self, event):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        title = self.result.videos[n]["channel"]['name']
        url = self.result.videos[n]["channel"]['url']
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        option = int(config_get('defaultformat'))
        fmt, conv = self._format_from_option(option)
        downloadAction(url, config_get('path'), dlg, fmt, convert=conv, channel_or_playlist=True)

    def playVideo(self):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        url = self.result.get_url(n)
        title = self.result.get_title(n)
        stream = LoadingDialog(self, "Playing video...", get_video_stream, url).res
        gui = MediaGui(self, title, stream, url, True, self.result)
        gui.path = os.path.join(gui.path, self.title)
        self.Hide()

    def playAudio(self):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        url = self.result.get_url(n)
        title = self.result.get_title(n)
        stream = LoadingDialog(self, "Playing audio...", get_audio_stream, url).res
        gui = MediaGui(self, title, stream, url, audio_mode=True, results=self.result)
        gui.path = os.path.join(gui.path, self.title)
        self.Hide()

    def onListBox(self, event):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        if n == self.videosBox.Count-1:
            def load():
                try:
                    if self.result.next():
                        titles = self.result.get_new_titles()
                        wx.CallAfter(self.videosBox.Append, titles)
                        speak("More videos loaded")
                    else:
                        speak("There are no more videos")
                except Exception as e:
                    speak("No more videos were loaded")
            Thread(target=load, daemon=True).start()

    def onVideoDownload(self, event):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        url = self.result.get_url(n)
        title = self.result.get_title(n)
        dlg = DownloadProgress(self.Parent, title)
        path = os.path.join(config_get("path"), self.title)
        downloadAction(url, path, dlg, VIDEO_DOWNLOAD_FORMAT, convert=False, channel_or_playlist=False)

    def directDownload(self):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        url = self.result.get_url(n)
        title = self.result.get_title(n)
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        option = int(config_get('defaultformat'))
        fmt, conv = self._format_from_option(option)
        path = os.path.join(config_get("path"), self.title)
        downloadAction(url, path, dlg, fmt, convert=conv, channel_or_playlist=False)

    def _format_from_option(self, option):
        return format_from_option(option)

    def onM4aDownload(self, event):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        url = self.result.get_url(n)
        title = self.result.get_title(n)
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        path = os.path.join(config_get("path"), self.title)
        downloadAction(url, path, dlg, AUDIO_M4A_FORMAT, convert=False, channel_or_playlist=False)

    def onMp3Download(self, event):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        url = self.result.get_url(n)
        title = self.result.get_title(n)
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        path = os.path.join(config_get("path"), self.title)
        downloadAction(url, path, dlg, AUDIO_DOWNLOAD_FORMAT, convert=True, channel_or_playlist=False)

    def onDownload(self, event):
        self.show_video_download_menu()
        self.videosBox.SetFocus()

    def onDownloadPlaylist(self, event):
        self.show_playlist_download_menu()
        self.videosBox.SetFocus()

    def show_video_download_menu(self):
        downloadMenu = wx.Menu()
        videoItem = downloadMenu.Append(-1, "Video")
        audioMenu = wx.Menu()
        m4aItem = audioMenu.Append(-1, "m4a")
        mp3Item = audioMenu.Append(-1, "mp3")
        downloadMenu.AppendSubMenu(audioMenu, "Audio")
        self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
        self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
        self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
        self.downloadButton.PopupMenu(downloadMenu)

    def show_playlist_download_menu(self):
        downloadMenu = wx.Menu()
        videoItem = downloadMenu.Append(-1, "Video")
        audioMenu = wx.Menu()
        m4aItem = audioMenu.Append(-1, "m4a")
        mp3Item = audioMenu.Append(-1, "mp3")
        downloadMenu.AppendSubMenu(audioMenu, "Audio")
        self.Bind(wx.EVT_MENU, self.onPlaylistVideoDownload, videoItem)
        self.Bind(wx.EVT_MENU, self.onPlaylistM4aDownload, m4aItem)
        self.Bind(wx.EVT_MENU, self.onPlaylistMp3Download, mp3Item)
        self.downloadPlaylistButton.PopupMenu(downloadMenu)

    def onPlaylistVideoDownload(self, event):
        self.downloadPlaylistSelection(0)

    def onPlaylistM4aDownload(self, event):
        self.downloadPlaylistSelection(1)

    def onPlaylistMp3Download(self, event):
        self.downloadPlaylistSelection(2)

    def downloadPlaylistSelection(self, option):
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), self.title)
        fmt, conv = self._format_from_option(option)
        downloadAction(self.url, config_get('path'), dlg, fmt, convert=conv, channel_or_playlist=True)

    def onFavoritePlaylist(self, event):
        data = {
            "title": self.title,
            "display_title": f"{self.title}. Playlist",
            "url": self.url,
            "live": 0,
            "channel_name": self.result.channel_name,
            "channel_url": self.result.channel_url,
            "item_type": "playlist",
        }
        if self.favCheck.Value:
            self.favorites.add_favorite(data)
            speak("Playlist added to favorites")
        else:
            self.favorites.remove_favorite(self.url)
            speak("Playlist removed from favorites")

    def togleFavorite(self):
        self.favCheck.SetValue(self.favorites.exists(self.url))

    def togleControls(self):
        enabled = self.result is not None and self.result.has_results()
        self.playButton.Enabled = enabled
        self.downloadButton.Enabled = enabled

    def valid_selection(self):
        return self.result is not None and self.result.has_results() and self.videosBox.Selection != -1

    def back(self):
        self.Parent.Show()
        self.Destroy()

    def onHook(self, event):
        if event.KeyCode in (wx.WXK_ESCAPE, wx.WXK_BACK) and not type(self.FindFocus()) == MediaGui:
            self.back()
        else:
            event.Skip()
