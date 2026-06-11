import wx

class DownloadProgress(wx.Frame):
    def __init__(self, parent, title=""):
        wx.Frame.__init__(self, parent=parent, style=wx.DEFAULT_FRAME_STYLE & ~wx.MAXIMIZE_BOX & ~wx.RESIZE_BORDER)
        self.Title = "Downloading - {}".format(title if title != "" else "YouTube player and downloader")
        self.downloader = None
        self.is_completed = False
        self.is_closing = False
        self.cancel_requested = False
        self.success_timer = None
        
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.lbl_status = wx.StaticText(panel, label="Initializing...")
        font = self.lbl_status.GetFont()
        font.MakeBold()
        self.lbl_status.SetFont(font)
        
        self.gaugeProgress = wx.Gauge(panel, range=100, size=(350, 20))
        
        self.list_box = wx.ListBox(panel, size=(350, 110), choices=[
            "Download progress: 0%",
            "Total file size: --",
            "Downloaded file size: --",
            "Remaining file size: --",
            "Downloading speed: --"
        ])
        self.list_box.SetSelection(0)
        self.list_box.SetFocus()
        
        self.btnStop = wx.Button(panel, label="Stop Downloading")
        self.btnStop.Bind(wx.EVT_BUTTON, self.onStopClick)
        
        main_sizer.Add(self.lbl_status, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 15)
        main_sizer.Add(self.gaugeProgress, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        main_sizer.Add(self.list_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        main_sizer.Add(self.btnStop, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 10)
        
        panel.SetSizer(main_sizer)
        main_sizer.Fit(self)
        self.Centre()
        
        self.Bind(wx.EVT_CLOSE, self.onClose)

    def update_stats(self, percent, total, downloaded, remaining, speed):
        if self.is_closing:
            return
        if self.list_box.GetCount() == 5:
            self.list_box.SetString(0, "Download progress: {}%".format(percent))
            self.list_box.SetString(1, "Total file size: {}".format(total))
            self.list_box.SetString(2, "Downloaded file size: {}".format(downloaded))
            self.list_box.SetString(3, "Remaining file size: {}".format(remaining))
            self.list_box.SetString(4, "Downloading speed: {}".format(speed))
        self.gaugeProgress.SetValue(percent)
        self.Layout()

    def update_status(self, msg):
        if self.is_closing:
            return
        self.lbl_status.SetLabel(msg)
        if msg == "Converting your audio...":
            self.list_box.Clear()
            self.list_box.Append("Converting into mp3...")
            self.list_box.SetSelection(0)
        self.Layout()

    def finish_download(self, success_message):
        if self.is_closing:
            return
        self.is_completed = True
        self.update_status("Completed Successfully!")
        self.btnStop.Disable()
        if not self.IsShown():
            self.Show()
        self.Raise()
        self.RequestUserAttention()
        self.success_timer = wx.CallLater(25, self.show_success_dialog, success_message)

    def show_success_dialog(self, success_message):
        if self.is_closing:
            return
        parent = self if self and self.IsShownOnScreen() else None
        dialog = wx.MessageDialog(parent, success_message, "Success", style=wx.OK | wx.ICON_INFORMATION | wx.STAY_ON_TOP)
        try:
            dialog.ShowModal()
        finally:
            dialog.Destroy()
            self.success_timer = None
        self.close_immediately()

    def finish_cancelled(self):
        self.is_completed = True
        self.close_immediately()

    def close_immediately(self):
        if self.is_closing:
            return
        self.is_closing = True
        if self.success_timer and self.success_timer.IsRunning():
            self.success_timer.Stop()
        self.success_timer = None
        if self:
            self.Destroy()

    def onStopClick(self, event):
        self.Close()

    def onClose(self, event):
        if self.is_closing:
            event.Skip()
            return

        if not self.is_completed and self.downloader is not None and not self.downloader.cancelled:
            message = wx.MessageBox("A download is in progress. Do you want to cancel it?", "Exit", style=wx.YES_NO | wx.ICON_QUESTION, parent=self)
            if message == wx.YES:
                self.cancel_requested = True
                self.downloader.cancelled = True
                self.btnStop.Disable()
                self.btnStop.SetLabel("Stopping...")
                self.update_status("Stopping download...")
                self.Hide()
                if event.CanVeto():
                    event.Veto()
            else:
                if event.CanVeto():
                    event.Veto()
        else:
            self.close_immediately()
