from procurement.documents import doc_id, is_pdf


def test_is_pdf_checks_the_header():
    assert is_pdf(b"%PDF-1.7 rest")
    assert not is_pdf(b"<html>error page</html>")


def test_doc_id_is_deterministic_and_depends_on_uri_and_hash():
    assert doc_id("u", "h") == doc_id("u", "h")
    assert doc_id("u", "h") != doc_id("u", "other")
    assert doc_id("u", None) == doc_id("u", "")
