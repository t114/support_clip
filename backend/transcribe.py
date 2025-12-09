from faster_whisper import WhisperModel
import os

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

def transcribe_video(video_path: str, progress_callback=None, model_size: str = "base") -> str:
    """
    Transcribes the video and returns the path to the generated VTT file.
    Also generates an SRT file in the same location.
    
    Args:
        video_path: Path to the video file
        progress_callback: Optional function(progress_percent: float) to call during transcription
        model_size: Whisper model size (tiny, base, small, medium, large)
    """
    print(f"Transcribing {video_path} using model '{model_size}'...")
    
    model = get_model(model_size)
    
    # faster-whisper returns a generator of segments
    segments, info = model.transcribe(video_path, beam_size=5)
    
    print(f"Detected language '{info.language}' with probability {info.language_probability}")
    
    # Convert generator to list to process segments and log progress
    segments_list = []
    
    # Estimate total duration for progress calculation if possible
    # info.duration might be available in newer versions or if provided
    total_duration = info.duration
    
    for i, segment in enumerate(segments):
        segments_list.append(segment)
        
        # Calculate progress
        if total_duration and total_duration > 0:
            progress = min(99, (segment.end / total_duration) * 100)
            if progress_callback:
                progress_callback(progress)
        
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

def parse_vtt_file(vtt_path):
    """
    Parse a VTT file and return a list of segments.
    Each segment is a dict with 'start', 'end', 'text'.
    """
    segments = []
    with open(vtt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_start = 0
    current_end = 0
    in_cue = False
    text_lines = []
    
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
        
        if "-->" in stripped:
            # If we have previous text, save it
            if in_cue and text_lines:
                segments.append({
                    "start": current_start,
                    "end": current_end,
                    "text": "\n".join(text_lines).strip()
                })
                text_lines = []

            times = stripped.split(" --> ")
            current_start = parse_time(times[0])
            current_end = parse_time(times[1])
            in_cue = True
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
                    "text": "\n".join(text_lines).strip()
                })
                text_lines = []
            in_cue = False
            
    # Add last segment if exists
    if in_cue and text_lines:
        segments.append({
            "start": current_start,
            "end": current_end,
            "text": "\n".join(text_lines).strip()
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

