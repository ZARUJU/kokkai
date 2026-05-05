# データソース

## 衆議院 会期一覧

- pipeline: `shugiin_sessions`
- 種別: HTML
- URL: https://www.shugiin.go.jp/internet/itdb_annai.nsf/html/statics/shiryo/kaiki.htm
- 取得対象:
  - 国会回次
  - 会期種別
  - 召集日
  - 終了日
  - 終了理由
  - 会期日数
  - 常会会期
  - 延長日数
- 主キー:
  - 国会回次
- 更新方針:
  - 手動または定期バッチで全件再取得し、国会回次で upsert する。
- 保存方針:
  - 解析後の会期データを SQLite に保存する。
  - 取得元 URL と取得日時を各レコードに保持する。
- 備考:
  - ページの文字コードは Shift_JIS。
  - 終了日欄に「解散」が含まれる場合は終了理由として保持する。

## 衆議院 議案一覧

- pipeline: `shugiin_bills`
- 種別: HTML
- URL: https://www.shugiin.go.jp/internet/itdb_gian.nsf/html/gian/kaiji{国会回次}.htm
- 取得対象:
  - 議案一覧を掲載している国会回次
  - 提出回次
  - 議案種別
  - 番号
  - 議案件名
  - 審議状況
  - 経過情報 URL
  - 本文情報 URL
  - 経過情報の項目と内容
  - 本文情報に掲載された本文ドキュメントの種別、URL、本文
- 主キー:
  - 経過情報 URL の識別子
- 更新方針:
  - 既定では、`shugiin_sessions` で保存した国会回次のうち番号が新しいものから最大 2 件だけを対象に再取得し、経過情報 URL の識別子で upsert する（経過・本文が動きやすい最新会期とその直前を定期更新する想定）。
  - `scripts/ingest.py` の `--session`、または環境変数 `SHUGIIN_BILL_SESSIONS`（カンマ区切り）で対象回次を明示できる。**CLI の `--session` が最優先**。いずれも無い場合は前述の DB 由来の既定に従う。
  - 会期一覧が未投入の DB ではフォールバックとしてコード内の既定回次（単一会期）を使うため、本番の定期実行では先に `shugiin_sessions` を走らせることが望ましい。
- 保存方針:
  - 解析後の議案一覧データを SQLite に保存する。
  - 経過情報は議案ごとの項目・内容として保存し、API では日付、委員会、結果、提出者などに構造化して返す。
  - 本文情報は本文ドキュメントごとのラベル、URL、抽出本文として保存する。
  - 取得元 URL と取得日時を各レコードに保持する。
  - 同一の経過ページ ID（`source_id`）が複数の国会回次の議案一覧に載る場合があるため、会期ごとの掲載行は `bill_listing_sessions` テーブルに `(bill_source_id, session_number)` 単位で保持する。
  - 番号付き議案は提出回次・種別・番号から求める `canonical_key` を `bills` に保持し、経過 URL が会期で分かれた別レコードを API 上で関連付け可能にする。
  - `GET /diet-sessions/{number}/bills` および会期で絞ったリポジトリ検索は、**当該会期の `bill_listing_sessions` に行がある議案のみ**を対象とする。`GET /bills` の全会期一覧とは異なり、`bills.session_number` だけが一致しても掲載行が無ければ会期別一覧には出ない。API の `Bill.listing_sessions` も同テーブル由来であり、行が無ければ空配列。
- 備考:
  - 衆議院と参議院で同内容の情報が提供されているため、衆議院のページから取得する。
  - ページの文字コードは Shift_JIS。
  - 予算、条約、承諾、決算その他など、本文情報や番号がない表では該当項目を `null` として保存する。
  - モデル名は取得元に依存しない議案一覧として扱い、衆議院は取得元の一つとして記録する。
  - HTTP API では、会期単位の一覧は `GET /diet-sessions/{number}/bills`、議案 ID 単位の取得・経過・本文は `GET /bills/{source_id}` 系とルーティングを分ける（詳細は [api.md](api.md)）。

## 国立国会図書館 国会会議録検索 API

- pipeline: `kokkai_meetings`
- 種別: JSON API
- 仕様: https://kokkai.ndl.go.jp/api.html
- 取得対象:
  - 会議録 ID、国会回次、院名、会議名、号、開催日
  - 会議単位出力による全発言（発言 ID、発言者、本文等）
  - 議事冒頭（`会議録情報` 発言）から抽出した開議・閉会などの時刻（`HH:MM`、冒頭に無い場合は全会話を走査）
  - 同テキストから抽出した取り扱い議題一覧
  - 全発言の `speaker` から得た発言者名の配列（敬称除去・`会議録情報` 除外、登場順で重複を除く。`meeting_records.speakers_json` に JSON 配列で保存）
