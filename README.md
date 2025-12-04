# Support Clip

YouTube動画や動画ファイルから自動的に面白いクリップを検出・生成するWebアプリケーションです。AI（Ollama）を使用して動画の文字起こしを分析し、最も興味深いシーンを自動的に特定します。

## 主な機能

- 🎬 **YouTube動画のダウンロード**: URLを入力するだけで動画をダウンロード
- 📝 **自動文字起こし**: Faster Whisperを使用した高精度な音声認識
- 🤖 **AI駆動のクリップ検出**: Ollamaを使用してトピックの境界を自動検出
- ✂️ **クリップ編集**: 検出されたクリップの開始・終了時刻を手動で調整可能
- 📊 **品質評価**: AIによるクリップの面白さスコアリング（1-5つ星）
- 💾 **複数の出力形式**:
  - 個別クリップのダウンロード
  - 全クリップの結合動画
  - Final Cut Pro XML (FCPXML)
  - SRT字幕ファイル
  - 字幕焼き込み動画
- 🎨 **リアルタイムプレビュー**: ブラウザ内での動画再生と字幕表示

## 技術スタック

### バックエンド
- **FastAPI**: 高速なPython Webフレームワーク
- **Faster Whisper**: 音声文字起こし（OpenAI Whisper最適化版）
- **Ollama**: ローカルLLMによるクリップ分析（デフォルト: qwen2.5）
- **yt-dlp**: YouTube動画ダウンロード
- **FFmpeg**: 動画処理
- **pydub**: 音声解析（無音区間検出）

### フロントエンド
- **React 19**: UIフレームワーク
- **Vite**: 高速ビルドツール
- **Tailwind CSS 4**: スタイリング

## 必要要件

### システム要件
- Python 3.12以上
- Node.js 18以上
- FFmpeg
- Ollama（ローカルLLMサーバー）

### Ollamaのセットアップ

1. [Ollama](https://ollama.ai/)をインストール
2. モデルをダウンロード:
```bash
ollama pull qwen2.5
```

3. Ollamaサーバーを起動（通常は自動起動）:
```bash
ollama serve
```

## インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/yourusername/support_clip.git
cd support_clip
```

### 2. バックエンドのセットアップ

```bash
# 仮想環境を作成
python3 -m venv venv

# 仮想環境をアクティベート
source venv/bin/activate  # Linux/Mac
# または
venv\Scripts\activate  # Windows

# 依存関係をインストール
pip install -r backend/requirements.txt
```

### 3. フロントエンドのセットアップ

```bash
cd frontend
npm install
cd ..
```

## 使い方

### サーバーの起動

#### バックエンド

```bash
./start_backend.sh
```

または手動で:

```bash
source venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

バックエンドは `http://localhost:8000` で起動します。

#### フロントエンド

```bash
cd frontend
npm run dev
```

フロントエンドは `http://localhost:5173` で起動します。

### 基本的なワークフロー

1. **動画のアップロード/ダウンロード**
   - ローカルファイルをアップロード、または
   - YouTube URLを入力してダウンロード

2. **文字起こし**
   - 「文字起こし開始」ボタンをクリック
   - Faster Whisperが自動的に音声を文字起こし

3. **クリップ検出**
   - 「クリップを検出」ボタンをクリック
   - AIが自動的に面白いシーンを検出

4. **編集と調整**
   - 検出されたクリップをプレビュー
   - 必要に応じて開始・終了時刻を調整
   - 不要なクリップを削除

5. **エクスポート**
   - 個別クリップをダウンロード
   - 全クリップを結合してダウンロード
   - FCPXMLをエクスポートして動画編集ソフトで使用

## 設定

`backend/config.py` で以下の設定をカスタマイズできます:

```python
# Ollama設定
OLLAMA_MODEL = "qwen2.5"  # 使用するモデル
OLLAMA_HOST = "http://localhost:11434"

# クリップ検出設定
MIN_CLIP_DURATION = 10  # 最小クリップ長（秒）
MAX_CLIP_DURATION = 60  # 最大クリップ長（秒）
DEFAULT_MAX_CLIPS = 5   # デフォルトの最大クリップ数

# YouTube設定
YOUTUBE_DOWNLOAD_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
```

## プロジェクト構造

```
support_clip/
├── backend/                 # FastAPIバックエンド
│   ├── main.py             # メインAPIエンドポイント
│   ├── transcribe.py       # 文字起こし機能
│   ├── clip_detector.py    # AIクリップ検出
│   ├── video_clipper.py    # 動画クリップ抽出
│   ├── video_processing.py # 動画処理（字幕焼き込み等）
│   ├── youtube_downloader.py # YouTube動画ダウンロード
│   ├── fcpxml_generator.py # FCPXML生成
│   ├── ass_generator.py    # ASS字幕生成
│   ├── config.py           # 設定ファイル
│   ├── requirements.txt    # Python依存関係
│   └── uploads/            # アップロードファイル保存先
├── frontend/               # React フロントエンド
│   ├── src/
│   │   ├── App.jsx        # メインアプリケーション
│   │   └── main.jsx       # エントリーポイント
│   ├── public/            # 静的ファイル
│   └── package.json       # Node.js依存関係
├── venv/                  # Python仮想環境
├── start_backend.sh       # バックエンド起動スクリプト
└── .gitignore            # Git除外設定
```

## API エンドポイント

主要なAPIエンドポイント:

- `POST /upload` - 動画ファイルのアップロード
- `POST /youtube/download` - YouTube動画のダウンロード
- `POST /transcribe/{video_id}` - 文字起こし開始
- `POST /detect-clips/{video_id}` - クリップ検出
- `POST /extract-clip` - クリップ抽出
- `POST /merge-clips` - クリップ結合
- `GET /download/{video_id}/{filename}` - ファイルダウンロード
- `POST /burn-subtitles` - 字幕焼き込み動画生成

詳細は `http://localhost:8000/docs` のSwagger UIを参照してください。

## トラブルシューティング

### Ollamaに接続できない

```bash
# Ollamaが起動しているか確認
ollama list

# サーバーを再起動
ollama serve
```

### FFmpegが見つからない

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# https://ffmpeg.org/download.html からダウンロード
```

### 仮想環境のパスエラー

プロジェクトを移動した場合、仮想環境を再作成してください:

```bash
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

## ライセンス

MIT License

## 貢献

プルリクエストを歓迎します！大きな変更の場合は、まずissueを開いて変更内容を議論してください。

## 関連ドキュメント

- [DaVinci Resolve連携ガイド](./docs/DAVINCI_RESOLVE.md) - SRTファイルをDaVinci ResolveのFusion Text+ノードに変換する方法

## 作者

開発者情報をここに記載
