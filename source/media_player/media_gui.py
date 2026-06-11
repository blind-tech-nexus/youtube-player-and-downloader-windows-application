import webbrowser
import pyperclip
import wx
import wx.adv
import wx.lib.agw.toasterbox as TB
from threading import Thread
import application
from settings_handler import config_get, config_set
from database import Continue


def has_player(method):
    def rapper(self, *args):
        if self.player is not None:
            method(self, *args)
    return rapper


class MediaGui(wx.Frame):

    def __init__(self, parent, title, stream, url, can_download=True, results=None, audio_mode=False):
        wx.Frame.__init__(self, parent, title=f'{title} - {application.name}')
        self.title = title
        self.stream = not can_download
        self.seek = int(config_get("seek"))
        self.results = results
        self.audio_mode = audio_mode
        self.path = config_get('path')
        self.Centre()
        self.SetSize(wx.DisplaySize())
        self.Maximize(True)
        self.SetBackgroundColour(wx.BLACK)
        self.player = None
        self._closing = False
        self.url = url
        from gui.custom_controls import CustomButton
        previousButton = CustomButton(self, -1, "Previous track", name="controls")
        previousButton.Show() if self.results is not None else previousButton.Hide()
        beginingButton = CustomButton(self, -1, "Start of track", name="controls")
        rewindButton = CustomButton(self, -1, "Rewind <", name="controls")
        playButton = CustomButton(self, -1, "Play/Pause", name="controls")
        forwardButton = CustomButton(self, -1, "Forward >", name="controls")
        nextButton = CustomButton(self, -1, "Next track", name="controls")
        nextButton.Show() if self.results is not None else nextButton.Hide()
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer1 = wx.BoxSizer(wx.HORIZONTAL)
        for control in self.GetChildren():
            if control.Name == "controls":
                sizer1.Add(control, 1)
        sizer.AddStretchSpacer()
        sizer.Add(sizer1)
        self.SetSizer(sizer)
        menuBar = wx.MenuBar()
        trackOptions = wx.Menu()
        downloadMenu = wx.Menu()
        videoItem = downloadMenu.Append(-1, "Video")
        audioMenu = wx.Menu()
        m4aItem = audioMenu.Append(-1, "m4a")
        mp3Item = audioMenu.Append(-1, "mp3")
        downloadMenu.AppendSubMenu(audioMenu, "Audio")
        downloadId = trackOptions.AppendSubMenu(downloadMenu, "Download").GetId()
        trackOptions.Enable(downloadId, can_download)
        directDownloadItem = trackOptions.Append(-1, "Direct download...\tctrl+d")
        directDownloadItem.Enable(can_download)
        descriptionItem = trackOptions.Append(-1, "Video description\tctrl+shift+d")
        copyItem = trackOptions.Append(-1, "Copy Video link\tctrl+l")
        browserItem = trackOptions.Append(-1, "Open in web browser\tctrl+b")
        settingsItem = trackOptions.Append(-1, "Settings...\talt+s")
        hotKeys = wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("D"), directDownloadItem.GetId()),
            (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("D"), descriptionItem.GetId()),
            (wx.ACCEL_CTRL, ord("L"), copyItem.GetId()),
            (wx.ACCEL_CTRL, ord("B"), browserItem.GetId()),
            (wx.ACCEL_ALT, ord("S"), settingsItem.GetId()),
        ])
        self.SetAcceleratorTable(hotKeys)
        menuBar.Append(trackOptions, "Track options")
        self.SetMenuBar(menuBar)
        self.Bind(wx.EVT_MENU, self.onVideoDownload, videoItem)
        self.Bind(wx.EVT_MENU, self.onM4aDownload, m4aItem)
        self.Bind(wx.EVT_MENU, self.onMp3Download, mp3Item)
        self.Bind(wx.EVT_MENU, self.onDirect, directDownloadItem)
        self.Bind(wx.EVT_MENU, self.onDescription, descriptionItem)
        self.Bind(wx.EVT_MENU, self.onCopy, copyItem)
        self.Bind(wx.EVT_MENU, self.onBrowser, browserItem)
        self.Bind(wx.EVT_MENU, lambda event: SettingsDialog(self), settingsItem)
        self.Bind(wx.EVT_KEY_DOWN, self.onKeyDown)
        self.prev_id = 100
        self.play_pause_id = 150
        self.next_id = 200
        self.registerHotKey()
        for hot_id in [self.prev_id, self.play_pause_id, self.next_id]:
            self.Bind(wx.EVT_HOTKEY, self.onHot, id=hot_id)
        for control in self.GetChildren():
            control.Bind(wx.EVT_KEY_DOWN, self.onKeyDown)
        previousButton.Bind(wx.EVT_BUTTON, lambda event: self.previous())
        beginingButton.Bind(wx.EVT_BUTTON, lambda event: self.beginingAction())
        rewindButton.Bind(wx.EVT_BUTTON, lambda event: self.rewindAction())
        playButton.Bind(wx.EVT_BUTTON, lambda event: self.playAction())
        forwardButton.Bind(wx.EVT_BUTTON, lambda event: self.forwardAction())
        nextButton.Bind(wx.EVT_BUTTON, lambda event: self.next())
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Show()
        self.SetFocus()
        self._start_playback(stream, url)

    def _start_playback(self, stream, url):
        from media_player.player import Player
        try:
            player = Player(stream["url"], self.GetHandle(), self)
        except Exception as e:
            wx.MessageBox(
                f"Failed to initialize player:\n{e}",
                "Player Error",
                wx.ICON_ERROR,
                self,
            )
            return
        self.player = player
        if config_get("continue"):
            try:
                saved = Continue.get_all()
                self.player.resume_from(saved.get(url))
            except Exception:
                pass
        self.player.start()
        Thread(target=self.extract_description, daemon=True).start()

    @has_player
    def playAction(self):
        import vlc
        state = self.player.media.get_state()
        if state in (vlc.State.NothingSpecial, vlc.State.Stopped, vlc.State.Ended):
            self.player.media.play()
        elif state in (vlc.State.Playing, vlc.State.Paused, vlc.State.Buffering, vlc.State.Opening):
            if not self.stream:
                self.player.media.pause()
            else:
                self.player.stop_async()

    @has_player
    def forwardAction(self):
        position = self.player.media.get_position()
        self.player.media.set_position(position + self.player.seek(self.seek))

    @has_player
    def rewindAction(self):
        position = self.player.media.get_position()
        self.player.media.set_position(position - self.player.seek(self.seek))

    @has_player
    def set_position(self, key):
        step = int(chr(key)) / 10
        self.player.media.set_position(step)
        from nvda_client.client import speak
        speak("Elapsed time: {}".format(self.player.get_elapsed()))

    @has_player
    def beginingAction(self):
        import vlc
        self.player.media.set_position(0.0)
        from nvda_client.client import speak
        speak("Start of track")
        if self.player.media.get_state() in (vlc.State.NothingSpecial, vlc.State.Stopped, vlc.State.Ended):
            self.player.media.play()

    def closeAction(self):
        if self._closing:
            return
        self._closing = True
        if self.player is not None:
            try:
                position = self.player.media.get_position()
                saved = Continue.get_all()
                if position in (0.0, -1) and self.url in saved:
                    Continue.remove_continue(self.url)
                elif self.url in saved:
                    Continue.update(self.url, position)
                else:
                    Continue.new_continue(self.url, position)
            except Exception:
                pass
            self.player.close()
            self.player = None
        try:
            self.UnregisterHotKey(self.prev_id)
            self.UnregisterHotKey(self.play_pause_id)
            self.UnregisterHotKey(self.next_id)
        except Exception:
            pass
        if self.GetParent():
            self.GetParent().Show()
            self.GetParent().SetFocus()
        self.Destroy()

    def onClose(self, event):
        self.closeAction()

    def show_toast(self, title, message):
        try:
            tb = TB.ToasterBox(self, tbstyle=TB.TB_SIMPLE)
            tb.SetPopupSize((300, 80))
            tb.SetPopupPauseTime(3000)
            tb.SetPopupText(f"{title}\n{message}")
            tb.Play()
        except Exception:
            wx.CallAfter(wx.MessageBox, message, title, parent=self)

    def speak_time(self, label, value):
        from nvda_client.client import speak
        if not value:
            value = "unknown"
        message = f"{label}: {value}"
        speak(message)
        self.show_toast(label, message)

    def registerHotKey(self):
        self.RegisterHotKey(
            self.prev_id,
            0, wx.WXK_MEDIA_PREV_TRACK)
        self.RegisterHotKey(
            self.play_pause_id,
            0, wx.WXK_MEDIA_PLAY_PAUSE)
        self.RegisterHotKey(
            self.next_id,
            0, wx.WXK_MEDIA_NEXT_TRACK)

    def onHot(self, event):
        if event.Id == self.prev_id:
            self.previous()
        elif event.Id == self.play_pause_id:
            self.playAction()
        elif event.Id == self.next_id:
            self.next()

    def onKeyDown(self, event):
        from nvda_client.client import speak

        event.Skip()
        if event.GetKeyCode() in (wx.WXK_SPACE, wx.WXK_PAUSE):
            self.playAction()
        elif event.GetKeyCode() == wx.WXK_RIGHT and not event.HasAnyModifiers():
            self.forwardAction()
        elif event.GetKeyCode() == wx.WXK_LEFT and not event.HasAnyModifiers():
            self.rewindAction()
        elif event.controlDown and event.KeyCode == wx.WXK_RIGHT:
            self.next()
        elif event.controlDown and event.KeyCode == wx.WXK_LEFT:
            self.previous()
        elif event.GetKeyCode() == wx.WXK_UP:
            self.increase_volume()
        elif event.GetKeyCode() == wx.WXK_DOWN:
            self.decrease_volume()
        elif event.GetKeyCode() == wx.WXK_HOME:
            self.beginingAction()
        elif event.KeyCode in range(49, 58):
            self.set_position(event.KeyCode)
        elif event.controlDown and event.shiftDown and event.KeyCode == ord("L"):
            self.get_duration()
        elif event.controlDown and event.shiftDown and event.KeyCode == ord("T"):
            if self.player is not None:
                speak("Elapsed time: {}".format(self.player.get_elapsed()))
        elif event.KeyCode == ord("C"):
            if self.player is not None:
                self.speak_time("Current time", self.player.get_elapsed())
        elif event.KeyCode == ord("R") and not event.HasAnyModifiers():
            if self.player is not None:
                self.speak_time("Remaining time", self.player.get_remaining())
        elif event.KeyCode == ord("S"):
            if self.player is not None:
                self.player.media.set_rate(1.4)
                speak("Fast")
        elif event.KeyCode == ord("D"):
            if self.player is not None:
                self.player.media.set_rate(1.0)
                speak("Normal")
        elif event.KeyCode == ord("F"):
            if self.player is not None:
                self.player.media.set_rate(0.6)
                speak("Slow")
        elif event.GetKeyCode() in (ord("-"), wx.WXK_NUMPAD_SUBTRACT):
            self.seek -= 1
            if self.seek < 1:
                self.seek = 1
            speak("{} {} {}".format("Seek", self.seek, "seconds"))
            config_set("seek", self.seek)
        elif event.GetKeyCode() in (ord("="), wx.WXK_NUMPAD_ADD):
            self.seek += 1
            if self.seek > 30:
                self.seek = 30
            speak("{} {} {}".format("Seek", self.seek, "seconds"))
            config_set("seek", self.seek)
        elif event.KeyCode == ord("R"):
            if config_get("repeatetracks"):
                config_set("repeatetracks", False)
                speak("Repeat off")
            else:
                config_set("repeatetracks", True)
                speak("Repeat on")
                config_set("autonext", False)
        elif event.KeyCode == ord("N"):
            if config_get("autonext"):
                config_set("autonext", False)
                speak("Auto play next off")
            else:
                config_set("autonext", True)
                speak("Auto play next on")
                config_set("repeatetracks", False)
        elif event.KeyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            if not self.audio_mode:
                self.togleFullScreen()
        elif event.KeyCode == wx.WXK_ALT:
            if self.IsFullScreen():
                self.ShowFullScreen(False)
        elif event.GetKeyCode() in (wx.WXK_ESCAPE, wx.WXK_BACK):
            self.closeAction()

    @has_player
    def get_duration(self):
        from nvda_client.client import speak
        speak("Duration: {}".format(self.player.get_duration()))

    @has_player
    def increase_volume(self):
        from nvda_client.client import speak
        self.player.volume = self.player.volume + 5 if self.player.volume < 350 else 350
        self.player.media.audio_set_volume(self.player.volume)
        speak(f"{self.player.volume}%")
        config_set("volume", self.player.volume)

    @has_player
    def decrease_volume(self):
        from nvda_client.client import speak
        self.player.volume = self.player.volume - 5 if self.player.volume > 0 else 0
        self.player.media.audio_set_volume(self.player.volume)
        speak(f"{self.player.volume}%")
        config_set("volume", self.player.volume)

    def togleFullScreen(self):
        from nvda_client.client import speak
        self.ShowFullScreen(not self.IsFullScreen())
        if self.IsFullScreen():
            speak("Full screen on")
        else:
            speak("Full screen off")

    def changeTrack(self, index):
        from nvda_client.client import speak
        from utiles import get_video_stream, get_audio_stream
        from gui.activity_dialog import AsyncLoadingDialog
        if not isinstance(self.results, list):
            url = self.results.get_url(index)
            title = self.results.get_title(index)
        else:
            url = self.results[index]["url"]
            title = self.results[index]["title"]
        if self.player is not None:
            self.player.stop_async()
        if hasattr(self, "description"):
            del self.description

        fetch_fn = get_audio_stream if self.audio_mode else get_video_stream
        label = "Playing audio..." if self.audio_mode else "Playing video..."

        def apply_stream(stream):
            if self._closing:
                return
            self.url = url
            self.title = title
            self.SetTitle(f"{title} - {application.name}")
            if self.player is None:
                self._start_playback(stream, url)
                return
            self.player.play_url(stream["url"])
            Thread(target=self.extract_description, daemon=True).start()

        def on_error(e):
            speak("The app could not fetch the streaming URL")

        AsyncLoadingDialog(self, label, fetch_fn, apply_stream, url, on_error=on_error)

    def next(self):
        from nvda_client.client import speak
        if self.results is None:
            return
        if hasattr(self.Parent, 'searchResults'):
            self.Parent.searchResults.Selection += 1
            index = self.Parent.searchResults.Selection
        elif hasattr(self.Parent, 'videosBox'):
            self.Parent.videosBox.Selection += 1
            index = self.Parent.videosBox.Selection
        else:
            self.Parent.favList.Selection += 1
            index = self.Parent.favList.Selection
            if index < len(self.results):
                self.changeTrack(index)
            return
        self.changeTrack(index)
        if index >= self.results.count - 2:
            def load_more():
                if hasattr(self.Parent, 'searchResults'):
                    if self.results.load_more():
                        wx.CallAfter(self.Parent.searchResults.AppendItems, self.results.get_last_titles())
                else:
                    if self.results.next():
                        wx.CallAfter(self.Parent.videosBox.AppendItems, self.results.get_new_titles())
            Thread(target=load_more, daemon=True).start()

    def previous(self):
        if self.results is None:
            return
        if hasattr(self.Parent, 'searchResults'):
            videosBox = self.Parent.searchResults
        elif hasattr(self.Parent, 'videosBox'):
            videosBox = self.Parent.videosBox
        else:
            videosBox = self.Parent.favList

        if not videosBox.Selection == 0:
            videosBox.Selection -= 1
            index = videosBox.Selection
            self.changeTrack(index)

    def onCopy(self, event):
        pyperclip.copy(self.url)
        wx.MessageBox("Video link copied successfully", "Done", parent=self)

    def onBrowser(self, event):
        from nvda_client.client import speak
        speak("Opening")
        webbrowser.open(self.url)

    def execute_download(self, d_format, convert=False):
        from gui.download_progress import DownloadProgress
        from download_handler.downloader import downloadAction
        dlg = DownloadProgress(wx.GetApp().GetTopWindow(), self.title)
        downloadAction(
            url=self.url,
            path=self.path,
            dlg=dlg,
            downloading_format=d_format,
            convert=convert,
            channel_or_playlist=False
        )

    def onM4aDownload(self, event):
        from download_handler.formats import AUDIO_M4A_FORMAT
        self.execute_download(AUDIO_M4A_FORMAT, convert=False)

    def onMp3Download(self, event):
        from download_handler.formats import AUDIO_DOWNLOAD_FORMAT
        self.execute_download(AUDIO_DOWNLOAD_FORMAT, convert=True)

    def onVideoDownload(self, event):
        from download_handler.formats import VIDEO_DOWNLOAD_FORMAT
        self.execute_download(VIDEO_DOWNLOAD_FORMAT, convert=False)

    def onDirect(self, event):
        from download_handler.formats import AUDIO_M4A_FORMAT, AUDIO_DOWNLOAD_FORMAT, VIDEO_DOWNLOAD_FORMAT
        def_format = int(config_get('defaultformat'))
        if def_format == 1:
            self.execute_download(AUDIO_M4A_FORMAT, convert=False)
        elif def_format == 2:
            self.execute_download(AUDIO_DOWNLOAD_FORMAT, convert=True)
        else:
            self.execute_download(VIDEO_DOWNLOAD_FORMAT, convert=False)

    def onDescription(self, event):
        from nvda_client.client import speak
        from gui.description import DescriptionDialog
        if hasattr(self, "description"):
            DescriptionDialog(self, self.description)
            return

        def extract_description():
            try:
                speak("Fetching video description")
                from youtubesearchpython import Video
                info = Video.getInfo(self.url)
            except Exception as e:
                print(e)
                speak("An error prevented the video description from being fetched")
                return
            self.description = info['description']
            wx.CallAfter(DescriptionDialog, self, self.description)
        Thread(target=extract_description, daemon=True).start()

    def extract_description(self):
        try:
            from youtubesearchpython import Video
            info = Video.get(self.url)
        except Exception:
            return
        self.description = info['description']
