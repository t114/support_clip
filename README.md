# Support Clip

YouTube動画や動画ファイルから自動的に面白いクリップを検出・生成するWebアプリケーションです。AI（Ollama）を使用して動画の文字起こしを分析し、最も興味深いシーンを自動的に特定します。

> 📋 **サーバー移行完全手順**: [docs/SERVER_MIGRATION.md](./docs/SERVER_MIGRATION.md) を参照してください。

## 主な機能

### 動画処理
- 🎬 **YouTube動画のダウンロード**: URLを入力するだけで動画をダウンロード（タイムスタンプ付きURL対応）
- 📝 **自動文字起こし**: Faster Whisperを使用した高精度な音声認識
- 🤖 **AI駆動のクリップ検出**: Ollamaを使用してトピックの境界を自動検出
- 📹 **OBS録画キャプチャ**: ブラウザソース（YouTube）を座標指定で高画質キャプチャ
- 🎭 **メンバースタンプ同期**: チャンネルのメンバースタンプを自動取得し、字幕や弾幕に反映
- ✂️ **クリップ編集**: 検出されたクリップの開始・終了時刻を手動で調整可能
- 📊 **品質評価**: AIによるクリップの面白さスコアリング（1-5つ星）
- 💬 **コメント分析**: YouTube Liveコメントの分析機能（各クリップのコメント数カウント）
- 🪜 **2画面スタック編集**: 2つの視点を上下に並べた縦型動画（Shorts/TikTok用）の作成
- 🚀 **弾幕焼き込み**: YouTubeのチャットを弾幕として動画に焼き込む機能
- 🐦 **Twitter PR生成**: AIを使用してクリップの魅力を伝えるTwitter(X)用PR文章を自動生成
- 🖼️ **サムネイル画像保存**: 動画からサムネイル画像を自動生成・保存

### 字幕機能
- 🎨 **マルチスタイル字幕**: 複数の字幕スタイルを管理・適用可能
- ⚙️ **デフォルトスタイル選択**: 好みの字幕スタイルをデフォルトとして設定
- 🏷️ **プレフィックス機能**: 各字幕トラックにプレフィックスを設定（話者識別など）
- 👥 **コラボ配信対応**: 複数話者用の字幕スタイル設定
- 🔤 **文字数制限**: 字幕の最大文字数を設定して読みやすさを向上

### 出力形式
- 💾 **複数の出力形式**:
  - 個別クリップのダウンロード
  - 全クリップの結合動画
  - 9:16 縦型動画（レターボックス/スタック形式対応）
  - Final Cut Pro XML (FCPXML)
  - SRT/VTT字幕ファイル
  - 字幕焼き込み動画（ASS字幕対応）
- 🎨 **リアルタイムプレビュー**: ブラウザ内での動画再生と字幕表示

### パフォーマンス
- 🚀 **キャッシング機能**: ダウンロード済み動画、文字起こし、FCPXMLの再利用
- 📊 **進捗管理**: 複数動画の同時処理と進捗追跡をサポート

## 技術スタック

### バックエンド
- **FastAPI**: 高速なPython Webフレームワーク（uvicornで起動）
- **Faster Whisper**: 音声文字起こし（OpenAI Whisper最適化版）
- **Ollama**: ローカルLLMによるクリップ分析（デフォルト: qwen2.5）
- **yt-dlp**: YouTube動画ダウンロード
- **FFmpeg**: 動画処理・字幕焼き込み・クリップ抽出
- **pydub**: 音声解析（無音区間検出）
- **Selenium + ChromeDriver**: OBSキャプチャ用ブラウザ制御
- **obs-websocket-py**: OBS WebSocket経由の録画制御

### フロントエンド
- **React 19**: UIフレームワーク
- **Vite 7**: 高速ビルドツール
- **Tailwind CSS 4**: スタイリング

## 必要要件

### システム要件
- **Python 3.12以上**
- **Node.js 18以上**（nvmでの管理を推奨）
- **FFmpeg**（動画処理全般）
- **Ollama**（ローカルLLMサーバー）
- **OBS Studio**（OBSキャプチャ機能を使う場合）
- **Chromium**（OBSキャプチャ機能を使う場合、Snap版推奨）
- **CUDA対応GPU**（Faster Whisperの高速化に推奨、CPUでも動作可）

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

### OBS Studioのセットアップ（OBSキャプチャ機能を使う場合）

1. OBS Studioをインストール
2. OBS WebSocketサーバーを有効化:
   - OBS → ツール → WebSocketサーバー設定
   - ポート: `4455`
   - パスワード設定（`backend/obs_recorder.py` の `password` と一致させること）
3. シーン `BrowserCapture` を作成し、ブラウザソース `YouTubeSource` を追加

## インストール

### 1. リポジトリのクローン

```bash
git clone https://github.com/natsugumo/support_clip.git
cd support_clip
```

