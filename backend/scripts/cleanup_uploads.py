#!/usr/bin/env python3
import os
import sys
import time
import argparse
import shutil
import glob
from datetime import datetime, timedelta

# 設定
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

def get_disk_info(path):
    """パスのディスク使用状況を取得 (全体)"""
    total, used, free = shutil.disk_usage(path)
    return {
        "total": total,
        "used": used,
        "free": free,
        "percent": (used / total) * 100
    }

def get_dir_size(path):
    """ディレクトリの合計サイズを取得"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
    return total_size

def format_size(size):
    """バイトを読みやすい形式に変換"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0

def get_video_id(filename):
    """ファイル名からYouTube ID（またはベース名）を抽出"""
    # [ID].[ext] or [ID].*.json or [ID].mp4.fcpxml などを想定
    return filename.split('.')[0]

def cleanup(target_size_gb=None, days=None, force=False):
    if not os.path.exists(UPLOAD_DIR):
        print(f"エラー: ディレクトリが見つかりません: {UPLOAD_DIR}")
        return

    print("=== ディスク使用状況 レポート ===")
    disk = get_disk_info(UPLOAD_DIR)
    uploads_size = get_dir_size(UPLOAD_DIR)
    
    print(f"全体ディスク  : {format_size(disk['used'])} / {format_size(disk['total'])} ({disk['percent']:.1f}% 使用中)")
    print(f"uploads/合計 : {format_size(uploads_size)}")
    print("================================")

    # 全ファイルをリストアップし、更新日時でソート
    all_files = []
    for f in os.listdir(UPLOAD_DIR):
        fp = os.path.join(UPLOAD_DIR, f)
        if os.path.isfile(fp):
            all_files.append({
                "name": f,
                "path": fp,
                "mtime": os.path.getmtime(fp),
                "size": os.path.getsize(fp)
            })
    
    # 更新日時が古い順にソート
    all_files.sort(key=lambda x: x['mtime'])

    delete_ids = set()
    reason = ""

    if days is not None:
        # 日付ベースの削除
        cutoff = time.time() - (days * 86400)
        reason = f"{days}日前より古いIDを削除します"
        for f in all_files:
            if f['mtime'] < cutoff:
                delete_ids.add(get_video_id(f['name']))
    
    elif target_size_gb is not None:
        # 容量ベースの削除
        target_bytes = target_size_gb * (1024**3)
        current_size = uploads_size
        reason = f"uploads/ の合計を {format_size(target_bytes)} 以下に削減します"
        
        if current_size <= target_bytes:
            print(f"現在の容量 ({format_size(current_size)}) は既に目標値以下です。")
            return

        # 古いファイルから順に、そのIDに関連する全ファイルを削除リストに加える
        for f in all_files:
            vid = get_video_id(f['name'])
            if vid not in delete_ids:
                # このIDに関連する全ファイルを特定してサイズ計算
                related_files = glob.glob(os.path.join(UPLOAD_DIR, f"{vid}*"))
                id_size = sum(os.path.getsize(rf) for rf in related_files if os.path.isfile(rf))
                
                delete_ids.add(vid)
                current_size -= id_size
                
                if current_size <= target_bytes:
                    break
    else:
        print("削除モードが指定されていません。--help を参照してください。")
        return

    if not delete_ids:
        print("削除対象のファイルは見つかりませんでした。")
        return

    # 削除対象のファイル一覧と合計容量の算出 (重複を避けるためにセットを使用)
    target_files_set = set()
    total_to_delete = 0
    for vid in delete_ids:
        # IDに共通のプレフィックスがある場合、globが重複する可能性があるため
        related = glob.glob(os.path.join(UPLOAD_DIR, f"{vid}*"))
        for rf in related:
            if os.path.isfile(rf) and rf not in target_files_set:
                try:
                    size = os.path.getsize(rf)
                    target_files_set.add(rf)
                    total_to_delete += size
                except OSError:
                    continue

    # ソートしてリスト化（表示用）
    target_files = sorted(list(target_files_set))

    print(f"\n[削除予定の概要]")
    print(f"理由: {reason}")
    print(f"対象ID数: {len(delete_ids)}")
    print(f"対象ファイル数: {len(target_files)}")
    print(f"削減予定容量: {format_size(total_to_delete)}")

    if not force:
        print("\n[注意] ドライランモードです。実際に削除するには --force オプションを付けて実行してください。")
        print("削除対象のID例 (最大10件):")
        for vid in list(delete_ids)[:10]:
            print(f" - {vid}*")
        return

    print("\n削除を実行中...")
    deleted_count = 0
    actual_deleted_size = 0
    for rf in target_files:
        if not os.path.exists(rf):
            continue
        try:
            size = os.path.getsize(rf)
            os.remove(rf)
            deleted_count += 1
            actual_deleted_size += size
        except Exception as e:
            print(f"エラー: {rf} の削除に失敗しました: {e}")

    print(f"\n完了: {deleted_count} 個のファイルを削除しました。")
    print(f"実際に削減された容量: {format_size(actual_deleted_size)}")
    
    print("\n=== 実行後 ディスク状況 ===")
    new_disk = get_disk_info(UPLOAD_DIR)
    new_uploads_size = get_dir_size(UPLOAD_DIR)
    print(f"全体ディスク  : {format_size(new_disk['used'])} / {format_size(new_disk['total'])} ({new_disk['percent']:.1f}% 使用中)")
    print(f"uploads/合計 : {format_size(new_uploads_size)}")
    print("================================")

def main():
    parser = argparse.ArgumentParser(
        description="Support Clip: uploads/ ディレクトリのクリーンアップスクリプト",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False
    )
    
    parser.add_argument('-h', '--help', action='store_true', help='使い方のヘルプを表示')
    parser.add_argument('--target-size', type=float, help='目標の合計容量 (GB) (例: 50)')
    parser.add_argument('--days', type=int, help='これより古いファイルを削除 (日数) (例: 30)')
    parser.add_argument('--force', action='store_true', help='実際に削除を実行する（指定がない場合はドライラン）')

    args = parser.parse_args()

    help_text = """
使い方:
  python3 cleanup_uploads.py [オプション]

オプション:
  --target-size GB  uploads ディレクトリがこの容量(GB)以下になるまで古いファイルからID単位で削除します。
  --days DAYS        指定した日数以前に更新されたファイルをID単位で削除します。
  --force           実際に削除を実行します。この指定がない場合は、何が削除されるかを表示するだけです。
  --help, -h        このヘルプを表示します。

例:
  # uploads を 50GB 以下にする（確認のみ）
  python3 cleanup_uploads.py --target-size 50

  # 15日以上前のファイルを実際に削除する
  python3 cleanup_uploads.py --days 15 --force
"""

    if args.help or (args.target_size is None and args.days is None):
        print(help_text)
        return

    cleanup(target_size_gb=args.target_size, days=args.days, force=args.force)

if __name__ == "__main__":
    main()
