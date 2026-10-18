import hashlib
import time

import requests


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
