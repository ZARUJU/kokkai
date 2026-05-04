# AGENTS.md

このリポジトリで作業するエージェント向けの指示です。

## 応答

- 日本語で簡潔かつ丁寧に回答する。
- 実装変更を行った場合は、変更点と確認したコマンドを短くまとめる。
- コミットメッセージを要求された場合は、差分を確認したうえで `英語のプレフィックス: 日本語での説明` の形式で提案する。

## プロジェクト方針

- 国会関連データを JSON API または HTML ページから取得し、解析・正規化して DB に保存し、FastAPI で提供する。
- PDF と CSV は現時点では収集対象にしない。
- DB は当面 SQLite を使い、接続先は `DATABASE_URL` で管理する。
- DB アクセスは SQLAlchemy を使う。
- ローカルの `.env` と `data/` は Git 管理しない。

## データ追加の流れ

新しいデータソースを追加するときは、次の流れにそろえる。

1. `docs/data-sources.md` に取得元、取得対象、主キー、更新方針、保存方針を追記する。
2. `src/kokkai/models/` にドメインモデルと SQLAlchemy モデルを追加する。
3. `src/kokkai/ingest/sources/` に取得処理を追加する。
4. `src/kokkai/ingest/parsers/` に解析処理を追加する。
5. `src/kokkai/repositories/` に SQLAlchemy 経由の DB 読み書きを追加する。
6. `src/kokkai/ingest/pipelines/` に取得、解析、DB 登録をつなぐ処理を追加する。
7. `src/kokkai/ingest/runner.py` の `PIPELINES` に登録する。
8. 必要に応じて `src/kokkai/api/routes/` に API route を追加し、`src/kokkai/api/app.py` で `include_router` する。

詳細は `docs/ingest-flow.md` を参照する。

## 実装ルール

- API 起動用の入口は `api.py` に置く。
- データ取り込み実行用の入口は `scripts/ingest.py` に置く。
- 取得結果の共通型は `src/kokkai/ingest/documents.py` の `SourceDocument` を使う。
- pipeline は `src/kokkai/ingest/pipeline.py` の `IngestRunContext` を受け取り `PipelineResult` を返す。
- 和暦変換や空白正規化など複数 parser で使う処理は `src/kokkai/ingest/parsers/common.py` に寄せる。
- DB テーブル作成は `src/kokkai/db/schema.py` の `create_all()` を使う。

## 確認

変更後は可能な範囲で次を確認する。

```bash
python3 -m compileall api.py scripts src
uv run python scripts/ingest.py <pipeline_name>
uv run pytest
```

`pytest` はテストが存在する場合に実行する。ネットワーク取得や `uv` のキャッシュアクセスで権限が必要な場合は、許可を得てから実行する。
