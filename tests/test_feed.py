from datetime import UTC, datetime

from procurement.feed import collect_since, parse_page

ATOM_HEADER = (
    '<feed xmlns="http://www.w3.org/2005/Atom"'
    ' xmlns:cbc="urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2"'
    ' xmlns:cac="urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2"'
    ' xmlns:at="http://purl.org/atompub/tombstones/1.0">'
)


def entry(entry_id: str, updated: str, cpv: str) -> str:
    return (
        f"<entry><id>{entry_id}</id><updated>{updated}</updated>"
        f"<cac:ProcurementProject><cac:RequiredCommodityClassification>"
        f"<cbc:ItemClassificationCode>{cpv}</cbc:ItemClassificationCode>"
        f"</cac:RequiredCommodityClassification></cac:ProcurementProject></entry>"
    )


def feed(entries: list[str], next_url: str | None = None, deleted: str = "") -> bytes:
    link = f'<link href="{next_url}" rel="next"/>' if next_url else ""
    body = "".join(entries)
    return f"{ATOM_HEADER}{link}{deleted}{body}</feed>".encode()


def test_parse_page_flags_scope_and_keeps_raw_xml_only_in_scope():
    content = feed(
        [
            entry("a", "2026-10-13T10:00:00.000+02:00", "72212000"),
            entry("b", "2026-10-13T09:00:00.000+02:00", "45000000"),
        ]
    )
    page = parse_page(content, "72")

    assert [e.in_scope for e in page.entries] == [True, False]
    assert page.entries[0].raw_xml is not None
    assert page.entries[1].raw_xml is None


def test_parse_page_preserves_original_prefixes():
    content = feed([entry("a", "2026-10-13T10:00:00.000+02:00", "72212000")])
    raw = parse_page(content, "72").entries[0].raw_xml

    assert "cbc:ItemClassificationCode" in raw
    assert "ns0" not in raw


def test_parse_page_reads_tombstones_and_next_link():
    deleted = (
        '<at:deleted-entry ref="https://x/1" when="2026-10-10T13:47:43.290+02:00">'
        '<at:comment type="ANULADA"/></at:deleted-entry>'
    )
    content = feed([], next_url="https://x/next", deleted=deleted)
    page = parse_page(content, "72")

    assert page.next_url == "https://x/next"
    assert page.tombstones[0].ref == "https://x/1"
    assert page.tombstones[0].comment_type == "ANULADA"


def test_page_range_and_new_entries_use_real_timestamps():
    content = feed(
        [
            entry("a", "2026-10-13T10:00:00.000+02:00", "72212000"),
            entry("b", "2026-10-13T08:00:00.000+02:00", "72212000"),
        ]
    )
    page = parse_page(content, "72")
    watermark = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)

    assert page.max_updated > page.min_updated
    assert [e.entry_id for e in page.new_entries(watermark)] == ["a"]


def test_collect_since_stops_at_the_page_that_reaches_the_watermark():
    pages = {
        "p1": feed([entry("a", "2026-10-13T10:00:00.000+02:00", "72")], "p2"),
        "p2": feed([entry("b", "2026-10-13T08:00:00.000+02:00", "72")], "p3"),
        "p3": feed([entry("c", "2026-10-12T08:00:00.000+02:00", "72")], None),
    }
    watermark = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)

    collected = list(collect_since("p1", watermark, "72", fetch=lambda u: pages[u]))

    assert len(collected) == 2


def test_collect_since_honours_max_pages():
    pages = {
        "p1": feed([entry("a", "2026-10-13T10:00:00.000+02:00", "72")], "p2"),
        "p2": feed([entry("b", "2026-10-13T08:00:00.000+02:00", "72")], None),
    }
    watermark = datetime(2020, 1, 1, tzinfo=UTC)

    collected = list(
        collect_since("p1", watermark, "72", fetch=lambda u: pages[u], max_pages=1)
    )

    assert len(collected) == 1
