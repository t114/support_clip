import os
import sys
import json

_MEMBERS_JSON_PATH = os.path.join(os.path.dirname(__file__), 'hololive_members.json')
_members_cache: list | None = None

def _load_hololive_members() -> list:
    """hololive_members.json をキャッシュして返す。"""
    global _members_cache
    if _members_cache is not None:
        return _members_cache
    try:
        with open(_MEMBERS_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _members_cache = data.get('members', [])
        sys.stderr.write(f'[CONTEXT] Loaded {len(_members_cache)} hololive members\\n')
    except Exception as e:
        sys.stderr.write(f'[CONTEXT] Could not load hololive_members.json: {e}\\n')
        _members_cache = []
    sys.stderr.flush()
    return _members_cache

def detect_streamer_context(info_json_path: str | None) -> dict:
    """
    info.json から配信者・コンテンツ情報を取得し、ホロライブメンバーと照合する。

    Returns:
        {
          'streamer_name': 'さくらみこ',       # 配信者名（日本語）
          'generation': '1期生',               # ホロライブ世代
          'game_title': 'マリオカート 8 DX',   # ゲームタイトル（抽出できた場合）
          'channel_name': '...',               # チャンネル名（生）
          'video_title': '...',                # 動画タイトル
          'context_sentence': '...',           # LLMに渡す前提文
          'is_hololive': True,                 # ホロライブメンバーか否か
        }
    """
    result = {
        'streamer_name': None,
        'generation': None,
        'game_title': None,
        'channel_name': None,
        'video_title': None,
        'context_sentence': '',
        'is_hololive': False,
    }

    if not info_json_path or not os.path.exists(info_json_path):
        return result

    try:
        with open(info_json_path, 'r', encoding='utf-8') as f:
            info = json.load(f)
    except Exception as e:
        sys.stderr.write(f'[CONTEXT] Failed to read info.json: {e}\\n')
        sys.stderr.flush()
        return result

    channel_url  = info.get('channel_url', '') or ''
    channel_name = info.get('uploader', '') or info.get('channel', '') or ''
    video_title  = info.get('title', '') or ''
    description  = info.get('description', '') or ''
    channel_id   = info.get('channel_id', '') or ''

    result['channel_name'] = channel_name
    result['video_title']  = video_title

    # ── ホロライブメンバー照合 ─────────────────────────────────────────────
    members = _load_hololive_members()
    matched_member = None

    # 1. チャンネルURLで完全一致
    for member in members:
        member_url = member.get('channel_url', '')
        if member_url and channel_url:
            m_handle = member_url.rstrip('/').split('/')[-1].lower()
            c_handle = channel_url.rstrip('/').split('/')[-1].lower()
            if m_handle == c_handle:
                matched_member = member
                break

    # 2. チャンネル名での完全一致/キーワード一致
    if not matched_member:
        for member in members:
            for kw in member.get('keywords', []):
                if kw in channel_name:
                    matched_member = member
                    break
            if matched_member:
                break

    # 3. タイトルでのキーワード一致
    if not matched_member:
        for member in members:
            for kw in member.get('keywords', []):
                if kw in video_title:
                    matched_member = member
                    break
            if matched_member:
                break

    # 4. 概要欄でのフルネーム一致（誤検出を防ぐためキーワードではなくフルネームを使用）
    if not matched_member:
        for member in members:
            if member.get('name_ja') in description[:500]:
                matched_member = member
                break

    if matched_member:
        result['is_hololive']    = True
        result['streamer_name']  = matched_member.get('name_ja', channel_name)
        result['generation']     = matched_member.get('generation', '')
        sys.stderr.write(
            f"[CONTEXT] Matched hololive member: {result['streamer_name']} ({result['generation']})\\n"
        )
    else:
        result['streamer_name'] = channel_name
        sys.stderr.write(f'[CONTEXT] Not a hololive member, using channel name: {channel_name}\\n')
    sys.stderr.flush()

    # ── ゲームタイトル抽出 ────────────────────────────────────────────────
    # yt-dlp の info.json には 'categories' / 'tags' / 'game' フィールドがある場合がある
    game = (info.get('game') or info.get('game_title') or
            info.get('categories', [None])[0] if info.get('categories') else None)
    if not game:
        # タイトルから【ゲーム名】や「ゲーム名」パターンを抽出
        import re
        m = re.search(r'[【「『]([^】」』]{1,30})[】」』]', video_title)
        if m:
            candidate = m.group(1)
            # 「雑談」「コラボ」等の非ゲームキーワードを除外
            SKIP = {'雑談', 'コラボ', '歌枠', '歌配信', 'Vtuber', 'ホロライブ', '告知', 'お知らせ'}
            if candidate not in SKIP:
                game = candidate
    result['game_title'] = game

    # ── 前提文の組み立て ──────────────────────────────────────────────────
    parts = []
    if result['is_hololive']:
        parts.append(f"これはホロライブ{result['generation']}の{result['streamer_name']}さんの配信です。")
    elif result['streamer_name']:
        parts.append(f"これは{result['streamer_name']}さんの配信です。")

    if result['game_title']:
        parts.append(f"配信コンテンツ: {result['game_title']}")
    elif video_title:
        parts.append(f"配信タイトル: {video_title[:80]}")

    result['context_sentence'] = '\\n'.join(parts)
    sys.stderr.write(f"[CONTEXT] Context: {result['context_sentence']!r}\\n")
    sys.stderr.flush()

    return result
