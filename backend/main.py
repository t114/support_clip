from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional
import shutil
import os
import uuid
import requests
import datetime
import json
import logging
import re

from .paths import UPLOAD_DIR, PREFIX_IMAGES_DIR, SOUNDS_DIR, EMOJIS_DIR, ensure_dirs
from .transcribe import transcribe_video
from .subtitle_utils import parse_vtt_file, convert_vtt_to_srt, convert_srt_to_vtt
from .clip_detector import evaluate_clip_quality, detect_comment_density_clips
from .fcpxml_generator import generate_fcpxml
from .video_processing import get_video_info, burn_subtitles_with_ffmpeg
from .ass_generator import generate_ass, generate_danmaku_ass
from .progress import update_progress, get_progress, clear_progress
from .chat_utils import extract_comments
from .description_generator import generate_description, detect_members, get_all_members
from .twitter_generator import generate_twitter_pr_text

# Import routers
from .api_emojis import router as emojis_router
from .api_emojis import youtube_sync_router
from .api_styles import router as styles_router
from .api_youtube import router as youtube_router

ensure_dirs()
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static/sounds", StaticFiles(directory=SOUNDS_DIR), name="sounds")
app.mount("/static/emojis", StaticFiles(directory=EMOJIS_DIR), name="emojis")
app.mount("/static/prefix_images", StaticFiles(directory=PREFIX_IMAGES_DIR), name="prefix_images")
app.mount("/static", StaticFiles(directory=UPLOAD_DIR), name="static")

# Register Routers
app.include_router(emojis_router)
app.include_router(youtube_sync_router)
app.include_router(styles_router)
app.include_router(youtube_router)

@app.get("/")
async def root():
    return {"message": "Video Transcription API is running"}

@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    model_size: str = Form("base"),
    max_chars_per_line: int = Form(0)
):
    try:
        file_extension = os.path.splitext(file.filename)[1]
        if not file_extension:
            file_extension = ".mp4"

        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Video uploaded: {unique_filename}, model_size: {model_size}")

        if model_size == "none":
            return {
                "video_url": f"/static/{unique_filename}",
                "subtitle_url": None,
                "srt_url": None,
                "fcpxml_url": None,
                "filename": file.filename,
                "unique_filename": unique_filename
            }

        vtt_path = transcribe_video(file_path, model_size=model_size, max_chars_per_line=max_chars_per_line)
        srt_path = vtt_path.replace('.vtt', '.srt')

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

class BurnRequest(BaseModel):
    video_filename: str
    subtitle_content: str
    styles: dict
    saved_styles: Optional[dict] = None
    style_map: Optional[dict] = None
    with_danmaku: bool = False
    danmaku_density: int = 10
    sound_events: Optional[list] = None

