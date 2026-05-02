import os
import json
import logging
import requests
import datetime
import shutil
from collections import Counter
from .paths import UPLOAD_DIR, EMOJIS_DIR
from .description_generator import MEMBERS_FILE

logger = logging.getLogger(__name__)

# In-memory cache for channel details
_MEMBERS_CACHE = None

def get_channel_info(cid, members_map=None):
    global _MEMBERS_CACHE
    if members_map is None:
        if _MEMBERS_CACHE is None:
            _MEMBERS_CACHE = {}
            try:
                if os.path.exists(MEMBERS_FILE):
                    with open(MEMBERS_FILE, "r", encoding='utf-8') as f:
                        data = json.load(f)
                        for m in data.get("members", []):
                            url = m.get("channel_url", "")
                            if "/channel/" in url:
                                c_id = url.split("/channel/")[-1]
                                _MEMBERS_CACHE[c_id] = m.get("name_ja")
            except Exception as e:
                logger.warning(f"Error loading members.json for cache: {e}")
        members_map = _MEMBERS_CACHE

    name = cid
    registered_at = None
    
    # 1. Check local channel_info.json
    c_dir = os.path.join(EMOJIS_DIR, cid)
    info_path = os.path.join(c_dir, "channel_info.json")
    if os.path.exists(info_path):
        try:
            with open(info_path, "r", encoding='utf-8') as f:
                data = json.load(f)
                name = data.get("name", cid)
                registered_at = data.get("registered_at")
        except: pass

    # Fallback for registration date: use folder modification time
    if not registered_at and os.path.exists(c_dir):
        mtime = os.path.getmtime(c_dir)
        registered_at = datetime.datetime.fromtimestamp(mtime).isoformat()

    if cid in members_map: 
        name = members_map[cid]

    # 2. Search info files in uploads if name is still unknown
    if name == cid or name == "Unknown Channel":
        import glob
        for info_file in glob.glob(os.path.join(UPLOAD_DIR, "*.info.json")):
            try:
                with open(info_file, "r") as f:
                    d = json.load(f)
                    if d.get("channel_id") == cid:
                        name = d.get("uploader")
                        break
            except: continue
    
    return name if name != cid else "Unknown Channel", registered_at

def extract_text_from_runs(runs, collected_emojis=None):
    """Helper to extract text and emoji shortcuts from YouTube message runs"""
    text = ""
    for run in runs:
        if 'text' in run:
            text += run['text']
        elif 'emoji' in run:
            emoji = run['emoji']
            shortcuts = emoji.get('shortcuts', [])
            shortcut = None
            if shortcuts:
                shortcut = shortcuts[0]
            else:
                label = emoji.get('image', {}).get('accessibility', {}).get('accessibilityData', {}).get('label', '')
                if label:
                    shortcut = f":{label}:"
            
            if shortcut:
                text += shortcut
                if collected_emojis is not None:
                    thumbnails = emoji.get('image', {}).get('thumbnails', [])
                    if thumbnails:
                        url = thumbnails[-1].get('url')
                        collected_emojis[shortcut] = url
    return text

def save_emojis_to_disk(channel_id, emoji_data):
    """Save emoji images to disk and update mapping file"""
    if not channel_id or channel_id == "UNKNOWN_CHANNEL":
        return
        
    channel_dir = os.path.join(EMOJIS_DIR, channel_id)
    os.makedirs(channel_dir, exist_ok=True)
    mapping_file = os.path.join(channel_dir, "map.json")
    
    local_mapping = {}
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                local_mapping = json.load(f)
        except: pass
        
    updated = False
    logger.info(f"Saving emojis for {channel_id}. Found {len(emoji_data)} emojis to check.")
    for shortcut, url in emoji_data.items():
        if shortcut in local_mapping: continue
        
        logger.info(f"Downloading new emoji: {shortcut} from {url}")
        
        safe_name = "".join([c for c in shortcut if c.isalnum() or c in "_-"]).strip("_")
        if not safe_name: safe_name = f"emoji_{hash(shortcut)}"
        
        ext = ".png"
        if ".webp" in url: ext = ".webp"
        elif ".gif" in url: ext = ".gif"
        
        filename = f"{safe_name}{ext}"
        file_path = os.path.join(channel_dir, filename)
        
        if not os.path.exists(file_path):
            try:
                resp = requests.get(url, stream=True, timeout=10)
                if resp.status_code == 200:
                    with open(file_path, 'wb') as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    local_mapping[shortcut] = filename
                    updated = True
            except Exception as e:
                logger.warning(f"Failed to auto-download emoji {shortcut}: {e}")
        else:
            local_mapping[shortcut] = filename
            updated = True
            
    if updated:
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(local_mapping, f, ensure_ascii=False, indent=2)

