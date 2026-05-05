# データ追加の流れ

新しいデータソースを追加するときは、次の順に実装します。

## 1. データソースを記述する

[data-sources.md](data-sources.md) に、取得元、取得対象、主キー、更新方針、保存方針を追記します。

## 2. ドメインモデルと DB モデルを定義する

`src/kokkai/models/` に、解析後に扱うドメインモデルと SQLAlchemy モデルを置きます。テーブル作成は `src/kokkai/db/schema.py` の `create_all()` が SQLAlchemy のモデル定義から行うのみで、**既存 SQLite に対する自動 ALTER やデータ移行は行わない**。スキーマ変更後は DB を作り直すか、手動でマイグレーションする。

```text
src/kokkai/models/<data_name>.py
```

## 3. 取得処理を作る

`src/kokkai/ingest/sources/` に、HTML ページや JSON API から原資料を取得する処理を置きます。

```text
src/kokkai/ingest/sources/<data_name>.py
```

取得結果は `SourceDocument` として返します。

## 4. 解析処理を作る

`src/kokkai/ingest/parsers/` に、取得した HTML や JSON レスポンスをドメインモデルへ変換する処理を置きます。

```text
src/kokkai/ingest/parsers/<data_name>.py
```

表記ゆれ補正や和暦変換など、複数データソースで使う処理は `src/kokkai/ingest/parsers/common.py` に寄せます。

## 5. DB 読み書きを作る

`src/kokkai/repositories/` に、SQLAlchemy 経由の upsert と取得処理を置きます。

```text
src/kokkai/repositories/<data_name>.py
```

## 6. pipeline を作る

`src/kokkai/ingest/pipelines/` に、取得、解析、DB 登録をつなぐ処理を置きます。

```text
src/kokkai/ingest/pipelines/<data_name>.py
```

pipeline は `IngestRunContext` を引数に取り `PipelineResult` を返します。

## 7. runner に登録する

`src/kokkai/ingest/runner.py` の `PIPELINES` に pipeline を登録します。

```python
PIPELINES = {
    "shugiin_sessions": shugiin_sessions.run,
}
```

登録後は個別実行できます。

```bash
uv run python scripts/ingest.py shugiin_sessions
```

`--session` で国会回次を渡すと、対応する pipeline（衆議院議案・国会会議録・質問主意書）では **CLI が環境変数より優先**されます。

```bash
uv run python scripts/ingest.py shugiin_bills questions --session 219,221
```

引数を省略すると、登録済み pipeline をすべて **`PIPELINES` の定義順**で実行します。

```bash
uv run python scripts/ingest.py
```

ログは標準エラーに出力されます。`-v`（`--verbose`）で DEBUG（HTTP の GET も出力）、`-q`（`--quiet`）で WARNING のみです。既定レベルは環境変数 `KOKKAI_INGEST_LOG_LEVEL`（例: `DEBUG`）でも変更できます。`--session` と runner の詳細は [scripts-ingest.md](scripts-ingest.md) を参照してください。

## 8. API route を追加する

`src/kokkai/api/routes/` に route を追加し、`src/kokkai/api/app.py` で `include_router` します。

```text
src/kokkai/api/routes/<data_name>.py
```

## 9. 動作確認する

最低限、次を確認します。

```bash
python3 -m compileall api.py scripts src
uv run python scripts/ingest.py <pipeline_name>
```
