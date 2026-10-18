from procurement.evaluation import (
    first_rank,
    first_rank_by_location,
    hit_rate,
    mean_reciprocal_rank,
)


def test_first_rank_is_one_based_and_none_when_missing():
    assert first_rank("b", ["a", "b", "c"]) == 2
    assert first_rank("z", ["a", "b", "c"]) is None
    assert first_rank("a", []) is None


def test_first_rank_by_location_matches_same_document_with_overlapping_pages():
    ranked = [("d1", 1, 2), ("d2", 5, 6), ("d2", 7, 8)]

    assert first_rank_by_location("d2", 6, 7, ranked) == 2
    assert first_rank_by_location("d2", 9, 9, ranked) is None
    assert first_rank_by_location("d3", 5, 6, ranked) is None


def test_hit_rate_counts_ranks_within_k():
    ranks = [1, 3, None, 6]

    assert hit_rate(ranks, 1) == 0.25
    assert hit_rate(ranks, 3) == 0.5
    assert hit_rate(ranks, 10) == 0.75
    assert hit_rate([], 5) == 0.0


def test_mean_reciprocal_rank_ignores_misses_but_counts_them_in_the_total():
    assert mean_reciprocal_rank([1, 2, None, None]) == (1 + 0.5) / 4
    assert mean_reciprocal_rank([]) == 0.0