def extract_comments(base_name):
    """Refactored helper to extract comments from json files"""
    live_chat_file = os.path.join(UPLOAD_DIR, f"{base_name}.live_chat.json")
    info_file = os.path.join(UPLOAD_DIR, f"{base_name}.info.json")
    
    comments_data = []
    logger.info(f"Extracting comments for {base_name}. Checking files...")
    
    collected_emojis = {}
    channel_id = None
    
    if os.path.exists(info_file):
        try:
            with open(info_file, 'r', encoding='utf-8') as f:
                info = json.load(f)
                channel_id = info.get('channel_id')
        except: pass

    if os.path.exists(live_chat_file):
        logger.info(f"Found live chat file: {live_chat_file}")
        with open(live_chat_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    data = json.loads(line)
                    actions_container = data.get('replayChatItemAction', {})
                    actions = actions_container.get('actions', [])
                    
                    if not actions and 'actions' in data:
                        actions = data.get('actions', [])
                    
                    packet_offset = actions_container.get('videoOffsetTimeMsec')
                    if not packet_offset and 'videoOffsetTimeMsec' in data:
                        packet_offset = data['videoOffsetTimeMsec']

                    for action in actions:
                        item_action = action.get('addChatItemAction', {})
                        if not item_action: continue
                        
                        item = item_action.get('item', {})
                        if not item: continue
                        
                        text = None
                        if 'liveChatTextMessageRenderer' in item:
                            renderer = item['liveChatTextMessageRenderer']
                            text_runs = renderer.get('message', {}).get('runs', [])
                            text = extract_text_from_runs(text_runs, collected_emojis)
                        elif 'liveChatPaidMessageRenderer' in item:
                            renderer = item['liveChatPaidMessageRenderer']
                            text_runs = renderer.get('message', {}).get('runs', [])
                            text = extract_text_from_runs(text_runs, collected_emojis)
                            purchase_amount = renderer.get('purchaseAmountText', {}).get('simpleText', '')
                            if purchase_amount:
                                text = f"[{purchase_amount}] {text}"
                        elif 'liveChatMembershipItemRenderer' in item:
                            renderer = item['liveChatMembershipItemRenderer']
                            header_runs = renderer.get('headerSubtext', {}).get('runs', [])
                            header_text = extract_text_from_runs(header_runs, collected_emojis)
                            msg_runs = renderer.get('message', {}).get('runs', [])
                            msg_text = extract_text_from_runs(msg_runs, collected_emojis)
                            text = f"{header_text} {msg_text}".strip()
                        elif 'liveChatSponsorshipGiftRedemptionAnnouncementRenderer' in item:
                            renderer = item['liveChatSponsorshipGiftRedemptionAnnouncementRenderer']
                            msg_runs = renderer.get('message', {}).get('runs', [])
                            text = extract_text_from_runs(msg_runs, collected_emojis)
                            
                        if text:
                            offset_str = packet_offset
                            if 'videoOffsetTimeMsec' in item.get('liveChatTextMessageRenderer', {}):
                                offset_str = item['liveChatTextMessageRenderer']['videoOffsetTimeMsec']
                            
                            if offset_str:
                                try:
                                    time_sec = int(offset_str) / 1000.0
                                    comments_data.append({'text': text, 'timestamp': time_sec})
                                except:
                                    pass
                except:
                    continue
                    
    if not comments_data and os.path.exists(info_file):
        logger.info(f"Checking info file for comments: {info_file}")
        try:
            with open(info_file, 'r', encoding='utf-8') as f:
                info = json.load(f)
                if 'comments' in info:
                    logger.info(f"Found {len(info['comments'])} comments in info.json")
                    for c in info['comments']:
                        text = c.get('text', '')
                        timestamp = c.get('timestamp')
                        if timestamp is not None:
                            comments_data.append({'text': text, 'timestamp': float(timestamp)})
        except Exception as e:
            logger.error(f"Error reading info.json comments: {e}")
            
    if collected_emojis and channel_id:
        save_emojis_to_disk(channel_id, collected_emojis)
            
    logger.info(f"Extracted {len(comments_data)} comments total.")
    return comments_data

def refresh_channels_summary_cache():
    """Recalculate summary for all channels and save to cache"""
    try:
        channels = []
        if not os.path.exists(EMOJIS_DIR):
            return []
            
        for channel_id in os.listdir(EMOJIS_DIR):
            channel_dir = os.path.join(EMOJIS_DIR, channel_id)
            if not os.path.isdir(channel_dir):
                continue
            if channel_id in ["common_emojis.json", "summary.json"]:
                continue
                
            mapping_file = os.path.join(channel_dir, "map.json")
            name, registered_at = get_channel_info(channel_id)
            
            count = 0
            examples = []
            if os.path.exists(mapping_file):
                try:
                    with open(mapping_file, "r", encoding='utf-8') as f:
                        emojis = json.load(f)
                        count = len(emojis)
                        examples = list(emojis.keys())[:5]
                except: pass
            
            channels.append({
                "id": channel_id,
                "name": name,
                "registered_at": registered_at,
                "count": count,
                "examples": examples
            })
            
        summary = sorted(channels, key=lambda x: x['name'])
        summary_path = os.path.join(EMOJIS_DIR, "summary.json")
        with open(summary_path, "w", encoding='utf-8') as f:
            json.dump({"channels": summary, "updated_at": datetime.datetime.now().isoformat()}, f, ensure_ascii=False)
        return summary
    except Exception as e:
        logger.error(f"Error refreshing channels summary cache: {e}")
        return []

def refresh_common_emojis_cache():
    """Recalculate common emojis and save to cache"""
    try:
        all_shortcuts = []
        if not os.path.exists(EMOJIS_DIR):
            return []
            
        for channel_id in os.listdir(EMOJIS_DIR):
            channel_dir = os.path.join(EMOJIS_DIR, channel_id)
            if not os.path.isdir(channel_dir):
                continue
            mapping_file = os.path.join(channel_dir, "map.json")
            if os.path.exists(mapping_file):
                try:
                    with open(mapping_file, "r", encoding='utf-8') as f:
                        emojis = json.load(f)
                        all_shortcuts.extend(emojis.keys())
                except: continue
        
        counts = Counter(all_shortcuts)
        common = [s for s, count in counts.items() if count >= 2]
        
        cache_path = os.path.join(EMOJIS_DIR, "common_emojis.json")
        with open(cache_path, "w", encoding='utf-8') as f:
            json.dump({"common": common, "updated_at": datetime.datetime.now().isoformat()}, f)
        return common
    except Exception as e:
        logger.error(f"Error refreshing common emojis cache: {e}")
        return []
