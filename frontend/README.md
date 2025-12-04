# Support Clip - Frontend

React + Vite で構築されたSupport Clipのフロントエンドアプリケーションです。

## 技術スタック

- **React 19**: UIライブラリ
- **Vite 7**: 高速ビルドツール
- **Tailwind CSS 4**: ユーティリティファーストCSSフレームワーク
- **ESLint**: コード品質チェック

## 開発環境のセットアップ

### 依存関係のインストール

```bash
npm install
```

### 開発サーバーの起動

```bash
npm run dev
```

開発サーバーは `http://localhost:5173` で起動します。

### ビルド

```bash
npm run build
```

ビルドされたファイルは `dist/` ディレクトリに出力されます。

### プレビュー

```bash
npm run preview
```

ビルドされたアプリケーションをローカルでプレビューします。

### Lint

```bash
npm run lint
```

ESLintを実行してコードの品質をチェックします。

## プロジェクト構造

```
frontend/
├── src/
│   ├── App.jsx          # メインアプリケーションコンポーネント
│   ├── main.jsx         # エントリーポイント
│   └── index.css        # グローバルスタイル
├── public/              # 静的ファイル（動画、字幕等）
├── index.html           # HTMLテンプレート
├── vite.config.js       # Vite設定
├── tailwind.config.js   # Tailwind CSS設定
├── postcss.config.js    # PostCSS設定
└── package.json         # 依存関係とスクリプト
```

## 主な機能

### 動画アップロード・ダウンロード
- ローカルファイルのドラッグ&ドロップアップロード
- YouTube URLからの動画ダウンロード

### 文字起こし
- Faster Whisperによる自動文字起こし
- リアルタイム進捗表示
- VTT/SRT字幕ファイルのダウンロード

### クリップ検出・編集
- AIによる自動クリップ検出
- クリップの開始・終了時刻の手動調整
- クリップのプレビュー再生
- クリップの削除・並び替え

### エクスポート
- 個別クリップのダウンロード
- 全クリップの結合動画
- FCPXML形式でのエクスポート
- 字幕焼き込み動画の生成

## API連携

バックエンドAPIは `http://localhost:8000` で動作している必要があります。

主なAPIエンドポイント:
- `/upload` - ファイルアップロード
- `/youtube/download` - YouTube動画ダウンロード
- `/transcribe/{video_id}` - 文字起こし
- `/detect-clips/{video_id}` - クリップ検出
- `/extract-clip` - クリップ抽出
- `/merge-clips` - クリップ結合

## カスタマイズ

### Tailwind CSS

`tailwind.config.js` でテーマをカスタマイズできます。

### Vite設定

`vite.config.js` でビルド設定を変更できます。

## トラブルシューティング

### ポート競合

デフォルトポート（5173）が使用中の場合、Viteは自動的に別のポートを使用します。

### バックエンド接続エラー

バックエンドサーバーが起動していることを確認してください:

```bash
# プロジェクトルートで
./start_backend.sh
```

## ライセンス

MIT License
