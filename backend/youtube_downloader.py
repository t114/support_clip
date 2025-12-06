import yt_dlp
import os
import uuid
import re
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
                    if download_comments and not has_comments:
                        print(f"Video cached but comments missing. Downloading comments for: {url}")
                        # コメントのみダウンロードする設定
                        ydl_opts_comments = {
                            'skip_download': True,  # 動画はダウンロードしない
                            'writeinfojson': True,  # info.jsonを保存（コメント含む）
                            'getcomments': True,    # コメントを取得
                            'writesubtitles': True, # 字幕（ライブチャット含む）を取得
                            'subtitleslangs': ['live_chat'], # ライブチャットを指定
                            'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
                            'quiet': True,
                            'no_warnings': True,
                        }
                        with yt_dlp.YoutubeDL(ydl_opts_comments) as ydl_c:
                            ydl_c.extract_info(url, download=True)
                        
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
                        "comments_file": live_chat_file if os.path.exists(live_chat_file) else (comments_file if os.path.exists(comments_file) else None)
                    }
        
        # キャッシュがない場合は通常のダウンロード
        print(f"Downloading new video: {url}")
        
        ydl_opts = {
            'format': YOUTUBE_DOWNLOAD_FORMAT,
            'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        # コメント取得オプション
        if download_comments:
            ydl_opts['writeinfojson'] = True
            ydl_opts['getcomments'] = True
            ydl_opts['writesubtitles'] = True
            ydl_opts['subtitleslangs'] = ['live_chat']

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
                "comments_file": final_comments_file
            }

    except yt_dlp.utils.DownloadError as e:
        error_msg = f"YouTube動画のダウンロードに失敗しました: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"予期しないエラーが発生しました: {str(e)}"
        print(error_msg)
        raise e
