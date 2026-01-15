import ollama
import json
import logging
from .config import OLLAMA_MODEL, OLLAMA_HOST
from .description_generator import detect_members

logger = logging.getLogger(__name__)

def generate_twitter_pr_text(
    original_title: str,
    original_url: str,
    clip_title: str = None,
    video_description: str = "",
    upload_date: str = None,
) -> str:
    """
    Generate Twitter PR text for a Hololive clip using LLM (Ollama).

    Args:
        original_title: Original video title
        original_url: Original video URL
        clip_title: Title of the clip (optional)
        video_description: Original video description (optional)

    Returns:
        Generated Twitter PR text
    """
    try:
        # Detect members and getting fan names
        detected_members = detect_members(original_title, video_description)
        fan_info_list = []
        for member in detected_members:
            if member.get('fan_name'):
                fan_info_list.append(f"{member['name_ja']}のファンネーム: {member['fan_name']}")
        
        fan_info_text = "\n".join(fan_info_list)

        # Construct prompt
        prompt = f"""
あなたはプロのホロライブ切り抜き動画の広報担当です。
以下の情報を元に、Twitter（X）で宣伝するための魅力的なPR文章を作成してください。

【情報】
元の動画タイトル: {original_title}
切り抜き動画のタイトル: {clip_title if clip_title else "未定"}
元の動画URL: {original_url}

元の動画の概要: {video_description[:500] if video_description else "なし"}
{fan_info_text}

【要件】
1. 読者の興味を惹く、キャッチーでエモーショナルな文章にしてください。
2. 絵文字を効果的に使用してください。
3. 適切なハッシュタグ（#ホロライブ #切り抜き など）を含めてください。
4. 元動画へのリンクは含めないでください（添付動画や画像がメインになるため）。ただし、引用元としての記載は別途行われるため、本文では動画の魅力を伝えることに集中してください。
5. 長さは140文字〜200文字程度で、読みやすく改行を入れてください。
6. 出演しているホロライブメンバーのファンネーム（上記情報にある場合）を文中に自然に取り入れ、ファンに呼びかけるような表現を積極的に使用してください。

【出力形式】
PR文章のみを出力してください。説明や前置きは不要です。
"""

        logger.info(f"Generating Twitter PR text with model: {OLLAMA_MODEL}")
        
        client = ollama.Client(host=OLLAMA_HOST, timeout=60.0)
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {
                    'role': 'system',
                    'content': 'You are a helpful assistant that writes catchy Twitter posts for VTuber clips in Japanese.'
                },
                {
                    'role': 'user',
                    'content': prompt,
                }
            ],
            options={
                'temperature': 0.7, # Slightly creative
            }
        )

        content = response['message']['content'].strip()
        logger.info(f"Generated PR text length: {len(content)}")
        return content

    except Exception as e:
        logger.error(f"Error generating Twitter PR text: {e}")
        return f"PR文章の生成に失敗しました: {str(e)}"
