from faster_whisper import WhisperModel
import os
import requests
import subprocess
import gc
import sys

from .subtitle_utils import create_vtt_content, create_srt_content
from .streamer_context import detect_streamer_context
from .audio_utils import separate_vocals_uvr5, prepare_audio_for_whisper
from .transcript_correction import remove_repeated_segments, correct_transcript_segments

# Global variable to hold the current model and its size
current_model = None
current_model_size = None

def get_model(model_size: str):
    """
    Get the Whisper model instance.
    If the requested size is different from the current one, reload the model.
    """
    global current_model, current_model_size
    
    if current_model is not None and current_model_size == model_size:
        return current_model
    
    print(f"Loading Whisper model: {model_size}...")
    
    # Unload previous model if exists
    if current_model is not None:
        del current_model
        gc.collect()
    
    # Load new model
    # device="cpu" and compute_type="int8" for CPU inference
    try:
        current_model = WhisperModel(model_size, device="cpu", compute_type="int8")
        current_model_size = model_size
        return current_model
    except Exception as e:
        print(f"Error loading model {model_size}: {e}")
        # Fallback to base if loading fails (e.g. invalid size)
        if model_size != "base":
            print("Falling back to 'base' model...")
            return get_model("base")
        raise e

def transcribe_video(video_path: str, progress_callback=None, model_size: str = "base", max_chars_per_line: int = 0, external_url: str = None) -> str:
    """
    Transcribes the video and returns the path to the generated VTT file.
    Also generates an SRT file in the same location.
    
    Args:
        video_path: Path to the video file
        progress_callback: Optional function(progress_percent: float) to call during transcription
        model_size: Whisper model size (tiny, base, small, medium, large, external)
        max_chars_per_line: Maximum characters per subtitle line. If > 0, long segments will be split.
        external_url: URL for external API if model_size is 'external'
    """
    print(f"Transcribing {video_path} using model '{model_size}' (max_chars={max_chars_per_line})...")

    # ── Step1: UVR5 で BGM を除去（ボーカル・音声のみ抽出）──────────────────
    vocals_path, is_temp_vocals = separate_vocals_uvr5(video_path)
    # ─────────────────────────────────────────────────────────────────────────

    # ── 配信者コンテキスト取得（info.json と hololive_members.json を照合）──
    base_path_for_info = os.path.splitext(video_path)[0]
    info_json_path = base_path_for_info + '.info.json'
    streamer_ctx = detect_streamer_context(info_json_path if os.path.exists(info_json_path) else None)
    context_sentence = streamer_ctx.get('context_sentence', '')
    if context_sentence:
        print(f"[CONTEXT] {context_sentence.replace(chr(10), ' | ')}")
    # ─────────────────────────────────────────────────────────────────────────

    # ── Step2: 16kHz / mono WAV に変換（Whisper 精度向上）────────────────────
    audio_path, is_temp_wav = prepare_audio_for_whisper(vocals_path)
    # ─────────────────────────────────────────────────────────────────────────

    # UVR5 の出力が WAV 変換の入力になった場合、vocals_path は
    # prepare_audio_for_whisper() が新しい WAV を作ったので不要になる
    # （フォールバックで vocals_path == audio_path の場合は削除しない）
    if is_temp_vocals and vocals_path != audio_path and os.path.exists(vocals_path):
        try:
            os.remove(vocals_path)
            sys.stderr.write(f'[UVR5] Removed intermediate vocals file: {vocals_path}\\n')
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f'[UVR5] Could not remove vocals file: {e}\\n')
            sys.stderr.flush()
        is_temp_vocals = False  # 削除済みなのでフラグをクリア

    model = get_model(model_size)

    # Use word_timestamps only if splitting is requested to avoid overhead,
    # though it's generally useful.
    word_ts = max_chars_per_line > 0

    segments_list = []
    
    class SimpleSegment:
        def __init__(self, start, end, text):
            self.start = start
            self.end = end
            self.text = text

    if model_size == "external" and external_url:
        print(f"Using external API for transcription: {external_url}")
        audio_path = video_path + ".wav"
        try:
            if progress_callback:
                progress_callback(10)
            
            subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if progress_callback:
                progress_callback(30)
                
            with open(audio_path, "rb") as f:
                # URLに応じてリクエスト形式を切り替え
                if "/asr" in external_url:
                    # onerahmet/openai-whisper-asr-webservice 形式
                    response = requests.post(
                        external_url,
                        files={"audio_file": (os.path.basename(audio_path), f, "audio/wav")},
                        params={"task": "transcribe", "language": "ja", "output": "json", "word_timestamps": "true"},
                        timeout=3600
                    )
                else:
                    # OpenAI互換 (fedirz/faster-whisper-server など)
                    response = requests.post(
                        external_url,
                        files={"file": (os.path.basename(audio_path), f, "audio/wav")},
                        data={"model": "whisper-1", "response_format": "verbose_json", "language": "ja"},
                        timeout=3600
                )
                
                if response.status_code != 200:
                    raise Exception(f"External API error ({response.status_code}): {response.text}")
                    
                result = response.json()
                
                raw_segments = []
                if "segments" in result:
                    for seg in result["segments"]:
                        raw_segments.append(SimpleSegment(seg["start"], seg["end"], seg["text"]))
                else:
                    raw_segments.append(SimpleSegment(0, 0, result.get("text", "")))
                
                # Apply max_chars_per_line split logic
                for i, segment in enumerate(raw_segments):
                    text = segment.text.strip()
                    if max_chars_per_line > 0 and len(text) > max_chars_per_line:
                        num_splits = (len(text) + max_chars_per_line - 1) // max_chars_per_line
                        duration = segment.end - segment.start
                        for s in range(num_splits):
                            part_text = text[s*max_chars_per_line : (s+1)*max_chars_per_line]
                            part_start = segment.start + (s / num_splits) * duration
                            part_end = segment.start + ((s + 1) / num_splits) * duration
                            segments_list.append(SimpleSegment(part_start, part_end, part_text))
                    else:
                        segments_list.append(segment)
                    
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                
        if progress_callback:
            progress_callback(100)
            
    else:
        model = get_model(model_size)
        
        word_ts = max_chars_per_line > 0
        segments, info = model.transcribe(video_path, beam_size=5, word_timestamps=word_ts, language="ja")
        
        print(f"Detected language '{info.language}' with probability {info.language_probability}")
        
        total_duration = info.duration

        for i, segment in enumerate(segments):
            if total_duration and total_duration > 0:
                progress = min(99, (segment.end / total_duration) * 100)
                if progress_callback:
                    progress_callback(progress)
            
            text = segment.text.strip()
            if max_chars_per_line > 0 and len(text) > max_chars_per_line:
                if word_ts and hasattr(segment, 'words') and segment.words:
                    current_words = []
                    current_len = 0
                    for word in segment.words:
                        w_text = word.word.strip()
                        if not w_text:
                            continue
                        
                        if current_len + len(w_text) > max_chars_per_line and current_words:
                            s_start = current_words[0].start
                            s_end = current_words[-1].end
                            s_text = "".join([w.word for w in current_words]).strip()
                            segments_list.append(SimpleSegment(s_start, s_end, s_text))
                            
                            current_words = []
                            current_len = 0
                        
                        current_words.append(word)
                        current_len += len(w_text)
                    
                    if current_words:
                        s_start = current_words[0].start
                        s_end = current_words[-1].end
                        s_text = "".join([w.word for w in current_words]).strip()
                        segments_list.append(SimpleSegment(s_start, s_end, s_text))
                else:
                    num_splits = (len(text) + max_chars_per_line - 1) // max_chars_per_line
                    duration = segment.end - segment.start
                    for s in range(num_splits):
                        part_text = text[s*max_chars_per_line : (s+1)*max_chars_per_line]
                        part_start = segment.start + (s / num_splits) * duration
                        part_end = segment.start + ((s + 1) / num_splits) * duration
                        segments_list.append(SimpleSegment(part_start, part_end, part_text))
            else:
                segments_list.append(segment)
            
            if i % 50 == 0:
                print(f"Transcribed segment {i}: {segment.start:.1f}s - {segment.end:.1f}s")
                
        if progress_callback:
            progress_callback(100)

    # ── 一時 WAV ファイルを削除 ───────────────────────────────────────────────
    if is_temp_wav and os.path.exists(audio_path):
        try:
            os.remove(audio_path)
            sys.stderr.write(f'[AUDIO_PREP] Removed temp WAV: {audio_path}\\n')
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f'[AUDIO_PREP] Could not remove temp WAV: {e}\\n')
            sys.stderr.flush()
    # 念のため vocals の一時ファイルも確認・削除
    if is_temp_vocals and os.path.exists(vocals_path):
        try:
            os.remove(vocals_path)
            sys.stderr.write(f'[UVR5] Removed leftover vocals file: {vocals_path}\\n')
            sys.stderr.flush()
        except Exception:
            pass
    # ─────────────────────────────────────────────────────────────────────────

    print(f"Transcription complete. Total segments: {len(segments_list)}")
    
    # ── 繰り返しセグメント除去（ルールベース） ────────────────────────────────
    before_count = len(segments_list)
    segments_list = remove_repeated_segments(segments_list)
    print(f"[DEDUP] Removed {before_count - len(segments_list)} repeated segments ({before_count} → {len(segments_list)})")
    # ─────────────────────────────────────────────────────────────────────────

    # ── 誤字脱字・繰り返し訂正（Ollama） ────────────────────────────────────
    print("[CORRECTION] Starting transcript correction...")
    segments_list = correct_transcript_segments(segments_list, context=context_sentence)
    print("[CORRECTION] Transcript correction complete.")
    # ─────────────────────────────────────────────────────────────────────────
    
    # Generate VTT
    vtt_content = create_vtt_content(segments_list)
    base_path = os.path.splitext(video_path)[0]
    vtt_path = f"{base_path}.vtt"
    
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write(vtt_content)
        
    # Generate SRT
    srt_content = create_srt_content(segments_list)
    srt_path = f"{base_path}.srt"
    
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
        
    return vtt_path
