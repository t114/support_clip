from faster_whisper import WhisperModel
import os
import requests
import subprocess
import sys
import json
import tempfile

# Load the model globally to avoid reloading it for every request
# Using 'base' for faster processing speed (good balance of speed and accuracy)
import gc

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

def format_timestamp(seconds: float) -> str:
    """Convert seconds to WebVTT timestamp format (HH:MM:SS.mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

def create_vtt_content(segments) -> str:
    """Create WebVTT content from segments"""
    vtt_output = ["WEBVTT", ""]
    for segment in segments:
        start = format_timestamp(segment.start)
        end = format_timestamp(segment.end)
        vtt_output.append(f"{start} --> {end}")
        vtt_output.append(segment.text.strip())
        vtt_output.append("")
    return "\n".join(vtt_output)

def create_srt_content(segments) -> str:
    """Create SRT content from segments"""
    srt_output = []
    for i, segment in enumerate(segments, start=1):
        # SRT format: 00:00:00,000
        start = format_timestamp(segment.start).replace('.', ',')
        end = format_timestamp(segment.end).replace('.', ',')
        srt_output.append(str(i))
        srt_output.append(f"{start} --> {end}")
        srt_output.append(segment.text.strip())
        srt_output.append("")
        
    return "\n".join(srt_output)

# hololive_members.json のパス（transcribe.py と同ディレクトリ）
_MEMBERS_JSON_PATH = os.path.join(os.path.dirname(__file__), 'hololive_members.json')
_members_cache: list | None = None


def _load_hololive_members() -> list:
    """hololive_members.json をキャッシュして返す。"""
    global _members_cache
    if _members_cache is not None:
        return _members_cache
    try:
        with open(_MEMBERS_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _members_cache = data.get('members', [])
        sys.stderr.write(f'[CONTEXT] Loaded {len(_members_cache)} hololive members\n')
    except Exception as e:
        sys.stderr.write(f'[CONTEXT] Could not load hololive_members.json: {e}\n')
        _members_cache = []
    sys.stderr.flush()
    return _members_cache


def detect_streamer_context(info_json_path: str | None) -> dict:
    """
    info.json から配信者・コンテンツ情報を取得し、ホロライブメンバーと照合する。

    Returns:
        {
          'streamer_name': 'さくらみこ',       # 配信者名（日本語）
          'generation': '1期生',               # ホロライブ世代
          'game_title': 'マリオカート 8 DX',   # ゲームタイトル（抽出できた場合）
          'channel_name': '...',               # チャンネル名（生）
          'video_title': '...',                # 動画タイトル
          'context_sentence': '...',           # LLMに渡す前提文
          'is_hololive': True,                 # ホロライブメンバーか否か
        }
    """
    result = {
        'streamer_name': None,
        'generation': None,
        'game_title': None,
        'channel_name': None,
        'video_title': None,
        'context_sentence': '',
        'is_hololive': False,
    }

    if not info_json_path or not os.path.exists(info_json_path):
        return result

    try:
        with open(info_json_path, 'r', encoding='utf-8') as f:
            info = json.load(f)
    except Exception as e:
        sys.stderr.write(f'[CONTEXT] Failed to read info.json: {e}\n')
        sys.stderr.flush()
        return result

    channel_url  = info.get('channel_url', '') or ''
    channel_name = info.get('uploader', '') or info.get('channel', '') or ''
    video_title  = info.get('title', '') or ''
    description  = info.get('description', '') or ''
    channel_id   = info.get('channel_id', '') or ''

    result['channel_name'] = channel_name
    result['video_title']  = video_title

    # ── ホロライブメンバー照合 ─────────────────────────────────────────────
    members = _load_hololive_members()
    matched_member = None

    # 1. チャンネルURLで完全一致
    for member in members:
        member_url = member.get('channel_url', '')
        if member_url and channel_url:
            m_handle = member_url.rstrip('/').split('/')[-1].lower()
            c_handle = channel_url.rstrip('/').split('/')[-1].lower()
            if m_handle == c_handle:
                matched_member = member
                break

    # 2. チャンネル名での完全一致/キーワード一致
    if not matched_member:
        for member in members:
            for kw in member.get('keywords', []):
                if kw in channel_name:
                    matched_member = member
                    break
            if matched_member:
                break

    # 3. タイトルでのキーワード一致
    if not matched_member:
        for member in members:
            for kw in member.get('keywords', []):
                if kw in video_title:
                    matched_member = member
                    break
            if matched_member:
                break

    # 4. 概要欄でのフルネーム一致（誤検出を防ぐためキーワードではなくフルネームを使用）
    if not matched_member:
        for member in members:
            if member.get('name_ja') in description[:500]:
                matched_member = member
                break

    if matched_member:
        result['is_hololive']    = True
        result['streamer_name']  = matched_member.get('name_ja', channel_name)
        result['generation']     = matched_member.get('generation', '')
        sys.stderr.write(
            f"[CONTEXT] Matched hololive member: {result['streamer_name']} ({result['generation']})\n"
        )
    else:
        result['streamer_name'] = channel_name
        sys.stderr.write(f'[CONTEXT] Not a hololive member, using channel name: {channel_name}\n')
    sys.stderr.flush()

    # ── ゲームタイトル抽出 ────────────────────────────────────────────────
    # yt-dlp の info.json には 'categories' / 'tags' / 'game' フィールドがある場合がある
    game = (info.get('game') or info.get('game_title') or
            info.get('categories', [None])[0] if info.get('categories') else None)
    if not game:
        # タイトルから【ゲーム名】や「ゲーム名」パターンを抽出
        import re
        m = re.search(r'[【「『]([^】」』]{1,30})[】」』]', video_title)
        if m:
            candidate = m.group(1)
            # 「雑談」「コラボ」等の非ゲームキーワードを除外
            SKIP = {'雑談', 'コラボ', '歌枠', '歌配信', 'Vtuber', 'ホロライブ', '告知', 'お知らせ'}
            if candidate not in SKIP:
                game = candidate
    result['game_title'] = game

    # ── 前提文の組み立て ──────────────────────────────────────────────────
    parts = []
    if result['is_hololive']:
        parts.append(f"これはホロライブ{result['generation']}の{result['streamer_name']}さんの配信です。")
    elif result['streamer_name']:
        parts.append(f"これは{result['streamer_name']}さんの配信です。")

    if result['game_title']:
        parts.append(f"配信コンテンツ: {result['game_title']}")
    elif video_title:
        parts.append(f"配信タイトル: {video_title[:80]}")

    result['context_sentence'] = '\n'.join(parts)
    sys.stderr.write(f"[CONTEXT] Context: {result['context_sentence']!r}\n")
    sys.stderr.flush()

    return result


# UVR5に使用するデフォルトモデル（MDX-Netを推奨。初回起動時に自動ダウンロードされる）
# 他の選捗舂: 'UVR_MDXNET_KARA_2.onnx' / 'Kim_Vocal_2.onnx' / 'htdemucs'
UVR5_MODEL = 'UVR-MDX-NET-Inst_HQ_3.onnx'



def separate_vocals_uvr5(audio_path: str) -> tuple[str, bool]:
    """
    UVR5 (audio-separator) を使って BGM を除去し、ボーカル・音声のみのファイルを返す。

    audio-separator ライブラリがインストールされていない場合やエラー時は元のパスをそのまま返す。

    Returns:
        (vocals_path, is_temp): vocals_path はボーカルのみの音声ファイルパス。
                               is_temp=True の場合は使用後に削除が必要。
    """
    try:
        from audio_separator.separator import Separator
    except ImportError:
        sys.stderr.write('[UVR5] audio-separator not installed, skipping vocal separation\n')
        sys.stderr.flush()
        return audio_path, False

    # 出力ディレクトリは入力ファイルと同じ場所
    output_dir = os.path.dirname(os.path.abspath(audio_path))
    base_name = os.path.splitext(os.path.basename(audio_path))[0]

    sys.stderr.write(f'[UVR5] Separating vocals with model: {UVR5_MODEL}\n')
    sys.stderr.write(f'[UVR5] Input: {audio_path}\n')
    sys.stderr.flush()

    try:
        separator = Separator(
            output_dir=output_dir,
            output_format='WAV',
            normalization_threshold=0.9,
            output_single_stem='Vocals',   # Vocals ステムのみ出力
            log_level=40,                  # WARNING以上のみ表示
        )
        separator.load_model(UVR5_MODEL)

        # separate() は [primary, secondary] のファイルパスリストを返す
        output_files = separator.separate(audio_path)

        sys.stderr.write(f'[UVR5] Output files: {output_files}\n')
        sys.stderr.flush()

        # ボーカルファイルを探す（"Vocals"を含むファイル名）
        vocals_path = None
        for f in output_files:
            abs_f = f if os.path.isabs(f) else os.path.join(output_dir, f)
            if os.path.exists(abs_f) and 'Vocals' in os.path.basename(abs_f):
                vocals_path = abs_f
                break

        # 見つからなければ先頭の出力ファイルを使用
        if vocals_path is None and output_files:
            vocals_path = (output_files[0] if os.path.isabs(output_files[0])
                           else os.path.join(output_dir, output_files[0]))

        if vocals_path and os.path.exists(vocals_path):
            size_mb = os.path.getsize(vocals_path) / 1024 / 1024
            sys.stderr.write(f'[UVR5] Vocals extracted: {vocals_path} ({size_mb:.1f} MB)\n')
            sys.stderr.flush()

            # Instrumental (伴奏) ファイルがあれば即座に削除（不要）
            for f in output_files:
                abs_f = f if os.path.isabs(f) else os.path.join(output_dir, f)
                if abs_f != vocals_path and os.path.exists(abs_f):
                    try:
                        os.remove(abs_f)
                        sys.stderr.write(f'[UVR5] Removed instrumental: {abs_f}\n')
                    except Exception:
                        pass
            sys.stderr.flush()
            return vocals_path, True
        else:
            sys.stderr.write('[UVR5] Vocals file not found in output, using original\n')
            sys.stderr.flush()
            return audio_path, False

    except Exception as e:
        sys.stderr.write(f'[UVR5] Separation failed: {e}\n')
        sys.stderr.flush()
        return audio_path, False


def prepare_audio_for_whisper(video_path: str) -> tuple[str, bool]:
    """
    Whisperの認識精度向上のため、入力ファイルを 16,000Hz / mono の WAV に変換する。
    ffmpeg がインストールされていない場合は元のパスをそのまま返す。

    Returns:
        (audio_path, is_temp): audio_path は渡すべきファイルパス。
                               is_temp=True の場合は使用後に削除が必要。
    """
    try:
        # ffmpeg が使えるか確認
        subprocess.run(
            ['ffmpeg', '-version'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.stderr.write('[AUDIO_PREP] ffmpeg not found, skipping WAV conversion\n')
        sys.stderr.flush()
        return video_path, False

    # 一時 WAV ファイルを入力動画と同じディレクトリに作成
    base = os.path.splitext(video_path)[0]
    wav_path = f'{base}.__whisper_tmp__.wav'

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-ac', '1',          # mono
        '-ar', '16000',      # 16 kHz
        '-sample_fmt', 's16',  # 16-bit PCM
        '-vn',               # 映像トラック除外
        wav_path,
    ]

    sys.stderr.write(f'[AUDIO_PREP] Converting to 16kHz mono WAV: {wav_path}\n')
    sys.stderr.flush()

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=600,  # 10分タイムアウト
        )
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', errors='replace')[-500:]
            sys.stderr.write(f'[AUDIO_PREP] ffmpeg error: {err}\n')
            sys.stderr.flush()
            return video_path, False

        wav_size_mb = os.path.getsize(wav_path) / 1024 / 1024
        sys.stderr.write(f'[AUDIO_PREP] WAV ready: {wav_size_mb:.1f} MB\n')
        sys.stderr.flush()
        return wav_path, True

    except subprocess.TimeoutExpired:
        sys.stderr.write('[AUDIO_PREP] ffmpeg timed out, using original file\n')
        sys.stderr.flush()
        if os.path.exists(wav_path):
            os.remove(wav_path)
        return video_path, False
    except Exception as e:
        sys.stderr.write(f'[AUDIO_PREP] Unexpected error: {e}\n')
        sys.stderr.flush()
        return video_path, False


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
            sys.stderr.write(f'[UVR5] Removed intermediate vocals file: {vocals_path}\n')
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f'[UVR5] Could not remove vocals file: {e}\n')
            sys.stderr.flush()
        is_temp_vocals = False  # 削除済みなのでフラグをクリア

    model = get_model(model_size)

    # Use word_timestamps only if splitting is requested to avoid overhead,
    # though it's generally useful.
    word_ts = max_chars_per_line > 0

    # faster-whisper returns a generator of segments
    segments, info = model.transcribe(audio_path, beam_size=5, word_timestamps=word_ts)
    
    print(f"Detected language '{info.language}' with probability {info.language_probability}")
    
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
            sys.stderr.write(f'[AUDIO_PREP] Removed temp WAV: {audio_path}\n')
            sys.stderr.flush()
        except Exception as e:
            sys.stderr.write(f'[AUDIO_PREP] Could not remove temp WAV: {e}\n')
            sys.stderr.flush()
    # 念のため vocals の一時ファイルも確認・削除
    if is_temp_vocals and os.path.exists(vocals_path):
        try:
            os.remove(vocals_path)
            sys.stderr.write(f'[UVR5] Removed leftover vocals file: {vocals_path}\n')
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


def remove_repeated_segments(segments: list, similarity_threshold: float = 0.85) -> list:
    """
    連続する重複・類似セグメントをルールベースで除去する。
    Whisperが同じフレーズを繰り返し出力する問題を修正。

    処理の流れ:
        1. 空・空白セグメントを除去（空セグメントがdedup連鎖を切る問題を解消）
        2. セグメント内繰り返しフレーズを修正
        3. ウィンドウ8のdedup（直近8セグメントと比較）

    Args:
        segments: セグメントのリスト
        similarity_threshold: 類似度がこの値以上なら重複とみなす (0〜1)

    Returns:
        重複除去済みセグメントのリスト
    """
    import re

    WINDOW_SIZE = 8  # 直近何個のセグメントを重複チェック対象にするか

    def normalize(text: str) -> str:
        """比較用に正規化（空白・句読点・記号除去、小文字化）"""
        text = re.sub(r'[\s　、。，．！？!?,.*★☆【】「」『』（）()]', '', text)
        return text.lower()

    def jaccard(a: str, b: str) -> float:
        """簡易文字レベルのJaccard類似度"""
        na, nb = normalize(a), normalize(b)
        if not na and not nb:
            return 1.0
        if not na or not nb:
            return 0.0
        set_a, set_b = set(na), set(nb)
        return len(set_a & set_b) / len(set_a | set_b)

    def remove_intra_repetition(text: str) -> str:
        """
        セグメント内の繰り返しフレーズを除去する。
        例:
          "そうですねそうですねそうですね" → "そうですね"
          "ありがとう ありがとう ありがとう" → "ありがとう"
          "渡め渡め渡め渡め渡め渡め渡め渡め渡め渡め渡め渡" → "渡め"
        """
        if not text:
            return text

        # スペース区切りの単語レベル繰り返し（最低3回分）
        words = text.split()
        if len(words) >= 4:
            half = len(words) // 2
            for rep_len in range(1, half + 1):
                pattern = words[:rep_len]
                chunks = [words[i:i+rep_len] for i in range(0, len(words), rep_len)]
                # 各chunkがpatternの先頭と一致し、3回以上繰り返すなら除去
                if (len(chunks) >= 3 and
                        all(c == pattern[:len(c)] for c in chunks)):
                    return ' '.join(pattern)

        # 文字列レベルの繰り返し（スペースなし日本語向け）
        n = len(text)
        for rep_len in range(2, n // 2 + 1):
            chunk = text[:rep_len]
            # 完全繰り返し
            if n % rep_len == 0 and chunk * (n // rep_len) == text:
                return chunk
            # 端数ありの繰り返し（例: "渡め" × 11 + "渡"）
            reps = n // rep_len
            if reps >= 3 and text.startswith(chunk * reps):
                return chunk

        return text

    if not segments:
        return segments

    # ── Step 1: 空・空白のみのセグメントを除去 ──────────────────────────────
    non_empty = []
    for seg in segments:
        text = (seg.text if hasattr(seg, 'text') else seg['text']).strip()
        if text:
            non_empty.append(seg)

    removed_empty = len(segments) - len(non_empty)
    if removed_empty > 0:
        sys.stderr.write(f"[DEDUP] Removed {removed_empty} empty/whitespace segments\n")

    if not non_empty:
        return segments  # 全部空なら元を返す

    # ── Step 2: セグメント内繰り返し除去 ───────────────────────────────────
    for seg in non_empty:
        text = (seg.text if hasattr(seg, 'text') else seg['text']).strip()
        cleaned = remove_intra_repetition(text)
        if cleaned != text:
            sys.stderr.write(f"[DEDUP] Intra-segment fixed: {text!r} -> {cleaned!r}\n")
            if hasattr(seg, 'text'):
                seg.text = cleaned
            else:
                seg['text'] = cleaned

    # ── Step 3: ウィンドウベースの重複除去 ──────────────────────────────────
    # 直近 WINDOW_SIZE 個のセグメントと比較し、重複なら除去する。
    # ウィンドウを広げることで、空セグメントで連鎖が切れる問題を解消する。
    deduped = []

    for seg in non_empty:
        curr_text = (seg.text if hasattr(seg, 'text') else seg['text']).strip()
        curr_norm = normalize(curr_text)

        is_dup = False
        for prev in deduped[-WINDOW_SIZE:]:
            prev_text = (prev.text if hasattr(prev, 'text') else prev['text']).strip()
            prev_norm = normalize(prev_text)

            # 完全一致
            if curr_norm and curr_norm == prev_norm:
                sys.stderr.write(f"[DEDUP] Exact-window removed: {curr_text!r}\n")
                is_dup = True
                break

            # Jaccard類似度（短いテキストはより積極的に除去）
            sim = jaccard(curr_text, prev_text)
            thr = similarity_threshold if len(curr_norm) > 5 else 0.75
            if sim >= thr:
                sys.stderr.write(f"[DEDUP] Similar-window removed (sim={sim:.2f}): {curr_text!r}\n")
                is_dup = True
                break

            # 前のセグメントに包含される短いセグメント（正規化後5文字以下）
            if curr_norm and len(curr_norm) <= 5 and curr_norm in prev_norm:
                sys.stderr.write(f"[DEDUP] Substring-window removed: {curr_text!r}\n")
                is_dup = True
                break

        if not is_dup:
            deduped.append(seg)

    sys.stderr.write(
        f"[DEDUP] {len(segments)} segs -> {len(non_empty)} (empty removed) -> {len(deduped)} (deduped)\n"
    )
    sys.stderr.flush()
    return deduped

def correct_transcript_segments(segments: list, batch_size: int = 30,
                                context: str = '') -> list:
    """
    文字起こしセグメントの誤字脱字・変換ミスをOllamaで訂正する。
    タイムスタンプはそのままに、テキストのみ修正する。

    Args:
        segments: SimpleSegment またはオブジェクトのリスト
        batch_size: 一度にOllamaへ送るセグメント数
        context: 配信者・コンテンツ情報の前提文（プロンプトに挿入される）

    Returns:
        訂正済みセグメントのリスト（タイムスタンプ保持）
    """
    try:
        import ollama
        from .config import OLLAMA_MODEL, OLLAMA_HOST
    except ImportError as e:
        sys.stderr.write(f"[CORRECTION] Import error: {e}. Skipping correction.\n")
        return segments

    corrected_all = []

    for batch_start in range(0, len(segments), batch_size):
        batch = segments[batch_start: batch_start + batch_size]

        # バッチのテキストをJSON配列で送る
        texts = []
        for seg in batch:
            t = seg.text if hasattr(seg, 'text') else seg['text']
            texts.append(t.strip())

        indexed_input = json.dumps(texts, ensure_ascii=False)

        prompt = f"""あなたは日本語の誤字脱字・音声認識ミスの訂正専門家です。
