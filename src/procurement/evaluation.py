def first_rank(target_chunk_id: str, ranked_chunk_ids: list[str]) -> int | None:
    for position, chunk_id in enumerate(ranked_chunk_ids, start=1):
        if chunk_id == target_chunk_id:
            return position
    return None


def first_rank_by_location(
    target_doc_id: str,
    target_page_start: int,
    target_page_end: int,
    ranked: list[tuple[str, int, int]],
) -> int | None:
    for position, (doc_id, page_start, page_end) in enumerate(ranked, start=1):
        if (
            doc_id == target_doc_id
            and page_start <= target_page_end
            and page_end >= target_page_start
        ):
            return position
    return None


def hit_rate(ranks: list[int | None], k: int) -> float:
    if not ranks:
        return 0.0
    return sum(1 for rank in ranks if rank is not None and rank <= k) / len(ranks)


def mean_reciprocal_rank(ranks: list[int | None]) -> float:
    if not ranks:
        return 0.0
    return sum(1 / rank for rank in ranks if rank is not None) / len(ranks)