@app.post("/burn")
async def burn_subtitles(request: BurnRequest):
    try:
        video_path = os.path.join(UPLOAD_DIR, request.video_filename)
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video not found")

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

        base_name = os.path.splitext(request.video_filename)[0]
        vtt_path = os.path.join(UPLOAD_DIR, f"{base_name}_modified.vtt")
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(request.subtitle_content)

        v_info = get_video_info(video_path)

        ass_path = os.path.join(UPLOAD_DIR, f"{base_name}_modified.ass")
        generate_ass(
            vtt_path, cleaned_styles, ass_path,
            saved_styles=cleaned_saved_styles,
            style_map=request.style_map,
            video_info=v_info
        )
        
        danmaku_ass_path = None
        emoji_overlays = None
        if request.with_danmaku:
            comments_data = extract_comments(base_name)

            if comments_data:
                density = getattr(request, 'danmaku_density', 100)
                if density < 100:
                    comments_data = [c for c in comments_data if (int(c['timestamp'] * 1000) % 100) < density]

                danmaku_ass_path = os.path.join(UPLOAD_DIR, f"{base_name}_danmaku.ass")
                w = v_info.get('width', 1920) or 1920
                h = v_info.get('height', 1080) or 1080
                
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
                    comments_data, danmaku_ass_path,
                    resolution_x=w, resolution_y=h,
                    emoji_map=emoji_map, emoji_dir=emoji_dir
                )

        processed_sounds = []
        if request.sound_events:
            for se in request.sound_events:
                if se.get('name'):
                    processed_sounds.append({
                        'path': os.path.join(SOUNDS_DIR, se['name']),
                        'time': float(se.get('time', 0)),
                        'volume': float(se.get('volume', 1.0))
                    })

        output_filename = f"{base_name}_burned.mp4"
        output_path = os.path.join(UPLOAD_DIR, output_filename)

        burn_subtitles_with_ffmpeg(
            video_path, ass_path, output_path,
            vtt_path=vtt_path,
            saved_styles=cleaned_saved_styles,
            style_map=request.style_map,
            default_style=cleaned_styles,
            upload_dir=UPLOAD_DIR,
            danmaku_ass_path=danmaku_ass_path,
            emoji_overlays=emoji_overlays,
            sound_events=processed_sounds
        )

        return {"filename": output_filename}
    except Exception as e:
        logger.error(f"Error burning subtitles: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{filename}")
async def download_video(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=file_path,
        filename=f"captioned_{filename}",
        media_type='application/octet-stream'
    )

@app.get("/progress/{video_id}")
async def get_video_progress(video_id: str):
    return get_progress(video_id)

@app.get("/api/sounds")
async def get_sounds():
    try:
        sounds = []
        if os.path.exists(SOUNDS_DIR):
            for filename in os.listdir(SOUNDS_DIR):
                if filename.lower().endswith(('.mp3', '.wav', '.ogg')):
                    sounds.append({
                        "name": filename,
                        "url": f"/static/sounds/{filename}"
                    })
        return {"sounds": sorted(sounds, key=lambda x: x["name"])}
    except Exception as e:
        logger.error(f"Error listing sounds: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-prefix-image")
