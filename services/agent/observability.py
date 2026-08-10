"""Small Prometheus metrics helpers for DialedIN.

The app does not need a full metrics dependency yet. These helpers keep the
instrumentation explicit and easy to test while still returning standard
Prometheus text exposition.
"""

from __future__ import annotations

from collections import defaultdict
from time import perf_counter
from typing import Callable

LabelSet = tuple[tuple[str, str], ...]

COUNTERS: dict[tuple[str, LabelSet], float] = defaultdict(float)
GAUGES: dict[tuple[str, LabelSet], float] = {}
HISTOGRAMS: dict[tuple[str, LabelSet], list[float]] = defaultdict(list)


def labels(**values: object) -> LabelSet:
    """Return a stable label tuple, skipping empty values."""
    return tuple(sorted((key, str(value)) for key, value in values.items() if value not in (None, "")))


def increment(name: str, amount: float = 1, **label_values: object) -> None:
    COUNTERS[(name, labels(**label_values))] += amount


def set_gauge(name: str, value: float, **label_values: object) -> None:
    GAUGES[(name, labels(**label_values))] = value


def observe(name: str, value: float | None, **label_values: object) -> None:
    if value is None:
        return
    HISTOGRAMS[(name, labels(**label_values))].append(float(value))


def time_call(name: str, fn: Callable[[], object], **label_values: object) -> object:
    start = perf_counter()
    try:
        return fn()
    finally:
        observe(name, perf_counter() - start, **label_values)


def reset() -> None:
    COUNTERS.clear()
    GAUGES.clear()
    HISTOGRAMS.clear()


def render_prometheus(extra_gauges: dict[str, int] | None = None) -> str:
    """Render metrics using Prometheus text exposition format."""
    lines: list[str] = []

    for name, value in sorted((extra_gauges or {}).items()):
        lines.append(f"# TYPE dialedin_{name} gauge")
        lines.append(f"dialedin_{name} {value}")

    for (name, label_set), value in sorted(COUNTERS.items()):
        lines.append(f"# TYPE {name} counter")
        lines.append(f"{name}{_label_text(label_set)} {value}")

    for (name, label_set), value in sorted(GAUGES.items()):
        lines.append(f"# TYPE {name} gauge")
        lines.append(f"{name}{_label_text(label_set)} {value}")

    for (name, label_set), observations in sorted(HISTOGRAMS.items()):
        count = len(observations)
        total = sum(observations)
        latest = observations[-1] if observations else 0
        lines.append(f"# TYPE {name}_count gauge")
        lines.append(f"{name}_count{_label_text(label_set)} {count}")
        lines.append(f"# TYPE {name}_sum gauge")
        lines.append(f"{name}_sum{_label_text(label_set)} {total}")
        lines.append(f"# TYPE {name}_latest gauge")
        lines.append(f"{name}_latest{_label_text(label_set)} {latest}")

    return "\n".join(lines) + "\n"


def _label_text(label_set: LabelSet) -> str:
    if not label_set:
        return ""
    pairs = ",".join(f'{key}="{_escape(value)}"' for key, value in label_set)
    return "{" + pairs + "}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
