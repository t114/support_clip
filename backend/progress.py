from typing import Dict, Any
import time

# In-memory storage for progress
# Format: { video_id: { "status": str, "progress": float, "message": str, "updated_at": float } }
progress_store: Dict[str, Dict[str, Any]] = {}

def update_progress(video_id: str, status: str, progress: float = 0, message: str = ""):
    """Update the progress for a specific video ID."""
    print(f"[PROGRESS] Updating {video_id}: {status} {progress}% - {message}")
    progress_store[video_id] = {
        "status": status,
        "progress": progress,
        "message": message,
        "updated_at": time.time()
    }

def get_progress(video_id: str) -> Dict[str, Any]:
    """Get the current progress for a video ID."""
    data = progress_store.get(video_id, {
        "status": "idle",
        "progress": 0,
        "message": "",
        "updated_at": 0
    })
    print(f"[PROGRESS] Getting {video_id}: {data['status']} {data['progress']}%")
    return data

def clear_progress(video_id: str):
    """Remove progress data for a video ID."""
    if video_id in progress_store:
        del progress_store[video_id]
