"""
solver.py — Run the scheduler and report what it did.

One method does the work (see `clustered_dp`): partition the locations into
regions, then solve exactly — inside each region, and across them.  A production
small enough for the exact solver has nothing to partition, so the method runs
with a single region and returns a proven global optimum; plain Held-Karp is the
degenerate case of the same method, not a separate one.

This module is the thin layer around it that times the run, records which case
it landed in, and keeps the guarantee honest in the reported output.

The one thing it adds is a fallback.  Whether the partition fits inside the
solver's limits depends on how the locations cluster, not just on how many there
are — `region_cap * MAX_REGIONS` bounds the capacity at 130 with the defaults,
but regions rarely pack to the cap exactly, so counts well below that bound can
still fail (uniformly scattered points first fail around 40 and always fail by
80).  Predicting
from the location count alone was wrong and crashed in that range, so the
partition is attempted and the geographic layer's greedy draft catches a
`PartitionError` if no partition can be formed.  Any other `ValueError` is a bad
argument and is left to propagate.  None of the productions studied here comes
close to that size.
"""

from __future__ import annotations

import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "liu"))

from dataclasses import dataclass
from typing import List, Optional

from greedy import greedy_nearest_neighbor                # geographic layer

from clustered_dp import (DEFAULT_REGION_CAP, PartitionError,
                          clustered_schedule)
from schedule_dp import EXACT_LIMIT, INF, ScheduleResult

MODES = ("scheduled", "draft")


@dataclass
class SolveReport:
    """The schedule plus how it was produced and how long it took."""
    result: ScheduleResult
    mode: str
    regions: int
    guarantee: str
    elapsed_ms: float

    def __str__(self) -> str:
        return (f"[{self.mode}, {self.regions} region"
                f"{'' if self.regions == 1 else 's'}] "
                f"cost={self.result.total_cost:.2f} "
                f"in {self.elapsed_ms:.1f} ms — {self.guarantee}")


def _greedy_draft(cost: List[List[float]], start: int,
                  return_to_base: bool) -> ScheduleResult:
    """Wrap the geographic layer's greedy draft in this layer's result type."""
    draft = greedy_nearest_neighbor(cost, start=start)
    order, legs, total = list(draft.order), list(draft.cost_breakdown), \
        draft.total_cost
    if return_to_base and len(order) > 1:
        back = cost[order[-1]][start]
        if back != INF:
            legs.append(back)
            total += back
            order.append(start)
    return ScheduleResult(order=order, total_cost=total, leg_costs=legs,
                          n_locations=len(cost), closed=return_to_base)


def solve(cost: List[List[float]],
          start: int = 0,
          return_to_base: bool = False,
          force_mode: Optional[str] = None,
          region_cap: int = DEFAULT_REGION_CAP) -> SolveReport:
    """
    Produce a shooting order and report how it was arrived at.

    Args:
        cost          : n x n all-pairs cost matrix from the geographic layer.
        start         : Base / first location.
        return_to_base: If True the crew returns to `start` at wrap.
        force_mode    : 'scheduled' or 'draft', to compare the two directly.
                        Forcing 'scheduled' lets a failed partition raise rather
                        than fall back silently.
        region_cap    : Maximum locations per region.  Has no effect when the
                        whole production already fits the exact solver, since
                        there is then nothing to partition.

    Returns:
        SolveReport with the schedule, the number of regions used, the guarantee
        that holds for it, and the wall-clock time.

    Raises:
        ValueError: If `force_mode` is not a known mode, if an argument is
                    invalid, or if no schedule reaching every location exists
                    because the cost matrix is disconnected.
    """
    if force_mode is not None and force_mode not in MODES:
        raise ValueError(f"Unknown mode {force_mode!r}; choose from {MODES}.")

    n = len(cost)
    t0 = time.perf_counter()

    if force_mode != "draft":
        try:
            res = clustered_schedule(cost, start=start, region_cap=region_cap,
                                     return_to_base=return_to_base)
        except PartitionError:
            # Too many locations to partition within the solver's limits.
            # Every other ValueError is a bad argument and must not be swallowed:
            # letting it through as a fallback produces a confusing failure deep
            # inside the geographic layer instead of the message that names the
            # offending argument.
            if force_mode is not None:
                raise
        else:
            if res.total_cost == INF:
                # Some location is unreachable from the base, so no schedule
                # covering all of them exists.  Reporting this as "optimal"
                # would be a guarantee about a schedule that does not exist.
                raise ValueError(
                    "No schedule visits every location: the cost matrix is "
                    "disconnected from the starting location.")
            regions = len(res.regions)
            guarantee = ("globally optimal (proven)" if regions == 1 else
                         "optimal within and between regions; "
                         "the partition is the only approximation")
            return SolveReport(result=res, mode="scheduled", regions=regions,
                               guarantee=guarantee,
                               elapsed_ms=(time.perf_counter() - t0) * 1000.0)

    res = _greedy_draft(cost, start, return_to_base)
    return SolveReport(result=res, mode="draft", regions=0,
                       guarantee="fast draft, no optimality guarantee",
                       elapsed_ms=(time.perf_counter() - t0) * 1000.0)
