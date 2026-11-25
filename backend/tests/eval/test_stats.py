from statistics import fmean

from nexus.eval.stats import bootstrap_ci, paired_diff_ci

VALUES = [0.0, 1.0, 1.0, 0.5, 1.0, 0.0, 1.0, 0.5]


def test_ci_contains_mean():
    low, high = bootstrap_ci(VALUES)
    assert low <= fmean(VALUES) <= high


def test_ci_deterministic():
    assert bootstrap_ci(VALUES, seed=7) == bootstrap_ci(VALUES, seed=7)


def test_ci_overlaps_zero_flagged_not_significant():
    a = {"q1": 1.0, "q2": 0.0, "q3": 1.0, "q4": 0.0}
    b = {"q1": 0.0, "q2": 1.0, "q3": 0.0, "q4": 1.0}
    _, low, high = paired_diff_ci(a, b)
    assert not (low > 0 or high < 0)
    _, low, high = paired_diff_ci({k: 1.0 for k in a}, {k: 0.0 for k in a})
    assert low > 0


def test_paired_diff_uses_shared_ids_only():
    a = {"q1": 1.0, "q2": 1.0, "only_a": 0.0}
    b = {"q1": 0.0, "q2": 0.0, "only_b": 1.0}
    mean, _, _ = paired_diff_ci(a, b)
    assert mean == 1.0