以下のJSON配列は動画の音声を自動文字起こしした結果です。
各テキストを確認し、以下の問題を修正して同じ数・同じ順番のJSON文字列配列として返してください。
{f"""\n【配信情報】\n{context}\n（固有名詞・ゲーム用語の訂正にこの情報を活用してください）\n""" if context else ""}
修正すべき問題:
1. 誤字・変換ミス（例: "きた" → "来た"、"もらった" が "もらた" になっている等）
2. 明らかな脱字
3. セグメント内の繰り返しフレーズ（例: "そうですね そうですね そうですね" → "そうですね"）
4. 音声認識特有の同音異義語ミス（文脈から明らかな場合のみ）

重要なルール:
- 配列の要素数を変えてはいけません（{len(texts)}個のまま）
- 意味を変えず、明らかな誤りのみ修正してください
- 修正不要な場合は元のテキストをそのまま返してください
- JSON配列のみ返してください（説明文不要）

入力:
{indexed_input}

修正後のJSON配列:"""

        try:
            sys.stderr.write(f"[CORRECTION] Correcting batch {batch_start//batch_size + 1} ({len(batch)} segments)...\n")
            sys.stderr.flush()

            client = ollama.Client(host=OLLAMA_HOST, timeout=180.0)
            response = client.chat(
                model=OLLAMA_MODEL,
                messages=[{
                    'role': 'user',
                    'content': prompt,
                }],
                format='json',
                options={'temperature': 0.1, 'num_predict': 2000},
            )

            raw = response['message']['content'].strip()

            # JSON配列として解析
            corrected_texts = None
            try:
                parsed = json.loads(raw)
                # リストとして返ってきた場合
                if isinstance(parsed, list):
                    corrected_texts = parsed
                # {"corrections": [...]} 等のラップ形式
                elif isinstance(parsed, dict):
                    for key in ('corrections', 'texts', 'result', 'results', 'data', 'output'):
                        if key in parsed and isinstance(parsed[key], list):
                            corrected_texts = parsed[key]
                            break
            except json.JSONDecodeError:
                import re
                m = re.search(r'\[.*?\]', raw, re.DOTALL)
                if m:
                    try:
                        corrected_texts = json.loads(m.group(0))
                    except Exception:
                        pass

            if corrected_texts and len(corrected_texts) == len(batch):
                # 訂正済みテキストをセグメントに反映
                for seg, new_text in zip(batch, corrected_texts):
                    if isinstance(new_text, str) and new_text.strip():
                        if hasattr(seg, 'text'):
                            seg.text = new_text
                        else:
                            seg['text'] = new_text
                corrected_all.extend(batch)
                sys.stderr.write(f"[CORRECTION] Batch corrected successfully.\n")
            else:
                sys.stderr.write(f"[CORRECTION] Correction result mismatch (got {len(corrected_texts) if corrected_texts else 'None'}, expected {len(batch)}). Keeping originals for this batch.\n")
                corrected_all.extend(batch)

        except Exception as e:
            sys.stderr.write(f"[CORRECTION] Error in batch {batch_start//batch_size + 1}: {e}. Keeping originals.\n")
            sys.stderr.flush()
            corrected_all.extend(batch)

    sys.stderr.write(f"[CORRECTION] Total segments corrected: {len(corrected_all)}\n")
    sys.stderr.flush()
    return corrected_all


def parse_vtt_file(vtt_path):
    """
    Parse a VTT file and return a list of segments.
    Each segment is a dict with 'start', 'end', 'text', and optionally other metadata.
    """
    segments = []
    with open(vtt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_start = 0
    current_end = 0
    in_cue = False
    text_lines = []
    pending_metadata = {}

    def parse_time(t):
        parts = t.split(":")
        seconds = float(parts[-1])
        if len(parts) > 1:
            seconds += int(parts[-2]) * 60
        if len(parts) > 2:
            seconds += int(parts[-3]) * 3600
        return seconds

    for line in lines:
        stripped = line.strip()
        
        # Check for metadata comment
        if stripped.startswith('NOTE metadata:'):
            try:
                json_str = stripped[len('NOTE metadata:'):]
                pending_metadata = json.loads(json_str)
            except Exception as e:
                print(f"Error parsing metadata: {e}")
            continue
        
        if "-->" in stripped:
            # If we have previous text, save it
            if in_cue and text_lines:
                segments.append({
                    "start": current_start,
                    "end": current_end,
                    "text": "\n".join(text_lines).strip(),
                    # Note: Previous metadata was already applied/cleared or this is complex.
                    # Wait, the structure here creates segment AFTER reading text.
                    # The metadata for THIS segment was read before THIS timestamp line.
                    # So current_metadata needs to be stored when timestamp is read.
                    **current_segment_metadata 
                })
                text_lines = []

            times = stripped.split(" --> ")
            current_start = parse_time(times[0])
            current_end = parse_time(times[1])
            in_cue = True
            
            # Store pending metadata for the segment we just started
            current_segment_metadata = pending_metadata.copy() if pending_metadata else {}
            pending_metadata = {} # Clear pending
            
        elif stripped and in_cue and "WEBVTT" not in stripped:
            # Skip cue numbers if they exist (digits only)
            if stripped.isdigit() and len(stripped) < 6:
                continue
            text_lines.append(stripped)
        elif not stripped:
            if in_cue and text_lines:
                segments.append({
                    "start": current_start,
                    "end": current_end,
                    "text": "\n".join(text_lines).strip(),
                    **current_segment_metadata
                })
                text_lines = []
                # Don't clear current_segment_metadata here, as it belongs to the current cue which just finished
            in_cue = False
            
    # Add last segment if exists
    if in_cue and text_lines:
        segments.append({
            "start": current_start,
            "end": current_end,
            "text": "\n".join(text_lines).strip(),
            **current_segment_metadata
        })

    return segments

def convert_vtt_to_srt(vtt_path: str, srt_path: str):
    """Convert VTT file to SRT format"""
    segments = parse_vtt_file(vtt_path)

    srt_output = []
    for i, segment in enumerate(segments, start=1):
        # SRT format: 00:00:00,000
        start = format_timestamp(segment['start']).replace('.', ',')
        end = format_timestamp(segment['end']).replace('.', ',')
        srt_output.append(str(i))
        srt_output.append(f"{start} --> {end}")
        srt_output.append(segment['text'].strip())
        srt_output.append("")

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_output))

def convert_srt_to_vtt(srt_path: str, vtt_path: str):
    """Convert SRT file to VTT format"""
    segments = []

    with open(srt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines and sequence numbers
        if not line or line.isdigit():
            i += 1
            continue

        # Check for timestamp line
        if "-->" in line:
            times = line.split(" --> ")
            # SRT uses comma, VTT uses dot
            start_str = times[0].strip().replace(',', '.')
            end_str = times[1].strip().replace(',', '.')

            # Parse times
            def parse_time(t):
                parts = t.split(":")
                seconds = float(parts[-1])
                if len(parts) > 1:
                    seconds += int(parts[-2]) * 60
                if len(parts) > 2:
                    seconds += int(parts[-3]) * 3600
                return seconds

            start = parse_time(start_str)
            end = parse_time(end_str)

            # Collect text lines
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1

            segments.append({
                'start': start,
                'end': end,
                'text': '\n'.join(text_lines)
            })
        else:
            i += 1

    # Write VTT
    vtt_output = ["WEBVTT", ""]
    for segment in segments:
        start = format_timestamp(segment['start'])
        end = format_timestamp(segment['end'])
        vtt_output.append(f"{start} --> {end}")
        vtt_output.append(segment['text'])
        vtt_output.append("")

    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(vtt_output))

