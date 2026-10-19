import re
from dataclasses import dataclass

NO_ANSWER = "No consta en los documentos consultados."

KIND_LABELS = {
    "legal": "PCAP",
    "technical": "PPT",
}

SYSTEM_PROMPT = (
    "Eres un asistente que responde preguntas sobre pliegos de contratación pública españoles. "
    "Usa SOLO los fragmentos numerados del contexto. "
    "Cita cada afirmación con el número de su fragmento entre corchetes normales, solo el número, por ejemplo [1]. "
    f'Si los fragmentos no contienen la respuesta, responde exactamente: "{NO_ANSWER}" '
    "No inventes datos, importes, plazos ni fechas. "
    "No añadas conclusiones, recomendaciones ni consejos. "
    "Responde en español, en un máximo de seis frases."
)

CITATION = re.compile(r"[\[【](\d+)(?:†[^\]】]*)?[\]】]")

SEARCH_COLUMNS = [
    "chunk_id",
    "folder_id",
    "tender_title",
    "organ_name",
    "kind",
    "file_name",
    "page_start",
    "page_end",
    "text",
    "detail_url",
]


@dataclass(frozen=True)
class Source:
    number: int
    chunk_id: str
    folder_id: str
    tender_title: str
    organ_name: str
    kind: str
    file_name: str
    page_start: int
    page_end: int
    text: str
    detail_url: str

    @property
    def pages(self) -> str:
        if self.page_start == self.page_end:
            return f"p. {self.page_start}"
        return f"pp. {self.page_start}-{self.page_end}"

    @property
    def label(self) -> str:
        document = KIND_LABELS.get(self.kind, self.kind)
        return f"{self.folder_id} · {document} · {self.pages}"


def parse_sources(data_array: list[list]) -> list[Source]:
    sources = []
    for number, row in enumerate(data_array, start=1):
        values = dict(zip(SEARCH_COLUMNS, row, strict=False))
        sources.append(
            Source(
                number=number,
                chunk_id=values["chunk_id"],
                folder_id=values["folder_id"],
                tender_title=values["tender_title"],
                organ_name=values["organ_name"],
                kind=values["kind"],
                file_name=values["file_name"],
                page_start=int(values["page_start"]),
                page_end=int(values["page_end"]),
                text=values["text"],
                detail_url=values["detail_url"],
            )
        )
    return sources


def format_context(sources: list[Source]) -> str:
    return "\n\n".join(f"[{s.number}] ({s.label})\n{s.text}" for s in sources)


def build_messages(question: str, sources: list[Source]) -> list[dict]:
    user = f"Pregunta: {question}\n\nFragmentos:\n{format_context(sources)}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def extract_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "\n".join(parts).strip()
    return str(content).strip()


def normalize_citations(text: str) -> str:
    return CITATION.sub(lambda match: f"[{match.group(1)}]", text)


def cited_numbers(answer: str) -> list[int]:
    seen = []
    for match in CITATION.findall(answer):
        number = int(match)
        if number not in seen:
            seen.append(number)
    return seen


def cited_sources(answer: str, sources: list[Source]) -> list[Source]:
    by_number = {s.number: s for s in sources}
    return [by_number[n] for n in cited_numbers(answer) if n in by_number]


def is_no_answer(answer: str) -> bool:
    return NO_ANSWER.lower() in answer.lower()


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list[Source]
    cited: list[Source]

    @property
    def is_refusal(self) -> bool:
        return is_no_answer(self.text)


def answer_question(question, search, complete, entry_id=None, num_results=5) -> Answer:
    sources = parse_sources(search(question, entry_id, num_results))
    if not sources:
        return Answer(text=NO_ANSWER, sources=[], cited=[])
    text = normalize_citations(
        extract_text(complete(build_messages(question, sources)))
    )
    return Answer(text=text, sources=sources, cited=cited_sources(text, sources))
