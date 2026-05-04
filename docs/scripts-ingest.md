# `scripts/ingest.py` 解説

国会関連データを取得・解析して SQLite（`DATABASE_URL`）へ保存する **ingest の CLI エントリポイント** です。個別または一括で [pipeline](ingest-flow.md) を実行し、件数サマリを標準出力に表示します。

## 前提

- プロジェクトルートで `uv run python scripts/ingest.py` として実行する（`uv` が `src/` 配下のパッケージ `kokkai` を解決する）。
- DB 接続先は環境変数 `DATABASE_URL`（未設定時は `kokkai.settings` と同様に `sqlite:///./data/kokkai.sqlite3` が使われる想定）。ローカルの `.env` は Git 管理外。
- ネットワーク越しに衆議院・国会 open data 等へアクセスする pipeline では、オフライン環境では失敗し得る。

## 基本的な使い方

```bash
# 登録済み pipeline をすべて実行（runner の PIPELINES 定義順）
uv run python scripts/ingest.py

# 指定した pipeline のみ順に実行（複数可）
uv run python scripts/ingest.py shugiin_sessions shugiin_bills

# 衆議院議案だけ、国会回次 219 と 220 を順に処理（一覧・質問主意書にも同様に渡る）
uv run python scripts/ingest.py shugiin_bills --session 219 --session 220

# 会議録は sessionFrom と sessionTo に、指定した回次の最小〜最大が使われる
uv run python scripts/ingest.py kokkai_meetings --session 218,219,221
```

登録名と実体の対応は `src/kokkai/ingest/runner.py` の `PIPELINES` を参照する。現時点のキー例:

| 名前 | 概略 |
|------|------|
| `shugiin_sessions` | 衆議院会期一覧など |
| `shugiin_bills` | 衆議院議案 |
| `kokkai_meetings` | 国会会議録関連 |
| `questions` | 質問主意書等（実装に依存） |

新規データソース追加時は [データ追加の流れ](ingest-flow.md) に沿って pipeline を実装し、`PIPELINES` に登録する。

## コマンドライン引数

| 引数 | 説明 |
|------|------|
| `pipelines` | positional、0 個以上。省略時は **全 pipeline**（`runner.run(None, context=...)` と同等で、`PIPELINES` のキー順に実行）。1 個以上ある場合は **指定した名前の順** でだけ実行する。 |
| `--session NUM[,NUM...]` | **`shugiin_bills`、`kokkai_meetings`、`questions` で有効**。指定した国会回次のリストをすべての実行中 pipeline に渡す（複数回指定可）。各値にカンマ区切りを含められる。順序は議案ではそのまま一覧取得の順、会議録は API 用に **最小〜最大に畳んだ範囲**、質問主意書は衆・参とも **各回次を順に** 一覧ページを取得する。 |
| `-v`, `--verbose` | ログレベルを `logging.DEBUG` に設定。HTTP の GET など詳細ログが増える。 |
| `-q`, `--quiet` | ログレベルを `logging.WARNING` に設定。`-v` と同時指定した場合は **`-v` が優先**。 |
| （どちらもなし） | `kokkai.ingest.cli_log.level_from_env()` の結果。環境変数 `KOKKAI_INGEST_LOG_LEVEL`（既定 `INFO`）を名前で解決し、無効な値のときは `INFO` とみなす。 |

### `--session` と環境変数・DB の優先順位（議案・会議録・質問主意書）

1. **`--session` が 1 つ以上有効な数として解決できれば、それのみを使う**（各 pipeline が解釈）。
2. 無指定のとき **`SHUGIIN_BILL_SESSIONS` / `KOKKAI_MEETING_SESSIONS` / `QUESTIONS_SESSIONS`**（カンマ区切り）。
3. さらに無ければ **`shugiin_sessions` で入れた会期一覧から新しい順最大 2 件**（該当 pipeline ごとに実装。DB が空ならコード内の単一会期フォールバック）。

`shugiin_sessions` は会期の母集団を作る pipeline のため **`--session` の影響を受けない**（常に衆議院会期一覧を全件取得）。

未知の pipeline 名を指定すると `runner.run` が `ValueError` を送出し、スクリプトはメッセージをログ出力したうえで **終了コード 1** で終了する。

## ログと標準出力

- **ログ**（進行状況・pipeline 開始・終了・所要時間・件数など）は、`logging.basicConfig` により **標準エラー** に出力される。フォーマットは `%(levelname)s [%(name)s] %(message)s`（`kokkai.ingest.cli_log.configure`）。
- **サマリ行** は **標準出力** に `ingested <name>: <count>` の形で、`runner` が返した各 `PipelineResult` ごとに 1 行ずつ出力される。同じ内容が `logging` の INFO にも `summary ...` として残る。

`PipelineResult` は `kokkai.ingest.pipeline` で定義され、`name`（pipeline 識別子）と `count`（取り込み件数など、pipeline 実装の意味）を持つ。

`Pipeline` は `IngestRunContext` を唯一の引数に取り `PipelineResult` を返す。`--session` は `runner` が各 pipeline に共通の `IngestRunContext.session_numbers` として渡す（`kokkai.ingest.cli_sessions.build_run_context`）。

## 処理の流れ（コード上）

1. `argparse` で引数解析。
2. `--verbose` / `--quiet` / 既定 で `kokkai.ingest.cli_log.configure(...)` を呼び、ログレベルを決める。
3. `kokkai.ingest.runner.run(args.pipelines or None, context=build_run_context(args.sessions))` を呼ぶ。
   - 空リストではなく **`None`** のときが「全 pipeline」モード（`runner` 側で `list(PIPELINES)` に展開）。
4. 各結果について stdout に 1 行ずつ表示し、合わせて INFO ログに記録。

## 終了コード

| 状況 | 終了コード |
|------|------------|
| 正常終了 | 0 |
| 未知の pipeline 名など `ValueError` | 1（元の例外は `raise SystemExit(1) from error` で連鎖保持） |

pipeline 内部の取得失敗や DB エラーは **各 pipeline 実装の挙動に依存**する。`scripts/ingest.py` 自体は `ValueError` 以外を特別扱いしない。

## 関連ファイル

| パス | 役割 |
|------|------|
| `scripts/ingest.py` | 本 CLI。引数・ログ設定・`runner.run` 呼び出し・サマリ表示。 |
| `src/kokkai/ingest/runner.py` | `PIPELINES` 登録と実行順制御。 |
| `src/kokkai/ingest/cli_log.py` | ingest 専用の `logging` 初期化と `KOKKAI_INGEST_LOG_LEVEL`。 |
| `src/kokkai/ingest/pipeline.py` | `PipelineResult` / `IngestRunContext` / `Pipeline` 型。 |
| `src/kokkai/ingest/cli_sessions.py` | `--session` のパースと `IngestRunContext` 組み立て。 |
| `src/kokkai/ingest/pipelines/` | 各データソースの `run()` 実装。 |

## 動作確認の例

```bash
python3 -m compileall api.py scripts src
uv run python scripts/ingest.py shugiin_sessions
uv run pytest
```

プロジェクトのエージェント向け手順は [AGENTS.md](../AGENTS.md) を参照。
