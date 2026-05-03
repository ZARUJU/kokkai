# API 仕様

この文書では、API が返す主な JSON オブジェクトの項目、意味、型を定義する。

## 共通

| 型 | 説明 |
| --- | --- |
| `string` | 文字列 |
| `integer` | 整数 |
| `array<T>` | `T` の配列 |
| `object` | JSON オブジェクト |
| `null` | 元データに値がない、または未確定 |

日付は原則として `YYYY-MM-DD` または `YYYY/MM/DD` の文字列で返す。議案経過情報内の日付は `YYYY/MM/DD` で返す。

## エンドポイント

| メソッド | パス | 内容 |
| --- | --- | --- |
| `GET` | `/health` | ヘルスチェック |
| `GET` | `/diet-sessions` | 会期一覧 |
| `GET` | `/diet-sessions/{number}` | 指定した国会回次の会期 |
| `GET` | `/diet-sessions/{number}/bills` | 指定した国会回次の議案一覧（衆議院議案一覧ページに相当） |
| `GET` | `/diet-sessions/{number}/bills?category=衆法` | 上記に加え議案種別で絞り込み |
| `GET` | `/bills` | 全会期をまたいだ議案一覧 |
| `GET` | `/bills?category=衆法` | 議案種別で絞り込んだ議案一覧 |
| `GET` | `/bills/{source_id}` | 指定した議案の詳細と構造化済み経過情報 |
| `GET` | `/bills/{source_id}/progress` | 指定した議案の構造化済み経過情報のみ |
| `GET` | `/bills/{source_id}/texts` | 指定した議案の本文情報 |

会期で議案を列挙するときは **`/diet-sessions/{number}/bills`**、議案を `source_id` で参照するときは **`/bills/...`** とパスを分けている。

## `DietSession`

`/diet-sessions` と `/diet-sessions/{number}` で返す会期情報。

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `number` | `integer` | 国会回次 |
| `session_type` | `string` | 会期種別。例: `常会`, `臨時会`, `特別会` |
| `start_date` | `string \| null` | 召集日。形式は `YYYY-MM-DD` |
| `end_date` | `string \| null` | 終了日。形式は `YYYY-MM-DD` |
| `end_note` | `string \| null` | 終了理由などの補足。例: `解散` |
| `total_days` | `integer \| null` | 会期日数 |
| `statutory_days` | `integer \| null` | 常会会期の日数 |
| `extension_days` | `integer \| null` | 延長日数 |
| `source_url` | `string` | 取得元 URL |
| `fetched_at` | `string` | 取得日時。ISO 8601 形式 |

## `Bill`

`/bills`・`/diet-sessions/{number}/bills`・`/bills/{source_id}` で返す議案情報。

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `source_id` | `string` | 取得元ページから採用した議案識別子。経過情報 URL のファイル名部分を使う |
| `session_number` | `integer` | いちばん新しく議案一覧を取り込んだときの国会回次。会期ごとの掲載履歴は `listing_sessions` を参照 |
| `submitted_session_number` | `integer` | 議案の提出回次 |
| `category` | `string` | 議案種別。例: `衆法`, `参法`, `閣法`, `予算`, `条約`, `決算` |
| `canonical_key` | `string \| null` | 番号付き議案のみ。`提出回次:種別:番号` 形式。会期をまたいで経過ページ ID が異なる別レコードをまとめるときのキー |
| `number` | `integer \| null` | 議案番号。番号がない議案では `null` |
| `title` | `string` | 議案件名 |
| `status` | `string` | 直近の取り込みにおける議案一覧上の審議状況 |
| `progress_url` | `string \| null` | 経過情報ページの URL |
| `text_url` | `string \| null` | 本文情報一覧ページの URL |
| `source_url` | `string` | 議案一覧の取得元 URL（直近取り込み） |
| `fetched_at` | `string` | 議案レコードの取得日時。ISO 8601 形式 |
| `listing_sessions` | `array<BillListingSession>` | 衆議院議案一覧のどの国会回次の表に載ったか（会期ごとの審議状況など） |
| `progress` | `BillProgress` | `/bills/{source_id}` のみ。構造化済み経過情報 |
| `related_bill_source_ids` | `array<string>` | `/bills/{source_id}` のみ。同じ `canonical_key` の別 `source_id`（別会期の経過ページなど） |

