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

def generate_ass(vtt_path, styles, output_path, saved_styles=None, style_map=None, video_info=None):
    """
    Generate an ASS file from VTT and styles.
    Supports multiple styles and per-line style mapping.
    """
    
    # Calculate PlayRes multiplier for horizontal coordinates if aspect ratio is not 16:9
    h_multiplier = 1.0
    if video_info and video_info.get('width') and video_info.get('height'):
        # PlayResX/Y are 1920x1080 (16:9). 
        # If video is 9:16, width is 1080/1920 of height.
        # multiplier = (H/W) * (16/9)
        w = video_info['width']
        h = video_info['height']
        h_multiplier = (h / w) * (16 / 9)

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
        # 1080 pixels is 100%, so 1% is 10.8 pixels
        margin_v = int(style_obj.get('bottom', 10) * 10.8)
        
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
            # Check if this style has a prefix image
            if style_obj and style_obj.get('prefixImage'):
                image_url = style_obj['prefixImage']
                # Removed 1.5x multiplier to match preview
                image_size = int(style_obj.get('prefixImageSize', 32))
                spacing = 10
                # Apply multiplier to match coordinate scaling in 9:16 videos
                margin_l += int((image_size + spacing) * h_multiplier)
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
        # PrimaryColour is set to fully transparent (&HFF000000) to avoid ghosting if metrics differ
        # The Box color comes from OutlineColour/BackColour
        definitions.append(f"Style: {name}_Box,{ass_font_family},{font_size},&HFF000000,&H00000000,{back_color},{back_color},{bold},0,0,0,100,100,0,0,3,{box_padding},0,{alignment},{margin_l},{margin_r},{margin_v},1")

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
        
    current_start = 0.0
    current_end = 0.0
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
                    "start_sec": current_start,
                    "end_sec": current_end,
                    "text": text
                })
            in_cue = False
            
    if in_cue and text_lines:
        text = "\\N".join(text_lines)
        events.append({
            "start_sec": current_start,
            "end_sec": current_end,
            "text": text
        })

    # Pre-calculate Styles for all events
    expanded_events = []
    
    # Helper to get alignment code without regenerating full style def
    alignment_map = {
        'left': 1, 'center': 2, 'right': 3,
        'top-left': 7, 'top': 8, 'top-right': 9,
    }
    
    for i, event in enumerate(events):
        style_name = "Default"
        has_outer = False 
        prefix = ""
        alignment = 2 # default center
        
        # Determine Style Object
        style_obj = styles # Default style object
        
        if style_map and str(i) in style_map:
            mapped_name = style_map[str(i)]
            safe_mapped_name = mapped_name.replace(" ", "_").replace(",", "")
            if saved_styles and mapped_name in saved_styles:
                style_name = safe_mapped_name
                style_obj = saved_styles[mapped_name]
                
                # Check outer outline (approximate check matching create_style_def logic)
                outer_w = int(style_obj.get('outerOutlineWidth', 0) * 1.5)
                has_outer = (outer_w > 0)
        else:
             # Default style has_outer?
             outer_w = int(styles.get('outerOutlineWidth', 0) * 1.5)
             has_outer = (outer_w > 0)

        # Resolve Prefix
        if style_obj.get('prefixImage'):
            prefix = ''
        else:
            prefix = style_obj.get('prefix', '')
            
        # Resolve Alignment
        alignment = alignment_map.get(style_obj.get('alignment', 'center'), 2)
        
        # Helper: Get font size and base MarginV for spacing calculation
        # This duplicates logic from create_style_def slightly but we need values here.
        e_font_size = int(style_obj.get('fontSize', 24) * 1.5)
        e_margin_v = int(style_obj.get('bottom', 10) * 10.8)
        
        # Calculate box padding (needed for offset compensation)
        e_outline_width = int(style_obj.get('outlineWidth', 0) * 1.5)
        e_box_padding = max(e_outline_width, 8)

        expanded_events.append({
            "start": event["start_sec"],
            "end": event["end_sec"],
            "text": event["text"],
            "style_name": style_name,
            "alignment": alignment,
            "has_outer": has_outer,
            "prefix": prefix,
            "font_size": e_font_size,
            "base_margin_v": e_margin_v,
            "box_padding": e_box_padding
        })



    # Merge Logic: Flatten overlaps into single events
    merged_events = []
    
    # 1. Collect all time points
    points = set()
    for e in expanded_events:
        points.add(e["start"])
        points.add(e["end"])
    times = sorted(list(points))
    
    # 2. Iterate intervals
    for j in range(len(times) - 1):
        t_start = times[j]
        t_end = times[j+1]
        
        if t_end - t_start < 0.01: 
            continue
            
        mid = (t_start + t_end) / 2.0
        
        # Find active events in this interval
        active = [e for e in expanded_events if e["start"] <= mid and e["end"] > mid]
        if not active:
            continue
            
        # Group by alignment (must share same positioning)
        by_align = {}
        for e in active:
            if e["alignment"] not in by_align:
                by_align[e["alignment"]] = []
            by_align[e["alignment"]].append(e)
            
        # Create Merged Events for each alignment group
        for align, group in by_align.items():
            primary = group[0]
            
            # Combine all text lines from all overlapping groups
            all_lines = []
            for e in group:
                disp_text = f"{e['prefix']} {e['text']}" if e['prefix'] else e['text']
                # Split by \N if the original event was already multiline (from VTT)
                sub_lines = disp_text.split('\\N')
                all_lines.extend(sub_lines)
            
            line_height = primary['font_size'] * 1.1 # Tighter line height (USER REQUEST: 1.5 -> 1.1)
            gap = 3 # Slight gap to prevent 1-2px overlap (USER REQUEST: Fix overlap)
            base_v = primary['base_margin_v']
            is_top = (primary['alignment'] in [7, 8, 9])
            # box_padding not needed for pos calculation if anchors work correctly
            
            for k, line_text in enumerate(all_lines):
                # Calculate index related offset
                if is_top:
                    offset_idx = k
                else: 
                    offset_idx = (len(all_lines) - 1) - k
                    
                final_margin_v = int(base_v + (offset_idx * (line_height + gap)))
                
                merged_events.append({
                    "start": t_start,
                    "end": t_end,
                    "style_name": primary["style_name"],
                    "has_outer": primary["has_outer"],
                    "alignment": primary['alignment'], # Store alignment
                    "line_text": line_text,
                    "margin_v": final_margin_v
                })

    # Generate ASS Content
    ass_lines = []
    
    # Header
    ass_lines.append("[Script Info]")
    ass_lines.append("ScriptType: v4.00+")
    ass_lines.append("WrapStyle: 0")
    ass_lines.append("PlayResX: 1920") 
    ass_lines.append("PlayResY: 1080")
    ass_lines.append("Collisions: Normal")
    ass_lines.append("")
    
    # Styles
    ass_lines.append("[V4+ Styles]")
    ass_lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    
    # Default Style
    default_defs, default_has_outer = create_style_def("Default", styles)
    ass_lines.extend(default_defs)
    
    # Saved Styles
    if saved_styles:
        for name, style_obj in saved_styles.items():
            safe_name = name.replace(" ", "_").replace(",", "")
            defs, h_out = create_style_def(safe_name, style_obj)
            ass_lines.extend(defs)
            
    ass_lines.append("")
    
    # Events
    ass_lines.append("[Events]")
    ass_lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
    
    PlayResX = 1920
    PlayResY = 1080
    
    for event in merged_events:
        s_start = seconds_to_ass_time(event["start"])
        s_end = seconds_to_ass_time(event["end"])
        sty = event["style_name"]
        mv = event["margin_v"]
        align = event["alignment"]
        txt = event["line_text"]
        
        # Calculate X, Y
        # Default margins from Style logic (simplified)
        # Left(1,7): L=150
        # Right(3,9): R=150
        # Center(2,8): L=96, R=96 (screen center)
        
        # X Position
        if align in [1, 7]: # Left
            # X = MarginL. 
            # Note: style defined MarginL is 150 (approx). 
            # We should probably use the same value or calculated.
            # But the MarginL in style is just default.
            # Here we want to pin it.
            pos_x = 150 # Standard left margin
        elif align in [3, 9]: # Right
            pos_x = PlayResX - 150 
        else: # Center
            pos_x = PlayResX // 2
            
        # Y Position
        if align in [1, 2, 3]: # Bottom
            pos_y = PlayResY - mv
        else: # Top
            pos_y = mv
            
        pos_tag = f"\\pos({pos_x},{pos_y})"
        
        # We use explicit \pos, so MarginL/R/V in event line can be 0
        
        # Layer 0: Box
        ass_lines.append(f"Dialogue: 0,{s_start},{s_end},{sty}_Box,,0,0,0,,{{{pos_tag}}}{txt}")
        
        # Layer 1: Outer
        if event["has_outer"]:
            ass_lines.append(f"Dialogue: 1,{s_start},{s_end},{sty}_Outer,,0,0,0,,{{{pos_tag}}}{txt}")
            
        # Layer 2: Inner
        ass_lines.append(f"Dialogue: 2,{s_start},{s_end},{sty}_Inner,,0,0,0,,{{{pos_tag}}}{txt}")
        
        # Layer 3: Text
        ass_lines.append(f"Dialogue: 3,{s_start},{s_end},{sty}_Text,,0,0,0,,{{{pos_tag}}}{txt}")
        
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(ass_lines))
        
    return output_path
