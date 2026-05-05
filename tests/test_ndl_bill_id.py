from kokkai.ingest.parsers.ndl_bill_id import build_ndl_bill_id
from kokkai.ingest.parsers.ndl_bill_id import gian_source_id_from_ndl_bill_id
from kokkai.ingest.parsers.ndl_bill_id import ndl_bill_id_from_bill_row
from kokkai.ingest.parsers.ndl_bill_id import ndl_bill_ids_from_topic_label
from kokkai.ingest.parsers.ndl_bill_id import parse_ndl_bill_id


def test_build_and_parse_roundtrip() -> None:
    assert build_ndl_bill_id(219, "03", 3) == "121903003"
    assert parse_ndl_bill_id("121903003") == (219, "03", 3)
    assert parse_ndl_bill_id("121901002") == (219, "01", 2)
    assert parse_ndl_bill_id("121902002") == (219, "02", 2)


def test_ndl_bill_id_from_bill_row_like_listing() -> None:
    """議案一覧相当の行から billId を組み立てる（ユーザー例: 221会 参法2号）。"""
    assert ndl_bill_id_from_bill_row(221, "参法", 2) == "122103002"
    assert ndl_bill_id_from_bill_row(221, "閣法", 1) == "122101001"
    assert ndl_bill_id_from_bill_row(221, "予算", 1) is None


def test_gian_source_id_examples() -> None:
    assert gian_source_id_from_ndl_bill_id("121903002") == "g21906002"
    assert gian_source_id_from_ndl_bill_id("121902002") == "g21905002"
    assert gian_source_id_from_ndl_bill_id("121901002") == "g21909002"


def test_ndl_bill_ids_from_topic_whole_line() -> None:
    label = "地方税法の一部を改正する法律案（内閣提出、法律案第二号）の趣旨説明"
    assert ndl_bill_ids_from_topic_label(label, 219) == ["121901002"]


def test_ndl_bill_ids_sangiin() -> None:
    label = "刑法等の一部を改正する法律案（参議院提出、法律案第三号）"
    assert ndl_bill_ids_from_topic_label(label, 219) == ["121903003"]
