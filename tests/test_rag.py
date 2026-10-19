from procurement.rag import (
    NO_ANSWER,
    build_messages,
    cited_numbers,
    cited_sources,
    extract_text,
    format_context,
    is_no_answer,
    normalize_citations,
    parse_sources,
)

ROWS = [
    [
        "c1",
        "EXP-1",
        "Servicio de soporte",
        "Organismo A",
        "legal",
        "PCAP.pdf",
        5.0,
        6.0,
        "Texto uno",
        "https://x/1",
    ],
    [
        "c2",
        "EXP-1",
        "Servicio de soporte",
        "Organismo A",
        "technical",
        "PPT.pdf",
        3.0,
        3.0,
        "Texto dos",
        "https://x/1",
    ],
]


def test_parse_sources_numbers_from_one_and_casts_pages_to_int():
    sources = parse_sources(ROWS)

    assert [s.number for s in sources] == [1, 2]
    assert sources[0].page_start == 5 and isinstance(sources[0].page_start, int)
    assert sources[0].pages == "pp. 5-6"
    assert sources[1].pages == "p. 3"
    assert sources[0].label == "EXP-1 · PCAP · pp. 5-6"
    assert sources[1].label == "EXP-1 · PPT · p. 3"


def test_format_context_and_messages_include_numbered_fragments():
    sources = parse_sources(ROWS)

    context = format_context(sources)
    messages = build_messages("¿Plazo?", sources)

    assert "[1] (EXP-1 · PCAP · pp. 5-6)\nTexto uno" in context
    assert "[2] (EXP-1 · PPT · p. 3)\nTexto dos" in context
    assert messages[0]["role"] == "system"
    assert NO_ANSWER in messages[0]["content"]
    assert messages[1]["content"].startswith("Pregunta: ¿Plazo?")


def test_cited_numbers_are_unique_and_ordered_by_first_appearance():
    assert cited_numbers("Es 12 meses [2]. Prorrogable [1][2].") == [2, 1]
    assert cited_numbers("Sin citas.") == []


def test_cited_sources_ignores_numbers_that_do_not_exist():
    sources = parse_sources(ROWS)

    selected = cited_sources("Dato [2] y otro [9].", sources)

    assert [s.number for s in selected] == [2]


def test_extract_text_handles_strings_and_block_lists():
    assert extract_text("  hola ") == "hola"
    blocks = [
        {"type": "reasoning", "summary": "..."},
        {"type": "text", "text": "Respuesta final [1]"},
    ]
    assert extract_text(blocks) == "Respuesta final [1]"


def test_is_no_answer_detects_the_refusal_phrase():
    assert is_no_answer(NO_ANSWER)
    assert is_no_answer("  " + NO_ANSWER.lower())
    assert not is_no_answer("El plazo es de 12 meses [1].")


def test_normalize_citations_unifies_the_variants_models_emit():
    fullwidth = "【1】"
    with_lines = "[2†L1-L3]"
    text = f"Plazo de 12 meses {fullwidth}. Prorrogable {with_lines} y [3]."

    assert normalize_citations(text) == "Plazo de 12 meses [1]. Prorrogable [2] y [3]."


def test_cited_numbers_recognises_every_citation_style():
    text = "A 【1】, B [2†L4-L9], C [3]."

    assert cited_numbers(text) == [1, 2, 3]
