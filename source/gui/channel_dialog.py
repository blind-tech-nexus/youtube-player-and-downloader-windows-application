# channel_dialog.py
import os
from threading import Thread
import webbrowser
import pyperclip
import wx
import application
from database import Favorite
from gui.download_progress import DownloadProgress
from download_handler.downloader import downloadAction
from download_handler.formats import AUDIO_DOWNLOAD_FORMAT, AUDIO_M4A_FORMAT, VIDEO_DOWNLOAD_FORMAT, format_from_option
from media_player.media_gui import MediaGui
from nvda_client.client import speak
from settings_handler import config_get
from utiles import get_audio_stream, get_video_stream
from youtube_browser.ytdlp_collections import ChannelResult
from .activity_dialog import LoadingDialog


class ChannelDialog(wx.Dialog):
    def __init__(self, parent, url, subscribers="", elements=""):
        super().__init__(parent, title=application.name)
        self.CenterOnParent()
        self.Maximize(True)
        self.url = url
        self.favorites = Favorite()
        self.result = None
        self.prefetched_subscribers = subscribers
        self.prefetched_elements = elements
        
        p = wx.Panel(self)
        self.infoText = wx.StaticText(p, -1, "")
        self.infoText.Wrap(900)
        listLabel = wx.StaticText(p, -1, "Channel videos: ")
        self.videosBox = wx.ListBox(p, -1)
        self.playButton = wx.Button(p, -1, "Play", name="control")
        self.downloadButton = wx.Button(p, -1, "Download video", name="control")
        self.downloadChannelButton = wx.Button(p, -1, "Download channel", name="control")
        self.favCheck = wx.CheckBox(p, -1, "Favorite channel", name="control")
        backButton = wx.Button(p, -1, "Back", name="control")
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
        sizer.Add(listLabel, 0, wx.ALL, 4)
        sizer.Add(self.videosBox, 1, wx.EXPAND)
        ctrlSizer = wx.BoxSizer(wx.HORIZONTAL)
        for control in p.GetChildren():
            if control.Name == "control":
                ctrlSizer.Add(control, 1)
        sizer.Add(ctrlSizer, 0, wx.EXPAND)
        p.SetSizer(sizer)
        self.videosBox.Bind(wx.EVT_LISTBOX, self.onListBox)
        self.playButton.Bind(wx.EVT_BUTTON, lambda e: self.playVideo())
        self.downloadButton.Bind(wx.EVT_BUTTON, self.onDownload)
        self.downloadChannelButton.Bind(wx.EVT_BUTTON, self.onDownloadChannel)
        self.favCheck.Bind(wx.EVT_CHECKBOX, self.onFavoriteChannel)
        backButton.Bind(wx.EVT_BUTTON, lambda e: self.back())
        self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
        self.Bind(wx.EVT_CLOSE, lambda e: wx.Exit())
        
        try:
            self.result = LoadingDialog(self.Parent, "Loading channel", ChannelResult, self.url).res
            self.SetTitle(self.result.title)
            self.infoText.Label = self.get_info_text()
            self.videosBox.Set(self.result.get_display_titles())
        except Exception as e:
            wx.MessageBox(f"An error occurred while opening the channel.\n\n{e}", "Error", style=wx.ICON_ERROR, parent=self)
            self.Destroy()
            return
            
        self.Parent.Hide()
        self.Show()
        if self.videosBox.Count:
            self.videosBox.Selection = 0
        self.togleControls()
        self.togleFavorite()
        self.videosBox.SetFocus()

    def get_info_text(self):
        parts = [f"Channel: {self.result.title}"]
        
        subscribers = self.result.subscribers or self.prefetched_subscribers
        if subscribers:
            parts.append(f"Subscribers: {subscribers}")
            
        upload_count = self.result.upload_count or self.prefetched_elements
        if upload_count:
            parts.append(f"Uploads: {upload_count}")
            
        if self.result.view_count:
            parts.append(f"Views: {self.result.view_count}")
            
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
        self.downloadId = self.contextMenu.AppendSubMenu(self.downloadMenu, "Download video").GetId()
        directDownloadItem = self.contextMenu.Append(-1, "Direct download...\tctrl+d")
        self.directDownloadId = directDownloadItem.GetId()
        downloadChannelItem = self.contextMenu.Append(-1, "Download channel")
        copyItem = self.contextMenu.Append(-1, "Copy video link")
        self.copyItemId = copyItem.GetId()
        webbrowserItem = self.contextMenu.Append(-1, "Open video in web browser")
        
        def popup():
            if self.result and self.result.has_results():
                self.videosBox.PopupMenu(self.contextMenu)
                
        self.videosBox.Bind(wx.EVT_CONTEXT_MENU, lambda event: popup())
        self.videosBox.Bind(wx.EVT_MENU, lambda e: self.playVideo(), id=self.videoPlayItemId)
        self.videosBox.Bind(wx.EVT_MENU, lambda e: self.playAudio(), id=self.audioPlayItemId)
        self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
        self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
        self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
        self.videosBox.Bind(wx.EVT_MENU, lambda e: self.directDownload(), id=self.directDownloadId)
        self.videosBox.Bind(wx.EVT_MENU, self.onDownloadChannel, downloadChannelItem)
        self.videosBox.Bind(wx.EVT_MENU, self.onCopy, id=self.copyItemId)
        self.Bind(wx.EVT_MENU, self.onOpenInBrowser, webbrowserItem)

    def valid_selection(self):
        return self.result is not None and self.result.has_results() and self.videosBox.Selection != -1

    def togleControls(self):
        enabled = self.result is not None and self.result.has_results()
        for control in (self.playButton, self.downloadButton):
            control.Enabled = enabled

    def onFavoriteChannel(self, event):
        if not self.result:
            return
        data = {
            "title": self.result.title,
            "display_title": f"{self.result.title}. Channel",
            "url": self.result.channel_url or self.url,
            "live": 0,
            "channel_name": self.result.title,
            "channel_url": self.result.channel_url or self.url,
            "item_type": "channel",
        }
        if self.favCheck.Value:
            self.favorites.add_favorite(data)
            speak("Channel added to favorites")
        else:
            self.favorites.remove_favorite(data["url"])
            speak("Channel removed from favorites")

    def togleFavorite(self):
        if not self.result:
            self.favCheck.SetValue(False)
            return
        self.favCheck.SetValue(self.favorites.exists(self.result.channel_url or self.url))

    def onOpenInBrowser(self, event):
        if self.valid_selection():
            webbrowser.open(self.result.get_url(self.videosBox.Selection))

    def onCopy(self, event):
        if not self.valid_selection():
            return
        pyperclip.copy(self.result.get_url(self.videosBox.Selection))
        wx.MessageBox("Video link copied successfully", "Done", parent=self)

    def playVideo(self):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        url = self.result.get_url(n)
        title = self.result.get_title(n)
        stream = LoadingDialog(self, "Playing video...", get_video_stream, url).res
        gui = MediaGui(self, title, stream, url, True, self.result)
        gui.path = os.path.join(gui.path, self.result.title)
        self.Hide()

    def playAudio(self):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        url = self.result.get_url(n)
        title = self.result.get_title(n)
        stream = LoadingDialog(self, "Playing audio...", get_audio_stream, url).res
        gui = MediaGui(self, title, stream, url, audio_mode=True, results=self.result)
        gui.path = os.path.join(gui.path, self.result.title)
        self.Hide()

    def onListBox(self, event):
        if not self.valid_selection():
            return
        if self.videosBox.Selection == self.videosBox.Count - 1:
            def load():
                try:
                    if self.result.next():
                        wx.CallAfter(self.videosBox.Append, self.result.get_new_titles())
                        speak("More channel videos loaded")
                    else:
                        speak("There are no more videos")
                except Exception:
                    speak("No more videos were loaded")
            Thread(target=load, daemon=True).start()

    def onVideoDownload(self, event):
        self.downloadSelected(0)

    def onM4aDownload(self, event):
        self.downloadSelected(1)

    def onMp3Download(self, event):
        self.downloadSelected(2)

    def downloadSelected(self, option):
        if not self.valid_selection():
            return
        n = self.videosBox.Selection
        title = self.result.get_title(n)
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        fmt, conv = self._format_from_option(option)
        path = os.path.join(config_get("path"), self.result.title)
        downloadAction(self.result.get_url(n), path, dlg, fmt, convert=conv, channel_or_playlist=False)

    def _format_from_option(self, option):
        return format_from_option(option)

    def directDownload(self):
        self.downloadSelected(int(config_get("defaultformat")))

    def onDownload(self, event):
        self.show_video_download_menu()
        self.videosBox.SetFocus()

    def onDownloadChannel(self, event):
        if not self.result:
            return
        self.show_channel_download_menu()
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

    def show_channel_download_menu(self):
        downloadMenu = wx.Menu()
        videoItem = downloadMenu.Append(-1, "Video")
        audioMenu = wx.Menu()
        m4aItem = audioMenu.Append(-1, "m4a")
        mp3Item = audioMenu.Append(-1, "mp3")
        downloadMenu.AppendSubMenu(audioMenu, "Audio")
        self.Bind(wx.EVT_MENU, self.onChannelVideoDownload, videoItem)
        self.Bind(wx.EVT_MENU, self.onChannelM4aDownload, m4aItem)
        self.Bind(wx.EVT_MENU, self.onChannelMp3Download, mp3Item)
        self.downloadChannelButton.PopupMenu(downloadMenu)

    def onChannelVideoDownload(self, event):
        self.downloadChannelSelection(0)

    def onChannelM4aDownload(self, event):
        self.downloadChannelSelection(1)

    def onChannelMp3Download(self, event):
        self.downloadChannelSelection(2)

    def downloadChannelSelection(self, option):
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), self.result.title)
        fmt, conv = self._format_from_option(option)
        downloadAction(self.result.channel_url or self.url, config_get('path'), dlg, fmt, convert=conv, channel_or_playlist=True)

    def back(self):
        self.Parent.Show()
        self.Destroy()

    def onHook(self, event):
        if event.KeyCode in (wx.WXK_ESCAPE, wx.WXK_BACK) and not type(self.FindFocus()) == MediaGui:
            self.back()
        else:
            event.Skip()