## `BillListingSession`

`Bill.listing_sessions` の各要素。会期ごとの一覧掲載事実に対応する。

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `session_number` | `integer` | 当該議案が掲載されていた国会回次（衆議院 `kaiji{回次}.htm` に相当） |
| `status` | `string` | その回次の議案一覧上の審議状況 |
| `source_url` | `string` | その取り込みの議案一覧 URL |
| `fetched_at` | `string` | その掲載情報の取得日時。ISO 8601 形式 |

## `BillProgress`

`/bills/{source_id}` の `progress` と `/bills/{source_id}/progress` で返す構造化済み経過情報。

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `bill_type` | `string \| null` | 経過情報ページ上の議案種類 |
| `submit_session` | `integer \| null` | 議案提出回次 |
| `bill_number` | `integer \| null` | 議案番号 |
| `title` | `string \| null` | 議案件名 |
| `submitter` | `SubmitterSummary` | 代表提出者と提出者数 |
| `submitter_groups` | `array<string>` | 議案提出会派 |
| `submitters` | `array<string>` | 議案提出者一覧。敬称は除去する |
| `supporters` | `array<string>` | 議案提出の賛成者。敬称は除去する |
| `house_of_representatives` | `HouseProgress` | 衆議院側の経過 |
| `house_of_councillors` | `HouseProgress` | 参議院側の経過 |
| `promulgation` | `DateDetail` | 公布年月日と法律番号 |

## `SubmitterSummary`

議案提出者欄の要約。

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `representative` | `string \| null` | 代表提出者。例: `竹詰 仁` |
| `count` | `integer \| null` | 提出者数。例: `竹詰 仁外一名` は `2` |

## `HouseProgress`

衆議院または参議院の経過情報。

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `preliminary_received_date` | `string \| null` | 予備審査議案受理年月日。形式は `YYYY/MM/DD` |
| `preliminary_referral` | `DateDetail` | 予備付託年月日と予備付託委員会 |
| `received_date` | `string \| null` | 議案受理年月日。形式は `YYYY/MM/DD` |
| `referral` | `DateDetail` | 付託年月日と付託委員会 |
| `committee_result` | `DateDetail` | 審査終了年月日と審査結果 |
| `plenary_result` | `DateDetail` | 審議終了年月日と審議結果 |
| `vote_attitudes` | `array<string>` | 衆議院審議時会派態度。参議院側では通常空配列または未使用 |
| `supporting_groups` | `array<string>` | 衆議院審議時賛成会派。参議院側では通常空配列または未使用 |
| `opposing_groups` | `array<string>` | 衆議院審議時反対会派。参議院側では通常空配列または未使用 |

## `DateDetail`

日付と、その日付に対応する補足情報を持つオブジェクト。補足キーは用途により異なる。

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `date` | `string \| null` | 日付。形式は `YYYY/MM/DD` |
| `committee` | `string \| null` | 委員会名。付託情報で使う |
| `result` | `string \| null` | 審査結果または審議結果 |
| `law_number` | `string \| null` | 法律番号。公布情報で使う |

## `BillTextDocument`

`/bills/{source_id}/texts` で返す本文ドキュメント。

| 項目 | 型 | 説明 |
| --- | --- | --- |
| `source_id` | `string` | 本文ドキュメントの識別子 |
| `bill_source_id` | `string` | 紐づく議案の `source_id` |
| `item_order` | `integer` | 本文情報一覧ページ上の表示順 |
| `label` | `string` | 本文ドキュメントの種別。例: `提出時法律案`, `[要綱]` |
| `document_url` | `string` | 本文ドキュメントの URL |
| `content_text` | `string \| null` | HTML から抽出・整形した本文 |
| `source_url` | `string` | 本文情報一覧ページの URL |
| `fetched_at` | `string` | 取得日時。ISO 8601 形式 |

