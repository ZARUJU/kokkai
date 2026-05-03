# kokkai

国会関連データを収集・解析し、検索しやすいメタデータを付与して API で提供するためのアプリケーションです。

## 目的

国会の会議録、議案、質問主意書、委員会情報などは複数の公開サイトに分散しています。このプロジェクトでは、それらを JSON API や HTML ページから継続的に取得し、出典 URL と取得日時を保持しながら正規化して、後段の検索・分析・アプリケーション利用に向いたデータとして扱えるようにします。

## 想定する処理の流れ

1. **収集**: 公開サイトの JSON API や HTML ページから原資料を取得する。
2. **解析**: 取得した資料から本文、日付、会議名、議員名、政党名、議案番号などを抽出する。
3. **正規化**: 表記ゆれや日付形式をそろえ、共通のデータモデルに変換する。
4. **保存**: 原資料、抽出結果、メタデータ、処理履歴を DB に登録する。
5. **提供**: FastAPI で検索・取得用 API を公開する。

## 主な技術候補

- Python 3.11+
- FastAPI
- SQLAlchemy
- pytest
- python-dotenv
- HTML 解析ライブラリ
- JSON API クライアント
- スクレイピング用ライブラリ

## ディレクトリ構成案

```text
.
├── api.py                # API サーバー起動用
├── scripts/
│   └── ingest.py         # データ取り込み実行用
├── pyproject.toml
├── .env.example
├── src/
│   └── kokkai/
│       ├── api/          # FastAPI のルーター、スキーマ、依存関係
│       ├── ingest/       # 外部データの取得、解析、正規化、登録
│       │   ├── sources/      # データソースごとの取得処理
│       │   ├── parsers/      # HTML や JSON レスポンスの解析処理
│       │   ├── normalizers/  # 共通データモデルへの変換
│       │   └── pipelines/    # 取得から DB 登録までの一連の処理
│       ├── models/       # DB モデルとドメインモデル
│       ├── repositories/ # DB 読み書き
│       └── settings.py   # 環境変数から設定を読み込む
├── tests/
└── README.md
```

## 開発

依存関係の管理には `uv` を使う想定です。

```bash
uv sync
cp .env.example .env
uv run python api.py
uv run python scripts/ingest.py
uv run pytest
```

## 環境変数

ローカル開発では `.env` に環境変数を記述します。`.env` は Git 管理せず、共有用の初期値は `.env.example` に記載します。

| 変数名 | 用途 | 例 |
| --- | --- | --- |
| `DATABASE_URL` | アプリケーションが接続する DB | `sqlite:///./data/kokkai.sqlite3` |
