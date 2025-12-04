#!/bin/bash

# Support Clip - バックエンド起動スクリプト

# 仮想環境をアクティベート
source venv/bin/activate

# バックエンドサーバーを起動
echo "バックエンドサーバーを起動中..."
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
