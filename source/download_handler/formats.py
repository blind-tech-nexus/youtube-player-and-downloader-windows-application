VIDEO_DOWNLOAD_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best"
PLAYABLE_VIDEO_FORMAT = "best[ext=mp4]/best"
AUDIO_M4A_FORMAT = "bestaudio[ext=m4a]/bestaudio"
AUDIO_DOWNLOAD_FORMAT = "bestaudio/best"


def format_from_option(option):
    option = int(option)
    if option == 0:
        return VIDEO_DOWNLOAD_FORMAT, False
    if option == 1:
        return AUDIO_M4A_FORMAT, False
    return AUDIO_DOWNLOAD_FORMAT, True