### 2. バックエンドのセットアップ

```bash
# 仮想環境を作成
python3 -m venv venv

# 仮想環境をアクティベート
source venv/bin/activate  # Linux/Mac

# 依存関係をインストール
pip install -r backend/requirements.txt
```

### 3. フロントエンドのセットアップ

```bash
# Node.jsバージョンを設定（nvmを使用している場合）
nvm use  # .nvmrc が存在する場合

cd frontend
npm install
cd ..
```

## 使い方

### サーバーの起動

#### バックエンド

**推奨: Makefileを使用**

```bash
make start    # バックグラウンドでサーバー起動
make stop     # サーバー停止
make restart  # サーバー再起動
make status   # サーバーステータス確認
make logs     # ログ表示（Ctrl+C で終了）
```

**手動起動**

```bash
source venv/bin/activate
uvicorn backend.main:app --reload --reload-dir backend --host 0.0.0.0 --port 8000 --log-config log_config.ini
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
YOUTUBE_DOWNLOAD_FORMAT = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
```

### OBS WebSocket接続設定

`backend/obs_recorder.py` の `OBSRecorder` クラス初期化部分:

```python
class OBSRecorder:
    def __init__(self, host='localhost', port=4455, password='your-password'):
```

パスワードはOBS Studio側の設定と一致させてください。

## プロジェクト構造

```
support_clip/
├── backend/                       # FastAPIバックエンド
│   ├── main.py                   # メインAPIエンドポイント（~2000行）
│   ├── transcribe.py             # Faster Whisper文字起こし機能
│   ├── clip_detector.py          # AIクリップ検出ロジック (無音/文章/AI分析)
│   ├── obs_recorder.py           # OBS WebSocketによるブラウザ音声/映像キャプチャ
│   ├── browser_collector.js      # ブラウザからメンバースタンプを抽出するスクリプト
│   ├── video_clipper.py          # 動画クリップ抽出・結合・スタック処理
│   ├── video_processing.py       # 動画処理・字幕焼き込み
│   ├── youtube_downloader.py     # YouTube動画ダウンロード
│   ├── twitter_generator.py      # Twitter(X) PR文章生成
│   ├── fcpxml_generator.py       # FCPXML生成
│   ├── ass_generator.py          # 字幕・弾幕ASSファイル生成
│   ├── description_generator.py  # 動画説明文生成
│   ├── progress.py               # 進捗管理システム
│   ├── config.py                 # 設定ファイル
│   ├── hololive_members.json     # ホロライブメンバー情報
│   ├── requirements.txt          # Python依存関係
│   ├── uploads/                  # アップロードファイル保存先 ⚠️ 大容量・gitignore対象
│   └── assets/                   # 生成ファイル・絵文字・効果音 ⚠️ gitignore対象
│       ├── emojis/               # チャンネル別メンバースタンプ画像
│       └── sounds/               # 効果音ファイル
├── frontend/                     # React フロントエンド
│   ├── src/
│   │   ├── App.jsx              # メインアプリケーション
│   │   ├── main.jsx             # Reactエントリーポイント
│   │   ├── components/
│   │   │   ├── YouTubeClipCreator.jsx # メインUI
│   │   │   ├── VideoPlayer.jsx        # ビデオプレイヤー
│   │   │   ├── ClipPreview.jsx        # クリッププレビュー
│   │   │   ├── StyleEditor.jsx        # 字幕スタイルエディタ
│   │   │   ├── SubtitleEditor.jsx     # 字幕エディタ
│   │   │   ├── TwitterModal.jsx       # Twitter PR生成モーダル
│   │   │   └── Upload.jsx             # ファイルアップロード
│   │   └── utils/
│   │       └── vtt.js           # VTT字幕パースユーティリティ
│   ├── public/                  # 静的ファイル
│   └── package.json             # Node.js依存関係
├── docs/
│   ├── DAVINCI_RESOLVE.md       # DaVinci Resolve連携ガイド
│   └── PROXMOX_MIGRATION.md    # Proxmox移行・復旧手順 ⚠️ 移行時必読
├── venv/                        # Python仮想環境 ⚠️ gitignore対象
├── Makefile                     # サーバー管理コマンド
├── start_backend.sh             # バックエンド起動スクリプト
├── log_config.ini               # ロギング設定
└── .gitignore                   # Git除外設定
```

## API エンドポイント

主要なAPIエンドポイント:

### 動画管理
- `POST /upload` - 動画ファイルのアップロード
- `POST /youtube/download` - YouTube動画のダウンロード（タイムスタンプ付きURL対応）
- `GET /progress/{video_id}` - 進捗状況取得

### 分析・処理
- `POST /transcribe/{video_id}` - 文字起こし開始
- `POST /detect-clips/{video_id}` - クリップ検出（無音区間、文章区切り、AI分析）
- `POST /youtube/analyze` - YouTube動画の統合分析

