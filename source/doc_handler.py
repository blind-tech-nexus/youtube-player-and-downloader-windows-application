import os
import application

def documentation_get():
	path = os.path.join(os.getcwd(), "docs", "en", "guide.txt")
	if not os.path.exists(path):
		return

	with open(path, "r", encoding="utf-8") as file:
		namespace = {"name": application.name, "version": application.version, "author": application.author}
		return file.read().format(**namespace)
