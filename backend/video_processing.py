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
                image_size = style_obj.get('prefixImageSize', 32)

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

def burn_subtitles_with_ffmpeg(video_path, ass_path, output_path, vtt_path=None, saved_styles=None, style_map=None, default_style=None, upload_dir="backend/uploads"):
    """
    Burn subtitles and prefix images into video using ffmpeg.
    """

    # Extract prefix images info
    image_overlays = []
    if vtt_path:
        image_overlays = extract_prefix_images_from_vtt(vtt_path, saved_styles, style_map, default_style)

    # Escape path for ffmpeg
    escaped_ass_path = ass_path.replace(":", "\\:").replace("'", "\\'")

    if not image_overlays:
        # Simple case: no images, just burn ASS subtitles
        cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-vf", f"subtitles='{escaped_ass_path}':fontsdir=/usr/share/fonts/",
            "-c:a", "copy",
            output_path
        ]
    else:
        # Complex case: burn ASS subtitles + overlay images
        # Build filter_complex

        # Get video info for positioning
        video_info = get_video_info(video_path)

        # Start with base video
        input_files = ["-i", video_path]

        # Add image inputs
        for i, overlay in enumerate(image_overlays):
            # Download/get local path
            local_image_path = download_image_if_needed(overlay['image_url'], upload_dir)
            input_files.extend(["-i", local_image_path])

        # Build filter_complex
        # Strategy: burn ASS subtitles first, THEN overlay images on top
        # This ensures images appear above the subtitle text

        # Step 1: Burn ASS subtitles first
        filter_parts = []
        filter_parts.append(f"[0:v]subtitles='{escaped_ass_path}':fontsdir=/usr/share/fonts/[subt]")

        current_label = "[subt]"

        # Step 2: Overlay images on top of subtitles
        for i, overlay in enumerate(image_overlays):
            image_index = i + 1  # Input 0 is video, images start at 1

            # Calculate position to match subtitle text position
            # bottom_percent: distance from bottom (0-100)
            # Convert to y position: H - (H * bottom_percent / 100) - image_height
            size = overlay['size']

            # ASS subtitles use MarginV which is calculated as: bottom * 7 (approx)
            # We need to align the image with the subtitle text position
            margin_v = overlay['bottom_percent'] * 7

            # Calculate Y position to match ASS subtitle position
            # ASS uses MarginV from bottom, so we do: H - MarginV - image_size
            y_pos = f"H-{margin_v}-{size}"

            # Alignment: left, center, right
            # Place image BEFORE subtitle text to avoid overlap
            # ASS margins must match ass_generator.py settings
            alignment = overlay['alignment']

            # ASS margin in PlayResX coordinates (1920)
            # Must match the values in ass_generator.py
            if alignment in ['left', 'top-left']:
                ass_margin_l = 150  # Left/top-left alignment uses 150px (~8%)
                ass_margin_r = 96
            elif alignment in ['right', 'top-right']:
                ass_margin_l = 96
                ass_margin_r = 150  # Right/top-right alignment uses 150px (~8%)
            else:  # center, top
                ass_margin_l = 96
                ass_margin_r = 96

            # Convert ASS margins to video coordinates
            # margin_ratio = ass_margin / 1920
            margin_l_ratio = ass_margin_l / 1920.0
            margin_r_ratio = ass_margin_r / 1920.0

            # Spacing between image and text
            spacing_px = 10  # 10px gap

            if alignment == 'left' or alignment == 'top-left':
                # Place image to the LEFT of subtitle text
                # Image right edge = MarginL - spacing
                # Image left edge (x position) = MarginL - image_size - spacing
                x_pos = f"W*{margin_l_ratio}-{size}-{spacing_px}"
            elif alignment == 'right' or alignment == 'top-right':
                # Place image to the LEFT of right-aligned text
                # This is complex, so just place it at a safe distance from right edge
                x_pos = f"W*(1-{margin_r_ratio})-{size}-{spacing_px}"
            else:  # center, top
                # Place image to the left of center text
                # Center point is W/2, place image before it
                x_pos = f"(W/2)-{size}-{spacing_px}"

            # Top alignments
            if alignment.startswith('top'):
                # For top alignment, calculate from top instead
                y_pos = f"{margin_v}+20"  # Add some padding from top

            # Scale image and overlay
            # enable expression: between(t, start, end)
            next_label = f"[v{i+1}]"

            filter_parts.append(
                f"[{image_index}:v]scale={size}:{size}[img{i}]; "
                f"{current_label}[img{i}]overlay=x={x_pos}:y={y_pos}:enable='between(t,{overlay['start']},{overlay['end']})'{next_label}"
            )
            current_label = next_label

        # Final output label
        # Rename the last label to [out]
        if image_overlays:
            # Replace the last label with [out]
            last_filter = filter_parts[-1]
            filter_parts[-1] = last_filter.replace(f'[v{len(image_overlays)}]', '[out]')
        else:
            # No images, just rename subtitle output
            filter_parts[0] = filter_parts[0].replace('[subt]', '[out]')

        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg",
            "-y",
            *input_files,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-map", "0:a?",  # Copy audio if exists
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
        return {"fps": 30.0, "duration": 0}
