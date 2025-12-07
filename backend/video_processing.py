import subprocess
import os


def hex_to_ass_color(hex_color, alpha=0):
    """
    Convert hex color (#RRGGBB or #RRGGBBAA) to ASS format &HAABBGGRR.
    alpha: 0-255 (0 is opaque, 255 is transparent in ASS, but we'll use standard alpha 0-1 from CSS if needed)
    Wait, ASS alpha is 00-FF where FF is transparent.
    CSS alpha is 0.0-1.0 where 0.0 is transparent.
    
    Input hex_color can be #RRGGBB or #RRGGBBAA.
    """
    hex_color = hex_color.lstrip('#')
    
    r, g, b, a = 0, 0, 0, 255
    
    if len(hex_color) == 6:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        a = 0 # Opaque in ASS (00)
    elif len(hex_color) == 8:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        # CSS #RRGGBBAA: AA is opacity (00=transparent, FF=opaque)
        # ASS Alpha: 00=opaque, FF=transparent
        css_alpha = int(hex_color[6:8], 16)
        a = 255 - css_alpha
        
    return f"&H{a:02X}{b:02X}{g:02X}{r:02X}"

def burn_subtitles_with_ffmpeg(video_path, ass_path, output_path):
    """
    Burn subtitles into video using ffmpeg with specified ASS file.
    """
    
    # Escape path for ffmpeg
    # subtitles filter needs escaped path: \: and \\
    escaped_ass_path = ass_path.replace(":", "\\:").replace("'", "\\'")
    
    # Use subtitles filter with fontsdir for emoji support
    # The force_style option allows overriding font but ASS styles take precedence for most settings
    # Using fontsdir ensures ffmpeg can find emoji fonts
    cmd = [
        "ffmpeg",
        "-y", # Overwrite
        "-i", video_path,
        "-vf", f"subtitles='{escaped_ass_path}':fontsdir=/usr/share/fonts/",
        "-c:a", "copy", # Copy audio
        output_path
    ]
    
    print(f"Running ffmpeg: {' '.join(cmd)}")
    
    # Capture output to prevent Broken Pipe
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"FFmpeg burn error output:\n{result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
    
    return output_path

def get_video_info(video_path):
    """
    Get video duration and FPS using ffprobe.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout.strip().split('\n')
        
        # Output order depends on show_entries, usually r_frame_rate then duration or vice versa
        # But ffprobe output order is not guaranteed to match show_entries order in older versions?
        # Let's parse carefully or request json.
        
        # Safer to use json format
        cmd_json = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate,duration",
            "-of", "json",
            video_path
        ]
        
        import json
        result = subprocess.run(cmd_json, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        stream = data['streams'][0]
        r_frame_rate = stream.get('r_frame_rate', '30/1')
        duration = float(stream.get('duration', 0))
        
        # Calculate FPS from "num/den" string
        num, den = map(int, r_frame_rate.split('/'))
        fps = num / den if den != 0 else 30.0
        
        return {
            "fps": fps,
            "duration": duration
        }
        
    except Exception as e:
        print(f"Error getting video info: {e}")
        return {"fps": 30.0, "duration": 0}
