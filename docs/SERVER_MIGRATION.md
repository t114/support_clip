# Support Clip — サーバー移行・復旧手順書

> **最終更新**: 2026-04-16  
> このドキュメントは support_clip を別の Linux サーバー（Ubuntu 24.04 推奨）へ移行・復旧するための完全な手順書です。  
> 仮想マシン（KVM / VMware / Proxmox 等）・物理マシン・クラウドインスタンス（AWS EC2 / GCP / VPS 等）問わず同一手順で対応できます。

---

## 目次

1. [移行全体の流れ](#1-移行全体の流れ)
2. [移行前の準備（旧サーバーで実施）](#2-移行前の準備旧サーバーで実施)
3. [新サーバーの準備](#3-新サーバーの準備)
4. [新環境でのシステム依存パッケージのインストール](#4-新環境でのシステム依存パッケージのインストール)
5. [アプリケーションのデプロイ](#5-アプリケーションのデプロイ)
6. [データの移行](#6-データの移行)
7. [OBS Studio のセットアップ（OBSキャプチャ機能利用時）](#7-obs-studio-のセットアップobsキャプチャ機能利用時)
8. [起動確認と動作テスト](#8-起動確認と動作テスト)
9. [自動起動の設定（systemd）](#9-自動起動の設定systemd)
10. [ポートフォワードとアクセス設定](#10-ポートフォワードとアクセス設定)
11. [トラブルシューティング](#11-トラブルシューティング)
12. [チェックリスト](#12-チェックリスト)

---

## 1. 移行全体の流れ

```
[旧サーバー]
  ↓ コードを git push
  ↓ uploads/ と assets/ を rsync または scp でバックアップ

[新サーバー（VM・物理・クラウド問わず）]
  ↓ Ubuntu 24.04 LTS をインストール
  ↓ 依存パッケージのインストール
  ↓ git clone でコードを取得
  ↓ Python venv と npm install
  ↓ uploads/ と assets/ を転送
  ↓ Ollama・OBS のセットアップ
  ↓ systemd で自動起動設定
  ↓ 動作確認
```

---

## 2. 移行前の準備（旧サーバーで実施）

### 2-1. 未コミットの変更をコミット・プッシュする

```bash
cd ~/workspace/support_clip

# 未コミットのファイルを確認
git status

# 変更をすべてステージしてコミット
git add -A
git commit -m "chore: pre-migration snapshot $(date +%Y%m%d)"

# リモートにプッシュ
git push origin main
```

### 2-2. 転送対象データのサイズを確認

```bash
# uploads/ のサイズ確認（数十GB〜数百GBになることがある）
du -sh ~/workspace/support_clip/backend/uploads/

# assets/ のサイズ確認（絵文字・効果音）
du -sh ~/workspace/support_clip/backend/assets/
```

> **注意**: `uploads/` には処理済み動画ファイルが蓄積されています。  
> 移行先に全ファイルを持っていく必要があるか確認をしてください。  
> 不要なファイルを削除することでデータ量を削減できます。

### 2-3. 不要ファイルの整理（任意）

```bash
cd ~/workspace/support_clip/backend/uploads/

# *.filter_complex ファイルは再生成可能なので削除可能
find . -name "*.filter_complex" -delete

# 一時的な ASS ファイル（*_modified.ass, *_danmaku.ass）も削除可能
find . -name "*_modified.ass" -delete
find . -name "*_danmaku.ass" -delete
```

### 2-4. データのバックアップ（tar.gz）

新環境への転送が大量ファイルで重い場合は tar にまとめる:

```bash
cd ~/workspace/support_clip

# uploads/ をアーカイブ（時間がかかる）
tar -czf /tmp/support_clip_uploads.tar.gz backend/uploads/

# assets/ をアーカイブ
tar -czf /tmp/support_clip_assets.tar.gz backend/assets/
```

---

## 3. 新サーバーの準備

### 3-1. スペックの目安

| 項目 | 推奨値 |
|------|--------|
| OS | Ubuntu 24.04 LTS |
| CPU | 4コア以上（Faster Whisperは重い） |
| RAM | 16GB以上（8GBは最低限） |
| ストレージ | 500GB以上（動画ファイルが大量蓄積される） |
| ネットワーク | SSH・HTTP にアクセスできること |

> プラットフォーム別の準備方法:
> - **VM（Proxmox / KVM / VMware）**: ハイパーバイザーのUIからUbuntu 24.04 のVMを作成
> - **物理マシン**: USBインストーラを作成して Ubuntu 24.04 を直接インストール
> - **VPS / クラウド（AWS EC2, GCP, さくらVPS 等）**: 管理コンソールから Ubuntu 24.04 イメージでインスタンスを作成

### 3-2. Ubuntu 24.04 のインストール

1. Ubuntu インストーラを起動
2. ユーザー名: `ubuntu`（または任意）
3. SSHサーバーを有効にする（インストール時にチェック）
4. 最小インストールで OK

### 3-3. 初期設定

```bash
# 旧サーバーから新サーバーにSSH接続できるように公開鍵を設定
ssh-copy-id ubuntu@<新サーバーのIPアドレス>

# 新サーバーにSSH接続
ssh ubuntu@<新サーバーのIPアドレス>

# パッケージリストを更新
sudo apt update && sudo apt upgrade -y
```

---

## 4. 新環境でのシステム依存パッケージのインストール

**以下はすべて新サーバーのターミナルで実行します。**

### 4-1. 基本ツール

```bash
sudo apt install -y \
  git \
  curl \
  wget \
  build-essential \
  software-properties-common \
  unzip \
  tar \
  lsof \
  htop
```

### 4-2. Python 3.12

Ubuntu 24.04 には Python 3.12 が標準搭載されています:

```bash
python3 --version
# Python 3.12.x と表示されれば OK

# pip と venv も確認
sudo apt install -y python3-pip python3-venv python3-full
```

### 4-3. FFmpeg

```bash
sudo apt install -y ffmpeg

# バージョン確認
ffmpeg -version
```

### 4-4. Node.js（nvm経由で管理）

```bash
# nvm をインストール
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

# シェルを再読み込み
source ~/.bashrc

# Node.js 20 LTS をインストール
nvm install 20
nvm use 20
nvm alias default 20

# 確認
node --version
npm --version
```

### 4-5. Ollama

```bash
# 公式インストールスクリプト
curl -fsSL https://ollama.com/install.sh | sh

# サービスとして有効化
sudo systemctl enable ollama
sudo systemctl start ollama

# qwen2.5 モデルのダウンロード（数GBあるので時間がかかる）
ollama pull qwen2.5

# 確認
ollama list
```

### 4-6. Chromium（OBSキャプチャ機能を使う場合）

```bash
# Snap版 Chromium（obs_recorder.py の設定と一致）
sudo snap install chromium

# バージョン確認（obs_recorder.py 内のバージョンと合わせること）
/snap/bin/chromium --version
```

> ⚠️ `backend/obs_recorder.py` の以下の行のバージョンを  
> インストールされた Chromium のバージョンに合わせて変更してください:
> ```python
> major_version = "143.0.7499.192"  # ← この値を合わせる
> ```

### 4-7. GPU ドライバー（CUDA、任意）

Faster Whisper の高速化のために NVIDIA GPU が使える場合:

```bash
# NVIDIA ドライバーのインストール
sudo apt install -y nvidia-driver-545  # バージョンは変わる場合あり

# CUDA Toolkit（Whisperの高速化）
# https://developer.nvidia.com/cuda-downloads から最新版を取得
# または
sudo apt install -y nvidia-cuda-toolkit

# 確認
nvidia-smi
```

---

## 5. アプリケーションのデプロイ

### 5-1. リポジトリのクローン

```bash
cd ~
git clone https://github.com/natsugumo/support_clip.git
cd support_clip
```

### 5-2. Python 仮想環境のセットアップ

```bash
# 仮想環境を作成
python3 -m venv venv

# アクティベート
source venv/bin/activate

# 依存関係をインストール（時間がかかる）
pip install -r backend/requirements.txt

# インストール確認
pip list | grep -E "fastapi|uvicorn|faster-whisper|yt-dlp|ollama"
```

> **Faster Whisper のインストール注意**:  
> GPU版を使いたい場合は `pip install faster-whisper[cuda]` が必要な場合があります。  
> CPU版でも動作しますが処理が遅くなります。

### 5-3. フロントエンドのセットアップ

```bash
cd ~/support_clip/frontend

# nvm でバージョンを設定
nvm use 20

# 依存関係インストール
npm install

cd ..
```

### 5-4. ディレクトリの作成

アプリケーション起動時に自動作成されますが、事前に確認:

```bash
mkdir -p ~/support_clip/backend/uploads/prefix_images
mkdir -p ~/support_clip/backend/assets/sounds
mkdir -p ~/support_clip/backend/assets/emojis
```

---

## 6. データの移行

> **重要**: `backend/uploads/` は `.gitignore` に含まれているため、Gitでは管理されていません。  
> 旧サーバーから手動で転送する必要があります。

### 6-1. 方法A: rsync を使って転送（推奨、差分転送が可能）

**旧サーバーから実行:**

```bash
# 事前チェック（--dry-run で実際の転送は行わない）
rsync -avhn --progress \
  ~/workspace/support_clip/backend/uploads/ \
  ubuntu@<新サーバーのIPアドレス>:~/support_clip/backend/uploads/

# 確認後、実際に転送
rsync -avh --progress \
  ~/workspace/support_clip/backend/uploads/ \
  ubuntu@<新サーバーのIPアドレス>:~/support_clip/backend/uploads/

# assets/ も転送
rsync -avh --progress \
  ~/workspace/support_clip/backend/assets/ \
  ubuntu@<新サーバーのIPアドレス>:~/support_clip/backend/assets/
```

### 6-2. 方法B: tar でまとめてから SCP で転送

**旧サーバーで:**

```bash
# アーカイブ作成
cd ~/workspace/support_clip
tar -czf /tmp/sc_uploads.tar.gz backend/uploads/
tar -czf /tmp/sc_assets.tar.gz backend/assets/

# 転送
scp /tmp/sc_uploads.tar.gz ubuntu@<新サーバーのIPアドレス>:/tmp/
scp /tmp/sc_assets.tar.gz ubuntu@<新サーバーのIPアドレス>:/tmp/
```

**新サーバー で:**

```bash
cd ~/support_clip

# 展開
tar -xzf /tmp/sc_uploads.tar.gz
tar -xzf /tmp/sc_assets.tar.gz

# 展開された内容を確認
ls -la backend/uploads/ | head -20
ls -la backend/assets/
```

### 6-3. 転送後の確認

```bash
# ファイル数の確認
find ~/support_clip/backend/uploads/ -type f | wc -l

# 旧サーバーのファイル数と比較してください!!
# (旧サーバーで実行) find ~/workspace/support_clip/backend/uploads/ -type f | wc -l
```

---

## 7. OBS Studio のセットアップ（OBSキャプチャ機能利用時）

OBS Studio のキャプチャ機能はデスクトップ環境が必要です。  
デスクトップ環境（GUI）なしのサーバーで OBS を利用する場合は Xvfb 等の仮想ディスプレイが必要です。

### 7-1. デスクトップ環境あり（GUI環境）の場合

```bash
# OBS Studio のインストール
sudo add-apt-repository ppa:obsproject/obs-studio
sudo apt update
sudo apt install -y obs-studio

# WebSocket プラグインの確認（OBS 28以降は標準搭載）
obs --version
```

**OBS の設定:**

1. OBS を起動
2. **ツール** → **WebSocketサーバー設定**
   - "WebSocketサーバーを有効にする" にチェック
   - ポート: `4455`
   - パスワードを設定（`backend/obs_recorder.py` の `password` と一致させる）
3. シーン名 `BrowserCapture` を作成
4. ブラウザソース `YouTubeSource` を追加（1920x1080）
5. 録画出力先を `~/support_clip/backend/uploads/obs_recordings/` に設定（任意）

### 7-2. デスクトップ環境なし（Headlessサーバー）の場合

```bash
# Xvfb（仮想X11ディスプレイ）のインストール
sudo apt install -y xvfb

# Xvfb を起動
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# OBS をヘッドレスで起動（デスクトップ環境不要）
sudo apt install -y obs-studio
obs --startrecording --headless
```

> ⚠️ ヘッドレスOBSの設定は複雑です。  
> OBSキャプチャ機能が必須でない場合、デスクトップGUI付きVMを選ぶ方が簡単です。

---

## 8. 起動確認と動作テスト

### 8-1. バックエンドの起動テスト

```bash
cd ~/support_clip

# 仮想環境のアクティベート
source venv/bin/activate

# 手動で起動して動作確認
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 別ターミナルで動作確認
curl http://localhost:8000/
# {"message": ...} 系のレスポンスが返ればOK

curl http://localhost:8000/api/emojis
# {"channels": [...]} が返ればOK

# Ctrl+C で停止
```

### 8-2. Ollama の確認

```bash
# Ollama サービスの確認
ollama list
# qwen2.5 が表示されれば OK

# API で確認
curl http://localhost:11434/api/tags
```

### 8-3. フロントエンドの起動テスト

```bash
cd ~/support_clip/frontend

# 開発サーバーを起動
npm run dev

# ブラウザで http://<新サーバーのIPアドレス>:5173 にアクセス
```

### 8-4. Makefile での起動

```bash
cd ~/support_clip

# バックグラウンドで起動
make start

# ステータス確認
make status

# ログ確認
make logs
```

---

## 9. 自動起動の設定（systemd）

### 9-1. バックエンドのサービスファイル

```bash
sudo nano /etc/systemd/system/support-clip-backend.service
```

以下の内容を貼り付け（ユーザー名 `ubuntu` を実際のユーザー名に変更）:

```ini
[Unit]
Description=Support Clip Backend (FastAPI)
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/support_clip
ExecStart=/home/ubuntu/support_clip/venv/bin/uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-config /home/ubuntu/support_clip/log_config.ini
Restart=on-failure
RestartSec=5
StandardOutput=append:/home/ubuntu/support_clip/backend.log
StandardError=append:/home/ubuntu/support_clip/backend.log
Environment=PYTHONPATH=/home/ubuntu/support_clip

[Install]
WantedBy=multi-user.target
```

```bash
# サービスを有効化・起動
sudo systemctl daemon-reload
sudo systemctl enable support-clip-backend
sudo systemctl start support-clip-backend

# 状態確認
sudo systemctl status support-clip-backend

# ログ確認
sudo journalctl -u support-clip-backend -f
```

### 9-2. フロントエンドのビルドと静的配信（本番用）

開発サーバー（`npm run dev`）は本番用途には不向きです。  
Nginx で静的ファイルを配信する方法を推奨します:

```bash
# フロントエンドをビルド
cd ~/support_clip/frontend
npm run build
# dist/ ディレクトリにビルド結果が出力される

# Nginx のインストール
sudo apt install -y nginx

# Nginx の設定
sudo nano /etc/nginx/sites-available/support-clip
```

以下の内容:

```nginx
server {
    listen 80;
    server_name _;  # または固定IPやホスト名

    # フロントエンド（静的ファイル）
    root /home/ubuntu/support_clip/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # バックエンドAPIのプロキシ
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        client_max_body_size 10G;  # 大容量動画ファイルのアップロード対応
        proxy_read_timeout 3600;   # 長時間処理対応
        proxy_send_timeout 3600;
    }

    location /static/ {
        proxy_pass http://localhost:8000;
        proxy_read_timeout 3600;
        client_max_body_size 10G;
    }

    location /upload {
        proxy_pass http://localhost:8000;
        proxy_read_timeout 3600;
        client_max_body_size 10G;
    }

    # すべての / 以外のバックエンドエンドポイント
    location ~ ^/(youtube|transcribe|detect-clips|extract-clip|merge-clips|burn|download|generate-fcpxml|generate-srt|progress) {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
        client_max_body_size 10G;
    }
}
```

```bash
# 有効化
sudo ln -s /etc/nginx/sites-available/support-clip /etc/nginx/sites-enabled/
sudo nginx -t  # 設定の文法チェック
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 9-3. Ollama の自動起動確認

```bash
# Ollama は install.sh で自動的にサービス登録される
sudo systemctl status ollama
sudo systemctl enable ollama
```

---

## 10. ポートフォワードとアクセス設定

### 10-1. 開放が必要なポート

以下のポートをサーバーまたはルーターのファイアウォールで許可してください:

| ポート | プロトコル | 用途 |
|--------|-----------|------|
| 22 | TCP | SSH |
| 80 | TCP | Nginx（フロントエンド+APIプロキシ） |
| 5173 | TCP | Vite開発サーバー（開発時のみ） |
| 8000 | TCP | FastAPI バックエンド直接アクセス（任意） |
| 11434 | TCP | Ollama（ローカルのみ推奨） |

> プラットフォーム別の設定場所:
> - **Proxmox**: Web UI → VM の **Firewall** タブ
> - **AWS EC2**: セキュリティグループのインバウンドルール
> - **GCP**: VPCネットワーク → ファイアウォールルール
> - **物理マシン/VPS**: UFW（下記）のみで制御

### 10-2. UFW ファイアウォール（VM内）

```bash
sudo apt install -y ufw

# 基本ルール
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH を許可（絶対に先に許可すること！）
sudo ufw allow 22/tcp

# HTTP を許可
sudo ufw allow 80/tcp

# 開発用（必要な場合のみ）
# sudo ufw allow 5173/tcp
# sudo ufw allow 8000/tcp

# 有効化
sudo ufw enable

# 状態確認
sudo ufw status
```

---

## 11. トラブルシューティング

### 11-1. バックエンドが起動しない

```bash
# エラーログを確認
make logs
# または
sudo journalctl -u support-clip-backend -n 50

# よくある原因:
# 1. ポート 8000 が既に使用されている
sudo lsof -i:8000
sudo kill -9 <PID>

# 2. 仮想環境のパスが間違っている
which python3
source venv/bin/activate
which python  # venv/bin/python が表示されること

# 3. Python 依存関係のインストール漏れ
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 11-2. Faster Whisper が動かない

```bash
# CUDA が使えるか確認
python3 -c "import torch; print(torch.cuda.is_available())"

# CPU モードで動作させる（config は自動検出するが、明示したい場合）
# backend/transcribe.py 内の WhisperModel の device 引数を "cpu" に設定

# メモリ不足の場合は小さいモデルを使用
# backend/transcribe.py で model_size="tiny" または "base" に変更
```

### 11-3. Ollama への接続エラー

```bash
# サービス状態確認
sudo systemctl status ollama

# 再起動
sudo systemctl restart ollama

# モデルが存在するか確認
ollama list

# 手動でAPIテスト
curl http://localhost:11434/api/generate \
  -d '{"model": "qwen2.5", "prompt": "test", "stream": false}'
```

### 11-4. uploads/ の動画ファイルにアクセスできない

```bash
# パーミッション確認
ls -la ~/support_clip/backend/uploads/ | head -5

# 所有者を修正
sudo chown -R ubuntu:ubuntu ~/support_clip/backend/uploads/

# ディレクトリのアクセス権を修正
chmod -R 755 ~/support_clip/backend/uploads/
```

### 11-5. Chromium/ChromeDriverバージョン不一致（OBSキャプチャ）

```bash
# インストールされている Chromium のバージョンを確認
/snap/bin/chromium --version
# 例: Chromium 143.0.7499.192

# backend/obs_recorder.py の以下の行を編集してバージョンを合わせる
# major_version = "143.0.7499.192"  ← 実際のバージョンに変更

# ChromeDriver のキャッシュをクリア（バージョン変更後）
rm -rf ~/.wdm/
```

### 11-6. venv のパスエラー（プロジェクトディレクトリが変わった場合）

```bash
cd ~/support_clip

# 仮想環境を再作成
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 11-7. OBS の WebSocket 接続エラー

```bash
# OBS が起動しているか確認
pgrep -a obs

# ポート 4455 が開いているか確認
nc -zv localhost 4455

# OBS の設定を確認
# ツール → WebSocketサーバー設定 → パスワードが obs_recorder.py と一致しているか
```

### 11-8. Nginx で動画が表示されない（大容量ファイル）

```bash
# Nginx のエラーログを確認
sudo tail -f /var/log/nginx/error.log

# client_max_body_size を確認
sudo grep client_max_body_size /etc/nginx/sites-available/support-clip

# タイムアウトが短い場合
# proxy_read_timeout と proxy_send_timeout を 3600 以上に設定
sudo nano /etc/nginx/sites-available/support-clip
sudo nginx -t
sudo systemctl reload nginx
```

---

## 12. チェックリスト

### 移行前（旧サーバー）

- [ ] 未コミットの変更をコミット・プッシュ済み
- [ ] `backend/uploads/` のサイズを確認済み
- [ ] 不要ファイルを削除して転送量を削減（任意）
- [ ] OBS WebSocketのパスワードをメモ済み
- [ ] Chromium のバージョンをメモ済み（OBSキャプチャ利用時）

### 新サーバーのセットアップ

- [ ] Ubuntu 24.04 LTS インストール済み
- [ ] SSH でアクセス可能
- [ ] git インストール済み
- [ ] Python 3.12 確認済み（`python3 --version`）
- [ ] FFmpeg インストール済み（`ffmpeg -version`）
- [ ] nvm + Node.js 20 インストール済み（`node --version`）
- [ ] Ollama インストール済み（`ollama list`）
- [ ] qwen2.5 モデルダウンロード済み
- [ ] Chromium インストール済み（OBSキャプチャ利用時）

### アプリケーションのデプロイ

- [ ] `git clone` 完了
- [ ] `pip install -r backend/requirements.txt` 完了
- [ ] `npm install` 完了（frontend/）
- [ ] `make start` で起動確認
- [ ] `curl http://localhost:8000/` でレスポンス確認
- [ ] フロントエンドでページ表示確認

### データ移行

- [ ] `backend/uploads/` の転送完了
- [ ] `backend/assets/emojis/` の転送完了（メンバースタンプ）
- [ ] `backend/assets/sounds/` の転送完了（効果音）
- [ ] ファイル数が旧サーバーと一致

### OBS セットアップ（OBSキャプチャ利用時）

- [ ] OBS Studio インストール済み
- [ ] WebSocket 有効化、ポート 4455、パスワード設定済み
- [ ] シーン `BrowserCapture`、ブラウザソース `YouTubeSource` 作成済み
- [ ] `obs_recorder.py` の Chromium バージョンを新環境に合わせて更新

### 本番設定

- [ ] systemd サービス設定済み（自動起動）
- [ ] Nginx 設定済み（静的ファイル + API プロキシ）
- [ ] ファイアウォール設定済み（UFW またはクラウド/ハイパーバイザーのセキュリティグループ）
- [ ] Ollama の自動起動確認（`sudo systemctl enable ollama`）

---

## 参考: 主要なファイルパス一覧

| 項目 | パス |
|------|------|
| プロジェクトルート | `~/support_clip/` |
| バックエンド設定 | `~/support_clip/backend/config.py` |
| OBS設定 | `~/support_clip/backend/obs_recorder.py` |
| アップロードデータ | `~/support_clip/backend/uploads/` |
| メンバースタンプ | `~/support_clip/backend/assets/emojis/` |
| 効果音 | `~/support_clip/backend/assets/sounds/` |
| バックエンドログ | `~/support_clip/backend.log` |
| ログ設定 | `~/support_clip/log_config.ini` |
| Python仮想環境 | `~/support_clip/venv/` |
| フロントエンドビルド | `~/support_clip/frontend/dist/` |
| Nginx設定 | `/etc/nginx/sites-available/support-clip` |
| systemdサービス | `/etc/systemd/system/support-clip-backend.service` |
