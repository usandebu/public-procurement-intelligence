from dataclasses import dataclass


@dataclass(frozen=True)
class PageText:
    page_number: int
    text: str
