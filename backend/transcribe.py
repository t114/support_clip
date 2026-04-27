from faster_whisper import WhisperModel
import os
import requests
import subprocess

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
                response = requests.post(
                    external_url,
                    files={"file": (os.path.basename(audio_path), f, "audio/wav")},
                    data={"model": "whisper-1", "response_format": "verbose_json"},
                    timeout=600
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
        segments, info = model.transcribe(video_path, beam_size=5, word_timestamps=word_ts)
        
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
    
    print(f"Transcription complete. Total segments: {len(segments_list)}")
    
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

import json

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

