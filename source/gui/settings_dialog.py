import os

import wx
from settings_handler import config_get, config_set


class SettingsDialog(wx.Dialog):
	def __init__(self, parent):
		wx.Dialog.__init__(self, parent, title="Settings")
		self.SetSize(500, 500)
		self.Centre()
		self.preferences = {}
		self.initial_values = {
			"path": config_get("path"),
			"autodetect": config_get("autodetect"),
			"checkupdates": config_get("checkupdates"),
			"autoload": config_get("autoload"),
			"continue": config_get("continue"),
			"repeatetracks": config_get("repeatetracks"),
			"autonext": config_get("autonext"),
			"defaultformat": int(config_get("defaultformat")),
			"conversion": int(config_get("conversion")),
			"seek": int(config_get("seek")),
		}
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
		lblSeek = wx.StaticText(playerOptions, -1, "Select a seek sequence")
		self.seekSlider = wx.Slider(playerOptions, -1, value=int(config_get("seek")), minValue=1, maxValue=30, style=wx.SL_HORIZONTAL | wx.SL_LABELS)
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
		sizer7.Add(self.continueWatching, 1)
		sizer7.Add(self.repeateTracks, 1)
		sizer7.Add(self.autoPlayNext, 1)
		seekSizer = wx.BoxSizer(wx.HORIZONTAL)
		seekSizer.Add(lblSeek, 1)
		seekSizer.Add(self.seekSlider, 1)
		sizer7.Add(seekSizer, 1, wx.EXPAND)
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
		import sys
		import subprocess
		import database

		# Check if any change has been made
		changed = False
		current_path = self.pathField.Value
		if current_path != self.initial_values["path"]:
			changed = True
		if self.autoDetectItem.Value != self.initial_values["autodetect"]:
			changed = True
		if self.autoCheckForUpdates.Value != self.initial_values["checkupdates"]:
			changed = True
		if self.autoLoadItem.Value != self.initial_values["autoload"]:
			changed = True
		if self.continueWatching.Value != self.initial_values["continue"]:
			changed = True
		if self.repeateTracks.Value != self.initial_values["repeatetracks"]:
			changed = True
		if self.autoPlayNext.Value != self.initial_values["autonext"]:
			changed = True
		if self.formats.Selection != self.initial_values["defaultformat"]:
			changed = True
		if self.mp3Quality.Selection != self.initial_values["conversion"]:
			changed = True
		if self.seekSlider.Value != self.initial_values["seek"]:
			changed = True

		# Save settings
		config_set("path", current_path)
		config_set("autodetect", self.autoDetectItem.Value)
		config_set("checkupdates", self.autoCheckForUpdates.Value)
		config_set("autoload", self.autoLoadItem.Value)
		config_set("continue", self.continueWatching.Value)
		config_set("repeatetracks", self.repeateTracks.Value)
		config_set("autonext", self.autoPlayNext.Value)
		config_set("defaultformat", self.formats.Selection)
		config_set("conversion", self.mp3Quality.Selection)
		config_set("seek", self.seekSlider.Value)

		if changed:
			res = wx.MessageBox(
				"Would you like to restart the application for the instant changes?",
				"Restart",
				wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
				parent=self
			)
			if res == wx.YES:
				try:
					database.disconnect()
				except Exception:
					pass
				python = sys.executable
				subprocess.Popen([python] + sys.argv)
				wx.GetApp().Exit()
				self.Destroy()
				return

		self.Destroy()
