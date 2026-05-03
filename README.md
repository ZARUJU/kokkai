# kokkai

国会に関するデータを収集・正規化し、メタデータを付与して相互にリンクできる形で蓄積し、APIとして提供するアプリケーションです。

## 目的

- 国会関連データを複数の取得元から継続的に収集する
- 取得したデータを正規化し、検索・参照しやすい形式で保存する
- 会議、議員、質問、答弁、資料などのメタデータを付与し、データ同士をリンクする
- 保存済みデータをAPI経由で提供する

## 方針

取得処理、データモデル、APIを疎結合に保ちます。

- 取得系スクリプトはAPIサーバーから分離する
- データの永続化はSQLAlchemyを使って抽象化する
- API入出力、設定、取得データの検証にはPydanticを使う
- 開発環境ではSQLiteを使う
- 本番環境ではPostgreSQLなどの別DBを利用できる構成にする
- DB接続先は環境変数で切り替える

## 想定ディレクトリ構成

```text
kokkai/
  src/
    kokkai/
      api/
        api.py               # FastAPIアプリケーションのエントリポイント
        routes/              # APIルーティング
        schemas/             # リクエスト・レスポンス用スキーマ
      core/
        config.py            # 設定、環境変数の読み込み
      db/
        session.py           # DB接続、セッション管理
        models/              # SQLAlchemyモデル
        migrations/          # DBマイグレーション
      ingest/
        sources/             # 取得元ごとのクライアント・パーサー
        jobs/                # 取得・更新ジョブ
        pipelines/           # 正規化・保存処理
      services/              # APIと取得処理から共有する業務ロジック
      main.py                # CLI用エントリポイント
  scripts/
    ingest/                  # 手動実行用の取得スクリプト
  tests/
  README.md
```

## データベース

SQLAlchemyを利用して、アプリケーション側のDB操作を特定のDB製品に依存させないようにします。

開発時はローカルSQLiteを使います。

```bash
DATABASE_URL=sqlite:///./data/kokkai.dev.sqlite3
```

本番環境では、同じ`DATABASE_URL`で接続先を差し替えます。

```bash
DATABASE_URL=postgresql+psycopg://user:password@host:5432/kokkai
```

本番DBは未定です。将来的な候補としてはPostgreSQLを想定しています。

## 取得処理

取得処理は`src/kokkai/ingest/`配下にまとめます。

- `sources/`: 取得元ごとのHTTPクライアント、HTML/APIパーサー
- `jobs/`: 定期実行または手動実行する単位のジョブ
- `pipelines/`: 取得結果を正規化し、DBへ保存する処理

手元で実行するための薄いCLIや補助スクリプトは`scripts/ingest/`に置きます。実処理はできるだけ`src/kokkai/ingest/`へ寄せ、API側からも再利用できる形にします。

## API

APIは`src/kokkai/api/`配下にまとめます。

API層はHTTP入出力に集中し、DB操作や集約処理は`services/`や`db/`へ委譲します。これにより、取得ジョブとAPIが同じデータモデル・保存処理を共有できます。

APIサーバーはFastAPIで実装し、`src/kokkai/api/api.py`をエントリーポイントにします。

APIのリクエスト・レスポンスはPydanticモデルで定義します。DBのSQLAlchemyモデルをそのまま外部へ返すのではなく、API用スキーマを分けて、外部公開する項目と内部保存する項目を明確にします。

## エントリーポイント

- `src/kokkai/main.py`: CLI用エントリーポイント
- `src/kokkai/api/api.py`: FastAPIによるAPIサーバー

## 採用予定ライブラリ

実装方針として採用するライブラリです。

- `fastapi`: APIサーバー
- `pydantic`: API入出力、取得データ、内部DTOのスキーマ定義とバリデーション
- `pydantic-settings`: 環境変数、`.env`、設定値の型付き読み込み
- `psycopg`: PostgreSQLドライバ
- `sqlalchemy`: ORM、DB接続の抽象化
- `uvicorn`: ASGIサーバー

## 利用候補ライブラリ

採用予定以外のライブラリ候補です。実装時に必要なものから追加します。

### データベース

- `alembic`: DBマイグレーション管理
- `aiosqlite`: SQLiteを非同期で扱う場合のドライバ

### 設定・環境変数

- `python-dotenv`: `.env`を直接読み込む必要がある場合の補助

設定は`pydantic-settings`で`DATABASE_URL`などを環境変数から読み込み、開発・本番で差し替えます。

### HTTP取得・スクレイピング

- `httpx`: HTTPクライアント。同期・非同期の両方に対応
- `beautifulsoup4`: HTMLの構造が安定しないページのパース
- `lxml`: 高速なHTML/XMLパーサー
- `selectolax`: 大量HTMLを高速に処理したい場合の候補
- `tenacity`: リトライ制御
- `requests-cache`または`hishel`: 取得結果のキャッシュ

まずは`httpx`と`beautifulsoup4`/`lxml`を基本にし、速度や規模が問題になった段階で`selectolax`などを検討します。

### CLI・ジョブ実行

- `typer`: 手動実行用CLI
- `rich`: CLI出力、進捗表示、ログの見やすさ向上
- `apscheduler`: アプリ内で簡易的に定期実行する場合の候補

本番の定期実行は、アプリ内スケジューラではなく外部のジョブ基盤に寄せる可能性があります。

### 型安全・品質管理

- `mypy`: 静的型チェック
- `ruff`: lint、format
- `pytest`: テストフレームワーク
- `pytest-cov`: カバレッジ計測
- `factory-boy`: テストデータ生成

データの入出力境界ではPydanticモデル、永続化層ではSQLAlchemyモデル、内部処理では型ヒントを使い、壊れやすい文字列辞書の受け渡しを減らします。

### ログ・監視

- `structlog`: 構造化ログ
- `sentry-sdk`: 本番エラー監視が必要になった場合の候補

取得処理は失敗原因を追いやすいように、取得元URL、HTTPステータス、対象ID、リトライ回数をログに残します。

## 開発

現在は初期構成の段階です。

```bash
uv run python -m kokkai.main
uv run uvicorn kokkai.api.api:app --reload
```

今後、APIサーバー、取得CLI、DBマイグレーションを追加していきます。

## コンテナ

アプリケーションはuvを使って依存関係を同期するDockerイメージとして構築します。

- `Dockerfile`: API/CLIで共通利用するアプリケーションイメージ
- `compose.yaml`: 開発用にAPIとPostgreSQLをまとめて起動する構成
- APIコンテナ: `uvicorn kokkai.api.api:app --host 0.0.0.0 --port 8000`

起動例:

```bash
docker compose up --build
```

ローカルのCompose構成では、APIがPostgreSQLを参照します。

```text
api container -> FastAPI -> PostgreSQL
```

本番でもSQLiteは使わず、コンテナ外部のDBを`DATABASE_URL`で指定します。

## GitHub Actionsでの取得実行

取得ジョブはアプリコンテナとは分離し、GitHub Actionsの定期実行からCLIを呼び出す想定です。

```bash
uv run python -m kokkai.main ingest
```

Actionsでは`DATABASE_URL`をSecretsから渡し、取得・正規化・保存処理だけを実行します。APIコンテナは定期取得を担当せず、保存済みデータの提供に集中します。

## 未定事項

- 本番DBの種類
- マイグレーション管理方法
- 取得対象データの優先順位
- 定期実行基盤
- 採用するスクレイピング用パーサー
- 型チェック・lintの厳格さ