async def upload_prefix_image(file: UploadFile = File(...)):
    try:
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
        file_extension = os.path.splitext(file.filename)[1].lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}")

        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(PREFIX_IMAGES_DIR, unique_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        image_url = f"/static/prefix_images/{unique_filename}"
        return {"success": True, "image_url": image_url, "filename": unique_filename}
    except Exception as e:
        logger.error(f"Error uploading prefix image: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/delete-prefix-image/{filename}")
async def delete_prefix_image(filename: str):
    try:
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
    from .clip_detector import analyze_transcript_with_ai
    test_segments = [
        {'start': 0.0, 'end': 5.0, 'text': 'テストセグメント1'},
        {'start': 5.0, 'end': 10.0, 'text': 'テストセグメント2'},
        {'start': 10.0, 'end': 15.0, 'text': 'テストセグメント3'},
    ]
    result = analyze_transcript_with_ai(test_segments, max_clips=1)
    return {"message": "Check backend logs for debug output", "result_count": len(result), "result": result}

class DescriptionRequest(BaseModel):
    original_url: str
    original_title: str
    video_description: str = ""
    clip_title: Optional[str] = None
    upload_date: Optional[str] = None

@app.post("/generate-description")
async def generate_video_description(request: DescriptionRequest):
    try:
        description = generate_description(
            original_url=request.original_url, original_title=request.original_title,
            video_description=request.video_description, clip_title=request.clip_title,
            upload_date=request.upload_date
        )
        detected_members = detect_members(request.original_title, request.video_description)
        return {"description": description, "detected_members": detected_members}
    except Exception as e:
        logger.error(f"Error generating description: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class TwitterPRRequest(BaseModel):
    original_url: str
    original_title: str
    video_description: str = ""
    clip_title: Optional[str] = None
    upload_date: Optional[str] = None

@app.post("/generate-twitter-pr")
async def generate_twitter_pr(request: TwitterPRRequest):
    try:
        pr_text = generate_twitter_pr_text(
            original_url=request.original_url, original_title=request.original_title,
            clip_title=request.clip_title, video_description=request.video_description,
            upload_date=request.upload_date
        )
        return {"pr_text": pr_text}
    except Exception as e:
        logger.error(f"Error generating Twitter PR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/hololive-members")
async def get_hololive_members():
    try:
        members = get_all_members()
        return {"members": members}
    except Exception as e:
        logger.error(f"Error getting members: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Extra YouTube routes not ported
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
        return evaluate_clip_quality(vtt_path, request.start, request.end)
    except Exception as e:
        logger.error(f"Error evaluating clip: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class TopStampsRequest(BaseModel):
    vtt_filename: Optional[str] = None
    video_filename: Optional[str] = None

@app.post("/youtube/top-stamps")
async def get_top_stamps(request: TopStampsRequest):
    try:
        from collections import Counter
        base_name = None
        if request.vtt_filename:
            base_name = os.path.splitext(request.vtt_filename)[0]
        elif request.video_filename:
            base_name = os.path.splitext(request.video_filename)[0]
        else:
            raise HTTPException(status_code=400, detail="Filename required")

        live_chat_path = os.path.join(UPLOAD_DIR, f"{base_name}.live_chat.json")
        info_json_path = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")

        comments_path = live_chat_path if os.path.exists(live_chat_path) else (
            info_json_path if os.path.exists(info_json_path) else None
        )
        if not comments_path:
            raise HTTPException(status_code=404, detail="コメントファイルが見つかりません。")

        stamp_counts = Counter()
        
        if comments_path.endswith('.live_chat.json'):
            with open(comments_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip(): continue
                    try:
                        data = json.loads(line)
                        if 'replayChatItemAction' not in data: continue
                        action_block = data['replayChatItemAction'].get('actions', [])
                        for act in action_block:
                            if 'addChatItemAction' in act:
                                item = act['addChatItemAction'].get('item', {})
                                if 'liveChatTextMessageRenderer' in item:
                                    runs = item['liveChatTextMessageRenderer'].get('message', {}).get('runs', [])
                                    for run in runs:
                                        if 'emoji' in run:
                                            emoji_data = run['emoji']
                                            scs = emoji_data.get('shortcuts', [])
                                            if scs:
                                                stamp_counts[scs[0]] += 1
                                        elif 'text' in run:
                                            text_stamps = re.findall(r':[a-zA-Z0-9_-]+:', run['text'])
                                            for ts in text_stamps:
                                                stamp_counts[ts] += 1
                    except: continue
        else:
            with open(comments_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for c in data.get('comments', []):
                text_stamps = re.findall(r':[a-zA-Z0-9_-]+:', c.get('text', ''))
                for ts in text_stamps:
                    stamp_counts[ts] += 1

        top_stamps = [{"shortcut": s, "count": c} for s, c in stamp_counts.most_common(20)]
        return {"top_stamps": top_stamps}
    except Exception as e:
        logger.error(f"Error in get_top_stamps: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class AnalyzeKusaRequest(BaseModel):
    vtt_filename: Optional[str] = None
    video_filename: Optional[str] = None
    clip_duration: int = 60
    start_time: float = 0

@app.post("/youtube/analyze-kusa")
async def analyze_kusa_clips(request: AnalyzeKusaRequest):
    from .api_youtube import analyze_stamps_clips, AnalyzeStampsRequest
    return await analyze_stamps_clips(AnalyzeStampsRequest(
        vtt_filename=request.vtt_filename,
        video_filename=request.video_filename,
        category="kusa",
        clip_duration=request.clip_duration,
        start_time=request.start_time
    ))

class AnalyzeCommentDensityRequest(BaseModel):
    vtt_filename: Optional[str] = None
    video_filename: Optional[str] = None
    clip_duration: int = 60
    start_time: float = 0

@app.post("/youtube/analyze-comment-density")
async def analyze_comment_density_clips(request: AnalyzeCommentDensityRequest):
    try:
        base_name = None
        video_path = None
        if request.vtt_filename:
            vtt_path = os.path.join(UPLOAD_DIR, request.vtt_filename)
            base_name = os.path.splitext(request.vtt_filename)[0]
        elif request.video_filename:
            video_path = os.path.join(UPLOAD_DIR, request.video_filename)
            base_name = os.path.splitext(request.video_filename)[0]
        else:
            raise HTTPException(status_code=400, detail="Either vtt_filename or video_filename must be provided")

        if not video_path:
            for ext in ['.mp4', '.webm', '.mkv', '.avi', '.mov']:
                candidate = os.path.join(UPLOAD_DIR, base_name + ext)
                if os.path.exists(candidate):
                    video_path = candidate
                    break

        if not video_path or not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video file not found")

        video_info = get_video_info(video_path)
        video_duration = video_info['duration']

        live_chat_path = os.path.join(UPLOAD_DIR, f"{base_name}.live_chat.json")
        info_json_path = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")

        comments_path = live_chat_path if os.path.exists(live_chat_path) else (
            info_json_path if os.path.exists(info_json_path) else None
        )
        if not comments_path:
            raise HTTPException(status_code=404, detail="コメントファイルが見つかりません。")

        clips = detect_comment_density_clips(
            comments_path=comments_path,
            video_duration=video_duration,
            clip_duration=request.clip_duration,
            start_time=request.start_time
        )

        if not clips:
            return {"clips": [], "message": "コメントを含むクリップが見つかりませんでした"}

        return {"clips": clips, "total_clips": len(clips), "message": f"コメント量が多い上位{len(clips)}件のクリップを検出しました"}
    except Exception as e:
        logger.error(f"Error analyzing comment density: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/youtube/upload-subtitle")
async def upload_subtitle(
    video_filename: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        video_path = os.path.join(UPLOAD_DIR, video_filename)
        if not os.path.exists(video_path):
            raise HTTPException(status_code=404, detail="Video file not found")

        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ['.vtt', '.srt']:
            raise HTTPException(status_code=400, detail="Only VTT or SRT files are supported")

        base_name = os.path.splitext(video_filename)[0]

        if file_extension == '.vtt':
            vtt_filename = f"{base_name}.vtt"
            vtt_path = os.path.join(UPLOAD_DIR, vtt_filename)
            srt_filename = f"{base_name}.srt"
            srt_path = os.path.join(UPLOAD_DIR, srt_filename)

            with open(vtt_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            convert_vtt_to_srt(vtt_path, srt_path)
        else:
            srt_filename = f"{base_name}.srt"
            srt_path = os.path.join(UPLOAD_DIR, srt_filename)
            vtt_filename = f"{base_name}.vtt"
            vtt_path = os.path.join(UPLOAD_DIR, vtt_filename)

            with open(srt_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            convert_srt_to_vtt(srt_path, vtt_path)

        segments = parse_vtt_file(vtt_path)
        fcpxml_filename = f"{base_name}.fcpxml"
        fcpxml_path = os.path.join(UPLOAD_DIR, fcpxml_filename)

        video_meta = get_video_info(video_path)
        generate_fcpxml(segments, fcpxml_path, video_path, fps=video_meta['fps'], duration_seconds=video_meta['duration'])

        return {
            "subtitle_url": f"/static/{vtt_filename}",
            "srt_url": f"/static/{srt_filename}",
            "fcpxml_url": f"/static/{fcpxml_filename}",
            "message": "字幕ファイルがアップロードされました"
        }
    except Exception as e:
        logger.error(f"Error uploading subtitle: {e}")
        raise HTTPException(status_code=500, detail=str(e))
