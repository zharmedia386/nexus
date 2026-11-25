import random
from statistics import fmean

BOOTSTRAP_N = 2000
BOOTSTRAP_SEED = 42


def _percentile_bounds(means: list[float], level: float) -> tuple[float, float]:
    means.sort()
    tail = (1 - level) / 2
    last = len(means) - 1
    return means[int(tail * last)], means[round((1 - tail) * last)]


def bootstrap_ci(
    values: list[float], *, n: int = BOOTSTRAP_N, seed: int = BOOTSTRAP_SEED, level: float = 0.95
) -> tuple[float, float]:
    rng = random.Random(seed)
    size = len(values)
    means = [fmean(rng.choices(values, k=size)) for _ in range(n)]
    return _percentile_bounds(means, level)


def paired_diff_ci(
    a: dict[str, float],
    b: dict[str, float],
    *,
    n: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
    level: float = 0.95,
) -> tuple[float, float, float]:
    shared = sorted(a.keys() & b.keys())
    diffs = [a[key] - b[key] for key in shared]
    low, high = bootstrap_ci(diffs, n=n, seed=seed, level=level)
    return fmean(diffs), low, high
