import yt_dlp
import os
import uuid
import re
import json
from urllib.parse import urlparse, parse_qs
from .config import YOUTUBE_DOWNLOAD_FORMAT

def extract_start_time_from_url(url: str) -> int:
    """
    YouTube URLからt=パラメータを抽出して秒数を返す
    例: t=120, t=2m30s, t=1h2m3s
    
    Args:
        url: YouTube URL
        
    Returns:
        開始時刻（秒）、パラメータがない場合は0
    """
    try:
        # クエリパラメータから t= を取得
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        if 't' in params:
            t_value = params['t'][0]
            
            # 数値のみの場合（秒）
            if t_value.isdigit():
                return int(t_value)
            
            # Check for colon format like 1:02:03 or 02:03
            if ':' in t_value:
                parts = t_value.split(':')
                if len(parts) == 3: # H:M:S
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                elif len(parts) == 2: # M:S
                    return int(parts[0]) * 60 + int(parts[1])
            
            # h/m/s形式の場合
            hours = re.search(r'(\d+)h', t_value)
            minutes = re.search(r'(\d+)m', t_value)
            seconds = re.search(r'(\d+)s', t_value)
            
            total_seconds = 0
            if hours:
                total_seconds += int(hours.group(1)) * 3600
            if minutes:
                total_seconds += int(minutes.group(1)) * 60
            if seconds:
                total_seconds += int(seconds.group(1))
            
            return total_seconds
    except Exception as e:
        print(f"Error extracting start time from URL: {e}")
    
    return 0

def extract_video_id(url: str) -> str:
    """
    Extracts video ID from YouTube URL using regex.
    """
    try:
        match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
        return match.group(1) if match else None
    except:
        return None

