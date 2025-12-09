import json
import os
from typing import List, Dict

# ホロライブメンバーデータをロード
MEMBERS_FILE = os.path.join(os.path.dirname(__file__), "hololive_members.json")

def load_hololive_members() -> List[Dict]:
    """Load Hololive members data from JSON file"""
    with open(MEMBERS_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['members']

def detect_members(title: str, description: str) -> List[Dict]:
    """
    Detect Hololive members from video title and description

    Args:
        title: Video title
        description: Video description

    Returns:
        List of detected member dictionaries
    """
    members = load_hololive_members()
    detected = []

    combined_text = f"{title} {description}".lower()

    for member in members:
        # Check if any keyword matches
        for keyword in member['keywords']:
            if keyword.lower() in combined_text:
                detected.append(member)
                break  # Avoid duplicate detection

    return detected

def generate_description(
    original_url: str,
    original_title: str,
    video_description: str,
    clip_title: str = None
) -> str:
    """
    Generate YouTube description for a clip following Hololive fan content guidelines

    Args:
        original_url: Original stream/video URL
        original_title: Original video title
        video_description: Original video description
        clip_title: Title of the clip (optional)

    Returns:
        Generated description text
    """
    # Detect members
    detected_members = detect_members(original_title, video_description)

    # Build description
    lines = []

    # Title section
    if clip_title:
        lines.append(f"【切り抜き】{clip_title}")
        lines.append("")

    # Original video information
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("■ 元動画")
    lines.append(f"　{original_title}")
    lines.append(f"　{original_url}")
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("")

    # Members section
    if detected_members:
        lines.append("■ 出演")
        for member in detected_members:
            lines.append(f"　{member['name_ja']} / {member['name_en']}")
            lines.append(f"　{member['channel_url']}")
        lines.append("")

    # Fan content guidelines
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("■ ホロライブ二次創作ガイドライン")
    lines.append("　本動画は、ホロライブの二次創作ガイドラインに")
    lines.append("　基づいて作成された切り抜き動画です。")
    lines.append("　https://hololivepro.com/terms/")
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("")

    # Tags section
    lines.append("■ タグ")
    tags = ["#ホロライブ", "#切り抜き"]

    # Add member-specific tags
    for member in detected_members:
        tags.append(f"#{member['name_ja']}")
        if member.get('generation'):
            # Add generation tag if available
            gen_tag = member['generation'].replace('期生', '期')
            if 'GAMERS' not in gen_tag:
                tags.append(f"#ホロライブ{gen_tag}")

    lines.append("　" + " ".join(tags))
    lines.append("")

    # Copyright notice
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("■ 著作権について")
    lines.append("　本動画内で使用されているコンテンツの")
    lines.append("　著作権・肖像権等は各権利所有者に帰属します。")
    lines.append("━━━━━━━━━━━━━━━━")

    return "\n".join(lines)

def get_all_members() -> List[Dict]:
    """Get all Hololive members data"""
    return load_hololive_members()
