from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, Any
import os
import json
import shutil
import logging
import time
import re

from .paths import UPLOAD_DIR, SOUNDS_DIR, EMOJIS_DIR
from .chat_utils import extract_comments
from .video_processing import get_video_info
from .progress import update_progress, get_progress
from .youtube_downloader import download_youtube_video, download_low_quality_for_analysis, extract_video_id
from .clip_detector import (
    analyze_transcript_with_ai, detect_boundaries_hybrid, 
    evaluate_clip_quality, count_comments_in_clips, 
    detect_comment_density_clips, detect_emoji_density_clips
)
from .transcribe import transcribe_video, detect_streamer_context
from .fcpxml_generator import generate_fcpxml
from .video_clipper import extract_clip, capture_and_process_clip
from .ass_generator import generate_ass, generate_danmaku_ass
from .config import DEFAULT_MAX_CLIPS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/youtube", tags=["youtube"])

class YouTubeDownloadRequest(BaseModel):
    url: str
    with_comments: bool = False
    model_size: str = "base"
    analysis_mode: bool = False
    max_chars_per_line: int = 0
    external_transcribe_url: Optional[str] = None

@router.post("/download")
def download_youtube(request: YouTubeDownloadRequest):
    # Implementation copied from main.py
    logger.info(f"[YOUTUBE_DOWNLOAD] Endpoint called with URL: {request.url}, model_size: {request.model_size}")
    try:
        video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', request.url)
        video_id = video_id_match.group(1) if video_id_match else "unknown"
        
        current_progress = get_progress(video_id)
        current_status = current_progress.get("status")
        last_updated = current_progress.get("updated_at", 0)
        now = time.time()
        
        if current_status in ["downloading", "transcribing"] and (now - last_updated) < 120:
            while True:
                time.sleep(2)
                prog = get_progress(video_id)
                status = prog.get("status")
                
                if status == "completed":
                    break
                if status == "error":
                    raise HTTPException(status_code=500, detail=f"Previous job failed: {prog.get('message')}")
                if (time.time() - prog.get("updated_at", 0)) > 120:
                    break
        
        update_progress(video_id, "downloading", 0, "動画をダウンロード中...")
        
        if request.analysis_mode:
            video_info = download_low_quality_for_analysis(request.url, UPLOAD_DIR)
        else:
            video_info = download_youtube_video(request.url, UPLOAD_DIR, download_comments=request.with_comments)
        
        video_path = video_info.get("file_path")
        real_video_id = video_info.get("id", "unknown")
        if real_video_id != video_id:
            video_id = real_video_id
            
        update_progress(video_id, "downloading", 100, "ダウンロード完了")
        
        is_cached = video_info.get("cached", False)
        
        vtt_path = None
        srt_path = None
        fcpxml_filename = None
        base_name = None

        if video_path:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            vtt_filename = f"{base_name}.vtt"
            vtt_path = os.path.join(UPLOAD_DIR, vtt_filename)
            srt_filename = f"{base_name}.srt"
            srt_path = os.path.join(UPLOAD_DIR, srt_filename)
            
            if request.model_size == "none":
                update_progress(video_id, "completed", 100, "文字起こしをスキップしました")
                vtt_path = None
                srt_path = None
            elif not os.path.exists(vtt_path):
                update_progress(video_id, "transcribing", 0, "文字起こし準備中...")

                def progress_callback(percent):
                    update_progress(video_id, "transcribing", percent, f"文字起こし中... {int(percent)}%")

                vtt_path = transcribe_video(
                    video_path, 
                    progress_callback=progress_callback, 
                    model_size=request.model_size,
                    max_chars_per_line=request.max_chars_per_line,
                    external_url=request.external_transcribe_url
                )
                srt_path = vtt_path.replace('.vtt', '.srt')
                update_progress(video_id, "transcribing", 100, "文字起こし完了")
            else:
                update_progress(video_id, "completed", 100, "キャッシュを使用中")
            
            if vtt_path:
                from .subtitle_utils import parse_vtt_file
                segments = parse_vtt_file(vtt_path)
                fcpxml_filename = f"{base_name}.fcpxml"
                fcpxml_path = os.path.join(UPLOAD_DIR, fcpxml_filename)
                if not os.path.exists(fcpxml_path):
                    video_meta = get_video_info(video_path)
                    generate_fcpxml(segments, fcpxml_path, video_path, fps=video_meta['fps'], duration_seconds=video_meta['duration'])
        else:
            update_progress(video_id, "completed", 100, "アーカイブ処理待ち")
        
        update_progress(video_id, "completed", 100, "処理完了")

        response_data = {
            "video_url": f"/static/{os.path.basename(video_path)}" if video_path else None,
            "subtitle_url": f"/static/{os.path.basename(vtt_path)}" if vtt_path else None,
            "srt_url": f"/static/{os.path.basename(srt_path)}" if srt_path else None,
            "fcpxml_url": f"/static/{fcpxml_filename}" if fcpxml_filename else None,
            "filename": os.path.basename(video_path) if video_path else None,
            "video_info": video_info,
            "start_time": video_info.get("start_time", 0),
            "cached": is_cached,
            "has_comments": video_info.get("comments_file") is not None or (base_name and (os.path.exists(os.path.join(UPLOAD_DIR, f"{base_name}.live_chat.json")) or os.path.exists(os.path.join(UPLOAD_DIR, f"{base_name}.info.json"))))
        }
        return response_data
    except Exception as e:
        logger.error(f"Error downloading YouTube video: {e}")
        video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', request.url)
        if video_id_match:
             update_progress(video_id_match.group(1), "error", 0, f"エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/comments/{video_filename}")
