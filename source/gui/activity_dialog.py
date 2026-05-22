import wx
from threading import Thread


class LoadingDialog(wx.Dialog):
    def __init__(self, parent, msg, function, *args, **kwargs):
        self.function = function
        self.args = args
        self.kwargs = kwargs

        # Always define these first
        self.res = None
        self.error = None

        super().__init__(
            parent,
            title="Please wait",
            style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP
        )

        self.SetSize((300, 120))
        self.CenterOnParent()

        panel = wx.Panel(self)

        self.message = wx.StaticText(panel, label=msg)
        self.message.SetCanFocus(True)
        self.message.SetFocus()

        indicator = wx.ActivityIndicator(panel)
        indicator.Start()

        mainSizer = wx.BoxSizer(wx.VERTICAL)

        mainSizer.AddStretchSpacer()

        mainSizer.Add(
            self.message,
            0,
            wx.ALIGN_CENTER | wx.ALL,
            10
        )

        mainSizer.Add(
            indicator,
            0,
            wx.ALIGN_CENTER | wx.ALL,
            10
        )

        mainSizer.AddStretchSpacer()

        panel.SetSizer(mainSizer)

        # Prevent accidental close issues
        self.Bind(wx.EVT_CLOSE, self.onClose)

        # Keyboard navigation hook
        self.Bind(wx.EVT_CHAR_HOOK, self.onHook)

        # Start worker thread
        worker = Thread(target=self.run, daemon=True)
        worker.start()

        # Show modal dialog
        self.ShowModal()

    def run(self):
        try:
            self.res = self.function(*self.args, **self.kwargs)

        except Exception as e:
            self.error = e

        finally:
            wx.CallAfter(self.safeDestroy)

    def safeDestroy(self):
        try:
            if self.IsModal():
                self.EndModal(wx.ID_OK)

            self.Destroy()

        except RuntimeError:
            pass

    def onClose(self, event):
        # Prevent wx.Exit() crash behaviour
        event.Veto()

    def onHook(self, event):
        key = event.GetKeyCode()

        if key in (
            wx.WXK_DOWN,
            wx.WXK_UP,
            wx.WXK_LEFT,
            wx.WXK_RIGHT
        ):
            self.message.SetFocus()
            return

        event.Skip()
