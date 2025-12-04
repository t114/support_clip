from faster_whisper import WhisperModel
import os

# Load the model globally to avoid reloading it for every request
# Using 'base' for faster processing speed (good balance of speed and accuracy)
# device="cpu" and compute_type="int8" for CPU inference
model = WhisperModel("base", device="cpu", compute_type="int8")

def format_timestamp(seconds: float) -> str:
    """Convert seconds to WebVTT timestamp format (HH:MM:SS.mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02}:{minutes:02}:{secs:02}.{millis:03}"

def format_timestamp_srt(seconds: float) -> str:
    """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def create_vtt(segments) -> str:
    """Convert faster-whisper segments to WebVTT format string."""
    vtt_output = ["WEBVTT\n"]
    
    for segment in segments:
        start = format_timestamp(segment.start)
        end = format_timestamp(segment.end)
        text = segment.text.strip()
        
        vtt_output.append(f"{start} --> {end}")
        vtt_output.append(f"{text}\n")
        
    return "\n".join(vtt_output)

def create_srt(segments) -> str:
    """Convert faster-whisper segments to SRT format string."""
    srt_output = []
    
    for i, segment in enumerate(segments, start=1):
        start = format_timestamp_srt(segment.start)
        end = format_timestamp_srt(segment.end)
        text = segment.text.strip()
        
        srt_output.append(f"{i}")
        srt_output.append(f"{start} --> {end}")
        srt_output.append(f"{text}\n")
        
    return "\n".join(srt_output)

def transcribe_video(video_path: str) -> str:
    """
    Transcribes the video and returns the path to the generated VTT file.
    Also generates an SRT file in the same location.
    """
    print(f"Transcribing {video_path}...")
    
    # faster-whisper returns a generator of segments
    segments, info = model.transcribe(video_path, beam_size=5)
    
    print(f"Detected language '{info.language}' with probability {info.language_probability}")
    
    # Convert generator to list to process segments
    segments_list = list(segments)
    
    # Generate VTT
    vtt_content = create_vtt(segments_list)
    base_path = os.path.splitext(video_path)[0]
    vtt_path = f"{base_path}.vtt"
    
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write(vtt_content)
        
    # Generate SRT
    srt_content = create_srt(segments_list)
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

