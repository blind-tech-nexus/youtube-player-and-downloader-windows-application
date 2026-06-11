import ctypes
import platform

arch = platform.architecture()[0]
dll = f".\\nvdaControllerClient{'32' if arch == '32bit' else '64'}.dll"
nvda = None


def _get_nvda():
	global nvda
	if nvda is None:
		nvda = ctypes.windll.LoadLibrary(dll)
	return nvda

def speak(msg):
	try:
		client = _get_nvda()
		running = client.nvdaController_testIfRunning()
		if running != 1:
			client.nvdaController_speakText(msg)
	except OSError:
		return
