"""Digital timing analysis on raw samples; no display downsampling or analog claims."""

import math
import statistics
from bisect import bisect_right


def summary(values, unit="s"):
    values = list(values)
    if not values:
        return {"count": 0, "unit": unit, "quality": "insufficient_data"}
    ordered = sorted(values)

    def percentile(p):
        x = (len(ordered) - 1) * p
        i = int(x)
        return ordered[i] + (ordered[min(i + 1, len(ordered) - 1)] - ordered[i]) * (
            x - i
        )

    return {
        "count": len(values),
        "unit": unit,
        "min": min(values),
        "max": max(values),
        "mean": statistics.fmean(values),
        "stddev": statistics.pstdev(values),
        "p50": percentile(0.5),
        "p95": percentile(0.95),
        "p99": percentile(0.99),
    }


def channel(samples, hz, bit=0):
    if hz <= 0 or not math.isfinite(hz) or not 0 <= bit < 16:
        raise ValueError("Invalid rate/channel")
    levels = [(v >> bit) & 1 for v in samples]
    edges = [i for i in range(1, len(levels)) if levels[i] != levels[i - 1]]
    rising = [i for i in edges if levels[i]]
    periods = [(b - a) / hz for a, b in zip(rising, rising[1:])]
    widths = {0: [], 1: []}
    duties = []
    # Only complete edge-to-edge pulses. Never treat a clipped endpoint as width.
    for a, b in zip(edges, edges[1:]):
        widths[levels[a]].append((b - a) / hz)
    falling = [i for i in edges if not levels[i]]
    for a, b in zip(rising, rising[1:]):
        position = bisect_right(falling, a)
        if position < len(falling) and falling[position] < b:
            duties.append((falling[position] - a) / (b - a) * 100)
    period = summary(periods)
    result = {
        "bit": bit,
        "sample_count": len(samples),
        "sample_hz": hz,
        "edges": len(edges),
        "resolution_s": 1 / hz,
        "two_edge_conservative_quantization_s": 2 / hz,
        "period": period,
        "high_width": summary(widths[1]),
        "low_width": summary(widths[0]),
        "duty": summary(duties, "%"),
        "calibration": "uncalibrated shared MCU clock",
    }
    if periods:
        result["frequency_hz"] = 1 / period["mean"]
    return result


def cursors(index_a, index_b, hz):
    if hz <= 0:
        raise ValueError("Invalid rate")
    delta = (index_b - index_a) / hz
    return {
        "sample_a": index_a,
        "sample_b": index_b,
        "delta_samples": index_b - index_a,
        "delta_s": delta,
        "reciprocal_hz": 1 / abs(delta) if delta else None,
    }
