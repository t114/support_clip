import subprocess
import os

def extract_clip(video_path: str, start: float, end: float, output_path: str, crop_params: dict = None, danmaku_ass_path: str = None, aspect_ratio: str = None):
    """
    Extracts a clip from the video using ffmpeg.
    crop_params: dict with keys 'x', 'y', 'width', 'height' (optional)
    danmaku_ass_path: path to ASS file for danmaku comments (optional)
    aspect_ratio: '9:16' for vertical letterbox (optional)
    """
    try:
        # Ensure absolute paths
        video_path = os.path.abspath(video_path)
        output_path = os.path.abspath(output_path)
        
        duration = end - start
        
        # Build filter chain
        filters = []
        if crop_params:
            x = int(crop_params.get('x', 0))
            y = int(crop_params.get('y', 0))
            w = int(crop_params.get('width', 0))
            h = int(crop_params.get('height', 0))
            if w > 0 and h > 0:
                filters.append(f"crop={w}:{h}:{x}:{y}")

        if aspect_ratio == '9:16':
            # Letterbox to 9:16 (720x1280)
            filters.append("scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2")

        if danmaku_ass_path:
            # Escape path for ffmpeg filter
            escaped_ass_path = danmaku_ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "'\\\\\\''")
            filters.append(f"subtitles='{escaped_ass_path}':fontsdir=/usr/share/fonts/")
                
        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start),
            "-i", video_path,
            "-t", str(duration)
        ]

        if filters:
            cmd.extend(["-vf", ",".join(filters)])
            
        cmd.extend([
            "-c:v", "libx264", # Re-encode to ensure accurate cutting and compatibility
            "-c:a", "aac",
            "-strict", "experimental",
            output_path
        ])
        
        print(f"Running ffmpeg: {' '.join(cmd)}")
        # Capture output to prevent Broken Pipe if stdout is closed
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"FFmpeg error output:\n{result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
            
        return output_path
        
    except subprocess.CalledProcessError as e:
        print(f"Error extracting clip: {e}")
        if hasattr(e, 'stderr') and e.stderr:
             print(f"FFmpeg stderr: {e.stderr}")
        raise e

def merge_clips(clip_paths: list, output_path: str):
    """
    Merges multiple clips into one video.
    """
    # Create a temporary file list for ffmpeg
    list_file = f"{output_path}.txt"
    with open(list_file, "w") as f:
        for path in clip_paths:
            f.write(f"file '{path}'\n")
            
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            output_path
        ]
        
        # Capture output to prevent Broken Pipe
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"FFmpeg merge error output:\n{result.stderr}")
            raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
        
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)