def download_youtube_video(url: str, output_dir: str, download_comments: bool = False) -> dict:
    """
    Downloads a YouTube video and returns the file path and video info.
    既にダウンロード済みの場合はキャッシュを使用。
    """
    try:
        # まず動画情報のみを取得（ダウンロードなし）
        ydl_opts_info = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'noplaylist': True,
            'playlist_items': '1',
        }
        
        print(f"Fetching video info for: {url}")
        
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except yt_dlp.utils.DownloadError as de:
                error_msg = str(de)
                print(f"DownloadError: {error_msg}")
                if "Private video" in error_msg:
                    raise Exception("この動画は非公開のため、ダウンロードできません")
                elif "members-only" in error_msg or "available to this channel's members" in error_msg:
                    raise Exception("この動画はメンバー限定のため、ダウンロードできません")
                elif "This video is not available" in error_msg:
                    raise Exception("この動画は利用できません（削除されたか、地域制限されている可能性があります）")
                elif "age" in error_msg.lower():
                    raise Exception("この動画は年齢制限があるため、ダウンロードできません")
                elif "This live event has ended" in error_msg:
                    video_id = extract_video_id(url)
                    return {
                        "file_path": None,
                        "title": "アーカイブ処理中 (YouTube)",
                        "duration": 0,
                        "thumbnail": "",
                        "id": video_id,
                        "filename": None,
                        "start_time": extract_start_time_from_url(url),
                        "cached": False,
                        "comments_file": None,
                        "is_processing": True,
                        "url": url
                    }
                else:
                    raise Exception(f"ダウンロードエラー: {error_msg}")
            
            video_id = info.get('id', '')
            
            # キャッシュ確認：動画IDでファイルを検索
            for ext in ['.mp4', '.mkv', '.webm']:
                cached_file = os.path.join(output_dir, f"{video_id}{ext}")
                if os.path.exists(cached_file):
                    print(f"Using cached video: {cached_file}")
                    
                    # コメントファイルの確認
                    comments_file = os.path.join(output_dir, f"{video_id}.info.json")
                    live_chat_file = os.path.join(output_dir, f"{video_id}.live_chat.json")
                    has_comments = os.path.exists(comments_file) or os.path.exists(live_chat_file)
                    
                    # コメントが必要で、まだない場合はダウンロードが必要
                    # また、ライブ配信だったのにlive_chatがない場合も再試行
                    is_live_archive = False
                    if os.path.exists(comments_file):
                        try:
                            with open(comments_file, 'r', encoding='utf-8') as f:
                                info_data = json.load(f)
                                if info_data.get('was_live') or info_data.get('is_live'):
                                    is_live_archive = True
                        except:
                            pass

                    missing_live_chat = is_live_archive and not os.path.exists(live_chat_file)
                    
                    if download_comments and (not has_comments or missing_live_chat):
                        print(f"Video cached but comments missing (or live chat missing). Downloading comments for: {url}")
                        # コメントのみダウンロードする設定
                        ydl_opts_comments = {
                            'skip_download': True,  # 動画はダウンロードしない
                            'writeinfojson': True,  # info.jsonを保存（コメント含む）
                            'getcomments': True,    # コメントを取得
                            'writesubtitles': True, # 字幕（ライブチャット含む）を取得
                            'writeautomaticsub': True, # 自動生成字幕（一部のライブチャット）も取得
                            'subtitleslangs': ['live_chat'], # ライブチャットを指定
                            'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
                            'quiet': False,
                            'no_warnings': False,
                            'noplaylist': True,
                            'playlist_items': '1',
                        }
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts_comments) as ydl_c:
                                ydl_c.extract_info(url, download=True)
                        except Exception as e:
                            print(f"Warning: Failed to download comments/live chat: {e}")
                            # Continue without comments if download fails
                        
                        # 再確認
                        has_comments = os.path.exists(comments_file) or os.path.exists(live_chat_file)

                    return {
                        "file_path": cached_file,
                        "title": info.get('title', 'Unknown Title'),
                        "duration": info.get('duration', 0),
                        "thumbnail": info.get('thumbnail', ''),
                        "id": video_id,
                        "filename": os.path.basename(cached_file),
                        "start_time": extract_start_time_from_url(url),
                        "cached": True,
                        "comments_file": live_chat_file if os.path.exists(live_chat_file) else (comments_file if os.path.exists(comments_file) else None),
                        "channel_id": info.get('channel_id'),
                        "upload_date": info.get('upload_date')
                    }
                else:
                    # Not cached, but check for comments_file anyway later
                    pass
        
        # ... download code ...
        # (Already handles it at the end)
        
        # キャッシュがない場合は通常のダウンロード
        print(f"Downloading new video: {url}")
        
        ydl_opts = {
            'format': YOUTUBE_DOWNLOAD_FORMAT,
            'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
            'noplaylist': True,
            'playlist_items': '1',
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'merge_output_format': 'mp4',  # Ensure output is mp4
            'postprocessor_args': {
                'ffmpeg': ['-c', 'copy']  # Use stream copy to avoid re-encoding
            },
            # Use Android client to bypass 403 Forbidden
            'extractor_args': {'youtube': {'player_client': ['android']}},
        }
        
        # コメント取得オプションはここでは設定しない（後で別に行う）
        # if download_comments:
        #     ydl_opts['writeinfojson'] = True
        #     ydl_opts['getcomments'] = True
        #     ydl_opts['writesubtitles'] = True
        #     ydl_opts['subtitleslangs'] = ['live_chat']

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except yt_dlp.utils.DownloadError as de:
                error_msg = str(de)
                print(f"DownloadError: {error_msg}")
                if "Private video" in error_msg:
                    raise Exception("この動画は非公開のため、ダウンロードできません")
                elif "members-only" in error_msg or "available to this channel's members" in error_msg:
                    raise Exception("この動画はメンバー限定のため、ダウンロードできません")
                elif "This video is not available" in error_msg:
                    raise Exception("この動画は利用できません（削除されたか、地域制限されている可能性があります）")
                elif "age" in error_msg.lower():
                    raise Exception("この動画は年齢制限があるため、ダウンロードできません")
                elif "This live event has ended" in error_msg:
                    video_id = extract_video_id(url)
                    return {
                        "file_path": None,
                        "title": "アーカイブ処理中 (YouTube)",
                        "duration": 0,
                        "thumbnail": "",
                        "id": video_id,
                        "filename": None,
                        "start_time": extract_start_time_from_url(url),
                        "cached": False,
                        "comments_file": None,
                        "is_processing": True,
                        "url": url
                    }
                else:
                    raise Exception(f"ダウンロードエラー: {error_msg}")

            filename = ydl.prepare_filename(info)

            # yt-dlp might change the extension (e.g. mkv -> mp4)
            # but prepare_filename usually gives the correct one.
            # However, sometimes it merges formats and the ext changes.
            # Let's verify the file exists.
            if not os.path.exists(filename):
                # Try to find the file if the extension is different
                base_name = os.path.splitext(filename)[0]
                for ext in ['.mp4', '.mkv', '.webm']:
                    if os.path.exists(f"{base_name}{ext}"):
                        filename = f"{base_name}{ext}"
                        break
            
            # コメントファイル（info.json または live_chat.json）のパス
            video_id = info.get('id', '')
            comments_file = os.path.join(output_dir, f"{video_id}.info.json")
            live_chat_file = os.path.join(output_dir, f"{video_id}.live_chat.json")
            
            # コメントのダウンロード（動画ダウンロード後に行う）
            if download_comments:
                print(f"Downloading comments for: {url}")
                ydl_opts_comments = {
                    'skip_download': True,
                    'writeinfojson': True,
                    'getcomments': True,
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': ['live_chat'],
                    'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
                    'quiet': False,
                    'no_warnings': False,
                    'noplaylist': True,
                    'playlist_items': '1',
                }
                try:
                    with yt_dlp.YoutubeDL(ydl_opts_comments) as ydl_c:
                        ydl_c.extract_info(url, download=True)
                except Exception as e:
                    print(f"Warning: Failed to download comments/live chat: {e}")
                    # Continue without comments
            
            final_comments_file = None
            if os.path.exists(live_chat_file):
                final_comments_file = live_chat_file
            elif os.path.exists(comments_file):
                final_comments_file = comments_file

            if not os.path.exists(filename):
                raise Exception(f"ダウンロードしたファイルが見つかりません: {filename}")

            print(f"Successfully downloaded: {filename}")

            return {
                "file_path": filename,
                "title": info.get('title', 'Unknown Title'),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', ''),
                "id": info.get('id', ''),
                "filename": os.path.basename(filename),
                "start_time": extract_start_time_from_url(url),
                "cached": False,
                "comments_file": final_comments_file,
                "channel_id": info.get('channel_id'),
                "upload_date": info.get('upload_date')
            }

    except yt_dlp.utils.DownloadError as e:
        error_msg = f"YouTube動画のダウンロードに失敗しました: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"予期しないエラーが発生しました: {str(e)}"
        print(error_msg)
        raise e

