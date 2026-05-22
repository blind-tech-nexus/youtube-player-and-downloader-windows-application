import wx

class DownloadProgress(wx.Frame):
    def __init__(self, parent, title=""):
        wx.Frame.__init__(self, parent=parent, style=wx.DEFAULT_FRAME_STYLE & ~wx.MAXIMIZE_BOX & ~wx.RESIZE_BORDER)
        self.Title = "Downloading - {}".format(title if title != "" else "YouTube player and downloader")
        self.downloader = None
        self.is_completed = False
        
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        self.lbl_status = wx.StaticText(panel, label="Initializing...")
        font = self.lbl_status.GetFont()
        font.MakeBold()
        self.lbl_status.SetFont(font)
        
        grid_sizer = wx.FlexGridSizer(4, 2, 10, 15)
        self.lbl_percent = wx.StaticText(panel, label="0%")
        self.lbl_size = wx.StaticText(panel, label="--")
        self.lbl_downloaded = wx.StaticText(panel, label="--")
        self.lbl_remaining = wx.StaticText(panel, label="--")
        self.lbl_speed = wx.StaticText(panel, label="--")
        
        grid_sizer.Add(wx.StaticText(panel, label="Progress:"), 0, wx.ALIGN_RIGHT)
        grid_sizer.Add(self.lbl_percent, 0, wx.EXPAND)
        grid_sizer.Add(wx.StaticText(panel, label="Total Size:"), 0, wx.ALIGN_RIGHT)
        grid_sizer.Add(self.lbl_size, 0, wx.EXPAND)
        grid_sizer.Add(wx.StaticText(panel, label="Downloaded:"), 0, wx.ALIGN_RIGHT)
        grid_sizer.Add(self.lbl_downloaded, 0, wx.EXPAND)
        grid_sizer.Add(wx.StaticText(panel, label="Remaining:"), 0, wx.ALIGN_RIGHT)
        grid_sizer.Add(self.lbl_remaining, 0, wx.EXPAND)
        
        self.gaugeProgress = wx.Gauge(panel, range=100, size=(350, 20))
        
        speed_sizer = wx.BoxSizer(wx.HORIZONTAL)
        speed_sizer.Add(wx.StaticText(panel, label="Speed: "), 0, wx.ALIGN_CENTER_VERTICAL)
        speed_sizer.Add(self.lbl_speed, 0, wx.ALIGN_CENTER_VERTICAL)
        
        self.btnStop = wx.Button(panel, label="Stop Downloading")
        self.btnStop.Bind(wx.EVT_BUTTON, self.onStopClick)
        
        main_sizer.Add(self.lbl_status, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 15)
        main_sizer.Add(self.gaugeProgress, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        main_sizer.Add(grid_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_CENTER_HORIZONTAL, 15)
        main_sizer.Add(speed_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 15)
        main_sizer.Add(self.btnStop, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 10)
        
        panel.SetSizer(main_sizer)
        main_sizer.Fit(self)
        self.Centre()
        
        self.Bind(wx.EVT_CLOSE, self.onClose)

    def update_stats(self, percent, total, downloaded, remaining, speed):
        self.lbl_percent.SetLabel("{}%".format(percent))
        self.lbl_size.SetLabel(total)
        self.lbl_downloaded.SetLabel(downloaded)
        self.lbl_remaining.SetLabel(remaining)
        self.lbl_speed.SetLabel(speed)
        self.gaugeProgress.SetValue(percent)
        self.Layout()

    def update_status(self, msg):
        self.lbl_status.SetLabel(msg)
        self.Layout()

    def onStopClick(self, event):
        self.Close()

    def onClose(self, event):
        if not self.is_completed and self.downloader is not None and not self.downloader.cancelled:
            message = wx.MessageBox("A download is in progress. Do you want to cancel it?", "Exit", style=wx.YES_NO | wx.ICON_QUESTION, parent=self)
            if message == wx.YES:
                self.downloader.cancelled = True
                self.Destroy()
            else:
                if event.CanVeto():
                    event.Veto()
        else:
            self.Destroy()
