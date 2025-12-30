import os

def hex_to_ass_color(hex_color):
    """
    Convert hex color (#RRGGBB or #RRGGBBAA) to ASS format &HAABBGGRR.
    """
    hex_color = hex_color.lstrip('#')
    
    r, g, b, a = 0, 0, 0, 0 # Default opaque
    
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

def seconds_to_ass_time(seconds):
    """Convert seconds to ASS timestamp format (H:MM:SS.cc)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def generate_ass(vtt_path, styles, output_path, saved_styles=None, style_map=None):
    """
    Generate an ASS file from VTT and styles.
    Supports multiple styles and per-line style mapping.
    """
    
    # Helper to generate style definition string
    def create_style_def(name, style_obj):
        # Apply 1.5x multiplier as requested by user to match preview appearance
        font_size = int(style_obj.get('fontSize', 24) * 1.5)
        font_family = style_obj.get('fontFamily', 'Noto Sans JP')
        font_weight = style_obj.get('fontWeight', 'normal')
        
        # Map frontend fonts to installed system fonts
        font_mapping = {
            'Noto Sans JP': 'Noto Sans CJK JP',
            'Klee One': 'Noto Serif CJK JP', # Fallback for handwriting
            'Dela Gothic One': 'Noto Sans CJK JP Black', # Fallback for heavy
            'Kilgo U': 'Noto Sans CJK JP' # Fallback
        }
        
        ass_font_family = font_mapping.get(font_family, 'Noto Sans CJK JP')
        
        bold = -1 if font_weight == 'bold' else 0
        
        primary_color = hex_to_ass_color(style_obj.get('color', '#ffffff'))
        back_color = hex_to_ass_color(style_obj.get('backgroundColor', '#00000080'))
        outline_color = hex_to_ass_color(style_obj.get('outlineColor', '#000000'))
        outline_width = int(style_obj.get('outlineWidth', 0) * 1.5)
        
        # New: Outer outline and shadow
        outer_outline_color = hex_to_ass_color(style_obj.get('outerOutlineColor', '#ffffff'))
        outer_outline_width = int(style_obj.get('outerOutlineWidth', 0) * 1.5)
        shadow_color = hex_to_ass_color(style_obj.get('shadowColor', '#000000'))
        shadow_blur = int(style_obj.get('shadowBlur', 0) * 1.5)
        # shadow_offset_x = int(style_obj.get('shadowOffsetX', 0) * 1.5) # Not used in standard ASS Style format directly
        # shadow_offset_y = int(style_obj.get('shadowOffsetY', 0) * 1.5)
        
        # MarginV calculation (approximate)
        margin_v = int(style_obj.get('bottom', 10) * 7)
        
        # Alignment: 1=left, 2=center, 3=right (bottom row)
        # Add 4 for middle row, add 8 for top row
        # So: 1,2,3=bottom; 5,6,7=middle; 9,10,11=top (but 4,5,6 and 7,8,9 in SSA)
        # ASS uses numpad layout: 1-9 corresponding to screen positions
        alignment_map = {
            'left': 1,      # bottom-left
            'center': 2,    # bottom-center
            'right': 3,     # bottom-right
            'top-left': 7,  # top-left
            'top': 8,       # top-center  
            'top-right': 9, # top-right
        }
        alignment = alignment_map.get(style_obj.get('alignment', 'center'), 2)
        
        # Calculate total outline width for outer layer
        total_outline = outline_width + outer_outline_width

        # Calculate box padding for background - use minimum 8px for visibility
        box_padding = max(outline_width, 8)

        # Calculate horizontal margins based on alignment
        # For PlayResX=1920, base margin is 5% = 96px
        # For left/right alignment, add extra margin to ensure text doesn't touch edges
        if alignment in [1, 7]:  # left, top-left
            margin_l = 150  # ~8% from left edge
            margin_r = 96
        elif alignment in [3, 9]:  # right, top-right
            margin_l = 96
            margin_r = 150  # ~8% from right edge
        else:  # center
            margin_l = 96
            margin_r = 96

        definitions = []

        # Style 1: Background Box (Layer 0)
        # BorderStyle 3 = opaque box, outline value acts as padding
        definitions.append(f"Style: {name}_Box,{ass_font_family},{font_size},{primary_color},&H00000000,{back_color},{back_color},{bold},0,0,0,100,100,0,0,3,{box_padding},0,{alignment},{margin_l},{margin_r},{margin_v},1")

        # Style 2: Outer Outline (Layer 1)
        if outer_outline_width > 0:
            definitions.append(f"Style: {name}_Outer,{ass_font_family},{font_size},{outer_outline_color},&H00000000,{outer_outline_color},{shadow_color},{bold},0,0,0,100,100,0,0,1,{total_outline},{shadow_blur},{alignment},{margin_l},{margin_r},{margin_v},1")

        # Style 3: Inner Outline (Layer 2)
        shadow_value = shadow_blur if outer_outline_width == 0 else 0
        definitions.append(f"Style: {name}_Inner,{ass_font_family},{font_size},{primary_color},&H00000000,{outline_color},{shadow_color},{bold},0,0,0,100,100,0,0,1,{outline_width},{shadow_value},{alignment},{margin_l},{margin_r},{margin_v},1")

        # Style 4: Text (Layer 3)
        definitions.append(f"Style: {name}_Text,{ass_font_family},{font_size},{primary_color},&H00000000,&H00000000,&H00000000,{bold},0,0,0,100,100,0,0,1,0,0,{alignment},{margin_l},{margin_r},{margin_v},1")
        
        return definitions, outer_outline_width > 0

    # Parse VTT
    events = []
    with open(vtt_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    current_start = 0
    current_end = 0
    in_cue = False
    text_lines = []
    
    for line in lines:
        stripped = line.strip()
        if "-->" in stripped:
            times = stripped.split(" --> ")
            current_start = parse_vtt_time(times[0])
            current_end = parse_vtt_time(times[1])
            in_cue = True
            text_lines = []
        elif stripped and in_cue and "WEBVTT" not in stripped:
            if stripped.isdigit() and not text_lines: 
                continue
            text_lines.append(stripped)
        elif not stripped and in_cue:
            if text_lines:
                text = "\\N".join(text_lines)
                events.append({
                    "start": seconds_to_ass_time(current_start),
                    "end": seconds_to_ass_time(current_end),
                    "text": text
                })
            in_cue = False
            
    if in_cue and text_lines:
        text = "\\N".join(text_lines)
        events.append({
            "start": seconds_to_ass_time(current_start),
            "end": seconds_to_ass_time(current_end),
            "text": text
        })

    # Generate ASS Content
    ass_lines = []
    
    # Header
    ass_lines.append("[Script Info]")
    ass_lines.append("ScriptType: v4.00+")
    ass_lines.append("WrapStyle: 0")
    ass_lines.append("PlayResX: 1920") 
    ass_lines.append("PlayResY: 1080")
    ass_lines.append("")
    
    # Styles
    ass_lines.append("[V4+ Styles]")
    ass_lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    
    # Default Style
    default_defs, default_has_outer = create_style_def("Default", styles)
    ass_lines.extend(default_defs)
    
    # Saved Styles
    saved_style_has_outer = {}
    if saved_styles:
        for name, style_obj in saved_styles.items():
            # Sanitize name for ASS (remove spaces, commas)
            safe_name = name.replace(" ", "_").replace(",", "")
            defs, has_outer = create_style_def(safe_name, style_obj)
            ass_lines.extend(defs)
            saved_style_has_outer[safe_name] = has_outer
            
    ass_lines.append("")
    
    # Events
    ass_lines.append("[Events]")
    ass_lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
    
    for i, event in enumerate(events):
        # Determine style for this event
        style_name = "Default"
        has_outer = default_has_outer
        prefix = ""

        # Check style map (index is string in JSON keys usually)
        if style_map and str(i) in style_map:
            mapped_name = style_map[str(i)]
            safe_mapped_name = mapped_name.replace(" ", "_").replace(",", "")
            # Verify style exists in saved_styles
            if saved_styles and mapped_name in saved_styles:
                style_name = safe_mapped_name
                has_outer = saved_style_has_outer.get(safe_mapped_name, False)
                # Get prefix from style
                # If image prefix exists, don't add text prefix (image will be overlaid by FFmpeg)
                if saved_styles[mapped_name].get('prefixImage'):
                    # Image prefix exists, don't use text prefix
                    prefix = ''
                else:
                    # No image prefix, use text prefix
                    prefix = saved_styles[mapped_name].get('prefix', '')
        else:
            # Default style
            # If image prefix exists, don't add text prefix (image will be overlaid by FFmpeg)
            if styles.get('prefixImage'):
                prefix = ''
            else:
                prefix = styles.get('prefix', '')

        # Add prefix to text if exists
        display_text = f"{prefix} {event['text']}" if prefix else event['text']

        # Layer 0: Box
        # Use empty MarginL/R/V to inherit from style definition
        ass_lines.append(f"Dialogue: 0,{event['start']},{event['end']},{style_name}_Box,,,,,,{display_text}")

        # Layer 1: Outer Outline
        if has_outer:
            ass_lines.append(f"Dialogue: 1,{event['start']},{event['end']},{style_name}_Outer,,,,,,{display_text}")

        # Layer 2: Inner Outline
        ass_lines.append(f"Dialogue: 2,{event['start']},{event['end']},{style_name}_Inner,,,,,,{display_text}")

        # Layer 3: Text
        ass_lines.append(f"Dialogue: 3,{event['start']},{event['end']},{style_name}_Text,,,,,,{display_text}")
        
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(ass_lines))
        
    return output_path
import random

def generate_danmaku_ass(comments, output_path, resolution_x=1920, resolution_y=1080, font_size=48, speed_min=8, speed_max=12):
    """
    Generate an ASS file for scrolling comments (Niconico style / Danmaku).
    
    Args:
        comments (list): List of dicts with 'text', 'timestamp' (seconds).
        output_path (str): Path to save the ASS file.
        resolution_x (int): Video width.
        resolution_y (int): Video height.
        font_size (int): Font size for comments.
        speed_min (int): Minimum duration for a comment to cross the screen.
        speed_max (int): Maximum duration for a comment to cross the screen.
    """
    
    ass_lines = []
    
    # Header
    ass_lines.append("[Script Info]")
    ass_lines.append("ScriptType: v4.00+")
    ass_lines.append("WrapStyle: 2") # No wrapping, wider than screen valid
    ass_lines.append(f"PlayResX: {resolution_x}")
    ass_lines.append(f"PlayResY: {resolution_y}")
    ass_lines.append("")
    
    # Styles
    ass_lines.append("[V4+ Styles]")
    ass_lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    
    # Danmaku Style
    # Check if a custom font is preferred, otherwise use a standard sans-serif
    font_name = "Noto Sans CJK JP"
    
    # Primary color white, Outline black
    # &H00FFFFFF (White), &H00000000 (Black)
    # Alignment 4 (Middle Left) - actually for move usually we want custom positioning
    # But for \move, alignment determines the anchor point. 
    # Use 7 (Top Left) or 4 (Center Left) or even 8 (Top Center).
    # Let's use 4 (Center Left) so y-coordinate is the center of the text line.
    ass_lines.append(f"Style: Danmaku,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,4,0,0,0,1")
    ass_lines.append("")
    
    # Events
    ass_lines.append("[Events]")
    ass_lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
    
    # Manage lanes to avoid overlapping
    # Divide screen height into lanes
    margin_top = 50
    margin_bottom = 100 # Leave space for subtitles
    usable_height = resolution_y - margin_top - margin_bottom
    lane_height = int(font_size * 1.2)
    num_lanes = usable_height // lane_height
    
    # Track when each lane becomes available (end time of previous comment in that lane + buffer)
    # Actually, for scrolling text, we need to ensure the *following* comment doesn't catch up to the *previous* one
    # AND the *previous* one has cleared the entrance point before the *following* one starts.
    # Simplified Logic: Just random lane or Round Robin.
    # Better Logic: Track the 'clear time' of the right edge of the screen for each lane.
    
    lane_available_times = [0.0] * num_lanes
    
    sorted_comments = sorted(comments, key=lambda x: x.get('timestamp', 0))
    
    for comment in sorted_comments:
        text = comment.get('text', '')
        if not text:
            continue
            
        start_time = comment.get('timestamp', 0)
        
        # Calculate duration based on text length to keep speed somewhat consistent?
        # Or just random duration for variety. Niconico is usually fixed duration (e.g. 4s) regardless of length?
        # Actuall usually 3-5 seconds.
        # Let's use random duration for variety.
        duration = random.uniform(speed_min, speed_max)
        end_time = start_time + duration
        
        # Find a suitable lane
        # A lane is available if the last comment in that lane has moved far enough to not overlap.
        # Since we don't calculate text width accurately in python without font metrics,
        # we'll use a simple heuristic or just checking start time > last available timestamp.
        # But `lane_available_times` stores when the lane is free for a NEW text to appear at right edge.
        # For simplicity, let's just use simple time tracking:
        # If start_time >= lane_available_time, we can use it.
        # We try to pick the lane with the smallest available time that is <= start_time.
        
        chosen_lane = -1
        
        # Shuffle lanes to check to avoid filling top lanes first always if multiple are free
        lane_indices = list(range(num_lanes))
        random.shuffle(lane_indices)
        
        for lane_idx in lane_indices:
            if start_time >= lane_available_times[lane_idx]:
                chosen_lane = lane_idx
                break
        
        # If no lane is completely free, just pick the one that becomes free soonest (overlap might happen but minimizes it)
        # OR just pick random to simulate chaos (danmaku)
        if chosen_lane == -1:
             chosen_lane = min(range(num_lanes), key=lambda i: lane_available_times[i])
        
        # Update available time for this lane
        # We need to estimate when the text clears the right edge enough for next text.
        # Heuristic: 20% of duration buffer?
        # Or simply: start_time + (duration * 0.2)
        lane_available_times[chosen_lane] = start_time + (duration * 0.3) 
        
        y_pos = margin_top + (chosen_lane * lane_height) + (lane_height // 2)
        
        # \move(x1, y1, x2, y2)
        # x1: Right edge + text_width/2 ? 
        # ASS \move origin depends on alignment. Alignment 4 (Center Left) means (x,y) is the left center of the text.
        # Start: Left side of text at Screen Width + Padding.
        # End: Right side of text at 0 - Padding -> Left side of text at 0 - Text Width - Padding.
        
        # Since we don't know text width, we can use a large enough range.
        # Standard trick: Start at X=Resolution+Buffer, End at X=-Resolution/2 (approximation)
        # Or better: Niconico style usually moves from right to left.
        # If alignment is bottom-center (2), x is center of text.
        # Start x: Resolution + Width/2 ??? No.
        
        # Let's trust libass simple move.
        # Start X: resolution_x + 100 (Just off screen right)
        # End X: -100 (Just off screen left? Text width complicates this).
        # Longer text needs more negative end point.
        # Let's guess text width chars * font_size.
        estimated_width = len(text) * font_size
        start_x = resolution_x + 50
        end_x = -(estimated_width + 50)
        
        # Convert to ASS time format
        ass_start = seconds_to_ass_time(start_time)
        ass_end = seconds_to_ass_time(end_time)
        
        # Format: \move(x1, y1, x2, y2)
        # y1 and y2 are same (y_pos)
        move_tag = f"\\move({start_x},{y_pos},{end_x},{y_pos})"
        
        # Color variety? (Optional: white default, sometimes others)
        
        ass_lines.append(f"Dialogue: 0,{ass_start},{ass_end},Danmaku,,0,0,0,,{{{move_tag}}}{text}")
        
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(ass_lines))
        
    return output_path
