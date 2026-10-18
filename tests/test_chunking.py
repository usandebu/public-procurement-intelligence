from procurement.chunking import (
    chunk_pages,
    clean_pages,
    is_table_of_contents,
    repeated_lines,
)
from procurement.pages import PageText

BODIES = [
    "objeto",
    "precio",
    "plazo",
    "garantia",
    "penalidades",
    "solvencia",
    "pago",
    "revision",
]


def make_pages(
    count: int, header: str = "ORGANISMO EJEMPLO CIF X1234"
) -> list[PageText]:
    return [
        PageText(
            page_number=number,
            text=f"{header}\nPagina {number} de {count}\nClausula {number}. {BODIES[number - 1]} del contrato.",
        )
        for number in range(1, count + 1)
    ]


def test_repeated_lines_detects_headers_and_page_counters_ignoring_digits():
    repeated = repeated_lines(make_pages(6))

    assert "ORGANISMO EJEMPLO CIF X#" in repeated
    assert "Pagina # de #" in repeated
    assert not any("Clausula" in line for line in repeated)


def test_repeated_lines_needs_enough_pages():
    assert repeated_lines(make_pages(2)) == set()


def test_is_table_of_contents_recognises_dot_leaders():
    toc = "TITULO I .................... 3\nCLAUSULA 1 ........................ 4\nCLAUSULA 2 ........... 5"

    assert is_table_of_contents(toc)
    assert not is_table_of_contents("Clausula 1. Objeto del contrato y su alcance.")
    assert not is_table_of_contents("")


def test_clean_pages_drops_headers_and_table_of_contents():
    toc = PageText(
        page_number=1, text="TITULO I ........... 3\nCLAUSULA 1 ........... 4"
    )
    pages = [toc] + [PageText(p.page_number + 1, p.text) for p in make_pages(6)]

    cleaned = clean_pages(pages)

    assert [p.page_number for p in cleaned] == [2, 3, 4, 5, 6, 7]
    assert "ORGANISMO" not in cleaned[0].text
    assert "Pagina" not in cleaned[0].text
    assert cleaned[0].text == "Clausula 1. objeto del contrato."


def test_chunk_pages_respects_size_and_tracks_pages():
    pages = [
        PageText(1, " ".join(f"alfa{i}" for i in range(100))),
        PageText(2, " ".join(f"beta{i}" for i in range(100))),
    ]

    chunks = chunk_pages(pages, chunk_chars=300, overlap_chars=50)

    assert all(len(c.text) <= 300 for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 2
    assert any(c.page_start == 1 and c.page_end == 2 for c in chunks)


def test_chunk_pages_overlaps_consecutive_chunks_and_covers_all_words():
    pages = [PageText(1, " ".join(f"w{i}" for i in range(200)))]

    chunks = chunk_pages(pages, chunk_chars=200, overlap_chars=40)

    first_words = chunks[0].text.split()
    second_words = chunks[1].text.split()
    assert second_words[0] in first_words
    all_words = {word for chunk in chunks for word in chunk.text.split()}
    assert all_words == {f"w{i}" for i in range(200)}


def test_chunk_pages_returns_one_chunk_for_short_text_and_none_for_empty():
    assert len(chunk_pages([PageText(3, "texto corto")])) == 1
    assert chunk_pages([]) == []
