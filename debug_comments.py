import os
import json
import sys
# Add backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.clip_detector import count_comments_in_clips

def test_comment_counting():
    video_id = "qoNEDzHqAuU"
    comments_path = f"backend/uploads/{video_id}.live_chat.json"
    
    if not os.path.exists(comments_path):
        print(f"File not found: {comments_path}")
        return

    # Create dummy clips covering the whole video
    clips = [
        {"start": 0, "end": 600, "text": "Clip 1"},
        {"start": 600, "end": 1200, "text": "Clip 2"},
        {"start": 1200, "end": 1800, "text": "Clip 3"},
        {"start": 1800, "end": 2400, "text": "Clip 4"},
        {"start": 2400, "end": 3000, "text": "Clip 5"},
    ]
    
    print(f"Testing comment counting for {comments_path}")
    result = count_comments_in_clips(clips, comments_path)
    
    for clip in result:
        print(f"Clip {clip['start']}-{clip['end']}: {clip.get('comment_count', 'N/A')} comments")

if __name__ == "__main__":
    test_comment_counting()
