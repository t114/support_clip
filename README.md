# Support Clip

YouTube動画や動画ファイルから自動的に面白いクリップを検出・生成するWebアプリケーションです。AI（Ollama）を使用して動画の文字起こしを分析し、最も興味深いシーンを自動的に特定します。

## 主な機能

### 動画処理
- 🎬 **YouTube動画のダウンロード**: URLを入力するだけで動画をダウンロード（タイムスタンプ付きURL対応）
- 📝 **自動文字起こし**: Faster Whisperを使用した高精度な音声認識
- 🤖 **AI駆動のクリップ検出**: Ollamaを使用してトピックの境界を自動検出
- ✂️ **クリップ編集**: 検出されたクリップの開始・終了時刻を手動で調整可能
- 📊 **品質評価**: AIによるクリップの面白さスコアリング（1-5つ星）
- 💬 **コメント分析**: YouTube Liveコメントの分析機能（各クリップのコメント数カウント）
- 🖼️ **サムネイル画像保存**: 動画からサムネイル画像を自動生成・保存

### 字幕機能
- 🎨 **マルチスタイル字幕**: 複数の字幕スタイルを管理・適用可能
- ⚙️ **デフォルトスタイル選択**: 好みの字幕スタイルをデフォルトとして設定
- 🏷️ **プレフィックス機能**: 各字幕トラックにプレフィックスを設定（話者識別など）
- 👥 **コラボ配信対応**: 複数話者用の字幕スタイル設定

### 出力形式
- 💾 **複数の出力形式**:
  - 個別クリップのダウンロード
  - 全クリップの結合動画
  - Final Cut Pro XML (FCPXML)
  - SRT/VTT字幕ファイル
  - 字幕焼き込み動画（ASS字幕対応）
- 🎨 **リアルタイムプレビュー**: ブラウザ内での動画再生と字幕表示

### パフォーマンス
- 🚀 **キャッシング機能**: ダウンロード済み動画、文字起こし、FCPXMLの再利用
- 📊 **進捗管理**: 複数動画の同時処理と進捗追跡をサポート

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

**方法1: 起動スクリプトを使用（推奨）**

```bash
./start_backend.sh
```

**方法2: Makefileを使用**

```bash
make start    # サーバー起動
make stop     # サーバー停止
make restart  # サーバー再起動
make status   # サーバーステータス確認
make logs     # ログ表示
```

**方法3: 手動起動**

```bash
source venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

バックエンドは `http://localhost:8000` で起動します。
APIドキュメントは `http://localhost:8000/docs` で確認できます（Swagger UI）。

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
   - タイムスタンプ付きURLにも対応（例: `?t=120` や `?t=2m30s`）

2. **文字起こし**
   - 「文字起こし開始」ボタンをクリック
   - Faster Whisperが自動的に音声を文字起こし
   - VTT形式で保存され、キャッシュされます

3. **クリップ検出**
   - 「クリップを検出」ボタンをクリック
   - AIが以下の方式で境界を検出:
     - 無音区間検出（pydub使用）
     - 文章区切り検出（句読点、改行）
     - AI分析（Ollama使用）
   - 各クリップにタイトル、説明、品質スコアが付与されます

4. **編集と調整**
   - 検出されたクリップをプレビュー
   - 必要に応じて開始・終了時刻を調整
   - 不要なクリップを削除
   - 字幕スタイルを編集（色、フォントサイズ、位置など）
   - マルチスタイル字幕を設定（複数話者の場合）

5. **エクスポート**
   - 個別クリップをダウンロード
   - 全クリップを結合してダウンロード
   - FCPXMLをエクスポートして動画編集ソフトで使用
   - 字幕焼き込み動画を生成（カスタムスタイル対応）
   - SRT/VTT字幕ファイルをダウンロード

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
├── backend/                       # FastAPIバックエンド
│   ├── main.py                   # メインAPIエンドポイント (530行)
│   ├── transcribe.py             # Faster Whisper文字起こし機能 (199行)
│   ├── clip_detector.py          # AIクリップ検出ロジック (873行) - 最重要モジュール
│   │                             # - 無音区間検出
│   │                             # - 文章区切り検出
│   │                             # - AI分析による境界検出
│   │                             # - 品質評価（1-5つ星）
│   │                             # - コメント分析
│   ├── video_clipper.py          # 動画クリップ抽出・結合 (73行)
│   ├── video_processing.py       # 動画処理・字幕焼き込み (116行)
│   ├── youtube_downloader.py     # YouTube動画ダウンロード (253行)
│   │                             # - タイムスタンプ付きURL対応
│   │                             # - キャッシング機能
│   ├── fcpxml_generator.py       # FCPXML生成 (163行)
│   ├── ass_generator.py          # ASS字幕生成 (238行)
│   ├── progress.py               # 進捗管理システム (32行)
│   ├── config.py                 # 設定ファイル (14行)
│   ├── requirements.txt          # Python依存関係
│   ├── uploads/                  # アップロードファイル保存先
│   └── assets/                   # サムネイル等の生成ファイル
├── frontend/                     # React フロントエンド
│   ├── src/
│   │   ├── App.jsx              # メインアプリケーション
│   │   ├── main.jsx             # Reactエントリーポイント
│   │   ├── components/
│   │   │   ├── YouTubeClipCreator.jsx # メインUI (522行)
│   │   │   ├── VideoPlayer.jsx        # ビデオプレイヤー (222行)
│   │   │   ├── ClipPreview.jsx        # クリッププレビュー (274行)
│   │   │   ├── StyleEditor.jsx        # 字幕スタイルエディタ (340行)
│   │   │   ├── SubtitleEditor.jsx     # 字幕エディタ (165行)
│   │   │   └── Upload.jsx             # ファイルアップロード (109行)
│   │   ├── utils/
│   │   │   └── vtt.js           # VTT字幕パースユーティリティ
│   │   ├── index.css            # グローバルスタイル
│   │   └── App.css              # アプリケーションスタイル
│   ├── public/                  # 静的ファイル
│   ├── dist/                    # ビルド出力
│   └── package.json             # Node.js依存関係
├── docs/
│   └── DAVINCI_RESOLVE.md       # DaVinci Resolve連携ガイド
├── venv/                        # Python仮想環境
├── Makefile                     # サーバー管理コマンド
├── start_backend.sh             # バックエンド起動スクリプト
├── debug_comments.py            # コメント分析デバッグスクリプト
├── log_config.ini               # ロギング設定
└── .gitignore                   # Git除外設定
```

## API エンドポイント

主要なAPIエンドポイント:

### 動画管理
- `POST /upload` - 動画ファイルのアップロード
- `POST /youtube/download` - YouTube動画のダウンロード（タイムスタンプ付きURL対応）
- `GET /progress/{video_id}` - 進捗状況取得（ダウンロード、文字起こしなど）

### 分析・処理
- `POST /transcribe/{video_id}` - 文字起こし開始
- `POST /detect-clips/{video_id}` - クリップ検出（無音区間、文章区切り、AI分析）
- `POST /youtube/analyze` - YouTube動画の統合分析（ダウンロード〜クリップ検出まで）

### クリップ操作
- `POST /extract-clip` - 個別クリップ抽出
- `POST /merge-clips` - クリップ結合

### エクスポート
- `POST /burn` - 字幕焼き込み動画生成（ASS字幕対応）
- `GET /download/{filename}` - ファイルダウンロード
- `POST /generate-fcpxml` - FCPXML生成
- `POST /generate-srt` - SRT字幕生成

### ユーティリティ
- `GET /static/{file_path}` - 静的ファイル配信（動画、字幕など）

詳細は `http://localhost:8000/docs` のSwagger UIを参照してください。

