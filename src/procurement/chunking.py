import re
from collections import Counter
from dataclasses import dataclass

from procurement.pages import PageText

MIN_PAGES_FOR_HEADER_DETECTION = 4
HEADER_PAGE_SHARE = 0.4
TOC_LINE_SHARE = 0.4
TOC_LINE = re.compile(r"\.{4,}\s*\d+\s*$")
DIGITS = re.compile(r"\d+")
SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class Chunk:
    chunk_index: int
    page_start: int
    page_end: int
    text: str


def _normalize_line(line: str) -> str:
    return DIGITS.sub("#", SPACES.sub(" ", line.strip()))


def repeated_lines(pages: list[PageText]) -> set[str]:
    if len(pages) < MIN_PAGES_FOR_HEADER_DETECTION:
        return set()
    counts = Counter()
    for page in pages:
        counts.update(
            {_normalize_line(line) for line in page.text.splitlines() if line.strip()}
        )
    threshold = HEADER_PAGE_SHARE * len(pages)
    return {line for line, count in counts.items() if count >= threshold}


def is_table_of_contents(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        return False
    leaders = sum(1 for line in lines if TOC_LINE.search(line))
    return leaders / len(lines) >= TOC_LINE_SHARE


def clean_pages(pages: list[PageText]) -> list[PageText]:
    repeated = repeated_lines(pages)
    cleaned = []
    for page in pages:
        if is_table_of_contents(page.text):
            continue
        lines = [
            SPACES.sub(" ", line.strip())
            for line in page.text.splitlines()
            if line.strip() and _normalize_line(line) not in repeated
        ]
        text = " ".join(lines)
        if text:
            cleaned.append(PageText(page_number=page.page_number, text=text))
    return cleaned


def chunk_pages(
    pages: list[PageText], chunk_chars: int = 1000, overlap_chars: int = 150
) -> list[Chunk]:
    words = [(word, page.page_number) for page in pages for word in page.text.split()]
    chunks = []
    start = 0
    while start < len(words):
        end = start
        size = 0
        while end < len(words) and size + len(words[end][0]) + 1 <= chunk_chars:
            size += len(words[end][0]) + 1
            end += 1
        end = max(end, start + 1)
        chunks.append(
            Chunk(
                chunk_index=len(chunks),
                page_start=words[start][1],
                page_end=words[end - 1][1],
                text=" ".join(word for word, _ in words[start:end]),
            )
        )
        if end >= len(words):
            break
        back = end
        overlap = 0
        while back > start + 1 and overlap < overlap_chars:
            back -= 1
            overlap += len(words[back][0]) + 1
        start = max(back, start + 1)
    return chunks
