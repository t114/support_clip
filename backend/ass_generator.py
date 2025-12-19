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
