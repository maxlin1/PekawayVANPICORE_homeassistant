"""Fahrt-Kalibrierung: Vorwärtsrichtung aus Anfahren und Bremsen bestimmen.

Ablauf für den Nutzer: Start drücken (Van steht), geradeaus anfahren,
kräftig bremsen bis zum Stillstand (gern 1 bis 3 Mal), dann Stop drücken.

Auswertung:
1. Beim Start wird 1 s im Stand gemittelt: das ist "oben" für diese Fahrt.
2. Während der Fahrt zählt nur der waagerechte Anteil der Messung
   (Beschleunigen zeigt nach vorne, Bremsen nach hinten).
3. Die Hauptachse dieser waagerechten Werte (Kovarianz) liefert die
   Fahrtrichtung als Linie. Ein Vorzeichen fehlt noch.
4. Das Vorzeichen kommt aus der Geschwindigkeit: Die Beschleunigung entlang
   der Achse wird aufintegriert. Fährt man vorwärts, ist die Geschwindigkeit
   überwiegend positiv. Damit gibt es keine 0°..90°-Mehrdeutigkeit wie bei
   Betragswerten.

Mehrere Anfahr-/Bremsvorgänge in einer Aufnahme machen das Ergebnis genauer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geometry import Vector, add, cross, dot, horizontal, norm, normalize, scale, sub

G = 9.80665
MIN_PEAK_G = 0.12  # mindestens so viel waagerechte Beschleunigung nötig
MIN_LINEARITY = 3.0  # Hauptachse muss deutlich dominieren
REST_SECONDS = 1.0
MAX_REST_SPREAD_G = 0.08


class CalibrationError(ValueError):
    """Fahrt war nicht auswertbar. Die Meldung ist für den Nutzer gedacht."""


@dataclass
class DriveRecorder:
    """Sammelt Messungen einer Fahrt. Messwerte in g, Zeit in Sekunden."""

    rest: list[Vector] = field(default_factory=list)
    samples: list[tuple[float, Vector]] = field(default_factory=list)
    _t0: float | None = None
    _up: Vector | None = None
    _e1: Vector | None = None
    _e2: Vector | None = None
    peak_g: float = 0.0

    def add(self, t: float, sample: Vector) -> None:
        if self._t0 is None:
            self._t0 = t
        if t - self._t0 < REST_SECONDS:
            self.rest.append(sample)
            return
        if self._up is None:
            if not self.rest:
                self.rest.append(sample)
            mean = scale(
                (
                    sum(v[0] for v in self.rest),
                    sum(v[1] for v in self.rest),
                    sum(v[2] for v in self.rest),
                ),
                1.0 / len(self.rest),
            )
            self._up = normalize(mean)
            # Zwei waagerechte Basisvektoren
            helper = (1.0, 0.0, 0.0) if abs(self._up[0]) < 0.9 else (0.0, 1.0, 0.0)
            self._e1 = normalize(horizontal(helper, self._up))
            self._e2 = cross(self._up, self._e1)
        h = horizontal(sample, self._up)
        self.peak_g = max(self.peak_g, norm(h))
        self.samples.append((t, h))

    @property
    def signal_g(self) -> float:
        """Aktuelle waagerechte Beschleunigung (für Live-Anzeige)."""
        if not self.samples:
            return 0.0
        return norm(self.samples[-1][1])

    def result(self) -> Vector:
        """Vorwärtsrichtung im Sensor-Koordinatensystem (Einheitsvektor)."""
        if self._up is None or len(self.samples) < 10:
            raise CalibrationError("Aufnahme zu kurz. Bitte anfahren und bremsen.")
        self._check_rest()
        if self.peak_g < MIN_PEAK_G:
            raise CalibrationError(
                f"Zu wenig Beschleunigung ({self.peak_g:.2f} g). "
                "Bitte zügiger anfahren und kräftiger bremsen."
            )
        assert self._e1 is not None and self._e2 is not None
        # 2D-Koordinaten in der Waagerechten
        raw = [(t, dot(h, self._e1), dot(h, self._e2)) for t, h in self.samples]
        # Start und Ende im Stand: die echte Beschleunigung mittelt sich zu 0.
        # Ein konstanter Rest (Gefälle, Ungenauigkeit von "oben") ist Messfehler
        # und wird abgezogen. Sonst kann er bei langer Fahrt das Vorzeichen kippen.
        n = len(raw)
        bx = sum(x for _, x, _ in raw) / n
        by = sum(y for _, _, y in raw) / n
        pts = [(t, x - bx, y - by) for t, x, y in raw]

        sxx = sum(x * x for _, x, _ in pts)
        syy = sum(y * y for _, _, y in pts)
        sxy = sum(x * y for _, x, y in pts)
        theta = 0.5 * math.atan2(2 * sxy, sxx - syy)
        ax, ay = math.cos(theta), math.sin(theta)
        major = sum((x * ax + y * ay) ** 2 for _, x, y in pts)
        minor = sum((-x * ay + y * ax) ** 2 for _, x, y in pts)
        if minor > 0 and major / minor < MIN_LINEARITY:
            raise CalibrationError(
                "Keine klare Fahrtrichtung erkannt. Bitte geradeaus fahren, "
                "nicht lenken."
            )

        # Vorzeichen 1: aufintegrierte Geschwindigkeit (vorwärts = überwiegend positiv)
        v = 0.0
        v_sum = 0.0
        prev_t = pts[0][0]
        for t, x, y in pts:
            dt = t - prev_t
            prev_t = t
            v += (x * ax + y * ay) * G * dt
            v_sum += v * dt
        sign_velocity = 1 if v_sum >= 0 else -1

        # Vorzeichen 2: das erste deutliche Ereignis ist das Anfahren
        threshold = max(0.06, 0.4 * self.peak_g)
        sign_first = 0
        for _, x, y in pts:
            a = x * ax + y * ay
            if abs(a) >= threshold:
                sign_first = 1 if a > 0 else -1
                break

        if sign_first and sign_first != sign_velocity:
            raise CalibrationError(
                "Fahrtrichtung nicht eindeutig. Bitte erst 1 Sekunde stehen, "
                "dann geradeaus anfahren, kräftig bis zum Stillstand bremsen "
                "und erst danach beenden."
            )
        if sign_velocity < 0:
            ax, ay = -ax, -ay
        return normalize(add(scale(self._e1, ax), scale(self._e2, ay)))

    def _check_rest(self) -> None:
        """Beim Start muss der Van stehen, sonst ist "oben" verfälscht."""
        if len(self.rest) < 3:
            return
        n = len(self.rest)
        mean = scale(
            (
                sum(v[0] for v in self.rest),
                sum(v[1] for v in self.rest),
                sum(v[2] for v in self.rest),
            ),
            1.0 / n,
        )
        spread = max(norm(sub(v, mean)) for v in self.rest)
        if spread > MAX_REST_SPREAD_G:
            raise CalibrationError(
                "Beim Start hat sich der Van schon bewegt. Bitte nach dem Drücken "
                "von Start 1 Sekunde stehen bleiben."
            )


def average_directions(directions: list[Vector]) -> tuple[Vector, float]:
    """Mittelt mehrere Vorwärtsrichtungen. Gibt Richtung und größte Abweichung (Grad)."""
    if not directions:
        raise CalibrationError("Keine Fahrt gespeichert")
    total: Vector = (0.0, 0.0, 0.0)
    for d in directions:
        total = add(total, normalize(d))
    mean = normalize(total)
    spread = max(
        math.degrees(math.acos(max(-1.0, min(1.0, dot(mean, normalize(d))))))
        for d in directions
    )
    return mean, spread