def download_low_quality_for_analysis(url: str, output_dir: str) -> dict:
    """
    Downloads a low quality (360p) version of the video for analysis purposes.
    Also downloads comments/metadata.
    """
    try:
        print(f"Downloading low quality (360p) video for analysis: {url}")
        
        # 360p以下のMP4を優先
        format_spec = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360]/best"
        
        ydl_opts = {
            'format': format_spec,
            'outtmpl': os.path.join(output_dir, '%(id)s_360p.%(ext)s'),
            'noplaylist': True,
            'playlist_items': '1',
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
            'merge_output_format': 'mp4',
            'postprocessor_args': {
                'ffmpeg': ['-c', 'copy']
            },
            # Use Android client to bypass 403 Forbidden even for 360p just in case
            'extractor_args': {'youtube': {'player_client': ['android']}},
            
            # Download comments/info as well
            'writeinfojson': True,
            'getcomments': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['live_chat'],
        }
        
        # Check for existing file using regex ID extraction FIRST (fast check)
        video_id = extract_video_id(url)
        
        if video_id:
            logger_msg = f"Fast checking cache for video_id: {video_id} in {output_dir}"
            print(logger_msg)
            
            potential_files = [
                os.path.join(output_dir, f"{video_id}_360p.mp4"),
                os.path.join(output_dir, f"{video_id}_360p.mkv"),
                os.path.join(output_dir, f"{video_id}_360p.webm"),
                # Also check for high quality versions (no need to redownload if we have better)
                os.path.join(output_dir, f"{video_id}.mp4"),
                os.path.join(output_dir, f"{video_id}.mkv"),
                os.path.join(output_dir, f"{video_id}.webm")
            ]
            
            existing_file = None
            for f in potential_files:
                if os.path.exists(f):
                    existing_file = f
                    break
            
            if existing_file:
                print(f"Using cached video for analysis (fast check): {existing_file}")
                
                # Check for comments
                # Check both 360p-specific and standard comment files
                comments_file_360 = os.path.join(output_dir, f"{video_id}_360p.info.json")
                live_chat_file_360 = os.path.join(output_dir, f"{video_id}_360p.live_chat.json")
                
                comments_file_std = os.path.join(output_dir, f"{video_id}.info.json")
                live_chat_file_std = os.path.join(output_dir, f"{video_id}.live_chat.json")
                
                final_comments_file = None
                # Prefer 360p specific, then standard
                if os.path.exists(live_chat_file_360):
                    final_comments_file = live_chat_file_360
                elif os.path.exists(comments_file_360):
                    final_comments_file = comments_file_360
                elif os.path.exists(live_chat_file_std):
                    final_comments_file = live_chat_file_std
                elif os.path.exists(comments_file_std):
                    final_comments_file = comments_file_std
                
                # Retrieve basic info from file or just placeholder
                title = "Cached Video"
                duration = 0
                thumbnail = ""
                channel_id = ""
                upload_date = ""
                
                info_json_path = None
                if os.path.exists(comments_file_360): info_json_path = comments_file_360
                elif os.path.exists(comments_file_std): info_json_path = comments_file_std or (live_chat_file_std if os.path.exists(live_chat_file_std) else None)
                
                if info_json_path:
                    try:
                        with open(info_json_path, 'r', encoding='utf-8') as f:
                            info_data = json.load(f)
                            title = info_data.get('title', title)
                            duration = info_data.get('duration', duration)
                            thumbnail = info_data.get('thumbnail', thumbnail)
                            channel_id = info_data.get('channel_id', channel_id)
                            upload_date = info_data.get('upload_date', upload_date)
                    except:
                        pass

                return {
                    "file_path": existing_file,
                    "title": title,
                    "duration": duration,
                    "thumbnail": thumbnail,
                    "id": video_id,
                    "filename": os.path.basename(existing_file),
                    "start_time": extract_start_time_from_url(url),
                    "cached": True,
                    "comments_file": final_comments_file,
                    "channel_id": channel_id,
                    "upload_date": upload_date
                }
        
        # Fallback to slow check if regex failed
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=True)
            except yt_dlp.utils.DownloadError as de:
                error_msg = str(de)
                if "This live event has ended" in error_msg:
                    video_id = extract_video_id(url)
                    return {
                        "file_path": None,
                        "title": "アーカイブ処理中 (YouTube)",
                        "duration": 0,
                        "thumbnail": "",
                        "id": video_id,
                        "filename": None,
                        "start_time": extract_start_time_from_url(url),
                        "cached": False,
                        "comments_file": None,
                        "is_processing": True,
                        "url": url
                    }
                raise Exception(f"Download Error (360p): {error_msg}")

            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                # Fallback check
                base_name = os.path.splitext(filename)[0]
                for ext in ['.mp4', '.mkv', '.webm']:
                    if os.path.exists(f"{base_name}{ext}"):
                        filename = f"{base_name}{ext}"
                        break
            
            video_id = info.get('id', '')
            comments_file = os.path.join(output_dir, f"{video_id}_360p.info.json")
            live_chat_file = os.path.join(output_dir, f"{video_id}_360p.live_chat.json")
            
            final_comments_file = None
            if os.path.exists(live_chat_file):
                final_comments_file = live_chat_file
            elif os.path.exists(comments_file):
                final_comments_file = comments_file
            
            # If standard comments file exists (from previous runs), allow using that too
            std_comments_file = os.path.join(output_dir, f"{video_id}.live_chat.json")
            if not final_comments_file and os.path.exists(std_comments_file):
                final_comments_file = std_comments_file

            return {
                "file_path": filename,
                "title": info.get('title', 'Unknown Title'),
                "duration": info.get('duration', 0),
                "thumbnail": info.get('thumbnail', ''),
                "id": video_id,
                "filename": os.path.basename(filename),
                "start_time": extract_start_time_from_url(url),
                "comments_file": final_comments_file,
                "channel_id": info.get('channel_id'),
                "upload_date": info.get('upload_date')
            }

    except Exception as e:
        print(f"Failed to download low quality video: {e}")
        raise e
