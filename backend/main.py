from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import uuid
import requests
from .transcribe import transcribe_video
from .youtube_downloader import download_youtube_video
from .clip_detector import analyze_transcript_with_ai, detect_boundaries_hybrid, extend_short_clips, evaluate_clip_quality, count_comments_in_clips, detect_kusa_emoji_clips, detect_comment_density_clips
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

# Ensure prefix images directory exists
PREFIX_IMAGES_DIR = os.path.join(UPLOAD_DIR, "prefix_images")
os.makedirs(PREFIX_IMAGES_DIR, exist_ok=True)

# Ensure emojis directory exists
EMOJIS_DIR = "backend/assets/emojis"
os.makedirs(EMOJIS_DIR, exist_ok=True)
app.mount("/static/emojis", StaticFiles(directory=EMOJIS_DIR), name="emojis")

# Mount static files to serve uploaded videos and generated subtitles
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

import logging

# Setup logger
logger = logging.getLogger(__name__)

@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    model_size: str = Form("base")
):
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

        logger.info(f"Video uploaded: {unique_filename}, model_size: {model_size}")

        # model_size が "none" の場合は文字起こしをスキップ
        if model_size == "none":
            logger.info(f"Skipping transcription (model_size=none) for {unique_filename}")
            return {
                "video_url": f"/static/{unique_filename}",
                "subtitle_url": None,
                "srt_url": None,
                "fcpxml_url": None,
                "filename": file.filename,
                "unique_filename": unique_filename
            }

        # Transcribe
        # Note: In a real app, this should be a background task
        vtt_path = transcribe_video(file_path, model_size=model_size)

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
        logger.error(f"Error processing upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel
from typing import Dict, Any, Optional
from .video_processing import burn_subtitles_with_ffmpeg
from .ass_generator import generate_ass, generate_danmaku_ass
import json

class BurnRequest(BaseModel):
    video_filename: str
    subtitle_content: str
    styles: dict
    saved_styles: Optional[dict] = None
    style_map: Optional[dict] = None
    with_danmaku: bool = False
    danmaku_density: int = 10

class SyncEmojiRequest(BaseModel):
    channel_id: str
    emojis: Dict[str, str] # shortcut -> url

def extract_text_from_runs(runs):
    """Helper to extract text and emoji shortcuts from YouTube message runs"""
    text = ""
    for run in runs:
        if 'text' in run:
            text += run['text']
        elif 'emoji' in run:
            emoji = run['emoji']
            shortcuts = emoji.get('shortcuts', [])
            if shortcuts:
                # Use the first shortcut (e.g. :_mioハトタウロス:)
                text += shortcuts[0]
            else:
                # Fallback to image label
                label = emoji.get('image', {}).get('accessibility', {}).get('accessibilityData', {}).get('label', '')
                if label:
                    text += f":{label}:"
    return text

def extract_comments(base_name):
    """Refactored helper to extract comments from json files"""
    live_chat_file = os.path.join(UPLOAD_DIR, f"{base_name}.live_chat.json")
    info_file = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")
    
    comments_data = []
    
    logger.info(f"Extracting comments for {base_name}. Checking files...")
    
    if os.path.exists(live_chat_file):
        logger.info(f"Found live chat file: {live_chat_file}")
        with open(live_chat_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    
                    # Live chat replay packets often group multiple actions
                    # Primary structure is replayChatItemAction -> actions -> [addChatItemAction, ...]
                    actions_container = data.get('replayChatItemAction', {})
                    actions = actions_container.get('actions', [])
                    
                    # Fallback for other structures
                    if not actions and 'actions' in data:
                        actions = data.get('actions', [])
                    
                    # Global offset for this packet
                    packet_offset = actions_container.get('videoOffsetTimeMsec')
                    if not packet_offset and 'videoOffsetTimeMsec' in data:
                        packet_offset = data['videoOffsetTimeMsec']

                    for action in actions:
                        item_action = action.get('addChatItemAction', {})
                        if not item_action: continue
                        
                        item = item_action.get('item', {})
                        if not item: continue
                        
                        text = None
                        if 'liveChatTextMessageRenderer' in item:
                            renderer = item['liveChatTextMessageRenderer']
                            text_runs = renderer.get('message', {}).get('runs', [])
                            text = extract_text_from_runs(text_runs)
                        elif 'liveChatPaidMessageRenderer' in item:
                            renderer = item['liveChatPaidMessageRenderer']
                            text_runs = renderer.get('message', {}).get('runs', [])
                            text = extract_text_from_runs(text_runs)
                            purchase_amount = renderer.get('purchaseAmountText', {}).get('simpleText', '')
                            if purchase_amount:
                                text = f"[{purchase_amount}] {text}"
                        elif 'liveChatMembershipItemRenderer' in item:
                            renderer = item['liveChatMembershipItemRenderer']
                            header_runs = renderer.get('headerSubtext', {}).get('runs', [])
                            header_text = extract_text_from_runs(header_runs)
                            msg_runs = renderer.get('message', {}).get('runs', [])
                            msg_text = extract_text_from_runs(msg_runs)
                            text = f"{header_text} {msg_text}".strip()
                        elif 'liveChatSponsorshipGiftRedemptionAnnouncementRenderer' in item:
                            renderer = item['liveChatSponsorshipGiftRedemptionAnnouncementRenderer']
                            msg_runs = renderer.get('message', {}).get('runs', [])
                            text = extract_text_from_runs(msg_runs)
                            
                        if text:
                            # Use packet offset as default, override if renderer has its own (unlikely but possible)
                            offset_str = packet_offset
                            if 'videoOffsetTimeMsec' in item.get('liveChatTextMessageRenderer', {}):
                                offset_str = item['liveChatTextMessageRenderer']['videoOffsetTimeMsec']
                            
                            if offset_str:
                                try:
                                    time_sec = int(offset_str) / 1000.0
                                    comments_data.append({'text': text, 'timestamp': time_sec})
                                except:
                                    pass
                except:
                    continue
                    
    if not comments_data and os.path.exists(info_file):
        logger.info(f"Checking info file for comments: {info_file}")
        try:
            with open(info_file, 'r', encoding='utf-8') as f:
                info = json.load(f)
                if 'comments' in info:
                    logger.info(f"Found {len(info['comments'])} comments in info.json")
                    for c in info['comments']:
                        text = c.get('text', '')
                        timestamp = c.get('timestamp')
                        if timestamp is not None:
                            comments_data.append({'text': text, 'timestamp': float(timestamp)})
        except Exception as e:
            logger.error(f"Error reading info.json comments: {e}")
            
    logger.info(f"Extracted {len(comments_data)} comments total.")
    return comments_data

@app.get("/youtube/comments/{video_filename}")
async def get_video_comments(video_filename: str):
    """Get comments for a video for frontend preview"""
    base_name = os.path.splitext(video_filename)[0]
    comments = extract_comments(base_name)
    return {"comments": comments}

@app.post("/youtube/sync-emojis")
async def sync_emojis(request: SyncEmojiRequest):
    """Download and sync membership emojis for a channel"""
    try:
        channel_id = request.channel_id
        if not channel_id or channel_id == "UNKNOWN_CHANNEL":
             raise HTTPException(status_code=400, detail="Channel ID is required")
             
        channel_dir = os.path.join(EMOJIS_DIR, channel_id)
        os.makedirs(channel_dir, exist_ok=True)
        
        saved_count = 0
        for shortcut, url in request.emojis.items():
            # Sanitize shortcut to use as filename
            safe_name = "".join([c for c in shortcut if c.isalnum() or c in "_-"]).strip("_")
            if not safe_name: safe_name = f"emoji_{hash(shortcut)}"
            
            # Identify extension from URL if possible, otherwise .png
            ext = ".png"
            if ".webp" in url: ext = ".webp"
            elif ".gif" in url: ext = ".gif"
            
            file_path = os.path.join(channel_dir, f"{safe_name}{ext}")
            
            # Download if not exists
            if not os.path.exists(file_path):
                logger.info(f"Downloading emoji {shortcut} for {channel_id}")
                resp = requests.get(url, stream=True)
                if resp.status_code == 200:
                    with open(file_path, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    saved_count += 1
            else:
                saved_count += 1
                
        # Also save a mapping file for the frontend to know which extension to use
        mapping_file = os.path.join(channel_dir, "map.json")
        with open(mapping_file, 'w', encoding='utf-8') as f:
            # We store the local filename (basename) for each shortcut
            local_mapping = {}
            for shortcut, url in request.emojis.items():
                 safe_name = "".join([c for c in shortcut if c.isalnum() or c in "_-"]).strip("_")
                 if not safe_name: safe_name = f"emoji_{hash(shortcut)}"
                 ext = ".png"
                 if ".webp" in url: ext = ".webp"
                 elif ".gif" in url: ext = ".gif"
                 local_mapping[shortcut] = f"{safe_name}{ext}"
            json.dump(local_mapping, f, ensure_ascii=False, indent=2)

        return {"status": "success", "saved_count": saved_count, "channel_id": channel_id}
    except Exception as e:
        logger.error(f"Error syncing emojis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/burn")
async def burn_subtitles(request: BurnRequest):
    try:
        # Find video file
        video_path = os.path.join(UPLOAD_DIR, request.video_filename)
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video not found")

        # Clean up styles: if prefixImage is set, clear the prefix text
        cleaned_styles = dict(request.styles)
        if cleaned_styles.get('prefixImage'):
            cleaned_styles['prefix'] = ''

        cleaned_saved_styles = None
        if request.saved_styles:
            cleaned_saved_styles = {}
            for name, style in request.saved_styles.items():
                cleaned_style = dict(style)
                if cleaned_style.get('prefixImage'):
                    cleaned_style['prefix'] = ''
                cleaned_saved_styles[name] = cleaned_style

        # Save temporary VTT
        base_name = os.path.splitext(request.video_filename)[0]
        vtt_path = os.path.join(UPLOAD_DIR, f"{base_name}_modified.vtt")
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(request.subtitle_content)

        # Generate ASS file with styles
        ass_path = os.path.join(UPLOAD_DIR, f"{base_name}_modified.ass")
        generate_ass(
            vtt_path,
            cleaned_styles,
            ass_path,
            saved_styles=cleaned_saved_styles,
            style_map=request.style_map
        )
        
        # Generate Danmaku ASS if requested
        danmaku_ass_path = None
        if request.with_danmaku:
            comments_data = extract_comments(base_name)

            if comments_data:
                # Apply density filtering
                density = getattr(request, 'danmaku_density', 100)
                if density < 100:
                    comments_data = [c for c in comments_data if (int(c['timestamp'] * 1000) % 100) < density]

                danmaku_ass_path = os.path.join(UPLOAD_DIR, f"{base_name}_danmaku.ass")
                
                # We need video resolution for danmaku generation.
                from .video_processing import get_video_info
                v_info = get_video_info(video_path)
                w = v_info.get('width', 1920) or 1920
                h = v_info.get('height', 1080) or 1080
                
                # Load emoji mapping for the channel
                emoji_map = None
                emoji_dir = None
                info_file = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")
                if os.path.exists(info_file):
                    try:
                        with open(info_file, 'r', encoding='utf-8') as f_i:
                            v_info_json = json.load(f_i)
                            channel_id = v_info_json.get('channel_id')
                            if channel_id:
                                emoji_dir = os.path.join(EMOJIS_DIR, channel_id)
                                map_path = os.path.join(emoji_dir, "map.json")
                                if os.path.exists(map_path):
                                    with open(map_path, 'r', encoding='utf-8') as f_m:
                                        emoji_map = json.load(f_m)
                    except: pass

                danmaku_ass_path, emoji_overlays = generate_danmaku_ass(
                    comments_data,
                    danmaku_ass_path,
                    resolution_x=w,
                    resolution_y=h,
                    emoji_map=emoji_map,
                    emoji_dir=emoji_dir
                )

        # Burn subtitles (now with image prefix support and danmaku)
        output_filename = f"{base_name}_burned.mp4"
        output_path = os.path.join(UPLOAD_DIR, output_filename)

        burn_subtitles_with_ffmpeg(
            video_path,
            ass_path,
            output_path,
            vtt_path=vtt_path,
            saved_styles=cleaned_saved_styles,
            style_map=request.style_map,
            default_style=cleaned_styles,
            upload_dir=UPLOAD_DIR,
            danmaku_ass_path=danmaku_ass_path,
            emoji_overlays=emoji_overlays if 'emoji_overlays' in locals() else None
        )

        return {"filename": output_filename}
    except Exception as e:
        logger.error(f"Error burning subtitles: {e}")
        import traceback
        traceback.print_exc()
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
    with_comments: bool = False
    model_size: str = "base"

from .progress import update_progress, get_progress, clear_progress

@app.get("/progress/{video_id}")
async def get_video_progress(video_id: str):
    return get_progress(video_id)

@app.post("/youtube/download")
def download_youtube(request: YouTubeDownloadRequest):
    logger.info(f"[YOUTUBE_DOWNLOAD] Endpoint called with URL: {request.url}, model_size: {request.model_size}, with_comments: {request.with_comments}")
    try:
        # Extract video ID early if possible, or wait until download
        import re
        import time
        video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', request.url)
        video_id = video_id_match.group(1) if video_id_match else "unknown"
        logger.info(f"[YOUTUBE_DOWNLOAD] Extracted video ID: {video_id}")
        
        # Check if job is already running
        current_progress = get_progress(video_id)
        current_status = current_progress.get("status")
        last_updated = current_progress.get("updated_at", 0)
        now = time.time()
        
        # If active and updated recently (within 2 minutes), wait for it
        if current_status in ["downloading", "transcribing"] and (now - last_updated) < 120:
            logger.info(f"Job for {video_id} is already running (status: {current_status}). Waiting for completion...")
            
            # Wait loop
            while True:
                time.sleep(2)
                prog = get_progress(video_id)
                status = prog.get("status")
                
                if status == "completed":
                    logger.info(f"Existing job for {video_id} completed. Returning result.")
                    # Proceed to return result using cached files
                    # We need to populate video_info and paths.
                    # Since it's completed, files should exist.
                    # We can just fall through to the "is_cached" logic, 
                    # but we need to set video_info.
                    # Let's just break and let the code proceed. 
                    # The download_youtube_video call will see the files and return cached info.
                    break
                
                if status == "error":
                    raise HTTPException(status_code=500, detail=f"Previous job failed: {prog.get('message')}")
                
                # Check timeout or stale
                if (time.time() - prog.get("updated_at", 0)) > 120:
                    logger.warning(f"Existing job for {video_id} seems stalled. Taking over.")
                    break
        
        update_progress(video_id, "downloading", 0, "動画をダウンロード中...")
        
        # Download video (or use cache)
        # with_commentsフラグを渡す
        video_info = download_youtube_video(request.url, UPLOAD_DIR, download_comments=request.with_comments)
        video_path = video_info["file_path"]
        real_video_id = video_info["id"]
        
        # Update video_id if we guessed wrong (though usually regex is fine)
        if real_video_id != video_id:
            video_id = real_video_id
            
        update_progress(video_id, "downloading", 100, "ダウンロード完了")
        
        is_cached = video_info.get("cached", False)
        
        if is_cached:
            logger.info(f"Video is cached, checking for transcription files...")
        
        # 文字起こしファイルのキャッシュ確認
        # 動画IDベースのファイル名を使用
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        vtt_filename = f"{base_name}.vtt"
        vtt_path = os.path.join(UPLOAD_DIR, vtt_filename)
        srt_filename = f"{base_name}.srt"
        srt_path = os.path.join(UPLOAD_DIR, srt_filename)
        
        # VTTファイルが存在しない場合のみ文字起こし実行
        # model_size が "none" の場合は文字起こしをスキップ
        if request.model_size == "none":
            logger.info(f"Skipping transcription (model_size=none)")
            update_progress(video_id, "completed", 100, "文字起こしをスキップしました（字幕ファイルをアップロードしてください）")
            # VTTとSRTのパスを空にする
            vtt_path = None
            srt_path = None
        elif not os.path.exists(vtt_path):
            logger.info(f"Transcribing video: {video_path}")
            update_progress(video_id, "transcribing", 0, "文字起こし準備中...")

            def progress_callback(percent):
                update_progress(video_id, "transcribing", percent, f"文字起こし中... {int(percent)}%")

            vtt_path = transcribe_video(video_path, progress_callback=progress_callback, model_size=request.model_size)
            srt_path = vtt_path.replace('.vtt', '.srt')

            update_progress(video_id, "transcribing", 100, "文字起こし完了")
        else:
            logger.info(f"Using cached transcription: {vtt_path}")
            update_progress(video_id, "completed", 100, "キャッシュを使用中")
        
        # Generate FCPXML (only if VTT exists)
        fcpxml_filename = None
        fcpxml_path = None

        if vtt_path:
            from .transcribe import parse_vtt_file
            segments = parse_vtt_file(vtt_path)

            # FCPXMLのキャッシュ確認
            fcpxml_filename = f"{base_name}.fcpxml"
            fcpxml_path = os.path.join(UPLOAD_DIR, fcpxml_filename)

            if not os.path.exists(fcpxml_path):
                logger.info(f"Generating FCPXML: {fcpxml_path}")
                # video_info already has duration but maybe not fps in the format we want?
                # youtube_downloader might return info.
                # Let's use get_video_info to be consistent and accurate with file on disk.
                video_meta = get_video_info(video_path)
                generate_fcpxml(segments, fcpxml_path, video_path, fps=video_meta['fps'], duration_seconds=video_meta['duration'])
            else:
                logger.info(f"Using cached FCPXML: {fcpxml_path}")
        
        update_progress(video_id, "completed", 100, "処理完了")

        response_data = {
            "video_url": f"/static/{os.path.basename(video_path)}",
            "subtitle_url": f"/static/{os.path.basename(vtt_path)}" if vtt_path else None,
            "srt_url": f"/static/{os.path.basename(srt_path)}" if srt_path else None,
            "fcpxml_url": f"/static/{fcpxml_filename}" if fcpxml_filename else None,
            "filename": os.path.basename(video_path),
            "video_info": video_info,
            "start_time": video_info.get("start_time", 0),
            "cached": is_cached,
            "has_comments": video_info.get("comments_file") is not None or os.path.exists(os.path.join(UPLOAD_DIR, f"{base_name}.live_chat.json")) or os.path.exists(os.path.join(UPLOAD_DIR, f"{base_name}.info.json"))
        }

        logger.info(f"[YOUTUBE_DOWNLOAD] Returning response for {video_id}: {response_data.keys()}")
        logger.info(f"[YOUTUBE_DOWNLOAD] has_comments={response_data['has_comments']}, comments_file={video_info.get('comments_file')}")
        return response_data
    except Exception as e:
        logger.error(f"Error downloading YouTube video: {e}")
        # Try to extract video ID to update error status
        import re
        video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', request.url)
        if video_id_match:
             update_progress(video_id_match.group(1), "error", 0, f"エラー: {str(e)}")
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

        # Count comments if available
        # VTT filename is usually [video_id].vtt
        # Comments file is [video_id].live_chat.json or [video_id].info.json
        base_name = os.path.splitext(request.vtt_filename)[0]
        
        live_chat_path = os.path.join(UPLOAD_DIR, f"{base_name}.live_chat.json")
        info_json_path = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")
        
        comments_path = None
        if os.path.exists(live_chat_path):
            comments_path = live_chat_path
        elif os.path.exists(info_json_path):
            comments_path = info_json_path
        
        if comments_path:
            print(f"Found comments file: {comments_path}")
            clips = count_comments_in_clips(clips, comments_path)
        else:
            print(f"No comments file found for {base_name}")

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

class AnalyzeKusaRequest(BaseModel):
    vtt_filename: Optional[str] = None
    video_filename: Optional[str] = None
    clip_duration: int = 60  # 1-minute clips by default

@app.post("/youtube/analyze-kusa")
async def analyze_kusa_clips(request: AnalyzeKusaRequest):
    """
    Analyze video for kusa emoji (:*kusa*:) frequency in live chat.
    Returns top 10 clips with highest kusa emoji density per minute.
    """
    try:
        base_name = None
        video_path = None
        
        # Determine base name and video path
        if request.vtt_filename:
            vtt_path = os.path.join(UPLOAD_DIR, request.vtt_filename)
            base_name = os.path.splitext(request.vtt_filename)[0]
        elif request.video_filename:
            video_path = os.path.join(UPLOAD_DIR, request.video_filename)
            base_name = os.path.splitext(request.video_filename)[0]
        else:
            raise HTTPException(status_code=400, detail="Either vtt_filename or video_filename must be provided")

        # Find video file if not already found
        if not video_path:
            # Find video file to get duration
            # base_name is from vtt, so try extensions
            for ext in ['.mp4', '.webm', '.mkv', '.avi', '.mov']:
                candidate = os.path.join(UPLOAD_DIR, base_name + ext)
                if os.path.exists(candidate):
                    video_path = candidate
                    break

        if not video_path or not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video file not found")

        # Get video duration
        video_info = get_video_info(video_path)
        video_duration = video_info['duration']

        # Find comments file
        live_chat_path = os.path.join(UPLOAD_DIR, f"{base_name}.live_chat.json")
        info_json_path = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")

        comments_path = None
        if os.path.exists(live_chat_path):
            comments_path = live_chat_path
            print(f"Found live chat file: {comments_path}")
        elif os.path.exists(info_json_path):
            comments_path = info_json_path
            print(f"Found info.json file: {comments_path}")
        else:
            raise HTTPException(
                status_code=404,
                detail="コメントファイルが見つかりません。動画ダウンロード時にコメント取得を有効にしてください。"
            )

        # Detect kusa emoji clips
        clips = detect_kusa_emoji_clips(
            comments_path=comments_path,
            video_duration=video_duration,
            clip_duration=request.clip_duration
        )

        if not clips:
            return {
                "clips": [],
                "message": "草絵文字を含むクリップが見つかりませんでした"
            }

        return {
            "clips": clips,
            "total_clips": len(clips),
            "message": f"草絵文字が多い上位{len(clips)}件のクリップを検出しました"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error analyzing kusa clips: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class AnalyzeCommentDensityRequest(BaseModel):
    vtt_filename: Optional[str] = None
    video_filename: Optional[str] = None
    clip_duration: int = 60  # 1-minute clips by default

@app.post("/youtube/analyze-comment-density")
async def analyze_comment_density_clips(request: AnalyzeCommentDensityRequest):
    """
    Analyze video for comment density (total comments per minute).
    Returns top 10 clips with highest comment count.
    """
    try:
        base_name = None
        video_path = None
        
        # Determine base name and video path
        if request.vtt_filename:
            vtt_path = os.path.join(UPLOAD_DIR, request.vtt_filename)
            base_name = os.path.splitext(request.vtt_filename)[0]
        elif request.video_filename:
            video_path = os.path.join(UPLOAD_DIR, request.video_filename)
            base_name = os.path.splitext(request.video_filename)[0]
        else:
            raise HTTPException(status_code=400, detail="Either vtt_filename or video_filename must be provided")

        # Find video file if not already found
        if not video_path:
            for ext in ['.mp4', '.webm', '.mkv', '.avi', '.mov']:
                candidate = os.path.join(UPLOAD_DIR, base_name + ext)
                if os.path.exists(candidate):
                    video_path = candidate
                    break

        if not video_path or not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video file not found")

        # Get video duration
        video_info = get_video_info(video_path)
        video_duration = video_info['duration']

        # Find comments file
        live_chat_path = os.path.join(UPLOAD_DIR, f"{base_name}.live_chat.json")
        info_json_path = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")

        comments_path = None
        if os.path.exists(live_chat_path):
            comments_path = live_chat_path
            print(f"Found live chat file: {comments_path}")
        elif os.path.exists(info_json_path):
            comments_path = info_json_path
            print(f"Found info.json file: {comments_path}")
        else:
            raise HTTPException(
                status_code=404,
                detail="コメントファイルが見つかりません。動画ダウンロード時にコメント取得を有効にしてください。"
            )

        # Detect comment density clips
        clips = detect_comment_density_clips(
            comments_path=comments_path,
            video_duration=video_duration,
            clip_duration=request.clip_duration
        )

        if not clips:
            return {
                "clips": [],
                "message": "コメントを含むクリップが見つかりませんでした"
            }

        return {
            "clips": clips,
            "total_clips": len(clips),
            "message": f"コメント量が多い上位{len(clips)}件のクリップを検出しました"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error analyzing comment density: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/youtube/upload-subtitle")
async def upload_subtitle(
    video_filename: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Upload subtitle file (VTT or SRT) for a downloaded YouTube video
    and generate associated files (SRT/VTT conversion and FCPXML)
    """
    try:
        logger.info(f"Uploading subtitle for video: {video_filename}, file: {file.filename}")

        # Verify video exists
        video_path = os.path.join(UPLOAD_DIR, video_filename)
        if not os.path.exists(video_path):
            logger.error(f"Video file not found: {video_path}")
            raise HTTPException(status_code=404, detail="Video file not found")

        # Check file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        logger.info(f"File extension: {file_extension}")

        if file_extension not in ['.vtt', '.srt']:
            raise HTTPException(status_code=400, detail="Only VTT or SRT files are supported")

        # Save uploaded subtitle file
        base_name = os.path.splitext(video_filename)[0]
        logger.info(f"Base name: {base_name}")

        # Determine paths
        if file_extension == '.vtt':
            vtt_filename = f"{base_name}.vtt"
            vtt_path = os.path.join(UPLOAD_DIR, vtt_filename)
            srt_filename = f"{base_name}.srt"
            srt_path = os.path.join(UPLOAD_DIR, srt_filename)

            logger.info(f"Saving VTT file to: {vtt_path}")
            # Save VTT file
            with open(vtt_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            logger.info(f"Converting VTT to SRT: {srt_path}")
            # Convert VTT to SRT
            from .transcribe import convert_vtt_to_srt
            convert_vtt_to_srt(vtt_path, srt_path)

        else:  # .srt
            srt_filename = f"{base_name}.srt"
            srt_path = os.path.join(UPLOAD_DIR, srt_filename)
            vtt_filename = f"{base_name}.vtt"
            vtt_path = os.path.join(UPLOAD_DIR, vtt_filename)

            logger.info(f"Saving SRT file to: {srt_path}")
            # Save SRT file
            with open(srt_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            logger.info(f"Converting SRT to VTT: {vtt_path}")
            # Convert SRT to VTT
            from .transcribe import convert_srt_to_vtt
            convert_srt_to_vtt(srt_path, vtt_path)

        logger.info(f"Parsing VTT file: {vtt_path}")
        # Generate FCPXML
        from .transcribe import parse_vtt_file
        segments = parse_vtt_file(vtt_path)
        logger.info(f"Parsed {len(segments)} segments")

        fcpxml_filename = f"{base_name}.fcpxml"
        fcpxml_path = os.path.join(UPLOAD_DIR, fcpxml_filename)

        logger.info(f"Generating FCPXML: {fcpxml_path}")
        video_meta = get_video_info(video_path)
        generate_fcpxml(segments, fcpxml_path, video_path, fps=video_meta['fps'], duration_seconds=video_meta['duration'])

        logger.info(f"Subtitle uploaded and processed successfully: {vtt_filename}")

        return {
            "subtitle_url": f"/static/{vtt_filename}",
            "srt_url": f"/static/{srt_filename}",
            "fcpxml_url": f"/static/{fcpxml_filename}",
            "message": "字幕ファイルがアップロードされました"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading subtitle: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

class ClipRequest(BaseModel):
    video_filename: str
    start: float
    end: float
    title: str
    crop_x: Optional[float] = None
    crop_y: Optional[float] = None
    crop_width: Optional[float] = None
    crop_height: Optional[float] = None
    with_danmaku: bool = False
    danmaku_density: int = 10
    aspect_ratio: Optional[str] = None

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

        crop_params = None
        if request.crop_width is not None and request.crop_height is not None:
            crop_params = {
                'x': request.crop_x or 0,
                'y': request.crop_y or 0,
                'width': request.crop_width,
                'height': request.crop_height
            }

        danmaku_ass_path = None
        if request.with_danmaku:
            # Extract and filter comments for this clip range
            all_comments = extract_comments(base_name)
            # Filter comments that fall within the clip range
            # Note: A comment starting at t might need to be shown even if it started slightly before start?
            # Actually, if we show it for 5s, we should include those that overlap.
            # But let's start simple: comments that *start* within [start, end].
            clip_comments = []
            density = request.danmaku_density
            for c in all_comments:
                if request.start <= c['timestamp'] <= request.end:
                    # Apply density filtering (deterministic)
                    if (int(c['timestamp'] * 1000) % 100) < density:
                        # Adjust timestamp to be relative to clip start
                        clip_comments.append({
                            'text': c['text'],
                            'timestamp': c['timestamp'] - request.start
                        })
            
            if clip_comments:
                danmaku_ass_path = os.path.join(UPLOAD_DIR, f"{base_name}_clip_{safe_title}_danmaku.ass")
                from .video_processing import get_video_info
                v_info = get_video_info(video_path)
                w = v_info.get('width', 1920) or 1920
                h = v_info.get('height', 1080) or 1080
                
                # Load emoji mapping for the channel
                emoji_map = None
                emoji_dir = None
                info_file = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")
                if os.path.exists(info_file):
                    try:
                        with open(info_file, 'r', encoding='utf-8') as f_i:
                            v_info_json = json.load(f_i)
                            channel_id = v_info_json.get('channel_id')
                            if channel_id:
                                emoji_dir = os.path.join(EMOJIS_DIR, channel_id)
                                map_path = os.path.join(emoji_dir, "map.json")
                                if os.path.exists(map_path):
                                    with open(map_path, 'r', encoding='utf-8') as f_m:
                                        emoji_map = json.load(f_m)
                    except: pass

                danmaku_ass_path, emoji_overlays = generate_danmaku_ass(
                    clip_comments,
                    danmaku_ass_path,
                    resolution_x=w,
                    resolution_y=h,
                    emoji_map=emoji_map,
                    emoji_dir=emoji_dir
                )

        extract_clip(
            video_path, 
            request.start, 
            request.end, 
            output_path, 
            crop_params=crop_params, 
            danmaku_ass_path=danmaku_ass_path, 
            aspect_ratio=request.aspect_ratio,
            emoji_overlays=emoji_overlays if 'emoji_overlays' in locals() else None
        )

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

@app.post("/upload-prefix-image")
async def upload_prefix_image(file: UploadFile = File(...)):
    """Upload a prefix image for subtitle styles"""
    try:
        # Validate file type
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        file_extension = os.path.splitext(file.filename)[1].lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
            )

        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(PREFIX_IMAGES_DIR, unique_filename)

        # Save uploaded file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Return URL relative to the static mount
        image_url = f"/static/prefix_images/{unique_filename}"

        return {
            "success": True,
            "image_url": image_url,
            "filename": unique_filename
        }

    except Exception as e:
        logger.error(f"Error uploading prefix image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete-prefix-image/{filename}")
async def delete_prefix_image(filename: str):
    """Delete a prefix image"""
    try:
        # Security: Only allow deletion from prefix_images directory
        file_path = os.path.join(PREFIX_IMAGES_DIR, os.path.basename(filename))

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Image not found")

        os.remove(file_path)

        return {"success": True, "message": "Image deleted"}

    except Exception as e:
        logger.error(f"Error deleting prefix image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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

from .description_generator import generate_description, detect_members, get_all_members
from .twitter_generator import generate_twitter_pr_text

class DescriptionRequest(BaseModel):
    original_url: str
    original_title: str
    video_description: str = ""
    clip_title: Optional[str] = None

@app.post("/generate-description")
async def generate_video_description(request: DescriptionRequest):
    """Generate YouTube description for Hololive clip"""
    try:
        description = generate_description(
            original_url=request.original_url,
            original_title=request.original_title,
            video_description=request.video_description,
            clip_title=request.clip_title
        )

        # Also detect members for frontend display
        detected_members = detect_members(
            request.original_title,
            request.video_description
        )

        return {
            "description": description,
            "detected_members": detected_members
        }
    except Exception as e:
        logger.error(f"Error generating description: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class TwitterPRRequest(BaseModel):
    original_url: str
    original_title: str
    video_description: str = ""
    clip_title: Optional[str] = None

@app.post("/generate-twitter-pr")
async def generate_twitter_pr(request: TwitterPRRequest):
    """Generate Twitter PR text for Hololive clip"""
    try:
        pr_text = generate_twitter_pr_text(
            original_url=request.original_url,
            original_title=request.original_title,
            clip_title=request.clip_title,
            video_description=request.video_description
        )

        return {"pr_text": pr_text}
    except Exception as e:
        logger.error(f"Error generating Twitter PR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/hololive-members")
async def get_hololive_members():
    """Get list of all Hololive members"""
    try:
        members = get_all_members()
        return {"members": members}
    except Exception as e:
        logger.error(f"Error getting members: {e}")
        raise HTTPException(status_code=500, detail=str(e))
