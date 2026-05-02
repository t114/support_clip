import os

UPLOAD_DIR = "backend/uploads"
PREFIX_IMAGES_DIR = os.path.join(UPLOAD_DIR, "prefix_images")
SOUNDS_DIR = "backend/assets/sounds"
EMOJIS_DIR = "backend/assets/emojis"

def ensure_dirs():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(PREFIX_IMAGES_DIR, exist_ok=True)
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    os.makedirs(EMOJIS_DIR, exist_ok=True)
