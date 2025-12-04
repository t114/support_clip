import xml.etree.ElementTree as ET
from xml.dom import minidom
import os

def generate_fcpxml(subtitles, output_path, video_path, fps=30, duration_seconds=0):
    """
    Generate FCPXML 1.9 file from subtitles using Basic Title effect.
    This format is compatible with DaVinci Resolve and creates text clips.
    
    Args:
        subtitles (list): List of dicts with 'start', 'end', 'text'.
        output_path (str): Path to save the .fcpxml file.
        video_path (str): Path to the video file (for asset reference).
        fps (float): Frames per second of the video.
        duration_seconds (float): Total duration of the video in seconds.
    """
    
    # FCPXML 1.9 uses rational time (value/scale)
    # Determine frame duration and time base
    if fps == 29.97:
        frame_duration = "1001/30000s"
        time_base = 30000
        time_scale = 1001
    elif fps == 23.976:
        frame_duration = "1001/24000s"
        time_base = 24000
        time_scale = 1001
    elif fps == 59.94:
        frame_duration = "1001/60000s"
        time_base = 60000
        time_scale = 1001
    elif fps == 25:
        frame_duration = "1/25s"
        time_base = 25
        time_scale = 1
    else:
        # Integer FPS or other
        frame_duration = f"1/{int(fps)}s"
        time_base = int(fps)
        time_scale = 1
        
    def seconds_to_rational(seconds):
        # Convert seconds to rational time string
        total_frames = int(seconds * (time_base / time_scale))
        return f"{total_frames * time_scale}/{time_base}s"

    # Root element
    fcpxml = ET.Element("fcpxml", version="1.9")
    
    # Resources
    resources = ET.SubElement(fcpxml, "resources")
    
    # Format resource
    format_id = "r1"
    fmt = ET.SubElement(resources, "format", 
                       id=format_id, 
                       name=f"FFVideoFormat1080p{int(fps)}", 
                       frameDuration=frame_duration, 
                       width="1920", 
                       height="1080",
                       colorSpace="1-1-1 (Rec. 709)")
    
    # Basic Title effect resource
    effect_id = "r2"
    effect = ET.SubElement(resources, "effect",
                          id=effect_id,
                          name="Basic Title",
                          uid=".../Titles.localized/Bumper:Opener.localized/Basic Title.localized/Basic Title.moti")
    
    # Library
    library = ET.SubElement(fcpxml, "library")
    event = ET.SubElement(library, "event", name="Subtitles")
    project = ET.SubElement(event, "project", name="Subtitles")
    
    # Sequence
    total_duration_rational = seconds_to_rational(duration_seconds)
    sequence = ET.SubElement(project, "sequence", 
                            format=format_id, 
                            duration=total_duration_rational,
                            tcStart="0s",
                            tcFormat="NDF",
                            audioLayout="stereo",
                            audioRate="48k")
    spine = ET.SubElement(sequence, "spine")
    
    # Create a gap that spans the entire duration
    gap = ET.SubElement(spine, "gap",
                       name="Gap",
                       offset="0s",
                       start="0s",
                       duration=total_duration_rational)
    
    # Sort subtitles by start time
    subtitles.sort(key=lambda x: x['start'])
    
    # Add each subtitle as a title element
    for i, sub in enumerate(subtitles):
        start_seconds = sub['start']
        end_seconds = sub['end']
        duration_seconds_sub = end_seconds - start_seconds
        text = sub['text']
        
        start_rational = seconds_to_rational(start_seconds)
        duration_rational = seconds_to_rational(duration_seconds_sub)
        
        # Create title element
        title = ET.SubElement(gap, "title",
                             ref=effect_id,
                             lane="1",
                             name=f"{text[:30]}... - Basic Title" if len(text) > 30 else f"{text} - Basic Title",
                             offset=start_rational,
                             start=start_rational,
                             duration=duration_rational)
        
        # Add parameters for Flatten and Alignment
        ET.SubElement(title, "param",
                     name="Flatten",
                     key="9999/999166631/999166633/2/351",
                     value="1")
        
        ET.SubElement(title, "param",
                     name="Alignment",
                     key="9999/999166631/999166633/2/354/3142713059/401",
                     value="1 (Center)")
        
        ET.SubElement(title, "param",
                     name="Alignment",
                     key="9999/999166631/999166633/2/354/999169573/401",
                     value="1 (Center)")
        
        # Add text content
        text_elem = ET.SubElement(title, "text")
        text_style = ET.SubElement(text_elem, "text-style", ref=f"ts{i+1}")
        text_style.text = text
        
        # Add text style definition
        text_style_def = ET.SubElement(title, "text-style-def", id=f"ts{i+1}")
        ET.SubElement(text_style_def, "text-style",
                     font="Helvetica",
                     fontSize="60",
                     fontColor="1 1 1 1",
                     alignment="center",
                     fontFace="Regular")
    
    # Convert to string with pretty formatting
    xml_str = ET.tostring(fcpxml, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent="  ")
    
    # Add DOCTYPE
    lines = pretty_xml.split('\n')
    # Insert DOCTYPE after XML declaration
    if lines[0].startswith('<?xml'):
        lines.insert(1, '<!DOCTYPE fcpxml>')
    
    # Remove extra blank lines
    lines = [line for line in lines if line.strip()]
    pretty_xml = '\n'.join(lines)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(pretty_xml)
        
    return output_path
