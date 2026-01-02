import subprocess
import os

def extract_clip(video_path: str, start: float, end: float, output_path: str, crop_params: dict = None, danmaku_ass_path: str = None, aspect_ratio: str = None, emoji_overlays: list = None):
    """
    Extracts a clip from the video using ffmpeg.
    crop_params: dict with keys 'x', 'y', 'width', 'height' (optional)
    danmaku_ass_path: path to ASS file for danmaku comments (optional)
    aspect_ratio: '9:16' for vertical letterbox (optional)
    emoji_overlays: list of dicts with 'path', 'start', 'end', 'x_expr', 'y_pos', 'size' (optional)
    """
    try:
        # Ensure absolute paths
        video_path = os.path.abspath(video_path)
        output_path = os.path.abspath(output_path)
        
        duration = end - start
        
        # Build inputs
        input_args = ["-ss", str(start), "-i", video_path]
        
        # Build filter chain
        filters = []
        current_v = "[0:v]"
        
        if crop_params:
            x = int(crop_params.get('x', 0))
            y = int(crop_params.get('y', 0))
            w = int(crop_params.get('width', 0))
            h = int(crop_params.get('height', 0))
            if w > 0 and h > 0:
                filters.append(f"{current_v}crop={w}:{h}:{x}:{y}[cropped]")
                current_v = "[cropped]"
        
        if aspect_ratio == '9:16':
            # Letterbox to 9:16 (720x1280)
            filters.append(f"{current_v}scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2[916]")
            current_v = "[916]"

        if danmaku_ass_path:
            # Escape path for ffmpeg filter
            escaped_ass_path = danmaku_ass_path.replace("\\", "/").replace(":", "\\:").replace("'", "'\\\\\\''")
            filters.append(f"{current_v}subtitles='{escaped_ass_path}':fontsdir=/usr/share/fonts/[danmaku]")
            current_v = "[danmaku]"
                
        # Apply emoji overlays using movie filter (avoids Argument list too long)
        if emoji_overlays:
            for i, overlay in enumerate(emoji_overlays):
                # Escape path for filter
                # Path should be absolute (handled at start of function)
                # Replace backslashes with forward slashes
                # Escape colons (for ffmpeg filter)
                # Escape single quotes
                path = overlay['path']
                safe_path = path.replace("\\", "/").replace(":", "\\:").replace("'", "'\\\\\\''")
                
                next_v = f"[v_emoji_{i}]"
                
                # Load image via movie filter, scale, and overlay
                # We do this in one chain or separate lines. Separate lines for clarity in list.
                filters.append(f"movie='{safe_path}'[raw_emoji_{i}]")
                filters.append(f"[raw_emoji_{i}]scale={overlay['size']}:{overlay['size']}[img{i}]")
                filters.append(f"{current_v}[img{i}]overlay=x='{overlay['x_expr']}':y={overlay['y_pos']}:enable='between(t,{overlay['start']:.3f},{overlay['end']:.3f})'{next_v}")
                
                current_v = next_v
                
        cmd = [
            "ffmpeg",
            "-y",
            *input_args,
            "-t", str(duration)
        ]

        if filters:
            # Join with semicolon for filter_complex
            filter_str = ";".join(filters)
            
            # Write filter_complex to file to avoid "Argument list too long"
            filter_script_path = f"{output_path}.filter_complex"
            with open(filter_script_path, "w", encoding="utf-8") as f:
                f.write(filter_str)
                
            cmd.extend(["-filter_complex_script", filter_script_path, "-map", current_v, "-map", "0:a?"])
        else:
            # If no filters, map 0:v (shouldn't happen with crop/scale checks but for safety)
            # Actually if no filters, current_v is [0:v]
            pass

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
