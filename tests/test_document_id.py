from amendaq.document_id import generate_document_id


def test_generate_ascii_slug():
    assert generate_document_id("XingHe_Handbook.txt") == "xinghe_handbook"


def test_generate_hash_for_cjk():
    doc = generate_document_id("星河科技_手册.txt")
    assert doc.startswith("doc_")
    assert len(doc) > 4
