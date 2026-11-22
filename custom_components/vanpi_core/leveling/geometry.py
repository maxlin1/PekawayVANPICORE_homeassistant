"""Rechenkern der Nivellierung (ohne Home-Assistant-Abhängigkeit).

Koordinaten im Fahrzeug: x = vorne, y = rechts, z = oben.
Vorzeichen: Neigung längs (pitch) > 0 heißt Front höher,
Neigung quer (roll) > 0 heißt rechte Seite höher.

Ein Beschleunigungssensor in Ruhe misst die Gegenkraft zur Schwerkraft, also
einen Vektor, der nach oben zeigt (ca. 1 g). Aus diesem "Oben"-Vektor im
Sensor-Koordinatensystem und einer Vorwärtsrichtung wird ein festes
rechtshändiges Achsensystem gebaut. Damit funktioniert jede Einbaulage.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations, product

Vector = tuple[float, float, float]

AXIS_VECTORS: dict[str, Vector] = {
    "+x": (1.0, 0.0, 0.0),
    "-x": (-1.0, 0.0, 0.0),
    "+y": (0.0, 1.0, 0.0),
    "-y": (0.0, -1.0, 0.0),
    "+z": (0.0, 0.0, 1.0),
    "-z": (0.0, 0.0, -1.0),
}

WHEELS = ("vl", "vr", "hl", "hr")  # vorne links, vorne rechts, hinten links, hinten rechts
WHEEL_NAMES = {
    "vl": "Vorne links",
    "vr": "Vorne rechts",
    "hl": "Hinten links",
    "hr": "Hinten rechts",
}


class OrientationError(ValueError):
    """Achsen lassen sich nicht bestimmen (z. B. Vorwärtsachse senkrecht)."""


def dot(a: Vector, b: Vector) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vector, b: Vector) -> Vector:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm(a: Vector) -> float:
    return math.sqrt(dot(a, a))


def scale(a: Vector, s: float) -> Vector:
    return (a[0] * s, a[1] * s, a[2] * s)


def sub(a: Vector, b: Vector) -> Vector:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a: Vector, b: Vector) -> Vector:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def normalize(a: Vector) -> Vector:
    n = norm(a)
    if n < 1e-9:
        raise OrientationError("Nullvektor")
    return scale(a, 1.0 / n)


def horizontal(v: Vector, up: Vector) -> Vector:
    """Anteil von v senkrecht zu up (up muss Einheitsvektor sein)."""
    return sub(v, scale(up, dot(v, up)))


@dataclass(frozen=True)
class Orientation:
    """Fahrzeugachsen, ausgedrückt im Sensor-Koordinatensystem."""

    forward: Vector
    right: Vector
    up: Vector

    @classmethod
    def from_vectors(cls, up: Vector, forward_hint: Vector) -> Orientation:
        """Baut die Achsen aus "oben" (Messung auf ebenem Boden) und einer Vorwärtsrichtung.

        forward_hint muss nicht exakt waagerecht sein, er wird auf die
        Waagerechte projiziert.
        """
        u = normalize(up)
        f_h = horizontal(forward_hint, u)
        if norm(f_h) < 0.2 * norm(forward_hint):
            raise OrientationError(
                "Vorwärtsachse zeigt fast senkrecht, bitte andere Achse wählen"
            )
        f = normalize(f_h)
        r = cross(f, u)  # rechtshändig: vorne x oben = rechts
        return cls(forward=f, right=r, up=u)

    def angles(self, measured: Vector) -> tuple[float, float]:
        """Neigung längs und quer in Grad aus einem gemessenen Beschleunigungsvektor."""
        a_f = dot(measured, self.forward)
        a_r = dot(measured, self.right)
        a_u = dot(measured, self.up)
        pitch = math.degrees(math.atan2(a_f, math.hypot(a_r, a_u)))
        roll = math.degrees(math.atan2(a_r, math.hypot(a_f, a_u)))
        return pitch, roll


@dataclass(frozen=True)
class Vehicle:
    """Fahrzeug- und Blockdaten. Längen in cm."""

    wheelbase: float
    track: float
    block_height: float
    stacks: int  # wie viele Räder gleichzeitig Blöcke bekommen können
    blocks_per_stack: int

    def wheel_positions(self) -> dict[str, tuple[float, float]]:
        lx, ly = self.wheelbase / 2.0, self.track / 2.0
        return {"vl": (lx, -ly), "vr": (lx, ly), "hl": (-lx, -ly), "hr": (-lx, ly)}


def wheel_heights(vehicle: Vehicle, pitch: float, roll: float) -> dict[str, float]:
    """Höhe jedes Radaufstandspunkts relativ zur Fahrzeugmitte in cm."""
    tp = math.tan(math.radians(pitch))
    tr = math.tan(math.radians(roll))
    return {w: x * tp + y * tr for w, (x, y) in vehicle.wheel_positions().items()}


def lift_per_wheel(vehicle: Vehicle, pitch: float, roll: float) -> dict[str, float]:
    """Nötige Anhebung je Rad, bezogen auf das höchste Rad (cm, >= 0)."""
    h = wheel_heights(vehicle, pitch, roll)
    top = max(h.values())
    return {w: top - v for w, v in h.items()}


def plane_tilt(vehicle: Vehicle, heights: dict[str, float]) -> tuple[float, float]:
    """Neigung (Grad) der Ausgleichsebene durch die vier Radpunkte.

    Bei symmetrischer Radanordnung ist die Kleinste-Quadrate-Ebene einfach:
    Steigung längs = (Mittel vorne - Mittel hinten) / Radstand, quer analog.
    """
    front = (heights["vl"] + heights["vr"]) / 2.0
    rear = (heights["hl"] + heights["hr"]) / 2.0
    right = (heights["vr"] + heights["hr"]) / 2.0
    left = (heights["vl"] + heights["hl"]) / 2.0
    pitch = math.degrees(math.atan((front - rear) / vehicle.wheelbase))
    roll = math.degrees(math.atan((right - left) / vehicle.track))
    return pitch, roll


@dataclass(frozen=True)
class BlockPlan:
    blocks: dict[str, int]
    residual_pitch: float
    residual_roll: float

    @property
    def residual(self) -> float:
        return math.hypot(self.residual_pitch, self.residual_roll)

    @property
    def total_blocks(self) -> int:
        return sum(self.blocks.values())

    def text(self, block_height: float) -> str:
        parts = [
            f"{WHEEL_NAMES[w]}: {n} {'Block' if n == 1 else 'Blöcke'} ({n * block_height:.1f} cm)"
            for w, n in self.blocks.items()
            if n > 0
        ]
        if not parts:
            return "Keine Blöcke nötig"
        return ", ".join(parts)


def best_block_plan(vehicle: Vehicle, pitch: float, roll: float) -> BlockPlan:
    """Sucht die Blockverteilung mit der kleinsten Restneigung.

    Probiert jede Auswahl von bis zu ``stacks`` Rädern mit 0..blocks_per_stack
    Blöcken. Bei gleicher Restneigung (Toleranz 0,01°) gewinnt die Variante
    mit weniger Blöcken.
    """
    base = wheel_heights(vehicle, pitch, roll)
    stacks = max(0, min(vehicle.stacks, len(WHEELS)))
    best: BlockPlan | None = None
    best_key: tuple[float, int] | None = None
    for wheels in combinations(WHEELS, stacks):
        for counts in product(range(vehicle.blocks_per_stack + 1), repeat=stacks):
            blocks = {w: 0 for w in WHEELS}
            for w, n in zip(wheels, counts):
                blocks[w] = n
            heights = {
                w: base[w] + blocks[w] * vehicle.block_height for w in WHEELS
            }
            rp, rr = plane_tilt(vehicle, heights)
            plan = BlockPlan(
                blocks={w: n for w, n in blocks.items()},
                residual_pitch=rp,
                residual_roll=rr,
            )
            key = (round(plan.residual, 2), plan.total_blocks)
            if best_key is None or key < best_key:
                best, best_key = plan, key
    assert best is not None
    return best
