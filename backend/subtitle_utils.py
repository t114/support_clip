import json

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
