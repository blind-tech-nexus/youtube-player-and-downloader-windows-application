import os

import wx
from settings_handler import config_get, config_set


class SettingsDialog(wx.Dialog):
	def __init__(self, parent):
		wx.Dialog.__init__(self, parent, title="Settings")
		self.SetSize(500, 500)
		self.Centre()
		self.preferences = {}
		panel = wx.Panel(self)
		lbl1 = wx.StaticText(panel, -1, "Download folder path: ", name="path")
		self.pathField = wx.TextCtrl(panel, -1, value=config_get("path"), name="path", style=wx.TE_READONLY|wx.TE_MULTILINE|wx.HSCROLL)
		changeButton = wx.Button(panel, -1, "&Change path", name="path")
		preferencesBox = wx.StaticBox(panel, -1, "General preferences")
		self.autoDetectItem = wx.CheckBox(preferencesBox, -1, "Automatically detect links when the app opens", name="autodetect")
		self.autoCheckForUpdates = wx.CheckBox(preferencesBox, -1, "Automatically check for updates when the app opens", name="checkupdates")
		self.autoLoadItem = wx.CheckBox(preferencesBox, -1, "Load more search results when reaching the end of the displayed videos", name="autoload")
		self.autoCheckForUpdates.SetValue(config_get("checkupdates"))
		self.autoDetectItem.SetValue(config_get("autodetect"))
		self.autoLoadItem.SetValue(config_get("autoload"))
		downloadPreferencesBox = wx.StaticBox(panel, -1, "Download settings")
		lbl2 = wx.StaticText(downloadPreferencesBox, -1, "Direct download format: ")
		self.formats = wx.Choice(downloadPreferencesBox, -1, choices=["Video (mp4)", "Audio (m4a)", "Audio (mp3)"])
		self.formats.Selection = int(config_get('defaultformat'))
		lbl3 = wx.StaticText(downloadPreferencesBox, -1, "MP3 conversion quality: ")
		self.mp3Quality = wx.Choice(downloadPreferencesBox, -1, choices=["96 kbps", "128 kbps", "192 kbps"], name="conversion")
		self.mp3Quality.Selection = int(config_get("conversion"))
		playerOptions = wx.StaticBox(panel, -1, "Player settings")
		self.continueWatching = wx.CheckBox(playerOptions, -1, "Resume playback after closing and reopening a video", name="continue")
		self.continueWatching.Value = config_get("continue")
		self.repeateTracks = wx.CheckBox(playerOptions, -1, "Repeat the current track when it ends", name="repeatetracks")
		self.autoPlayNext = wx.CheckBox(playerOptions, -1, "Automatically play the next track when the current track ends", name="autonext")
		self.autoPlayNext.Value = config_get('autonext')
		self.repeateTracks.Value = config_get("repeatetracks")
		okButton = wx.Button(panel, wx.ID_OK, "&OK", name="ok_cancel")
		okButton.SetDefault()
		cancelButton = wx.Button(panel, wx.ID_CANCEL, "&Cancel", name="ok_cancel")
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer2 = wx.BoxSizer(wx.HORIZONTAL)
		sizer3 = wx.BoxSizer(wx.HORIZONTAL)
		sizer4 = wx.BoxSizer(wx.VERTICAL)
		sizer5 = wx.BoxSizer(wx.HORIZONTAL)
		sizer6 = wx.BoxSizer(wx.HORIZONTAL)
		sizer7 = wx.BoxSizer(wx.HORIZONTAL)
		okCancelSizer = wx.BoxSizer(wx.HORIZONTAL)
		for control in panel.GetChildren():
			if control.Name == "ok_cancel":
				okCancelSizer.Add(control, 1)
			elif control.Name == "path":
				sizer2.Add(control, 1)
		for item in preferencesBox.GetChildren():
			sizer3.Add(item, 1)
		preferencesBox.SetSizer(sizer3)
		sizer5.Add(lbl3, 1)
		sizer5.Add(self.mp3Quality, 1)
		sizer6.Add(lbl2, 1)
		sizer6.Add(self.formats, 1)
		sizer4.Add(sizer5)
		sizer4.Add(sizer6)
		downloadPreferencesBox.SetSizer(sizer4)
		for ctrl in playerOptions.GetChildren():
			sizer7.Add(ctrl, 1)
		playerOptions.SetSizer(sizer7)
		sizer.Add(sizer2, 1, wx.EXPAND)
		sizer.Add(preferencesBox, 1, wx.EXPAND)
		sizer.Add(downloadPreferencesBox, 1, wx.EXPAND)
		sizer.Add(playerOptions, 1, wx.EXPAND)
		sizer.Add(okCancelSizer, 1, wx.EXPAND)
		panel.SetSizer(sizer)
		changeButton.Bind(wx.EVT_BUTTON, self.onChange)
		self.autoDetectItem.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.autoLoadItem.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.autoCheckForUpdates.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.repeateTracks.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.autoPlayNext.Bind(wx.EVT_CHECKBOX, self.onCheck)
		self.continueWatching.Bind(wx.EVT_CHECKBOX, self.onCheck)
		okButton.Bind(wx.EVT_BUTTON, self.onOk)
		self.ShowModal()

	def onCheck(self, event):
		obj = event.EventObject
		if all((self.repeateTracks.Value, self.autoPlayNext.Value)) and obj in (self.repeateTracks, self.autoPlayNext):
			self.repeateTracks.Value = self.autoPlayNext.Value = False
		if obj.Name in self.preferences and config_get(obj.Name) == obj.Value:
			del self.preferences[obj.Name]
		elif not obj.Value == config_get(obj.Name):
			self.preferences[obj.Name] = obj.Value

	def onChange(self, event):
		new = wx.DirSelector("Choose download folder", os.path.join(os.getenv("userprofile"), "downloads"), parent=self)
		if not new == "":
			self.preferences['path'] = new
			self.pathField.Value = new
			self.pathField.SetFocus()

	def onOk(self, event):
		for key, item in self.preferences.items():
			config_set(key, item)
		if not self.mp3Quality.Selection == int(config_get("conversion")):
			config_set("conversion", self.mp3Quality.Selection)
		config_set("defaultformat", self.formats.Selection) if not self.formats.Selection == int(config_get('defaultformat')) else None
		self.Destroy()
