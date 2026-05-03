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
