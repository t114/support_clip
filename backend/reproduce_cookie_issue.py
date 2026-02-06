import yt_dlp
import os

url = "https://www.youtube.com/watch?v=6k5IOoNDP44"
output_dir = "."

ydl_opts = {
    'format': "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
    'outtmpl': '%(id)s.%(ext)s',
    'cookies_from_browser': 'firefox',
    'js_runtimes': {'node': {}},
    'remote_components': ['ejs:github'],
    'extractor_args': {'youtube': {'player_client': ['android']}},
    'verbose': True
}

print(f"Attempting download of {url} with Firefox cookies...")
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
except Exception as e:
    print(f"Caught error: {e}")
