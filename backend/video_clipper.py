import subprocess
import os
from .obs_recorder import capture_clip as obs_capture

def capture_and_process_clip(url: str, start: float, end: float, output_path: str, **kwargs):
    """
    Captures clip via OBS then processes it (adds overlays).
    """
    duration = end - start
    # Create temp path for raw capture
    raw_path = output_path + ".raw.mkv"
    
    # Capture
    # OBS recorder returns the path where it saved the file
    saved_path = obs_capture(url, start, duration + 5) # Add 5s buffer for loading/seeking
    
    if not saved_path or not os.path.exists(saved_path):
        raise Exception("OBS Capture failed: No file created")
        
    try:
        # Process the captured file
        # We assume the captured file content roughly corresponds to the requested start/end.
        # But there might be a seek delay or loading time captured.
        # The capture_clip function in obs_recorder.py waits 5s for buffering then records.
        # So the video should start exactly at 'start' (or close to it) if playback started correctly.
        # We trim the first few seconds if needed? 
        # Actually obs_recorder logic:
        # player.play_video(url, start_time)
        # sleep(5) -> buffering
        # recorder.start_recording()
        # So the recording starts 5 seconds AFTER play command.
        # If video loaded instantly, we missed 5 seconds.
        # If video took 5 seconds to load, we are at 0.
        
        # This timing is tricky.
        # Better approach:
        # Start recording immediately.
        # Play video.
        # Then we capture everything including loading spinner.
        # Then we rely on the user to check or we analyze the video to find start?
        # OR we just try to be loose and say "It includes some buffer".
        
        # User said: "標準のyoutubeの画面しかキャプチャできないためそこから、動画再生部分だけを座標指定..."
        # They want to crop the video player area.
        
        # Let's just process whatever we got. 
        # For now, pass start=0, end=duration to extract_clip?
        # No, extract_clip cuts. If we pass start=0, end=duration, it takes the first 'duration' seconds.
        
        extract_clip(saved_path, 0, duration, output_path, **kwargs)
        
    finally:
        # Cleanup raw capture
        if os.path.exists(saved_path):
            os.remove(saved_path)
    
    return output_path


def extract_clip(video_path: str, start: float, end: float, output_path: str, crop_params: dict = None, danmaku_ass_path: str = None, aspect_ratio: str = None, emoji_overlays: list = None, sound_events: list = None, letterbox_align: str = 'center', secondary_crop_params: dict = None, split_ratio: float = 0.5):
    """
    Extracts a clip from the video using ffmpeg.
    crop_params: dict with keys 'x', 'y', 'width', 'height' (optional)
    danmaku_ass_path: path to ASS file for danmaku comments (optional)
    aspect_ratio: '9:16' for vertical letterbox, 'stacked' for two-screen vertical (optional)
    emoji_overlays: list of dicts with 'path', 'start', 'end', 'x_expr', 'y_pos', 'size' (optional)
    letterbox_align: 'center' or 'top' for vertical alignment in 9:16 (optional)
    secondary_crop_params: second crop for 'stacked' mode (optional)
    split_ratio: ratio of top screen height (0-1) in 'stacked' mode (optional)
    """
    try:
        # Ensure absolute paths
        video_path = os.path.abspath(video_path)
        output_path = os.path.abspath(output_path)
        
        duration = end - start
        
        # Build inputs
        input_args = ["-ss", str(start), "-i", video_path]
        
        # Build audio inputs and filter
        audio_filters = []
        if sound_events:
            for i, se in enumerate(sound_events):
                input_args.extend(["-i", se['path']])
                delay_ms = int(se['time'] * 1000)
                # Input index for SE starts from 1 (0 is the video)
                se_input_idx = i + 1
                audio_filters.append(f"[{se_input_idx}:a]adelay={delay_ms}|{delay_ms}[se{i}]")
            
            se_labels = "".join([f"[se{i}]" for i in range(len(sound_events))])
            audio_filters.append(f"[0:a]{se_labels}amix=inputs={1+len(sound_events)}:duration=first[out_a]")
        
        # Build filter chain
        filters = []
        current_v = "[0:v]"
        
        if aspect_ratio == 'stacked' and secondary_crop_params and crop_params:
            # Stack mode: Crop two areas and stack them vertically
            t_x, t_y, t_w, t_h = int(crop_params.get('x',0)), int(crop_params.get('y',0)), int(crop_params.get('width',0)), int(crop_params.get('height',0))
            b_x, b_y, b_w, b_h = int(secondary_crop_params.get('x',0)), int(secondary_crop_params.get('y',0)), int(secondary_crop_params.get('width',0)), int(secondary_crop_params.get('height',0))
            
            # Default split ratio to 0.5 if not provided or invalid
            try:
                s_ratio = float(split_ratio) if split_ratio is not None else 0.5
            except:
                s_ratio = 0.5
                
            top_h = int(1280 * s_ratio)
            bottom_h = 1280 - top_h
            
            # Scale both to width 720 and their respective target heights
            # Use force_original_aspect_ratio=increase then crop to ensure the area is filled
            filters.append(f"[0:v]crop={t_w}:{t_h}:{t_x}:{t_y},scale=720:{top_h}:force_original_aspect_ratio=increase,crop=720:{top_h}[top]")
            filters.append(f"[0:v]crop={b_w}:{b_h}:{b_x}:{b_y},scale=720:{bottom_h}:force_original_aspect_ratio=increase,crop=720:{bottom_h}[bottom]")
            filters.append(f"[top][bottom]vstack=inputs=2[stacked]")
            current_v = "[stacked]"
        elif crop_params:
            x = int(crop_params.get('x', 0))
            y = int(crop_params.get('y', 0))
            w = int(crop_params.get('width', 0))
            h = int(crop_params.get('height', 0))
            if w > 0 and h > 0:
                filters.append(f"{current_v}crop={w}:{h}:{x}:{y}[cropped]")
                current_v = "[cropped]"
        
        if aspect_ratio == '9:16':
            # Letterbox to 9:16 (720x1280)
            # Support both string labels and percentage (0-100)
            y_percent = 0.5
            if letterbox_align == 'top':
                y_percent = 0.0
            elif letterbox_align == 'center':
                y_percent = 0.5
            else:
                try:
                    y_percent = float(letterbox_align) / 100.0
                except (ValueError, TypeError):
                    y_percent = 0.5
            
            y_pad = f"(oh-ih)*{y_percent}"
            filters.append(f"{current_v}scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:{y_pad}[916]")
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

        if filters or audio_filters:
            # Join with semicolon for filter_complex
            # Combine video and audio filters
            all_filters = filters + audio_filters
            filter_str = ";".join(all_filters)
            
            # Write filter_complex to file to avoid "Argument list too long"
            filter_script_path = f"{output_path}.filter_complex"
            with open(filter_script_path, "w", encoding="utf-8") as f:
                f.write(filter_str)
            
            cmd.extend(["-filter_complex_script", filter_script_path, "-map", current_v, "-map", "[out_a]" if sound_events else "0:a?"])
        else:
            # If no filters at all, map original streams
            cmd.extend(["-map", "0:v", "-map", "0:a?"])

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
