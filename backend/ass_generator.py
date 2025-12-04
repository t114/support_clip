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

def generate_ass(vtt_path, styles, output_path):
    """
    Generate an ASS file from VTT and styles.
    Supports:
    - Background box
    - Inner outline
    - Outer outline (double outline)
    - Shadow
    """
    
    # Parse Styles
    # Apply 1.5x multiplier as requested by user to match preview appearance
    font_size = int(styles.get('fontSize', 24) * 1.5)
    font_family = styles.get('fontFamily', 'Noto Sans JP')
    font_weight = styles.get('fontWeight', 'normal')
    
    # Map frontend fonts to installed system fonts
    font_mapping = {
        'Noto Sans JP': 'Noto Sans CJK JP',
        'Klee One': 'Noto Serif CJK JP', # Fallback for handwriting
        'Dela Gothic One': 'Noto Sans CJK JP Black', # Fallback for heavy
        'Kilgo U': 'Noto Sans CJK JP' # Fallback
    }
    
    ass_font_family = font_mapping.get(font_family, 'Noto Sans CJK JP')
    
    bold = -1 if font_weight == 'bold' else 0
    
    primary_color = hex_to_ass_color(styles.get('color', '#ffffff'))
    back_color = hex_to_ass_color(styles.get('backgroundColor', '#00000080'))
    outline_color = hex_to_ass_color(styles.get('outlineColor', '#000000'))
    outline_width = int(styles.get('outlineWidth', 0) * 1.5)
    
    # New: Outer outline and shadow
    outer_outline_color = hex_to_ass_color(styles.get('outerOutlineColor', '#ffffff'))
    outer_outline_width = int(styles.get('outerOutlineWidth', 0) * 1.5)
    shadow_color = hex_to_ass_color(styles.get('shadowColor', '#000000'))
    shadow_blur = int(styles.get('shadowBlur', 0) * 1.5)
    shadow_offset_x = int(styles.get('shadowOffsetX', 0) * 1.5)
    shadow_offset_y = int(styles.get('shadowOffsetY', 0) * 1.5)
    
    # MarginV calculation (approximate)
    margin_v = int(styles.get('bottom', 10) * 7)
    
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
            # Skip cue numbers
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
            
    # Handle last cue
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
    ass_lines.append("PlayResX: 1920") 
    ass_lines.append("PlayResY: 1080")
    ass_lines.append("")
    
    # Styles
    ass_lines.append("[V4+ Styles]")
    ass_lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding")
    
    # Calculate total outline width for outer layer
    total_outline = outline_width + outer_outline_width
    
    # Style 1: Background Box (Layer 0) - only if background is visible
    ass_lines.append(f"Style: BoxStyle,{ass_font_family},{font_size},{primary_color},&H00000000,{back_color},{back_color},{bold},0,0,0,100,100,0,0,3,{outline_width},0,2,10,10,{margin_v},1")
    
    # Style 2: Outer Outline (Layer 1) - only if outer outline is enabled
    if outer_outline_width > 0:
        ass_lines.append(f"Style: OuterOutline,{ass_font_family},{font_size},{outer_outline_color},&H00000000,{outer_outline_color},{shadow_color},{bold},0,0,0,100,100,0,0,1,{total_outline},{shadow_blur},2,10,10,{margin_v},1")
    
    # Style 3: Inner Outline (Layer 2)
    # If we have shadow but no outer outline, apply shadow here
    shadow_value = shadow_blur if outer_outline_width == 0 else 0
    ass_lines.append(f"Style: InnerOutline,{ass_font_family},{font_size},{primary_color},&H00000000,{outline_color},{shadow_color},{bold},0,0,0,100,100,0,0,1,{outline_width},{shadow_value},2,10,10,{margin_v},1")
    
    # Style 4: Text (Layer 3) - final text layer without outline
    ass_lines.append(f"Style: TextStyle,{ass_font_family},{font_size},{primary_color},&H00000000,&H00000000,&H00000000,{bold},0,0,0,100,100,0,0,1,0,0,2,10,10,{margin_v},1")
    
    ass_lines.append("")
    
    # Events
    ass_lines.append("[Events]")
    ass_lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")
    
    for event in events:
        # Layer 0: Box (only if background is visible)
        bg_alpha = int(back_color[2:4], 16)
        if bg_alpha < 255:
            ass_lines.append(f"Dialogue: 0,{event['start']},{event['end']},BoxStyle,,0,0,0,,{event['text']}")
        
        # Layer 1: Outer Outline (only if enabled)
        if outer_outline_width > 0:
            ass_lines.append(f"Dialogue: 1,{event['start']},{event['end']},OuterOutline,,0,0,0,,{event['text']}")
        
        # Layer 2: Inner Outline
        ass_lines.append(f"Dialogue: 2,{event['start']},{event['end']},InnerOutline,,0,0,0,,{event['text']}")
        
        # Layer 3: Text
        ass_lines.append(f"Dialogue: 3,{event['start']},{event['end']},TextStyle,,0,0,0,,{event['text']}")
        
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(ass_lines))
        
    return output_path
