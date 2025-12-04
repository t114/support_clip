# Support Clip - Backend

FastAPIで構築されたSupport Clipのバックエンドサーバーです。動画の文字起こし、クリップ検出、動画処理を行います。

## 技術スタック

- **FastAPI**: 高速なPython Webフレームワーク
- **Faster Whisper**: 音声文字起こし（CTranslate2ベース）
- **Ollama**: ローカルLLMによるクリップ分析
- **yt-dlp**: YouTube動画ダウンロード
- **FFmpeg**: 動画・音声処理
- **pydub**: 音声解析（無音区間検出）

## セットアップ

### 依存関係のインストール

```bash
# 仮想環境を作成（プロジェクトルートで）
python3 -m venv venv

# 仮想環境をアクティベート
source venv/bin/activate  # Linux/Mac
# または
venv\Scripts\activate  # Windows

# 依存関係をインストール
pip install -r backend/requirements.txt
```

### 必要なソフトウェア

#### FFmpeg

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# https://ffmpeg.org/download.html からダウンロード
```

#### Ollama

1. [Ollama](https://ollama.ai/)をインストール
2. モデルをダウンロード:
```bash
ollama pull qwen2.5
```

## サーバーの起動

### 簡単な方法（推奨）

```bash
# プロジェクトルートで
./start_backend.sh
```

### 手動起動

```bash
source venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

サーバーは `http://localhost:8000` で起動します。

## API ドキュメント

サーバー起動後、以下のURLでインタラクティブなAPIドキュメントにアクセスできます:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 主要なエンドポイント

### 動画管理

- `POST /upload` - 動画ファイルのアップロード
- `POST /youtube/download` - YouTube動画のダウンロード
- `GET /video/{video_id}/info` - 動画情報の取得

### 文字起こし

- `POST /transcribe/{video_id}` - 文字起こし開始
- `GET /download/{video_id}/{filename}` - VTT/SRTファイルのダウンロード

### クリップ検出・編集

- `POST /detect-clips/{video_id}` - AIによるクリップ検出
- `POST /extract-clip` - 個別クリップの抽出
- `POST /merge-clips` - 複数クリップの結合
- `POST /evaluate-clip` - クリップ品質評価

### エクスポート

- `POST /generate-fcpxml` - Final Cut Pro XMLの生成
- `POST /burn-subtitles` - 字幕焼き込み動画の生成

## プロジェクト構造

```
backend/
├── main.py                 # FastAPIアプリケーション、APIエンドポイント
├── config.py              # 設定ファイル（Ollama、クリップ設定等）
├── transcribe.py          # Faster Whisperによる文字起こし
├── clip_detector.py       # AIクリップ検出ロジック
├── video_clipper.py       # 動画クリップ抽出・結合
├── video_processing.py    # 動画処理（字幕焼き込み等）
├── youtube_downloader.py  # YouTube動画ダウンロード
├── fcpxml_generator.py    # FCPXML生成
├── ass_generator.py       # ASS字幕ファイル生成
├── requirements.txt       # Python依存関係
└── uploads/              # アップロードファイル保存先
```

## 設定

`config.py` で以下の設定を変更できます:

```python
# Ollama設定
OLLAMA_MODEL = "qwen2.5"  # 使用するLLMモデル
OLLAMA_HOST = "http://localhost:11434"

# クリップ検出設定
MIN_CLIP_DURATION = 10  # 最小クリップ長（秒）
MAX_CLIP_DURATION = 60  # 最大クリップ長（秒）
DEFAULT_MAX_CLIPS = 5   # デフォルトの最大クリップ数

# YouTube設定
YOUTUBE_DOWNLOAD_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
```

## クリップ検出アルゴリズム

### ハイブリッド検出方式

`detect_boundaries_hybrid()` は以下を組み合わせてクリップ境界を検出します:

1. **無音区間検出** (pydub)
   - 音声の無音部分を検出
   - 話の区切りとして使用

2. **文章区切り検出**
   - 句読点や改行を検出
   - 文章の終わりを境界候補とする

3. **時間制約**
   - MIN_CLIP_DURATION以上の長さを確保
   - MAX_CLIP_DURATIONを超えないように制限

### AI分析方式

`analyze_transcript_with_ai()` はOllamaを使用して:

1. 文字起こしテキストを分析
2. トピックの境界を検出
3. 各クリップのタイトルと説明を生成
4. 短すぎるクリップを自動的に結合

## 開発

### テスト

```bash
# 開発サーバーを起動（ホットリロード有効）
uvicorn backend.main:app --reload
```

### デバッグ

ログは標準エラー出力に出力されます。詳細なログを確認するには:

```bash
uvicorn backend.main:app --reload --log-level debug
```

## トラブルシューティング

### Ollamaに接続できない

```bash
# Ollamaサービスが起動しているか確認
ollama list

# サーバーを起動
ollama serve
```

### ModuleNotFoundError

```bash
# 仮想環境がアクティベートされているか確認
which python

# 依存関係を再インストール
pip install -r backend/requirements.txt
```

### FFmpegエラー

```bash
# FFmpegがインストールされているか確認
ffmpeg -version
```

## ライセンス

MIT License
