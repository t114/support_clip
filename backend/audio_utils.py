import os
import subprocess
import sys

# UVR5に使用するデフォルトモデル（MDX-Netを推奨。初回起動時に自動ダウンロードされる）
UVR5_MODEL = 'UVR-MDX-NET-Inst_HQ_3.onnx'

def separate_vocals_uvr5(audio_path: str) -> tuple[str, bool]:
    """
    UVR5 (audio-separator) を使って BGM を除去し、ボーカル・音声のみのファイルを返す。

    audio-separator ライブラリがインストールされていない場合やエラー時は元のパスをそのまま返す。

    Returns:
        (vocals_path, is_temp): vocals_path はボーカルのみの音声ファイルパス。
                               is_temp=True の場合は使用後に削除が必要。
    """
    try:
        from audio_separator.separator import Separator
    except ImportError:
        sys.stderr.write('[UVR5] audio-separator not installed, skipping vocal separation\\n')
        sys.stderr.flush()
        return audio_path, False

    # 出力ディレクトリは入力ファイルと同じ場所
    output_dir = os.path.dirname(os.path.abspath(audio_path))
    base_name = os.path.splitext(os.path.basename(audio_path))[0]

    sys.stderr.write(f'[UVR5] Separating vocals with model: {UVR5_MODEL}\\n')
    sys.stderr.write(f'[UVR5] Input: {audio_path}\\n')
    sys.stderr.flush()

    try:
        separator = Separator(
            output_dir=output_dir,
            output_format='WAV',
            normalization_threshold=0.9,
            output_single_stem='Vocals',   # Vocals ステムのみ出力
            log_level=40,                  # WARNING以上のみ表示
        )
        separator.load_model(UVR5_MODEL)

        # separate() は [primary, secondary] のファイルパスリストを返す
        output_files = separator.separate(audio_path)

        sys.stderr.write(f'[UVR5] Output files: {output_files}\\n')
        sys.stderr.flush()

        # ボーカルファイルを探す（"Vocals"を含むファイル名）
        vocals_path = None
        for f in output_files:
            abs_f = f if os.path.isabs(f) else os.path.join(output_dir, f)
            if os.path.exists(abs_f) and 'Vocals' in os.path.basename(abs_f):
                vocals_path = abs_f
                break

        # 見つからなければ先頭の出力ファイルを使用
        if vocals_path is None and output_files:
            vocals_path = (output_files[0] if os.path.isabs(output_files[0])
                           else os.path.join(output_dir, output_files[0]))

        if vocals_path and os.path.exists(vocals_path):
            size_mb = os.path.getsize(vocals_path) / 1024 / 1024
            sys.stderr.write(f'[UVR5] Vocals extracted: {vocals_path} ({size_mb:.1f} MB)\\n')
            sys.stderr.flush()

            # Instrumental (伴奏) ファイルがあれば即座に削除（不要）
            for f in output_files:
                abs_f = f if os.path.isabs(f) else os.path.join(output_dir, f)
                if abs_f != vocals_path and os.path.exists(abs_f):
                    try:
                        os.remove(abs_f)
                        sys.stderr.write(f'[UVR5] Removed instrumental: {abs_f}\\n')
                    except Exception:
                        pass
            sys.stderr.flush()
            return vocals_path, True
        else:
            sys.stderr.write('[UVR5] Vocals file not found in output, using original\\n')
            sys.stderr.flush()
            return audio_path, False

    except Exception as e:
        sys.stderr.write(f'[UVR5] Separation failed: {e}\\n')
        sys.stderr.flush()
        return audio_path, False


def prepare_audio_for_whisper(video_path: str) -> tuple[str, bool]:
    """
    Whisperの認識精度向上のため、入力ファイルを 16,000Hz / mono の WAV に変換する。
    ffmpeg がインストールされていない場合は元のパスをそのまま返す。

    Returns:
        (audio_path, is_temp): audio_path は渡すべきファイルパス。
                               is_temp=True の場合は使用後に削除が必要。
    """
    try:
        # ffmpeg が使えるか確認
        subprocess.run(
            ['ffmpeg', '-version'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.stderr.write('[AUDIO_PREP] ffmpeg not found, skipping WAV conversion\\n')
        sys.stderr.flush()
        return video_path, False

    # 一時 WAV ファイルを入力動画と同じディレクトリに作成
    base = os.path.splitext(video_path)[0]
    wav_path = f'{base}.__whisper_tmp__.wav'

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-ac', '1',          # mono
        '-ar', '16000',      # 16 kHz
        '-sample_fmt', 's16',  # 16-bit PCM
        '-vn',               # 映像トラック除外
        wav_path,
    ]

    sys.stderr.write(f'[AUDIO_PREP] Converting to 16kHz mono WAV: {wav_path}\\n')
    sys.stderr.flush()

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=600,  # 10分タイムアウト
        )
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', errors='replace')[-500:]
            sys.stderr.write(f'[AUDIO_PREP] ffmpeg error: {err}\\n')
            sys.stderr.flush()
            return video_path, False

        wav_size_mb = os.path.getsize(wav_path) / 1024 / 1024
        sys.stderr.write(f'[AUDIO_PREP] WAV ready: {wav_size_mb:.1f} MB\\n')
        sys.stderr.flush()
        return wav_path, True

    except subprocess.TimeoutExpired:
        sys.stderr.write('[AUDIO_PREP] ffmpeg timed out, using original file\\n')
        sys.stderr.flush()
        if os.path.exists(wav_path):
            os.remove(wav_path)
        return video_path, False
    except Exception as e:
        sys.stderr.write(f'[AUDIO_PREP] Unexpected error: {e}\\n')
        sys.stderr.flush()
        return video_path, False
