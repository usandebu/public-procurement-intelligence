import hashlib
import io
import time
from dataclasses import dataclass

import requests
from pypdf import PdfReader

MIN_CHARS_PER_PAGE = 100


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str


@dataclass(frozen=True)
class Extraction:
    pages: list[PageText]
    total_chars: int
    needs_ocr: bool


def doc_id(uri: str, document_hash: str | None) -> str:
    return hashlib.sha256(f"{uri}|{document_hash or ''}".encode()).hexdigest()


def is_pdf(content: bytes) -> bool:
    return b"%PDF-" in content[:1024]


def download_pdf(uri: str, timeout: int = 60, retries: int = 3) -> bytes:
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(uri, timeout=timeout)
            response.raise_for_status()
            if not is_pdf(response.content):
                raise ValueError("response is not a PDF")
            return response.content
        except (requests.RequestException, ValueError):
            if attempt == retries:
                raise
            time.sleep(2 * attempt)


def extract_pages(content: bytes) -> Extraction:
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").replace("\x00", "").strip()
        pages.append(PageText(page_number=number, text=text))

    total_chars = sum(len(page.text) for page in pages)
    needs_ocr = not pages or total_chars / len(pages) < MIN_CHARS_PER_PAGE
    return Extraction(pages=pages, total_chars=total_chars, needs_ocr=needs_ocr)
