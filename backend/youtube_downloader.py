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

def download_youtube_video(url: str, output_dir: str) -> dict:
    """
    Downloads a YouTube video and returns the file path and video info.
    """
    try:
        ydl_opts = {
            'format': YOUTUBE_DOWNLOAD_FORMAT,
            'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }

        print(f"Attempting to download YouTube video: {url}")

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
                "start_time": extract_start_time_from_url(url)
            }

    except yt_dlp.utils.DownloadError as e:
        error_msg = f"YouTube動画のダウンロードに失敗しました: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"予期しないエラーが発生しました: {str(e)}"
        print(error_msg)
        raise e
