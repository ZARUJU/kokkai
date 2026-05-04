from kokkai.ingest.parsers import questions


def test_parse_shugiin_minimal_table() -> None:
    html = """
    <html><body>
    <h1>第221回国会 質問の一覧</h1>
    <table>
      <tr>
        <th>番号</th><th>質問件名</th><th>提出者氏名</th><th>経過状況</th>
        <th>経過情報</th><th>質問情報(HTML)</th><th>質問情報(PDF)</th><th>答弁情報(HTML)</th><th>答弁情報(PDF)</th>
      </tr>
      <tr>
        <td>1</td><td>テスト質問主意書</td><td>山田太郎君</td><td>答弁受理</td>
        <td><a href="221001.htm">経過</a></td>
        <td><a href="a221001.htm">質問</a></td>
        <td><a href="a221001.pdf">PDF</a></td>
        <td><a href="b221001.htm">答弁</a></td>
        <td><a href="b221001.pdf">PDF</a></td>
      </tr>
    </table>
    </body></html>
    """
    items = questions.parse_shugiin(
        html,
        "https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon/kaiji221_l.htm",
    )
    assert len(items) == 1
    item = items[0]
    assert item.chamber == "shugiin"
    assert item.session_number == 221
    assert item.number == 1
    assert item.title == "テスト質問主意書"
    assert item.submitter == "山田太郎"
    assert item.status == "答弁受理"
    assert item.question_text is None
    assert item.answer_text is None
    assert item.question_url is not None and item.question_url.endswith("/a221001.htm")
    assert item.answer_url is not None and item.answer_url.endswith("/b221001.htm")


def test_parse_shugiin_submitter_uses_kokkai_like_normalization() -> None:
    """先頭の ○・敬称除去は会議録の clean_kokkai_speaker_name と同系の処理。"""
    html = """
    <html><body>
    <h1>第221回国会 質問の一覧</h1>
    <table>
      <tr>
        <th>番号</th><th>質問件名</th><th>提出者氏名</th><th>経過状況</th>
        <th>経過情報</th><th>質問情報(HTML)</th><th>質問情報(PDF)</th><th>答弁情報(HTML)</th><th>答弁情報(PDF)</th>
      </tr>
      <tr>
        <td>2</td><td>件名B</td><td>○山田　太 郎君</td><td></td>
        <td></td><td></td><td></td><td></td><td></td>
      </tr>
    </table>
    </body></html>
    """
    items = questions.parse_shugiin(
        html,
        "https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon/kaiji221_l.htm",
    )
    assert len(items) == 1
    assert items[0].submitter == "山田 太 郎"


def test_parse_sangiin_minimal_rows() -> None:
    html = """
    <html><body>
    <h1>第221回国会質問主意書・答弁書一覧</h1>
    <a href="meisai/m221001.htm">テスト質問主意書</a>
    <table>
      <tr><td>1</td><td>提出者</td><td>石垣 のりこ君</td>
      <td><a href="syuh/s221001.htm">質問本文（html）</a></td>
      <td><a href="touh/t221001.htm">答弁本文（html）</a></td></tr>
    </table>
    </body></html>
    """
    items = questions.parse_sangiin(
        html,
        "https://www.sangiin.go.jp/japanese/joho1/kousei/syuisyo/221/syuisyo.htm",
    )
    assert len(items) == 1
    item = items[0]
    assert item.chamber == "sangiin"
    assert item.session_number == 221
    assert item.number == 1
    assert item.title == "テスト質問主意書"
    assert item.submitter == "石垣 のりこ"
    assert item.question_text is None
    assert item.answer_text is None
    assert item.question_url is not None and item.question_url.endswith("/syuh/s221001.htm")
    assert item.answer_url is not None and item.answer_url.endswith("/touh/t221001.htm")


def test_extract_document_text_removes_script_and_footer() -> None:
    html = """
    <html><body>
      <h1>見出し</h1>
      <script>var x=1;</script>
      <p>本文A</p><p>本文B</p>
      <div>利用案内</div><div>著作権</div><div>免責事項</div>
      <div>All rights reserved. Copyright(c)</div>
    </body></html>
    """
    text = questions.extract_document_text(html)
    assert text is not None
    assert "本文A" in text
    assert "本文B" in text
    assert "var x" not in text
    assert "All rights reserved" not in text


def test_extract_document_text_sangiin_contentsbox_focus() -> None:
    html = """
    <html><body>
    <div id="Header"><a href="#ContentsBox">本文へ</a>ヘッダー</div>
    <div id="ContentsBox">
      <p class="exp">第221回国会（特別会）</p>
      <h2 class="title_text">質問主意書</h2>
      <p>条文本文だけ残したい。</p>
    </div>
    <div id="Footer"><small>All rights reserved.</small></div>
    </body></html>
    """
    text = questions.extract_document_text(
        html,
        "https://www.sangiin.go.jp/japanese/joho1/kousei/syuisyo/221/syuh/s221001.htm",
    )
    assert text is not None
    assert "ヘッダー" not in text
    assert "条文本文だけ残したい" in text
    assert "All rights reserved" not in text


def test_extract_document_text_shugiin_mainlayout_skips_breadcrumb() -> None:
    html = """
    <html><body>
    <div id="mainlayout">
      <div id="breadcrumb">
        <ul><li>トップ &gt;</li><li>立法情報</li></ul>
      </div>
      <h1 id="TopContents">質問主意書</h1>
      <p>本文ブロック</p>
    </div>
    <div>フッター案内 お問い合わせ 衆議院</div>
    </body></html>
    """
    text = questions.extract_document_text(
        html,
        "https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon/a221001.htm",
    )
    assert text is not None
    assert "breadcrumb" not in text.lower()
    assert "トップ" not in text
    assert "立法情報" not in text
    assert "本文ブロック" in text
