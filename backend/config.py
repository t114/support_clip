
# Ollama settings
OLLAMA_MODEL = "qwen2.5"
OLLAMA_HOST = "http://localhost:11434"

# Clip detection settings
MIN_CLIP_DURATION = 10  # seconds
MAX_CLIP_DURATION = 60  # seconds
DEFAULT_MAX_CLIPS = 5

# YouTube settings
# Download best quality MP4, fallback to merging best video+audio, then any best format
# Download best quality MP4, fallback to merging best video+audio, then any best format
YOUTUBE_DOWNLOAD_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