import random

def generate_danmaku_ass(comments, output_path, resolution_x=1920, resolution_y=1080, font_size=48, speed_min=8, speed_max=12, emoji_map=None, emoji_dir=None):
    """
    Generate an ASS file for scrolling comments (Niconico style / Danmaku).
    Returns a list of emoji overlays: [{"path", "start", "end", "x_expr", "y_pos", "size"}]
    """
    import re
    
    ass_lines = []
    emoji_overlays = []
    
    # Header
    ass_lines.append("[Script Info]")
    ass_lines.append("ScriptType: v4.00+")
    ass_lines.append("WrapStyle: 2")
    ass_lines.append(f"PlayResX: {resolution_x}")
    ass_lines.append(f"PlayResY: {resolution_y}")
    ass_lines.append("")
    
    # Styles
    ass_lines.append("[V4+ Styles]")
    ass_lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    
    font_name = "Noto Sans CJK JP"
    ass_lines.append(f"Style: Danmaku,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,4,0,0,0,1")
    ass_lines.append("")
    
    # Events
    ass_lines.append("[Events]")
    ass_lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
    
    margin_top = 50
    margin_bottom = 100
    usable_height = resolution_y - margin_top - margin_bottom
    lane_height = int(font_size * 1.2)
    num_lanes = max(1, usable_height // lane_height)
    
    lane_available_times = [0.0] * num_lanes
    sorted_comments = sorted(comments, key=lambda x: x.get('timestamp', 0))
    
    # Regex for emojis (same as frontend: anything between colons that isn't a colon or space)
    emoji_pattern = re.compile(r'(:[^:\s]+:)')
    
    for comment in sorted_comments:
        original_text = comment.get('text', '')
        if not original_text:
            continue
            
        start_time = comment.get('timestamp', 0)
        
        # Estimated width for scrolling range (calculated first)
        # Japanese/Chinese characters are typically wider than font_size
        # Use 2.0x multiplier for safe width estimation (accounts for bold fonts, spacing, etc.)
        text_length = len(original_text)
        estimated_width = text_length * font_size * 2.0
        
        # Add generous buffer to ensure comment completely scrolls off
        start_x = resolution_x + 100  # Start fully off right edge
        end_x = -(estimated_width + 300)  # End fully off left edge with extra buffer
        
        # Calculate duration based on constant speed (pixels per second)
        # This ensures comments completely scroll off before disappearing
        total_distance = start_x - end_x  # Total pixels to travel
        
        # Match frontend preview speed: ~652 px/s (170% in 5 seconds at 1920px width)
        # Frontend: (1920 * 1.7) / 5.0 = 652.8 px/s
        base_speed = random.uniform(600, 700)  # pixels per second
        
        # Duration = distance / speed
        # This ensures the comment reaches end_x exactly when duration ends
        duration = total_distance / base_speed
        
        end_time = start_time + duration
        
        # Lane selection
        chosen_lane = -1
        lane_indices = list(range(num_lanes))
        random.shuffle(lane_indices)
        for lane_idx in lane_indices:
            if start_time >= lane_available_times[lane_idx]:
                chosen_lane = lane_idx
                break
        if chosen_lane == -1:
             chosen_lane = min(range(num_lanes), key=lambda i: lane_available_times[i])
        
        lane_available_times[chosen_lane] = start_time + (duration * 0.3) 
        y_pos = margin_top + (chosen_lane * lane_height) + (lane_height // 2)
        
        
        # Process emojis in text
        display_text = original_text
        if emoji_map and emoji_dir:
            parts = emoji_pattern.split(original_text)
            new_parts = []
            current_offset_chars = 0
            
            for part in parts:
                if emoji_pattern.match(part) and part in emoji_map:
                    # It's an emoji. Hide it in ASS text but add to overlays.
                    img_name = emoji_map[part]
                    img_path = os.path.join(emoji_dir, img_name)
                    
                    if os.path.exists(img_path):
                        # Calculate emoji X expression: 
                        # We guess the X position based on its character offset.
                        # Niconico style: x(t) = start_x - ((t-start)/duration)*(start_x - end_x)
                        # Offset factor: the emoji starts after 'current_offset_chars'
                        # Roughly each char is `font_size` wide.
                        char_offset_px = current_offset_chars * font_size
                        
                        # The emoji's x at time t is (text_x_at_t + char_offset_px)
                        # expression = f"({start_x}-((t-{start_time:1f})/{duration:1f})*({start_x-end_x}))+{char_offset_px}"
                        
                        emoji_overlays.append({
                            "path": img_path,
                            "start": start_time,
                            "end": end_time,
                            "x_expr": f"({start_x}-((t-{start_time:.3f})/{duration:.3f})*({start_x - end_x}))+{char_offset_px}",
                            "y_pos": y_pos - (font_size // 2), # Center it on the lane
                            "size": int(font_size * 1.2)
                        })
                        
                        # Replace with transparent placeholder to keep space? 
                        # Actually ASS doesn't support easily "transparent but keep width" without complex tags.
                        # Let's just use some spaces of similar width.
                        # 1 emoji ~ 1.2 chars width?
                        new_parts.append("  ") 
                        current_offset_chars += 2
                    else:
                        # logger.warning(f"generate_danmaku_ass: Image file not found at {img_path}")
                        new_parts.append(part)
                        current_offset_chars += len(part)
                else:
                    new_parts.append(part)
                    current_offset_chars += len(part)
            display_text = "".join(new_parts)

        # Convert to ASS time format
        ass_start = seconds_to_ass_time(start_time)
        ass_end = seconds_to_ass_time(end_time)
        
        move_tag = f"\\move({start_x},{y_pos},{end_x},{y_pos})"
        ass_lines.append(f"Dialogue: 0,{ass_start},{ass_end},Danmaku,,0,0,0,,{{{move_tag}}}{display_text}")
        
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(ass_lines))
        
    return output_path, emoji_overlays
