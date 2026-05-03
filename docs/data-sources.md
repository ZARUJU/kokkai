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
  - 手動または定期バッチで対象回次を再取得し、経過情報 URL の識別子で upsert する。
- 保存方針:
  - 解析後の議案一覧データを SQLite に保存する。
  - 経過情報は議案ごとの項目・内容として保存し、API では日付、委員会、結果、提出者などに構造化して返す。
  - 本文情報は本文ドキュメントごとのラベル、URL、抽出本文として保存する。
  - 取得元 URL と取得日時を各レコードに保持する。
  - 同一の経過ページ ID（`source_id`）が複数の国会回次の議案一覧に載る場合があるため、会期ごとの掲載行は `bill_listing_sessions` テーブルに `(bill_source_id, session_number)` 単位で保持する。
  - 番号付き議案は提出回次・種別・番号から求める `canonical_key` を `bills` に保持し、経過 URL が会期で分かれた別レコードを API 上で関連付け可能にする。
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
  - 議題が法律案で `bills` と題名が一致する場合、`bill_source_ids`（`string[]`）で複数議案を紐づけ可能（議題本文を断片化して議案ごとに照合）
- 主キー:
  - 会議録: `issue_id`
  - 発言: `speech_id`
  - 議題行: `{issue_id}:topic:{順序}`（同一行に `bill_source_ids_json`: 紐づく議案 `source_id` の JSON 配列）
- 更新方針:
  - `meeting_list` で対象回次の `issue_id` をページング取得し、各 ID を `meeting` で再取得して upsert する。
  - 公式利用条件に従い、リクエスト間に数秒空ける。
- 保存方針:
  - 会議録ヘッダ・抽出メタデータ・発言全文・議題・発言者一覧を SQLite に保存する。
  - API リクエスト URL（例: `.../api/meeting?issueID=...`）と取得日時は `meeting_records` のみに保持する（発言・議題・発言者一覧の子行には重複させない）。
  - `KOKKAI_MEETING_INGEST_LIMIT` を設定すると取得件数を上限で打ち切れる（検証用）。
