import webbrowser
from threading import Thread
import pyperclip
import wx
from gui.download_progress import DownloadProgress
from gui.search_dialog import SearchDialog
from gui.settings_dialog import SettingsDialog
from gui.playlist_dialog import PlaylistDialog
from gui.channel_dialog import ChannelDialog
from gui.activity_dialog import LoadingDialog

from download_handler.downloader import downloadAction
from media_player.media_gui import MediaGui
from media_player.player import Player
from nvda_client.client import speak
from settings_handler import config_get
from youtube_browser.search_handler import Search
from utiles import direct_download, get_audio_stream, get_video_stream
from database import Favorite, Continue


class YoutubeBrowser(wx.Frame):
    # Normalized strings to 'shorts' across the entire class
    def is_playable_result(self, result_type):
        return result_type in ("video", "shorts", "movie")

    def is_favoritable_result(self, result_type):
        return result_type in ("video", "shorts", "movie", "playlist", "channel")

    def can_direct_download(self, result_type, views):
        if result_type not in ("video", "shorts", "movie", "playlist", "channel"):
            return False
        if result_type == "video" and views is None:
            return False
        return True

    def __init__(self, parent):
        wx.Frame.__init__(self, parent=parent, title=parent.Title)
        self.Centre()
        self.SetSize(wx.DisplaySize())
        self.Maximize(True)
        self.panel = wx.Panel(self)
        lbl = wx.StaticText(self.panel, -1, "Search results: ")
        self.searchResults = wx.ListBox(self.panel, -1)
        self.loadMoreButton = wx.Button(self.panel, -1, "Load more results")
        self.loadMoreButton.Enabled = False
        self.loadMoreButton.Show(not config_get("autoload"))
        self.playButton = wx.Button(self.panel, -1, "Play audio (enter)", name="controls")
        self.downloadButton = wx.Button(self.panel, -1, "Download", name="controls")
        self.favCheck = wx.CheckBox(self.panel, -1, "Favorite")
        searchButton = wx.Button(self.panel, -1, "Search... (ctrl+f)")
        backButton = wx.Button(self.panel, -1, "Back to main window")
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        sizer1.Add(backButton, 1, wx.ALL)
        sizer1.Add(searchButton, 1, wx.ALL)
        sizer2 = wx.BoxSizer(wx.HORIZONTAL)
        for control in self.panel.GetChildren():
            if control.Name == "controls":
                sizer2.Add(control, 1)
        sizer.Add(sizer1, 1, wx.EXPAND)
        sizer.Add(lbl, 1, wx.ALL)
        sizer.Add(self.searchResults, 1, wx.EXPAND)
        sizer.Add(self.loadMoreButton, 1)
        sizer.Add(sizer2, 1)
        self.panel.SetSizer(sizer)
        
        self._suppress_autoplay = False
        self._loading_more = False
        self._mouse_selecting = False
        self._current_fav_url = None # Used to track current active selection and prevent thread race conditions
        
        self.contextSetup()
        results_shortcuts = wx.AcceleratorTable([
            (0, wx.WXK_RETURN, self.videoPlayItemId),
            (wx.ACCEL_CTRL, wx.WXK_RETURN, self.audioPlayItemId)
        ])
        self.searchResults.SetAcceleratorTable(results_shortcuts)
        menuBar = wx.MenuBar()
        optionsMenu = wx.Menu()
        settingsItem = optionsMenu.Append(-1, "Settings...\talt+s")
        hotKeys = wx.AcceleratorTable([
            (wx.ACCEL_ALT, ord("S"), settingsItem.GetId()),
            (wx.ACCEL_CTRL, ord("F"), searchButton.GetId()),
            (wx.ACCEL_CTRL, ord("D"), self.directDownloadId),
            (wx.ACCEL_CTRL, ord("L"), self.copyItemId)
        ])
        self.SetAcceleratorTable(hotKeys)
        menuBar.Append(optionsMenu, "Options")
        self.SetMenuBar(menuBar)
        
        self.Bind(wx.EVT_MENU, lambda event: SettingsDialog(self), settingsItem)
        self.loadMoreButton.Bind(wx.EVT_BUTTON, self.onLoadMore)
        self.playButton.Bind(wx.EVT_BUTTON, self.onPlayButton)
        self.downloadButton.Bind(wx.EVT_BUTTON, self.onDownload)
        self.favCheck.Bind(wx.EVT_CHECKBOX, self.onFavorite)
        searchButton.Bind(wx.EVT_BUTTON, self.onSearch)
        backButton.Bind(wx.EVT_BUTTON, lambda event: self.backAction())
        self.Bind(wx.EVT_CHAR_HOOK, self.onHook)

        self.searchResults.Bind(wx.EVT_LISTBOX, self.onListBox)
        self.searchResults.Bind(wx.EVT_LEFT_DOWN, self.onListMouseDown)
        self.searchResults.Bind(wx.EVT_LEFT_UP, self.onListMouseUp)
        self.Bind(wx.EVT_SHOW, self.onShow)
        self.Bind(wx.EVT_CLOSE, lambda event: wx.Exit())
        
        if self.searchAction():
            self.Show()
            self.Parent.Hide()
        else:
            self.Destroy()
        self.favorites = Favorite()
        self.toggleFavorite()

    def searchAction(self, value=""):
        dialog = SearchDialog(self, value=value)
        query = dialog.query
        filter = dialog.filter

        if query is None:
            self.toggleControls()
            return False

        loading = LoadingDialog(self, "Searching", Search, query, filter)

        if loading.error:
            wx.MessageBox(f"Search could not be completed.\n\n{loading.error}", "Error", style=wx.OK | wx.ICON_ERROR)
            return False

        if not loading.res:
            wx.MessageBox("No search results were returned.", "Error", style=wx.OK | wx.ICON_ERROR)
            return False

        self.search = loading.res

        try:
            titles = self.search.get_titles()
        except Exception as e:
            wx.MessageBox(f"Failed to load titles.\n\n{e}", "Error", style=wx.OK | wx.ICON_ERROR)
            return False

        self._suppress_autoplay = True
        self.searchResults.Set(titles)
        self.SetTitle(query)
        self.toggleControls()

        try:
            if titles:
                self.searchResults.SetSelection(0)
        except Exception:
            pass

        self._suppress_autoplay = False
        self.searchResults.SetFocus()
        self.toggleDownload()
        self.togglePlay()
        return True

    def onSearch(self, event):
        if hasattr(self, "search"):
            self.searchAction(self.search.query)
        else:
            self.searchAction()

    def playVideo(self):
        number = self.searchResults.Selection
        if number == -1:
            return
        result_type = self.search.get_type(number)
        if result_type == "playlist":
            views = self.search.get_views(number)
            elements = self.search.get_elements(number)
            PlaylistDialog(self, self.search.get_url(number), views=views, elements=elements)
            return
        if result_type == "channel":
            subscribers = self.search.get_subscribers(number)
            elements = self.search.get_elements(number)
            ChannelDialog(self, self.search.get_url(number), subscribers=subscribers, elements=elements)
            return
        if not self.is_playable_result(result_type):
            return
        title = self.search.get_title(number)
        url = self.search.get_url(number)
        stream = LoadingDialog(self, "Playing video", get_video_stream, url).res
        gui = MediaGui(self, title, stream, url, self.can_direct_download(result_type, self.search.get_views(number)), results=self.search)
        self.Hide()

    def playAudio(self):
        number = self.searchResults.Selection
        if number == -1:
            return
        result_type = self.search.get_type(number)
        if not self.is_playable_result(result_type):
            return
        title = self.search.get_title(number)
        url = self.search.get_url(number)
        stream = LoadingDialog(self, "Playing audio", get_audio_stream, url).res
        gui = MediaGui(self, title, stream, url, results=self.search, audio_mode=True)
        self.Hide()

    def onListMouseDown(self, event):
        self._mouse_selecting = True
        event.Skip()

    def onListMouseUp(self, event):
        event.Skip()
        if not hasattr(self, "search"):
            self._mouse_selecting = False
            return
        wx.CallAfter(self.playSelectedVideoFromClick)

    def playSelectedVideoFromClick(self):
        try:
            n = self.searchResults.Selection
            if self._mouse_selecting and n != -1 and self.is_playable_result(self.search.get_type(n)):
                self.playVideo()
        finally:
            self._mouse_selecting = False

    def onHook(self, event):
        if not hasattr(self, "search"):
            event.Skip()
            return
        n = self.searchResults.Selection
        if event.KeyCode == wx.WXK_SPACE and n != -1 and self.is_favoritable_result(self.search.get_type(n)) and self.FindFocus() == self.searchResults:
            self.favCheck.Value = not self.favCheck.Value
            self.onFavorite(None)
        elif event.KeyCode == wx.WXK_BACK and not isinstance(self.FindFocus(), MediaGui):
            self.backAction()
        else:
            event.Skip()

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
            if self.has_real_results():
                self.searchResults.PopupMenu(self.contextMenu)
                
        self.searchResults.Bind(wx.EVT_MENU, lambda event: self.playVideo(), id=self.videoPlayItemId)
        self.searchResults.Bind(wx.EVT_MENU, lambda event: self.playAudio(), id=self.audioPlayItemId)
        self.searchResults.Bind(wx.EVT_MENU, self.onOpenChannel, openChannelItem)
        self.searchResults.Bind(wx.EVT_MENU, self.onDownloadChannel, downloadChannelItem)
        self.Bind(wx.EVT_MENU, self.onCopy, copyItem)
        self.Bind(wx.EVT_MENU, self.onOpenInBrowser, webbrowserItem)
        self.searchResults.Bind(wx.EVT_CONTEXT_MENU, lambda event: popup())
        self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
        self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
        self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
        self.Bind(wx.EVT_MENU, lambda event: self.directDownload(), directDownloadItem)

    def show_download_menu(self):
        if not hasattr(self, "search") or self.searchResults.Selection == -1:
            return
        menu = wx.Menu()
        result_type = self.search.get_type(self.searchResults.Selection)
        if result_type == "channel":
            videoItem = menu.Append(-1, "Video")
            audioMenu = wx.Menu()
            m4aItem = audioMenu.Append(-1, "m4a")
            mp3Item = audioMenu.Append(-1, "mp3")
            menu.AppendSubMenu(audioMenu, "Audio")
            self.Bind(wx.EVT_MENU, self.onChannelVideoDownload, videoItem)
            self.Bind(wx.EVT_MENU, self.onChannelM4aDownload, m4aItem)
            self.Bind(wx.EVT_MENU, self.onChannelMp3Download, mp3Item)
        else:
            videoItem = menu.Append(-1, "Video")
            audioMenu = wx.Menu()
            m4aItem = audioMenu.Append(-1, "m4a")
            mp3Item = audioMenu.Append(-1, "mp3")
            menu.AppendSubMenu(audioMenu, "Audio")
            self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
            self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
            self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
        self.downloadButton.PopupMenu(menu)
        self.downloadButton.SetFocus()

    def onOpenChannel(self, event):
        n = self.searchResults.Selection
        if n == -1 or not hasattr(self, "search"):
            return
        result_type = self.search.get_type(n)
        url = self.search.get_url(n) if result_type == "channel" else self.search.get_channel(n)["url"]
        if url:
            ChannelDialog(self, url)

    def onDownloadChannel(self, event):
        n = self.searchResults.Selection
        if n == -1 or not hasattr(self, "search"):
            return
        if self.search.get_type(n) == "channel":
            title = self.search.get_title(n)
            url = self.search.get_url(n)
        else:
            channel = self.search.get_channel(n)
            title = channel["name"]
            url = channel["url"]
        if not url:
            return
        self.download_channel_url(url, title, int(config_get('defaultformat')))

    def download_channel_url(self, url, title, option):
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        direct_download(option, url, dlg, "channel")

    def onOpenInBrowser(self, event):
        number = self.searchResults.Selection
        if number == -1 or not hasattr(self, "search"):
            return
        url = self.search.get_url(number)
        webbrowser.open(url)

    def onDownload(self, event):
        self.show_download_menu()

    def onM4aDownload(self, event):
        if self.searchResults.Selection == -1 or not hasattr(self, "search"):
            return
        url = self.search.get_url(self.searchResults.Selection)
        title = self.search.get_title(self.searchResults.Selection)
        download_type = self.search.get_type(self.searchResults.Selection)
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        direct_download(1, url, dlg, download_type)

    def onMp3Download(self, event):
        if self.searchResults.Selection == -1 or not hasattr(self, "search"):
            return
        url = self.search.get_url(self.searchResults.Selection)
        title = self.search.get_title(self.searchResults.Selection)
        download_type = self.search.get_type(self.searchResults.Selection)
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        direct_download(2, url, dlg, download_type)

    def onVideoDownload(self, event):
        if self.searchResults.Selection == -1 or not hasattr(self, "search"):
            return
        url = self.search.get_url(self.searchResults.Selection)
        title = self.search.get_title(self.searchResults.Selection)
        download_type = self.search.get_type(self.searchResults.Selection)
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        direct_download(0, url, dlg, download_type)

    def onChannelVideoDownload(self, event):
        n = self.searchResults.Selection
        if n == -1 or not hasattr(self, "search"):
            return
        url = self.search.get_url(n) if self.search.get_type(n) == "channel" else self.search.get_channel(n)["url"]
        title = self.search.get_title(n) if self.search.get_type(n) == "channel" else self.search.get_channel(n)["name"]
        if url:
            self.download_channel_url(url, title, 0)

    def onChannelM4aDownload(self, event):
        n = self.searchResults.Selection
        if n == -1 or not hasattr(self, "search"):
            return
        url = self.search.get_url(n) if self.search.get_type(n) == "channel" else self.search.get_channel(n)["url"]
        title = self.search.get_title(n) if self.search.get_type(n) == "channel" else self.search.get_channel(n)["name"]
        if url:
            self.download_channel_url(url, title, 1)

    def onChannelMp3Download(self, event):
        n = self.searchResults.Selection
        if n == -1 or not hasattr(self, "search"):
            return
        url = self.search.get_url(n) if self.search.get_type(n) == "channel" else self.search.get_channel(n)["url"]
        title = self.search.get_title(n) if self.search.get_type(n) == "channel" else self.search.get_channel(n)["name"]
        if not url:
            return
        self.download_channel_url(url, title, 2)

    def onCopy(self, event):
        if self.searchResults.Selection == -1 or not hasattr(self, "search"):
            return
        pyperclip.copy(self.search.get_url(self.searchResults.Selection))
        wx.MessageBox("Video link copied successfully", "Done", parent=self)

    def loadMore(self):
        if self.searchResults.Strings == [] or not self.has_real_results():
            return
        if self._loading_more:
            return
        self._loading_more = True
        try:
            speak("Loading more results")
            try:
                ok = self.search.load_more()
            except Exception:
                ok = None
            if ok is None:
                speak("The app could not load more results")
                return
            new_titles = self.search.get_last_titles()
            if not new_titles:
                return
            self._suppress_autoplay = True
            wx.CallAfter(self.searchResults.Append, new_titles)
            speak("More search results loaded")
            wx.CallAfter(self.searchResults.SetFocus)
        finally:
            self._suppress_autoplay = False
            self._loading_more = False

    def onListBox(self, event):
        self.toggleDownload()
        self.togglePlay()
        self.toggleFavorite()
        if not self.has_real_results():
            self.loadMoreButton.Enabled = False
            return
        if self._mouse_selecting:
            return
        if self.searchResults.Selection == len(self.searchResults.Strings)-1:
            if not config_get("autoload"):
                self.loadMoreButton.Enabled = True
                return
            Thread(target=self.loadMore, daemon=True).start()
        else:
            self.loadMoreButton.Enabled = False

    def onLoadMore(self, event):
        if self._loading_more:
            return
        Thread(target=self.loadMore, daemon=True).start()

    def backAction(self):
        self.Destroy()
        self.Parent.Show()

    def has_real_results(self):
        return hasattr(self, "search") and self.search.has_results()

    def toggleControls(self):
        if not self.has_real_results():
            for control in self.panel.GetChildren():
                if control.Name == "controls":
                    control.Hide()
            self.loadMoreButton.Hide()
        else:
            for control in self.panel.GetChildren():
                if control.Name == "controls":
                    control.Show()
            self.loadMoreButton.Show(not config_get("autoload"))

    def toggleDownload(self):
        n = self.searchResults.Selection
        if n == -1 or not self.has_real_results():
            self.contextMenu.Enable(self.downloadId, False)
            self.contextMenu.Enable(self.directDownloadId, False)
            self.downloadButton.Enabled = False
            return
        result_type = self.search.get_type(n)
        if not self.can_direct_download(result_type, self.search.get_views(n)):
            self.contextMenu.Enable(self.downloadId, False)
            self.contextMenu.Enable(self.directDownloadId, False)
            self.downloadButton.Enabled = False
            return
        self.contextMenu.Enable(self.downloadId, True)
        self.contextMenu.Enable(self.directDownloadId, True)
        self.downloadButton.Enabled = True
        self.downloadButton.Label = "Download channel" if result_type == "channel" else "Download playlist" if result_type == "playlist" else "Download"

    def togglePlay(self):
        n = self.searchResults.Selection
        contextMenuIds = (self.videoPlayItemId, self.audioPlayItemId)
        if n == -1 or not self.has_real_results():
            self.playButton.Label = "Play audio (enter)"
            self.playButton.Enabled = False
            for i in contextMenuIds:
                self.contextMenu.Enable(i, False)
            return
        result_type = self.search.get_type(n)
        if result_type == "playlist":
            self.playButton.Label = "Open playlist"
            self.playButton.Enabled = True
            for i in contextMenuIds:
                self.contextMenu.Enable(i, False)
            return
        if result_type == "channel":
            self.playButton.Label = "Open channel"
            self.playButton.Enabled = True
            for i in contextMenuIds:
                self.contextMenu.Enable(i, False)
            return
        if not self.is_playable_result(result_type):
            self.playButton.Label = "Play audio (enter)"
            self.playButton.Enabled = False
            for i in contextMenuIds:
                self.contextMenu.Enable(i, False)
            return
        self.playButton.Label = "Play audio (enter)"
        self.playButton.Enabled = True
        for i in contextMenuIds:
            self.contextMenu.Enable(i, True)

    def onFavorite(self, event):
        n = self.searchResults.Selection
        if n == -1 or not self.has_real_results():
            return
        result_type = self.search.get_type(n)
        if not self.is_favoritable_result(result_type):
            return
        url = self.search.get_url(n)
        if self.favCheck.Value:
            title = self.search.get_title(n)
            # Safe attribute checking order for channels vs playlists/videos
            if result_type == "channel":
                channel_name = title
                channel_url = url
                display_title = f"{title}. Channel"
            else:
                channel_data = self.search.get_channel(n)
                channel_name = channel_data['name']
                channel_url = channel_data['url']
                if result_type == "playlist":
                    display_title = f"{title}. Playlist. By {channel_name}"
                else:
                    display_title = f"{title}. {channel_name}"
            
            live = 1 if not self.search.get_views(n) else 0
            data = {"title": title, "display_title": display_title, "url": url, "live": live, "channel_url": channel_url, "channel_name": channel_name, "item_type": result_type}
            self.favorites.add_favorite(data)
            speak("Added to favorites")
        else:
            self.favorites.remove_favorite(url)
            speak("Removed from favorites")

    def toggleFavorite(self):
        n = self.searchResults.Selection
        if n == -1 or not self.has_real_results():
            self.favCheck.Enabled = False
            self.favCheck.SetValue(False)
            self._current_fav_url = None
            return
        result_type = self.search.get_type(n)
        labels = {
            "video": "Favorite video",
            "shorts": "Favorite short",
            "movie": "Favorite movie",
            "playlist": "Favorite playlist",
            "channel": "Favorite channel",
        }
        self.favCheck.Label = labels.get(result_type, "Favorite")
        self.favCheck.Enabled = self.is_favoritable_result(result_type)
        if not self.favCheck.Enabled:
            self.favCheck.SetValue(False)
            self._current_fav_url = None
            return
        
        url = self.search.get_url(n)
        self._current_fav_url = url  # Tag current active target
        
        def check_url(target_url):
            exists = self.favorites.exists(target_url)
            # Only update UI if the user hasn't scrolled to a different item
            if self._current_fav_url == target_url:
                wx.CallAfter(self.favCheck.SetValue, exists)
                
        Thread(target=check_url, args=[url], daemon=True).start()

    def directDownload(self):
        n = self.searchResults.Selection
        if n == -1 or not self.has_real_results():
            return
        result_type = self.search.get_type(n)
        if not self.can_direct_download(result_type, self.search.get_views(n)):
            return
        url = self.search.get_url(n)
        title = self.search.get_title(n)
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), title)
        direct_download(int(config_get('defaultformat')), url, dlg, result_type)

    def onShow(self, event):
        self.searchResults.SetFocus()

    def onPlayButton(self, event):
        n = self.searchResults.Selection
        if n == -1:
            return
        result_type = self.search.get_type(n)
        if result_type == "playlist":
            views = self.search.get_views(n)
            elements = self.search.get_elements(n)
            PlaylistDialog(self, self.search.get_url(n), views=views, elements=elements)
            return
        if result_type == "channel":
            subscribers = self.search.get_subscribers(n)
            elements = self.search.get_elements(n)
            ChannelDialog(self, self.search.get_url(n), subscribers=subscribers, elements=elements)
            return
        if not self.is_playable_result(result_type):
            return
        self.playAudio()