### クリップ操作
- `POST /extract-clip` - 個別クリップ抽出
- `POST /merge-clips` - クリップ結合

### エクスポート
- `POST /burn` - 字幕焼き込み動画生成（ASS字幕・弾幕対応）
- `GET /download/{filename}` - ファイルダウンロード
- `POST /generate-fcpxml` - FCPXML生成
- `POST /generate-srt` - SRT字幕生成

### メンバースタンプ・絵文字
- `GET /api/emojis` - 登録済みチャンネル一覧
- `GET /api/emojis/{channel_id}` - チャンネル別絵文字一覧
- `POST /youtube/sync-emojis` - 絵文字同期

### コメント
- `GET /youtube/comments/{video_filename}` - 動画コメント取得
- `POST /youtube/comments/range` - 時間範囲のコメント取得

### 音声
- `GET /api/sounds` - 利用可能な効果音一覧

詳細は `http://localhost:8000/docs` のSwagger UIを参照してください。

## 高度な機能

### ハイブリッドクリップ検出

`backend/clip_detector.py` は以下の検出方式を組み合わせています:

1. **無音区間検出** (`detect_silence_boundaries`)
   - pydubで音声の無音部分を検出
   - デフォルト: 800ms以上の無音（-40dB）

2. **文章区切り検出** (`detect_sentence_boundaries`)
   - 句読点や改行を検出して境界候補を生成

3. **AI分析方式** (`analyze_transcript_with_ai`)
   - Ollama (qwen2.5) を使用してトピック境界を検出
   - 各クリップのタイトルと説明を自動生成

4. **品質評価** (`evaluate_clip_quality`)
   - AIによる面白さスコアリング（1-5つ星）

5. **コメント密度分析** (`detect_comment_density_clips`)
   - YouTube Liveコメントの密度が高い区間を自動検出

### OBSブラウザキャプチャ

直接ダウンロードが難しい動画や、ブラウザソースとしてカスタマイズした画面を録画したい場合に利用します。
- OBS WebSocket経由で録画を開始・停止
- 座標指定によるクロップ、CSSカスタマイズに対応
- **注意**: ChromiumのSnapバージョン固有のバイナリパス(`/snap/bin/chromium`)とバージョン設定が必要

### 縦型動画制作 (Shorts/TikTok対応)

- **9:16 レターボックス**: 通常の16:9動画を中央または上下に配置
- **スタック形式**: 2箇所のクロップ領域を上下に配置（例：ゲーム画面と配信者カメラ）
- 分割比率の微調整が可能

### メンバースタンプ同期

1. `browser_collector.js` をブラウザコンソールで実行してスタンプ情報をコピー
2. アプリケーションの「メンバースタンプ管理」で情報を同期
3. 字幕エディタや弾幕機能でメンバースタンプが自動的に画像として描画
4. 画像データは `backend/assets/emojis/{channel_id}/` に保存

### キャッシング機能

以下のデータがキャッシュされ、再利用されます:
- ダウンロード済みYouTube動画（`backend/uploads/`）
- 文字起こし済みVTTファイル（`backend/uploads/*.vtt`）
- 生成済みFCPXMLファイル（`backend/uploads/*.fcpxml`）
- メンバースタンプ画像（`backend/assets/emojis/`）

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

# バージョン確認
ffmpeg -version
```

### 仮想環境のパスエラー（プロジェクト移動後など）

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

### OBSキャプチャが動かない

```bash
# Chromiumのバージョン確認（obs_recorder.py内のバージョンと合わせること）
/snap/bin/chromium --version

# OBS WebSocketの接続確認（ポート4455）
nc -zv localhost 4455
```

### メモリ不足エラー

大きな動画ファイルや長時間の動画を処理する場合:
- より小さなモデルを使用（`config.py`で設定）
- クリップの最大数を減らす
- システムのメモリを増やす

## 最新の更新

### 2026年2月25日
- フォントの不透明度制御（フォント・シャドウ・アウトラインの個別透明度設定）
- クリップ作成ロジックの修正（start/end時刻の正確な反映）
- OBSキャプチャの疑似フルスクリーン修正

### 2026年2月9日
- OBSキャプチャのタイミング精度向上（リードタイム導入による冒頭欠落防止）
- 縦型動画制作時の2画面スタックモードと分割比率調整機能
- YouTube Liveコメントの弾幕焼き込み機能
- メンバースタンプの同期・管理および自動画像描画機能
- AIによるTwitter(X)プロモーション文章の自動生成
- 字幕の文字数制限機能

## 関連ドキュメント

- [DaVinci Resolve連携ガイド](./docs/DAVINCI_RESOLVE.md) - SRTファイルをDaVinci Resolve用に変換する方法
- [サーバー移行・復旧手順](./docs/SERVER_MIGRATION.md) - 別サーバーへの移行時の完全な手順（VM・物理・クラウド対応）

## ライセンス

MIT License
