import yt_dlp
import os
import uuid
from .config import YOUTUBE_DOWNLOAD_FORMAT

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
                "filename": os.path.basename(filename)
            }

    except yt_dlp.utils.DownloadError as e:
        error_msg = f"YouTube動画のダウンロードに失敗しました: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"予期しないエラーが発生しました: {str(e)}"
        print(error_msg)
        raise e