async def get_video_comments(video_filename: str):
    base_name = os.path.splitext(video_filename)[0]
    comments = extract_comments(base_name)
    return {"comments": comments}

class CommentsRangeRequest(BaseModel):
    video_filename: str
    start: float
    end: float

@router.post("/comments/range")
async def get_comments_range(request: CommentsRangeRequest):
    try:
        base_name = os.path.splitext(request.video_filename)[0]
        all_comments = extract_comments(base_name)
        filtered_comments = [c for c in all_comments if request.start <= c['timestamp'] <= request.end]
        return {"comments": filtered_comments}
    except Exception as e:
        logger.error(f"Error fetching range comments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class AnalyzeRequest(BaseModel):
    vtt_filename: str
    max_clips: int = DEFAULT_MAX_CLIPS
    offset: int = 0
    start_time: float = 0
    ollama_host: Optional[str] = None
    ollama_model: Optional[str] = None

@router.post("/analyze")
async def analyze_video(request: AnalyzeRequest):
    try:
        vtt_path = os.path.join(UPLOAD_DIR, request.vtt_filename)
        if not os.path.exists(vtt_path):
            raise HTTPException(status_code=404, detail="Subtitle file not found")

        from .subtitle_utils import parse_vtt_file
        segments = parse_vtt_file(vtt_path)
        total_segments = len(segments)

        if request.start_time > 0:
            segments = [s for s in segments if s['start'] >= request.start_time]
            if not segments:
                raise HTTPException(status_code=400, detail=f"No segments found after start_time={request.start_time}s")

        base_path = os.path.splitext(vtt_path)[0]
        video_path = None
        for ext in ['.mp4', '.webm', '.mkv', '.avi', '.mov']:
            candidate = base_path + ext
            if os.path.exists(candidate):
                video_path = candidate
                break

        if not video_path:
            raise HTTPException(status_code=404, detail="Video file not found")

        base_name = os.path.splitext(request.vtt_filename)[0]
        comments = extract_comments(base_name)

        clips = detect_boundaries_hybrid(video_path, segments, request.max_clips, request.start_time)

        if comments:
            live_chat_path = os.path.join(UPLOAD_DIR, f"{base_name}.live_chat.json")
            info_json_path = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")
            comments_path = live_chat_path if os.path.exists(live_chat_path) else (
                info_json_path if os.path.exists(info_json_path) else None
            )
            if comments_path:
                clips = count_comments_in_clips(clips, comments_path)

        info_json_path_for_ctx = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")
        streamer_ctx = detect_streamer_context(info_json_path_for_ctx if os.path.exists(info_json_path_for_ctx) else None)
        context_sentence = streamer_ctx.get('context_sentence', '')

        try:
            ai_clips = analyze_transcript_with_ai(
                segments=segments,
                max_clips=request.max_clips,
                start_time=request.start_time,
                comments=comments,
                context=context_sentence,
                ollama_host=request.ollama_host,
                ollama_model=request.ollama_model
            )
            if comments and ai_clips:
                for ai_clip in ai_clips:
                    clip_comments = [c for c in comments if ai_clip['start'] <= c.get('timestamp', -1) <= ai_clip['end']]
                    ai_clip['comment_count'] = len(clip_comments)
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            ai_clips = []

        for clip in clips + ai_clips:
            try:
                evaluation = evaluate_clip_quality(
                    vtt_path, clip['start'], clip['end'],
                    ollama_host=request.ollama_host,
                    ollama_model=request.ollama_model
                )
                clip['evaluation_score'] = evaluation['score']
                clip['evaluation_reason'] = evaluation['reason']
            except Exception as e:
                clip['evaluation_score'] = 3
                clip['evaluation_reason'] = "評価に失敗しました"

        return {
            "clips": clips,
            "ai_clips": ai_clips,
            "total_segments": total_segments,
            "analyzed_segments": total_segments,
            "has_more": False,
            "next_offset": None
        }
    except Exception as e:
        logger.error(f"Error analyzing video: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class AnalyzeStampsRequest(BaseModel):
    vtt_filename: Optional[str] = None
    video_filename: Optional[str] = None
    category: Optional[str] = "kusa"
    custom_patterns: Optional[list] = None
    clip_duration: int = 60
    start_time: float = 0

@router.post("/analyze-stamps")
async def analyze_stamps_clips(request: AnalyzeStampsRequest):
    # Implementation adapted from main.py
    try:
        base_name = None
        video_path = None
        
        if request.vtt_filename:
            base_name = os.path.splitext(request.vtt_filename)[0]
        elif request.video_filename:
            base_name = os.path.splitext(request.video_filename)[0]
        else:
            raise HTTPException(status_code=400, detail="Either vtt_filename or video_filename must be provided")

        for ext in ['.mp4', '.webm', '.mkv', '.avi', '.mov']:
            candidate = os.path.join(UPLOAD_DIR, base_name + ext)
            if os.path.exists(candidate):
                video_path = candidate
                break

        if not video_path:
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

        custom_patterns = request.custom_patterns or []
        if request.category:
            try:
                if os.path.exists(info_json_path):
                    with open(info_json_path, 'r', encoding='utf-8') as f:
                        v_data = json.load(f)
                        channel_id = v_data.get('channel_id')
                        if channel_id:
                            configs_file = os.path.join(EMOJIS_DIR, channel_id, "configs.json")
                            if os.path.exists(configs_file):
                                with open(configs_file, "r", encoding='utf-8') as f:
                                    c_data = json.load(f)
                                    for shortcut, categories in c_data.items():
                                        if request.category in categories and shortcut not in custom_patterns:
                                            custom_patterns.append(shortcut)
            except: pass

        clips = detect_emoji_density_clips(
            comments_path=comments_path,
            video_duration=video_duration,
            category=request.category,
            custom_patterns=custom_patterns,
            clip_duration=request.clip_duration,
            start_time=request.start_time
        )

        return {
            "clips": clips,
            "total_clips": len(clips),
            "message": f"{request.category if request.category else 'スタンプ'}盛り上がり上位{len(clips)}件を検出しました"
        }
    except Exception as e:
        logger.error(f"Error in analyze_stamps_clips: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Note: Added /create-clip, /evaluate-clip, /upload-subtitle, etc below to fully migrate routes

class ClipRequest(BaseModel):
    video_filename: Optional[str] = None
    url: Optional[str] = None
    start: float
    end: float
    title: str
    crop_x: Optional[float] = None
    crop_y: Optional[float] = None
    crop_width: Optional[float] = None
    crop_height: Optional[float] = None
    crop2_x: Optional[float] = None
    crop2_y: Optional[float] = None
    crop2_width: Optional[float] = None
    crop2_height: Optional[float] = None
    split_ratio: Optional[float] = 0.5
    use_obs_capture: bool = False
    with_danmaku: bool = False
    danmaku_density: int = 10
    aspect_ratio: Optional[str] = None
    letterbox_align: Optional[Any] = 50
    sound_events: Optional[list] = None
    subtitle_content: Optional[str] = None
    styles: Optional[dict] = None
    saved_styles: Optional[dict] = None
    style_map: Optional[dict] = None

@router.post("/create-clip")
async def create_clip(request: ClipRequest):
    try:
        logger.info(f"Create clip request: {request.dict()}")
        video_path = os.path.join(UPLOAD_DIR, request.video_filename) if request.video_filename else None
        
        if not request.use_obs_capture:
            if not video_path or not os.path.exists(video_path):
                raise HTTPException(status_code=404, detail="Video not found and direct extraction requested")
        elif not video_path or not os.path.exists(video_path):
            if not request.url:
                 raise HTTPException(status_code=404, detail="Video not found and no YouTube URL provided for OBS capture")

        base_name = os.path.splitext(request.video_filename)[0] if request.video_filename else (extract_video_id(request.url) if request.url else "clip")
        safe_title = "".join([c for c in request.title if c.isalnum() or c in (' ', '-', '_')]).strip()
        output_filename = f"{base_name}_clip_{safe_title}.mp4"
        output_path = os.path.join(UPLOAD_DIR, output_filename)

        analysis_w = 1920
        analysis_h = 1080
        if video_path and os.path.exists(video_path):
            v_info_analysis = get_video_info(video_path)
            analysis_w = v_info_analysis.get('width', 1920) or 1920
            analysis_h = v_info_analysis.get('height', 1080) or 1080

        scale_x = 1.0
        scale_y = 1.0
        if request.use_obs_capture and analysis_w < 1920:
            scale_x = 1920 / analysis_w
            scale_y = 1080 / analysis_h

        crop_params = None
        if request.crop_width is not None and request.crop_height is not None:
            crop_params = {
                'x': (request.crop_x or 0) * scale_x,
                'y': (request.crop_y or 0) * scale_y,
                'width': request.crop_width * scale_x,
                'height': request.crop_height * scale_y
            }

        secondary_crop_params = None
        if request.crop2_width is not None and request.crop2_height is not None:
            secondary_crop_params = {
                'x': (request.crop2_x or 0) * scale_x,
                'y': (request.crop2_y or 0) * scale_y,
                'width': request.crop2_width * scale_x,
                'height': request.crop2_height * scale_y
            }

        danmaku_ass_path = None
        emoji_overlays = None
        if request.with_danmaku:
            all_comments = extract_comments(base_name)
            clip_comments = []
            density = request.danmaku_density
            for c in all_comments:
                if request.start <= c['timestamp'] <= request.end:
                    if (int(c['timestamp'] * 1000) % 100) < density:
                        clip_comments.append({
                            'text': c['text'],
                            'timestamp': c['timestamp'] - request.start
                        })
            
            if clip_comments:
                danmaku_ass_path = os.path.join(UPLOAD_DIR, f"{base_name}_clip_{safe_title}_danmaku.ass")
                
                if request.use_obs_capture:
                    output_w, output_h = 1920, 1080
                else:
                    output_w = analysis_w
                    output_h = analysis_h

                if request.aspect_ratio in ['9:16', 'stacked']:
                    w, h = 720, 1280
                elif crop_params and crop_params['width'] and crop_params['height']:
                    w, h = int(crop_params['width']), int(crop_params['height'])
                else:
                    w, h = output_w, output_h

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

        ass_path = None
        if request.subtitle_content and request.styles:
            ass_path = os.path.join(UPLOAD_DIR, f"{base_name}_clip_{safe_title}_subs.ass")
            
            if request.use_obs_capture:
                output_w, output_h = 1920, 1080
            else:
                output_w = analysis_w
                output_h = analysis_h

            if request.aspect_ratio in ['9:16', 'stacked']:
                w, h = 720, 1280
            elif crop_params and crop_params['width'] and crop_params['height']:
                w, h = int(crop_params['width']), int(crop_params['height'])
            else:
                w, h = output_w, output_h
            
            temp_vtt = ass_path + ".vtt"
            with open(temp_vtt, "w", encoding="utf-8") as f_v:
                f_v.write(request.subtitle_content)
            
            generate_ass(
                temp_vtt, request.styles, ass_path,
                saved_styles=request.saved_styles,
                style_map=request.style_map,
                video_info={"width": w, "height": h}
            )
            try: os.remove(temp_vtt)
            except: pass

        processed_sounds = []
        if request.sound_events:
            for se in request.sound_events:
                if se.get('name'):
                    processed_sounds.append({
                        'path': os.path.join(SOUNDS_DIR, se['name']),
                        'time': float(se.get('time', 0))
                    })

        if request.use_obs_capture:
            url = request.url
            if not url:
                info_file = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")
                if os.path.exists(info_file):
                     try:
                         with open(info_file, 'r') as f:
                              info = json.load(f)
                              url = info.get('webpage_url') or info.get('original_url')
                              if not url and info.get('id'):
                                   url = f"https://www.youtube.com/watch?v={info.get('id')}"
                     except: pass

            if url:
                 try:
                     output_path = capture_and_process_clip(
                          url, request.start, request.end, output_path,
                          crop_params=crop_params,
                          secondary_crop_params=secondary_crop_params,
                          split_ratio=request.split_ratio,
                          ass_path=ass_path,
                          danmaku_ass_path=danmaku_ass_path,
                          aspect_ratio=request.aspect_ratio,
                          letterbox_align=request.letterbox_align,
                          emoji_overlays=emoji_overlays,
                          sound_events=processed_sounds
                     )
                     return {
                         "video_url": f"/static/{output_filename}",
                         "filename": output_filename
                     }
                 except Exception as obs_err:
                     logger.error(f"OBS capture failed: {obs_err}")
                     raise HTTPException(status_code=503, detail="OBSに接続できませんでした。")
            else:
                 raise HTTPException(status_code=400, detail="OBSキャプチャが要求されましたが、YouTube URLが見つかりませんでした。")

        output_path = extract_clip(
            video_path, request.start, request.end, output_path, 
            crop_params=crop_params, 
            secondary_crop_params=secondary_crop_params,
            split_ratio=request.split_ratio,
            ass_path=ass_path,
            danmaku_ass_path=danmaku_ass_path, 
            aspect_ratio=request.aspect_ratio,
            letterbox_align=request.letterbox_align,
            emoji_overlays=emoji_overlays,
            sound_events=processed_sounds
        )

        return {
            "video_url": f"/static/{output_filename}",
            "filename": output_filename
        }

    except Exception as e:
        logger.error(f"Error creating clip: {e}")
        raise HTTPException(status_code=500, detail=str(e))