- 派生・リンク:
  - 当該国会回次の `bills` 各行について、`submitted_session_number`・`category`（閣法/衆法/参法/条約）・`number` から日本法令索引の `billId` を組み立てる。`https://kokkai.ndl.go.jp/#/result?billId=` を Playwright で開き、検索 API の `min_id`（= 会議録 `issueID`）に当該会議録が含まれる議案だけを `meeting_records.bill_source_ids_json` に保存する（議題行とは紐づけない）
  - 最適化: `sessionFrom`〜`sessionTo` の会期について、議案行を一度だけ走査し `billId` 単位で `min_id` 一覧を先にキャッシュしてから会議録を保存する（会議数×議案数回の NDL 取得を避ける）。2件目以降の `billId` 取得ではトップへの往復と localStorage クリアを省略する
- 主キー:
  - 会議録: `issue_id`（`bill_source_ids_json`: 当会議録に審議が載る議案の `source_id` の JSON 配列）
  - 発言: `speech_id`
  - 議題行: `{issue_id}:topic:{順序}`（`meeting_topics`。ラベル・順序のみで、議案 ID は会議録ヘッダにのみ保持）
- 更新方針:
  - 対象国会回次は既定では `shugiin_sessions` で保存した番号のうち新しい方から最大 2 件の範囲（API の `sessionFrom` にその最小、`sessionTo` にその最大）とし、`meeting_list` で `issue_id` をページング取得し、各 ID を `meeting` で再取得して upsert する。
  - `scripts/ingest.py` の `--session`、または環境変数 `KOKKAI_MEETING_SESSIONS`（カンマ区切り）で対象回次を列挙すると、その **最小〜最大** が API の `sessionFrom`〜`sessionTo` になる。**CLI が最優先**。いずれも無い場合は前述の DB 既定に従う。
  - 会期一覧が未投入の DB ではフォールバックとして単一会期（コード内既定）に縮れるため、本番の定期実行では先に `shugiin_sessions` を走らせることが望ましい。
  - 公開済み会議録は不変とみなし、DB に同一 `issue_id` が既にある場合はデフォルトで API 再取得を省略する（議案一覧 ingest を後から足した場合などで会議録と議案の紐づけをやり直したいときは `KOKKAI_MEETING_REINGEST` を真に設定して再取得する）。
  - 公式利用条件に従い、リクエスト間に数秒空ける。
- 保存方針:
  - 会議録ヘッダ・抽出メタデータ・発言全文・議題（ラベルのみ）・発言者一覧を SQLite に保存する。
  - API リクエスト URL（例: `.../api/meeting?issueID=...`）と取得日時は `meeting_records` のみに保持する（発言・議題・発言者一覧の子行には重複させない）。
  - `KOKKAI_MEETING_INGEST_LIMIT` を設定すると取得件数を上限で打ち切れる（検証用）。
  - `KOKKAI_MEETING_REINGEST` を `1` / `true` / `yes` / `on` のいずれかにすると、既存 `issue_id` も含めて再取得する。
  - `--session` も `KOKKAI_MEETING_SESSIONS` も無い場合、対象回次は議案 ingest と同様に DB の最新側 2 会期から決まる。

## 質問主意書一覧（衆議院・参議院）

- pipeline: `questions`
- 種別: HTML
- URL（`{国会回次}` で一覧ページを構築）:
  - https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon/kaiji{国会回次}_l.htm
  - https://www.sangiin.go.jp/japanese/joho1/kousei/syuisyo/{国会回次}/syuisyo.htm
- 取得対象:
  - 院別（`shugiin` / `sangiin`）
  - 国会回次
  - 提出番号
  - 件名
  - 提出者（取得できる場合）。会議録の発言者名と同じ `clean_kokkai_speaker_name` に相当する処理で正規化して保存する
  - 経過・状態（衆議院）
  - 詳細 URL、質問本文 HTML URL、答弁本文 HTML URL
  - 質問本文・答弁本文のプレーンテキスト（各 HTML を取得して抽出）
- 主キー:
  - `院別 + 国会回次 + 提出番号`
- 更新方針:
  - 対象国会回次は既定では `shugiin_sessions` で保存した番号のうち新しい方から最大 2 件（DB が空なら単一会期のコード内フォールバック）。`scripts/ingest.py` の `--session`、または環境変数 `QUESTIONS_SESSIONS`（カンマ区切り）で明示できる。**CLI が最優先**。各回次について衆議院・参議院の一覧を順に取得する。
  - 各院の配布一覧ページを再取得し、主キーで upsert する。
- 保存方針:
  - 解析後の質問主意書一覧データを SQLite に保存する。
  - 取得元 URL と取得日時を各レコードに保持する。
