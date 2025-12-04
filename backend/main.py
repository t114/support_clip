from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
from .transcribe import transcribe_video
from .youtube_downloader import download_youtube_video
from .clip_detector import analyze_transcript_with_ai, detect_boundaries_hybrid, extend_short_clips, evaluate_clip_quality
from .video_clipper import extract_clip, merge_clips
from .config import DEFAULT_MAX_CLIPS
from .fcpxml_generator import generate_fcpxml
from .video_processing import get_video_info

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure uploads directory exists
UPLOAD_DIR = "backend/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount static files to serve uploaded videos and generated subtitles
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    try:
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        if not file_extension:
            file_extension = ".mp4" # Default to mp4 if no extension
            
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Transcribe
        # Note: In a real app, this should be a background task
        vtt_path = transcribe_video(file_path)
        
        # Return URLs relative to the static mount
        srt_path = vtt_path.replace('.vtt', '.srt')
        
        # Generate FCPXML
        # Parse VTT to get segments for FCPXML
        # We need to parse VTT again or have transcribe return segments.
        # transcribe_video returns path. Let's parse it quickly or refactor.
        # For now, let's parse the VTT file we just made.
        from .transcribe import parse_vtt_file
        segments = parse_vtt_file(vtt_path)
        
        video_info = get_video_info(file_path)
        fcpxml_filename = f"{unique_filename}.fcpxml"
        fcpxml_path = os.path.join(UPLOAD_DIR, fcpxml_filename)
        
        generate_fcpxml(segments, fcpxml_path, file_path, fps=video_info['fps'], duration_seconds=video_info['duration'])
        
        return {
            "video_url": f"/static/{unique_filename}",
            "subtitle_url": f"/static/{os.path.basename(vtt_path)}",
            "srt_url": f"/static/{os.path.basename(srt_path)}",
            "fcpxml_url": f"/static/{fcpxml_filename}",
            "filename": file.filename,
            "unique_filename": unique_filename
        }
        
    except Exception as e:
        print(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel
from typing import Dict, Any
from .video_processing import burn_subtitles

class BurnRequest(BaseModel):
    video_filename: str
    subtitle_content: str
    styles: Dict[str, Any]

@app.post("/burn")
async def burn_video(request: BurnRequest):
    try:
        # Validate video exists
        video_path = os.path.join(UPLOAD_DIR, request.video_filename)
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video not found")
            
        # Save modified VTT
        base_name = os.path.splitext(request.video_filename)[0]
        vtt_filename = f"{base_name}_modified.vtt"
        vtt_path = os.path.join(UPLOAD_DIR, vtt_filename)
        
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(request.subtitle_content)
            
        # Output filename
        output_filename = f"{base_name}_burned.mp4"
        output_path = os.path.join(UPLOAD_DIR, output_filename)
        
        # Burn subtitles
        burn_subtitles(video_path, vtt_path, output_path, request.styles)
        
        return {
            "video_url": f"/static/{output_filename}",
            "filename": output_filename
        }
        
    except Exception as e:
        print(f"Error burning subtitles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from fastapi.responses import FileResponse

@app.get("/download/{filename}")
async def download_video(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    # Determine original filename for download
    # We expect filename to be like "{uuid}_burned.mp4"
    # We want the user to see "captioned_video.mp4" but we don't have the original name here easily
    # unless we store it or pass it.
    # For now, let's just use the filename on disk or a generic one.
    # Actually, let's try to preserve the extension.
    
    return FileResponse(
        path=file_path,
        filename=f"captioned_{filename}",
        media_type='application/octet-stream'
    )

class YouTubeDownloadRequest(BaseModel):
    url: str

@app.post("/youtube/download")
async def download_youtube(request: YouTubeDownloadRequest):
    try:
        # Download video
        video_info = download_youtube_video(request.url, UPLOAD_DIR)
        video_path = video_info["file_path"]
        
        # Transcribe immediately
        vtt_path = transcribe_video(video_path)
        srt_path = vtt_path.replace('.vtt', '.srt')
        
        # Generate FCPXML
        from .transcribe import parse_vtt_file
        segments = parse_vtt_file(vtt_path)
        
        # video_info already has duration but maybe not fps in the format we want?
        # youtube_downloader might return info.
        # Let's use get_video_info to be consistent and accurate with file on disk.
        video_meta = get_video_info(video_path)
        
        fcpxml_filename = f"{os.path.basename(video_path)}.fcpxml"
        fcpxml_path = os.path.join(UPLOAD_DIR, fcpxml_filename)
        
        generate_fcpxml(segments, fcpxml_path, video_path, fps=video_meta['fps'], duration_seconds=video_meta['duration'])
        
        return {
            "video_url": f"/static/{os.path.basename(video_path)}",
            "subtitle_url": f"/static/{os.path.basename(vtt_path)}",
            "srt_url": f"/static/{os.path.basename(srt_path)}",
            "fcpxml_url": f"/static/{fcpxml_filename}",
            "filename": os.path.basename(video_path),
            "video_info": video_info,
            "start_time": video_info.get("start_time", 0)
        }
    except Exception as e:
        print(f"Error downloading YouTube video: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class AnalyzeRequest(BaseModel):
    vtt_filename: str
    max_clips: int = DEFAULT_MAX_CLIPS
    offset: int = 0  # Starting segment index
    start_time: float = 0  # 解析開始時刻（秒）

@app.post("/youtube/analyze")
async def analyze_video(request: AnalyzeRequest):
    try:
        CHUNK_SIZE = 200  # Process 200 segments at a time

        vtt_path = os.path.join(UPLOAD_DIR, request.vtt_filename)
        if not os.path.exists(vtt_path):
            raise HTTPException(status_code=404, detail="Subtitle file not found")

        # Parse VTT to get segments
        # Improved parser that handles all text including numbers
        segments = []
        with open(vtt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        current_start = 0
        current_end = 0
        in_cue = False
        prev_line_was_empty = True  # Track empty lines to identify cue numbers

        for i, line in enumerate(lines):
            stripped = line.strip()

            if "-->" in stripped:
                times = stripped.split(" --> ")

                def parse_time(t):
                    parts = t.split(":")
                    seconds = float(parts[-1])
                    if len(parts) > 1:
                        seconds += int(parts[-2]) * 60
                    if len(parts) > 2:
                        seconds += int(parts[-3]) * 3600
                    return seconds

                current_start = parse_time(times[0])
                current_end = parse_time(times[1])
                in_cue = True
            elif stripped and in_cue and "WEBVTT" not in stripped:
                # Skip cue numbers (single digit/number on a line right after empty line)
                if prev_line_was_empty and stripped.isdigit() and len(stripped) <= 6:
                    # Likely a cue number, skip it
                    pass
                else:
                    # This is actual subtitle text
                    segments.append({
                        "start": current_start,
                        "end": current_end,
                        "text": stripped
                    })
            elif not stripped:
                in_cue = False

            prev_line_was_empty = not stripped

        total_segments = len(segments)
        offset = request.offset

        # Calculate video duration from segments
        video_duration = max([seg['end'] for seg in segments]) if segments else 0
        print(f"Video duration: {video_duration:.1f}s")

        # Get the chunk to analyze
        end_index = min(offset + CHUNK_SIZE, total_segments)
        segments_chunk = segments[offset:end_index]

        print(f"Analyzing segments {offset}-{end_index} of {total_segments}")

        # Find the video file from VTT filename
        # VTT files are named the same as video files (e.g., video.mp4 -> video.vtt)
        base_path = os.path.splitext(vtt_path)[0]
        # Try common video extensions
        video_path = None
        for ext in ['.mp4', '.webm', '.mkv', '.avi', '.mov']:
            candidate = base_path + ext
            if os.path.exists(candidate):
                video_path = candidate
                print(f"Found video file: {video_path}")
                break

        if not video_path:
            raise HTTPException(status_code=404, detail="Video file not found")

        # Filter segments by start_time if specified
        if request.start_time > 0:
            segments_chunk = [
                seg for seg in segments_chunk
                if seg['start'] >= request.start_time
            ]
            print(f"Filtered to {len(segments_chunk)} segments after start_time={request.start_time}s")
        
        if not segments_chunk:
            raise HTTPException(status_code=400, detail=f"No segments found after start_time={request.start_time}s")

        # Analyze with hybrid detection (silence + sentence boundaries)
        clips = detect_boundaries_hybrid(video_path, segments_chunk, request.max_clips, request.start_time)

        # Automatically evaluate each clip
        print(f"Evaluating {len(clips)} clips...")
        for clip in clips:
            try:
                evaluation = evaluate_clip_quality(vtt_path, clip['start'], clip['end'])
                clip['evaluation_score'] = evaluation['score']
                clip['evaluation_reason'] = evaluation['reason']
                print(f"Evaluated clip {clip['start']:.1f}-{clip['end']:.1f}: {evaluation['score']}/5 - {evaluation['reason']}")
            except Exception as e:
                print(f"Failed to evaluate clip {clip['start']:.1f}-{clip['end']:.1f}: {e}")
                clip['evaluation_score'] = 3
                clip['evaluation_reason'] = "評価に失敗しました"

        # Return clips with metadata
        return {
            "clips": clips,
            "total_segments": total_segments,
            "analyzed_segments": end_index,
            "has_more": end_index < total_segments,
            "next_offset": end_index if end_index < total_segments else None
        }

    except Exception as e:
        print(f"Error analyzing video: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ClipRequest(BaseModel):
    video_filename: str
    start: float
    end: float
    title: str

@app.post("/youtube/create-clip")
async def create_clip(request: ClipRequest):
    try:
        video_path = os.path.join(UPLOAD_DIR, request.video_filename)
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video not found")

        base_name = os.path.splitext(request.video_filename)[0]
        safe_title = "".join([c for c in request.title if c.isalnum() or c in (' ', '-', '_')]).strip()
        output_filename = f"{base_name}_clip_{safe_title}.mp4"
        output_path = os.path.join(UPLOAD_DIR, output_filename)

        extract_clip(video_path, request.start, request.end, output_path)

        return {
            "video_url": f"/static/{output_filename}",
            "filename": output_filename
        }

    except Exception as e:
        print(f"Error creating clip: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class EvaluateClipRequest(BaseModel):
    vtt_filename: str
    start: float
    end: float

@app.post("/youtube/evaluate-clip")
async def evaluate_clip(request: EvaluateClipRequest):
    try:
        vtt_path = os.path.join(UPLOAD_DIR, request.vtt_filename)
        if not os.path.exists(vtt_path):
            raise HTTPException(status_code=404, detail="Subtitle file not found")

        evaluation = evaluate_clip_quality(vtt_path, request.start, request.end)

        return evaluation

    except Exception as e:
        print(f"Error evaluating clip: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    return {"message": "Video Transcription API is running"}

@app.get("/test-clip-detector")
async def test_clip_detector():
    """Test endpoint to verify clip_detector module is loaded correctly"""
    print("=== TEST ENDPOINT CALLED ===")
    import sys
    import importlib

    # Force reload the module
    if 'backend.clip_detector' in sys.modules:
        print("Reloading backend.clip_detector module")
        importlib.reload(sys.modules['backend.clip_detector'])

    from .clip_detector import analyze_transcript_with_ai

    # Test with minimal data
    test_segments = [
        {'start': 0.0, 'end': 5.0, 'text': 'テストセグメント1'},
        {'start': 5.0, 'end': 10.0, 'text': 'テストセグメント2'},
        {'start': 10.0, 'end': 15.0, 'text': 'テストセグメント3'},
    ]

    print(f"Calling analyze_transcript_with_ai with {len(test_segments)} test segments")
    result = analyze_transcript_with_ai(test_segments, max_clips=1)
    print(f"Result: {len(result)} clips returned")

    return {
        "message": "Check backend logs for debug output",
        "result_count": len(result),
        "result": result
    }