## 高度な機能

### ハイブリッドクリップ検出

`backend/clip_detector.py` (873行) は以下の検出方式を組み合わせています:

1. **無音区間検出** (`detect_silence_boundaries`)
   - pydubで音声の無音部分を検出
   - デフォルト: 800ms以上の無音（-40dB）

2. **文章区切り検出** (`detect_sentence_boundaries`)
   - 句読点や改行を検出して境界候補を生成

3. **AI分析方式** (`analyze_transcript_with_ai`)
   - Ollama (qwen2.5) を使用してトピック境界を検出
   - 各クリップのタイトルと説明を自動生成
   - 短すぎるクリップの自動結合

4. **品質評価** (`evaluate_clip_quality`)
   - AIによる面白さスコアリング（1-5つ星）

5. **コメント分析** (`count_comments_in_clips`)
   - YouTube Liveコメントを分析して各クリップのコメント数をカウント

### キャッシング機能

以下のデータがキャッシュされ、再利用されます:
- ダウンロード済みYouTube動画
- 文字起こし済みVTTファイル
- 生成済みFCPXMLファイル
- サムネイル画像

これにより、同じ動画を再処理する際の時間を大幅に短縮できます。

### 進捗管理

`backend/progress.py` によるインメモリ進捗管理:
- 複数の同時動画処理をサポート
- 動画IDごとの進捗追跡
- ステータス: `downloading`, `transcribing`, `completed`, `error`
- タイムスタンプ付き進捗情報

## トラブルシューティング

### Ollamaに接続できない

```bash
# Ollamaが起動しているか確認
ollama list

# サーバーを再起動
ollama serve

# モデルがダウンロードされているか確認
ollama pull qwen2.5
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

### バックエンドサーバーが起動しない

```bash
# プロセスが既に起動しているか確認
make status

# 既存プロセスを停止
make stop

# 再起動
make start

# ログを確認
make logs
```

### メモリ不足エラー

大きな動画ファイルや長時間の動画を処理する場合、メモリ不足になることがあります:
- より小さなモデルを使用（`config.py`で設定）
- クリップの最大数を減らす
- システムのメモリを増やす

## ライセンス

MIT License

## 最新の更新

### 2025年12月7日
- デフォルトスタイル選択とプレフィックス機能
- マルチスタイル字幕トラックとプレフィックス機能
- YouTube動画ダウンロードのpostprocessing問題を修正

### 2025年12月3日
- コメント分析機能の改善とメモリ問題の修正

### 主要な機能追加（過去のアップデート）
- サムネイル画像保存機能
- コラボ配信用の字幕スタイル機能
- 開始位置設定、動画キャッシュ、UI改善

詳細は [コミット履歴](https://github.com/yourusername/support_clip/commits) を参照してください。

## 貢献

プルリクエストを歓迎します！大きな変更の場合は、まずissueを開いて変更内容を議論してください。

### 開発に貢献する際のガイドライン

1. フォークしてブランチを作成
2. コードを変更
3. テストを実行して動作確認
4. プルリクエストを作成

## 関連ドキュメント

- [DaVinci Resolve連携ガイド](./docs/DAVINCI_RESOLVE.md) - SRTファイルをDaVinci ResolveのFusion Text+ノードに変換する方法

## 技術詳細

### コードベース統計
- **バックエンド**: 約2,491行のPythonコード
- **フロントエンド**: 約1,632行のReact/JSXコード
- **最重要モジュール**: `clip_detector.py` (873行) - AIクリップ検出の中核

### 依存関係のバージョン
主要な依存関係は定期的に更新されます。詳細は以下を参照:
- バックエンド: `backend/requirements.txt`
- フロントエンド: `frontend/package.json`

## 作者

開発者情報をここに記載
