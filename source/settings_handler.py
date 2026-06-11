import configparser
import os
from paths import settings_path

# settings_path = os.path.join(os.getenv("appdata"), "YouTube player and downloader")

defaults = {
	"path": f"{os.getenv('USERPROFILE')}\\downloads\\YouTube player and downloader",
	"defaultaudio": 0,
	"autodetect": True,
	"checkupdates": True,
	"autoload": True,
	"seek": 5,
	"lastfilter": 0,
	"conversion": 1,
	"repeatetracks":False,
	"autonext": False,
	"defaultformat": 0,
	"volume": 100,
	"continue": True,
}

def config_initialization():
	try:
		os.mkdir(settings_path)
	except FileExistsError:
		pass
	if not os.path.exists(os.path.join(settings_path, "settings.ini")):
		config = configparser.ConfigParser()
		config.add_section("settings")
		for key, value in defaults.items():
			config["settings"][key] = str(value)
		with open(os.path.join(settings_path, "settings.ini"), "w") as file:
			config.write(file)

def string_to_bool(string):
	if string == "True":
		return True
	elif string == "False":
		return False
	else:
		return string


def config_get(string):
	config = configparser.ConfigParser()
	config.read(os.path.join(settings_path, "settings.ini"))
	try:
		value = config["settings"][string]
		return string_to_bool(value)
	except KeyError:
		config_set(string, defaults[string])
		return defaults[string]


def config_set(key, value):
	config = configparser.ConfigParser()
	config.read(os.path.join(settings_path, "settings.ini"))
	config["settings"][key] = str(value)
	with open(os.path.join(settings_path, "settings.ini"), "w") as file:
		config.write(file)
