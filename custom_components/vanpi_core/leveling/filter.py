"""Glättung der Beschleunigungswerte.

Ziel: ruhige Anzeige, wenn der Van steht, aber schnelle Reaktion, wenn er
auf die Blöcke rollt. Vorbild sind die ESPHome-Filter aus dem SmartyVan-Projekt
(20 Hz, kurzer gleitender Mittelwert gegen Ausreißer, längerer für die Anzeige).

Aufbau:
1. Median über die letzten 5 Messungen je Achse: entfernt einzelne Ausreißer
   (Erschütterung, Tür zu), ohne zu verzögern.
2. Zwei exponentielle Mittelwerte auf dem Vektor: ein schneller und ein ruhiger.
   Weicht der schnelle um mehr als ``fast_threshold_deg`` vom ruhigen ab,
   wird der ruhige auf den schnellen nachgezogen. So zittert nichts im
   Stand, und echte Lageänderungen kommen nach etwa einer halben Sekunde an.

Es wird der Vektor geglättet, nicht der Winkel. Das vermeidet Sprünge bei
der Winkelberechnung und funktioniert für jede Einbaulage gleich.
"""

from __future__ import annotations

import math
from collections import deque
from statistics import median

from .geometry import Vector, dot, norm

DEFAULT_SLOW_TAU = 1.5  # Sekunden, Anzeige im Stand
DEFAULT_FAST_TAU = 0.25  # Sekunden, Reaktion bei Bewegung
DEFAULT_FAST_THRESHOLD_DEG = 0.5
MEDIAN_WINDOW = 5


def _angle_between(a: Vector, b: Vector) -> float:
    na, nb = norm(a), norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    c = max(-1.0, min(1.0, dot(a, b) / (na * nb)))
    return math.degrees(math.acos(c))


def _ema(prev: Vector, new: Vector, dt: float, tau: float) -> Vector:
    alpha = 1.0 - math.exp(-dt / tau) if tau > 0 else 1.0
    return (
        prev[0] + alpha * (new[0] - prev[0]),
        prev[1] + alpha * (new[1] - prev[1]),
        prev[2] + alpha * (new[2] - prev[2]),
    )


class AdaptiveVectorFilter:
    """Median plus adaptiver exponentieller Mittelwert für 3D-Vektoren."""

    def __init__(
        self,
        slow_tau: float = DEFAULT_SLOW_TAU,
        fast_tau: float = DEFAULT_FAST_TAU,
        fast_threshold_deg: float = DEFAULT_FAST_THRESHOLD_DEG,
    ) -> None:
        self.slow_tau = slow_tau
        self.fast_tau = fast_tau
        self.fast_threshold_deg = fast_threshold_deg
        self.reset()

    def reset(self) -> None:
        self._window: deque[Vector] = deque(maxlen=MEDIAN_WINDOW)
        self._fast: Vector | None = None
        self._slow: Vector | None = None

    @property
    def value(self) -> Vector | None:
        return self._slow

    def update(self, sample: Vector, dt: float) -> Vector:
        self._window.append(sample)
        med: Vector = (
            median(v[0] for v in self._window),
            median(v[1] for v in self._window),
            median(v[2] for v in self._window),
        )
        if self._fast is None or self._slow is None:
            self._fast = self._slow = med
            return med

        self._fast = _ema(self._fast, med, dt, self.fast_tau)
        if _angle_between(self._fast, self._slow) > self.fast_threshold_deg:
            # Echte Bewegung: ruhigen Wert sofort nachziehen
            self._slow = self._fast
        else:
            self._slow = _ema(self._slow, med, dt, self.slow_tau)
        return self._slow


class Debounce:
    """Zustand erst übernehmen, wenn er ``delay`` Sekunden stabil ist."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.state: bool | None = None
        self._candidate: bool | None = None
        self._since = 0.0

    def update(self, value: bool, now: float) -> bool | None:
        if self.state is None:
            self.state = value
            self._candidate = value
            return self.state
        if value != self._candidate:
            self._candidate = value
            self._since = now
        elif value != self.state and now - self._since >= self.delay:
            self.state = value
        return self.state
