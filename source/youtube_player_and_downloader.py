import sys
import os
from paths import get_app_base_dir

app_base_dir = get_app_base_dir()
os.chdir(app_base_dir)
if hasattr(os, "add_dll_directory"):
	os.add_dll_directory(app_base_dir)
import settings_handler
settings_handler.config_initialization()
import database
import application
import wx
import webbrowser

import subprocess
from utiles import youtube_regexp
from gui.custom_controls import CustomLabel
from doc_handler import documentation_get
from threading import Thread


class HomeScreen(wx.Frame):
	def __init__(self):
		wx.Frame.__init__(self, parent=None, title=application.name)
		self.Centre()
		self.SetSize(wx.DisplaySize())
		self.Maximize(True)
		panel = wx.Panel(self)
		self.instruction = CustomLabel(panel, -1, "Press Alt to open the program menus, or use Tab to quickly reach the main available options.") # a breafe instruction message witch is shown by the custome StaticText to automaticly be focused when launching the app
		youtubeBrowseButton = wx.Button(panel, -1, "Search YouTube\tctrl+f", name="tab")
		downloadFromLinkButton = wx.Button(panel, -1, "Download from link\tctrl+d", name="tab")
		playYoutubeLinkButton = wx.Button(panel, -1, "Play YouTube video from link\tctrl+y", name="tab")
		favButton = wx.Button(panel, -1, "Favorite videos\tctrl+shift+f", name="tab")
		# quick access buttons
		sizer = wx.BoxSizer(wx.VERTICAL) # the main sizer
		sizer1 = wx.BoxSizer(wx.HORIZONTAL) # quick access buttons sizer
		for control in panel.GetChildren():
			if control.Name == "tab":
				sizer1.Add(control, 1) # adding quick access buttons using for loop sins that eatch button named by the "tab" word
		sizer.Add(self.instruction, 1)
		sizer.AddStretchSpacer()
		sizer.Add(sizer1, 1, wx.EXPAND)
		panel.SetSizer(sizer) # adding the sizer to the main panel
		menuBar = wx.MenuBar() # seting up the menu bar
		mainMenu = wx.Menu()
		searchItem = mainMenu.Append(-1, "Search YouTube\tctrl+f") # search in youtube item
		downloadItem = mainMenu.Append(-1, "Download from link\tctrl+d")# download link item
		playItem = mainMenu.Append(-1, "Play YouTube video from link\tctrl+y") # play youtube link item
		favoriteItem = mainMenu.Append(-1, "Favorite videos\tctrl+shift+f")
		openDownloadingPathItem = mainMenu.Append(-1, "Open download folder\tctrl+p") # open downloading folder item
		settingsItem = mainMenu.Append(-1, "Settings...\talt+s") # settings item
		exitItem = mainMenu.Append(-1, "Exit\tctrl+w") # quit item
		hotKeys = wx.AcceleratorTable([
			(wx.ACCEL_CTRL, ord("F"), searchItem.GetId()),
			(wx.ACCEL_CTRL, ord("D"), downloadItem.GetId()),
			(wx.ACCEL_CTRL, ord("Y"), playItem.GetId()),
			(wx.ACCEL_CTRL+wx.ACCEL_SHIFT, ord("F"), favoriteItem.GetId()),
			(wx.ACCEL_CTRL, ord("P"), openDownloadingPathItem.GetId()),
			(wx.ACCEL_ALT, ord("S"), settingsItem.GetId()),
			(wx.ACCEL_CTRL, ord("W"), exitItem.GetId())
		])
		# the accelerator table asociated with the menu items
		self.SetAcceleratorTable(hotKeys) # adding the accelerator table to the frame
		menuBar.Append(mainMenu, "Main menu") # append the main menu to the menu bar
		aboutMenu = wx.Menu()
		userGuideItem = aboutMenu.Append(-1, "User guide...\tf1") # userguide
		checkForUpdatesItem = aboutMenu.Append(-1, "Check for updates")
		aboutItem = aboutMenu.Append(-1, "About...") # about item
		contactMenu = wx.Menu()
		emailItem = contactMenu.Append(-1, "Email...")
		twitterItem = contactMenu.Append(-1, "Twitter...")
		aboutMenu.AppendSubMenu(contactMenu, "Contact me")
		menuBar.Append(aboutMenu, "About") # append the about menu to the menu bar
		self.SetMenuBar(menuBar) # add the menu bar to the window
		# event bindings
		self.Bind(wx.EVT_MENU, self.onSearch, searchItem)
		youtubeBrowseButton.Bind(wx.EVT_BUTTON, self.onSearch)
		self.Bind(wx.EVT_MENU, self.onDownload, downloadItem)
		downloadFromLinkButton.Bind(wx.EVT_BUTTON, self.onDownload)
		self.Bind(wx.EVT_MENU, self.onPlay, playItem)
		playYoutubeLinkButton.Bind(wx.EVT_BUTTON, self.onPlay)
		self.Bind(wx.EVT_MENU, self.onFavorite, favoriteItem)
		favButton.Bind(wx.EVT_BUTTON, self.onFavorite)
		self.Bind(wx.EVT_MENU, self.onOpen, openDownloadingPathItem)
		self.Bind(wx.EVT_MENU, self.onSettings, settingsItem)
		self.Bind(wx.EVT_MENU, lambda event: wx.Exit(), exitItem)
		self.Bind(wx.EVT_MENU, self.onGuide, userGuideItem)
		self.Bind(wx.EVT_MENU, self.onCheckForUpdates, checkForUpdatesItem)
		self.Bind(wx.EVT_MENU, self.onAbout, aboutItem)
		self.Bind(wx.EVT_MENU, lambda event: webbrowser.open("mailto:Suleiman.alqusaimi@gmail.com"), emailItem)
		self.Bind(wx.EVT_MENU, lambda event: webbrowser.open("https://twitter.com/suleiman3ahmed"), twitterItem)
		self.Bind(wx.EVT_CHAR_HOOK, self.onHook)
		self.Bind(wx.EVT_SHOW, self.onShow)
		self.Bind(wx.EVT_CLOSE, self.onClose)
		self.Show()
		wx.CallAfter(self.finish_startup)

	def finish_startup(self):
		self.detectFromClipboard(settings_handler.config_get("autodetect"))
		if settings_handler.config_get("checkupdates"):
			from utiles import check_for_updates
			Thread(target=check_for_updates, args=[True], daemon=True).start()

	def onPlay(self, event): # the event function called when the play youtube link is clicked
		from gui.activity_dialog import AsyncLoadingDialog
		from gui.link_dlg import LinkDlg
		from utiles import get_audio_stream, get_video_stream
		linkDlg = LinkDlg(self)
		data = linkDlg.data # get the link and playing format from the dialog
		if not data:
			return
		url = data["link"]
		def open_player(stream):
			from media_player.media_gui import MediaGui
			title = stream.get("title") or url
			MediaGui(self, title, stream, data["link"], audio_mode=data["audio"]) # initiating the media gui
			self.Hide()
		AsyncLoadingDialog(self, "Fetching streaming URL...", get_audio_stream if data["audio"] else get_video_stream, open_player, url)

	def onDownload(self, event): # the event function for the link downloading item to show the appropriate dialog
		from gui.download_dialog import DownloadDialog
		dlg = DownloadDialog(self)
		dlg.Show()
	def onSearch(self, event): # showing the youtube browser window event function
		from youtube_browser.browser import YoutubeBrowser
		browser = YoutubeBrowser(self)
	def detectFromClipboard(self, config):
		if not config:
			return
		import pyperclip
		from gui.auto_detect_dialog import AutoDetectDialog
		clip_content = pyperclip.paste() # get the clipboard content
		match = youtube_regexp(clip_content)
		if match is not None:
			AutoDetectDialog(self, clip_content)
	def onFavorite(self, event):
		from gui.favorites import Favorites
		Favorites(self)
		self.Hide()
	def onSettings(self, event):
		from gui.settings_dialog import SettingsDialog
		SettingsDialog(self)
	def onOpen(self, event):
		path = settings_handler.config_get("path")
		if not os.path.exists(path):
			os.mkdir(path)
		explorer = os.path.join(os.getenv("SYSTEMDRIVE"), "\\windows\\explorer")
		subprocess.call(f"{explorer} {path}")
	def onHook(self, event):
		if event.KeyCode == wx.WXK_F1:
			content = documentation_get()
			if content is None:
				event.Skip()
				return
			from gui.text_viewer import Viewer
			Viewer(self, "YouTube player and downloader user guide", content)
		event.Skip()
	def onShow(self, event):
		self.instruction.SetFocus()
	def onGuide(self, event):
		content = documentation_get()
		if content is None:
			return
		from gui.text_viewer import Viewer
		Viewer(self, "YouTube player and downloader user guide", content).ShowModal()
	def onCheckForUpdates(self, event):
		from gui.activity_dialog import LoadingDialog
		from utiles import check_for_updates
		# speak("Checking for updates. Please wait")
		LoadingDialog(self, "Checking for updates. Please wait", check_for_updates)
		self.instruction.SetFocus()

	def onAbout(self, event):
		about = f"""Program name: {application.name}.
Version: {application.version}.
Developed by: {application.author}.
Description: {application.description}."""
		wx.MessageBox(about, "About", parent=self)
	def onClose(self, event):
		database.disconnect()
		wx.Exit()

app = wx.App()
HomeScreen()
app.MainLoop()
