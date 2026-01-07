import subprocess
import os
import re
import urllib.parse
import urllib.request


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

def parse_vtt_time(time_str):
    """Parse VTT timestamp to seconds."""
    parts = time_str.split(':')
    seconds = float(parts[-1])
    if len(parts) > 1:
        seconds += int(parts[-2]) * 60
    if len(parts) > 2:
        seconds += int(parts[-3]) * 3600
    return seconds

def extract_prefix_images_from_vtt(vtt_path, saved_styles=None, style_map=None, default_style=None):
    """
    Extract prefix image information from VTT file and style mapping.
    Returns list of {image_url, start, end, size, position_info}
    """
    if not saved_styles and not (default_style and default_style.get('prefixImage')):
        return []

    # Parse VTT
    image_overlays = []
    with open(vtt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_start = 0
    current_end = 0
    in_cue = False
    cue_index = 0

    for line in lines:
        stripped = line.strip()
        if "-->" in stripped:
            times = stripped.split(" --> ")
            current_start = parse_vtt_time(times[0])
            current_end = parse_vtt_time(times[1])
            in_cue = True
        elif not stripped and in_cue:
            # End of cue, process it
            # Determine which style applies to this cue
            style_name = None
            if style_map and str(cue_index) in style_map:
                style_name = style_map[str(cue_index)]

            # Get the style object
            style_obj = None
            if style_name and saved_styles and style_name in saved_styles:
                style_obj = saved_styles[style_name]
            elif default_style:
                style_obj = default_style

            # Check if this style has a prefix image
            if style_obj and style_obj.get('prefixImage'):
                image_url = style_obj['prefixImage']
                # Removed 1.5x multiplier to match preview
                image_size = int(style_obj.get('prefixImageSize', 32))

                # Get position info from style
                bottom_percent = style_obj.get('bottom', 10)
                alignment = style_obj.get('alignment', 'center')

                image_overlays.append({
                    'image_url': image_url,
                    'start': current_start,
                    'end': current_end,
                    'size': image_size,
                    'bottom_percent': bottom_percent,
                    'alignment': alignment
                })

            in_cue = False
            cue_index += 1

    return image_overlays

def download_image_if_needed(image_url, upload_dir):
    """
    Download image from URL if it's a remote URL, or return local path.
    Returns local file path.
    """
    # Check if it's already a local path
    if image_url.startswith('/static/'):
        # Convert to absolute path
        # /static/prefix_images/xxx.png -> backend/uploads/prefix_images/xxx.png
        relative_path = image_url.replace('/static/', '')
        local_path = os.path.join(upload_dir, relative_path)
        return local_path
    elif image_url.startswith('http://') or image_url.startswith('https://'):
        # Download to temp location
        parsed = urllib.parse.urlparse(image_url)
        filename = os.path.basename(parsed.path)
        local_path = os.path.join(upload_dir, 'prefix_images', filename)

        # Download if not already exists
        if not os.path.exists(local_path):
            urllib.request.urlretrieve(image_url, local_path)

        return local_path
    else:
        # Assume it's already a local path
        return image_url

def burn_subtitles_with_ffmpeg(video_path, ass_path, output_path, vtt_path=None, saved_styles=None, style_map=None, default_style=None, upload_dir="backend/uploads", danmaku_ass_path=None, emoji_overlays=None):
    """
    Burn subtitles and prefix images into video using ffmpeg.
    Optional: burn Niconico-style danmaku comments with membership emojis.
    """

    # Extract prefix images info (per-cue icons)
    prefix_overlays = []
    if vtt_path:
        prefix_overlays = extract_prefix_images_from_vtt(vtt_path, saved_styles, style_map, default_style)

    # Escape path for ffmpeg
    escaped_ass_path = ass_path.replace(":", "\\:").replace("'", "\\'")
    escaped_danmaku_ass_path = danmaku_ass_path.replace(":", "\\:").replace("'", "\\'") if danmaku_ass_path else None

    # Common subtitle filter string
    sub_filter = f"subtitles='{escaped_ass_path}':fontsdir=/usr/share/fonts/"
    danmaku_filter = f"subtitles='{escaped_danmaku_ass_path}':fontsdir=/usr/share/fonts/" if danmaku_ass_path else None

    # Start with base video
    input_files = ["-i", video_path]
    current_label = "[0:v]"
    filter_parts = []

    # Handle Prefix Images (Per-cue icons)
    # Convert paths to movie filter inputs
    prefix_img_paths = [download_image_if_needed(o['image_url'], upload_dir) for o in prefix_overlays]
    
    # 1. Apply Danmaku if exists
    if danmaku_filter:
        filter_parts.append(f"{current_label}{danmaku_filter}[danmaku]")
        current_label = "[danmaku]"

    # 2. Apply Main Subtitles
    filter_parts.append(f"{current_label}{sub_filter}[subt]")
    current_label = "[subt]"

    # 3. Overlay Prefix Images using movie filter
    # Get video info for scaling
    from .video_processing import get_video_info
    v_info = get_video_info(video_path)
    h_scale = v_info.get('height', 1080) / 1080.0

    for i, overlay in enumerate(prefix_overlays):
        path = prefix_img_paths[i]
        # Escape path
        safe_path = path.replace("\\", "/").replace(":", "\\:").replace("'", "'\\\\\\''")
        
        # Load image
        filter_parts.append(f"movie='{safe_path}'[raw_p_{i}]")
        
        # Scale size based on video height (matching libass text scaling)
        base_size = overlay['size']
        size = int(base_size * h_scale)
        
        # 10.8 matches the 1% unit in 1080p vertical resolution
        margin_v = int(overlay['bottom_percent'] * 10.8 * h_scale)
        y_pos = f"H-{margin_v}-{size}"
        
        alignment = overlay['alignment']
        ass_margin_l = 150 if alignment in ['left', 'top-left'] else 96
        ass_margin_r = 150 if alignment in ['right', 'top-right'] else 96
        margin_l_ratio = ass_margin_l / 1920.0
        margin_r_ratio = ass_margin_r / 1920.0
        spacing_px = int(10 * h_scale)
        
        if alignment == 'left' or alignment == 'top-left':
            # Start at margin_l. The text is shifted by MarginL in ASS.
            x_pos = f"W*{margin_l_ratio}"
        elif alignment == 'right' or alignment == 'top-right':
            x_pos = f"W*(1-{margin_r_ratio})-{size}-{spacing_px}"
        else:
            x_pos = f"(W/2)-{size}-{spacing_px}"

        if alignment.startswith('top'): y_pos = f"{margin_v}+20"

        next_label = f"[v_prefix_{i}]"
        filter_parts.append(
            f"[raw_p_{i}]scale={size}:{size}[pimg{i}]; "
            f"{current_label}[pimg{i}]overlay=x={x_pos}:y={y_pos}:enable='between(t,{overlay['start']},{overlay['end']})'{next_label}"
        )
        current_label = next_label

    # 4. Overlay Membership Emojis using movie filter
    if emoji_overlays:
        for i, overlay in enumerate(emoji_overlays):
            path = overlay['path']
            safe_path = os.path.abspath(path).replace("\\", "/").replace(":", "\\:").replace("'", "'\\\\\\''")
            
            filter_parts.append(f"movie='{safe_path}'[raw_e_{i}]")
            
            next_label = f"[v_emoji_{i}]"
            filter_parts.append(
                f"[raw_e_{i}]scale={overlay['size']}:{overlay['size']}[eimg{i}]; "
                f"{current_label}[eimg{i}]overlay=x='{overlay['x_expr']}':y={overlay['y_pos']}:enable='between(t,{overlay['start']:.3f},{overlay['end']:.3f})'{next_label}"
            )
            current_label = next_label

    # Final mapping
    if not filter_parts:
        # Simple burn if only ASS
        cmd = ["ffmpeg", "-y", "-i", video_path, "-vf", sub_filter, "-c:a", "copy", output_path]
    else:
        # Replace last label with [out]
        # Replace last label with [out]
        last_f = filter_parts[-1]
        filter_parts[-1] = last_f[:last_f.rfind('[')] + "[out]"
        filter_complex = ";".join(filter_parts)

        # Write filter_complex to file to avoid "Argument list too long"
        filter_script_path = output_path + ".filter_complex"
        with open(filter_script_path, "w", encoding="utf-8") as f:
            f.write(filter_complex)

        cmd = [
            "ffmpeg", "-y",
            *input_files,
            "-filter_complex_script", filter_script_path,
            "-map", "[out]",
            "-map", "0:a?",
            "-c:a", "copy",
            output_path
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
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
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-of", "json",
            video_path
        ]
        
        import json
        result = subprocess.run(cmd_json, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        stream = data['streams'][0]
        r_frame_rate = stream.get('r_frame_rate', '30/1')
        duration = float(stream.get('duration', 0))
        width = int(stream.get('width', 0))
        height = int(stream.get('height', 0))
        
        # Calculate FPS from "num/den" string
        num, den = map(int, r_frame_rate.split('/'))
        fps = num / den if den != 0 else 30.0
        
        return {
            "fps": fps,
            "duration": duration,
            "width": width,
            "height": height
        }

    except Exception as e:
        return {"fps": 30.0, "duration": 0, "width": 0, "height": 0}
