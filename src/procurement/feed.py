import time
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime

import requests

ATOM = "http://www.w3.org/2005/Atom"
TOMBSTONE = "http://purl.org/atompub/tombstones/1.0"
CPV_TAG_SUFFIX = "}ItemClassificationCode"

NAMESPACES = {
    "": ATOM,
    "cbc": "urn:dgpe:names:draft:codice:schema:xsd:CommonBasicComponents-2",
    "cac": "urn:dgpe:names:draft:codice:schema:xsd:CommonAggregateComponents-2",
    "cbc-place-ext": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonBasicComponents-2",
    "cac-place-ext": "urn:dgpe:names:draft:codice-place-ext:schema:xsd:CommonAggregateComponents-2",
    "at": TOMBSTONE,
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}


@dataclass(frozen=True)
class FeedEntry:
    entry_id: str
    updated: str
    updated_ts: datetime
    in_scope: bool
    raw_xml: str | None


@dataclass(frozen=True)
class Tombstone:
    ref: str
    when: str
    when_ts: datetime
    comment_type: str | None


@dataclass(frozen=True)
class FeedPage:
    entries: list[FeedEntry]
    tombstones: list[Tombstone]
    next_url: str | None

    @property
    def min_updated(self) -> datetime | None:
        return min((e.updated_ts for e in self.entries), default=None)

    @property
    def max_updated(self) -> datetime | None:
        return max((e.updated_ts for e in self.entries), default=None)

    def new_entries(self, watermark: datetime) -> list[FeedEntry]:
        return [e for e in self.entries if e.in_scope and e.updated_ts > watermark]

    def new_tombstones(self, watermark: datetime) -> list[Tombstone]:
        return [t for t in self.tombstones if t.when_ts > watermark]


def register_namespaces() -> None:
    for prefix, uri in NAMESPACES.items():
        ET.register_namespace(prefix, uri)


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def has_cpv_prefix(entry: ET.Element, prefix: str) -> bool:
    return any(
        el.tag.endswith(CPV_TAG_SUFFIX) and (el.text or "").startswith(prefix)
        for el in entry.iter()
    )


def parse_page(content: bytes, cpv_prefix: str) -> FeedPage:
    register_namespaces()
    root = ET.fromstring(content)

    entries = []
    for entry in root.findall(f"{{{ATOM}}}entry"):
        updated = entry.find(f"{{{ATOM}}}updated").text
        in_scope = has_cpv_prefix(entry, cpv_prefix)
        entries.append(
            FeedEntry(
                entry_id=entry.find(f"{{{ATOM}}}id").text,
                updated=updated,
                updated_ts=parse_timestamp(updated),
                in_scope=in_scope,
                raw_xml=ET.tostring(entry, encoding="unicode") if in_scope else None,
            )
        )

    tombstones = []
    for deleted in root.findall(f"{{{TOMBSTONE}}}deleted-entry"):
        comment = deleted.find(f"{{{TOMBSTONE}}}comment")
        tombstones.append(
            Tombstone(
                ref=deleted.get("ref"),
                when=deleted.get("when"),
                when_ts=parse_timestamp(deleted.get("when")),
                comment_type=comment.get("type") if comment is not None else None,
            )
        )

    next_url = None
    for link in root.findall(f"{{{ATOM}}}link"):
        if link.get("rel") == "next":
            next_url = link.get("href")

    return FeedPage(entries=entries, tombstones=tombstones, next_url=next_url)


def fetch_content(url: str, timeout: int = 120, retries: int = 3) -> bytes:
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return response.content
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(5 * attempt)


def collect_since(
    start_url: str,
    watermark: datetime,
    cpv_prefix: str,
    fetch: Callable[[str], bytes] = fetch_content,
    max_pages: int | None = None,
) -> Iterator[FeedPage]:
    url = start_url
    pages = 0
    while url is not None and (max_pages is None or pages < max_pages):
        page = parse_page(fetch(url), cpv_prefix)
        yield page
        pages += 1
        oldest = page.min_updated
        if oldest is not None and oldest <= watermark:
            break
        url = page.next_url
