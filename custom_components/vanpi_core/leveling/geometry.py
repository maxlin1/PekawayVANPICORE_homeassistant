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
from dataclasses import dataclass, field
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
        # Mehr als 45° geneigt: die Achse ist eher "oben/unten" als "vorne".
        # Eine Projektion wäre dann reiner Zufall und kann vorne/hinten vertauschen.
        if norm(f_h) < 0.7 * norm(forward_hint):
            raise OrientationError(
                "Die eingestellte Vorwärtsachse zeigt eher nach oben oder unten. "
                "Bitte unter Konfigurieren eine andere Achse oder "
                "'Aus Fahrt-Kalibrierung' wählen."
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
    # Luftfederung hinten: jede Seite um bis zu air_up cm heben, air_down cm senken
    air_up: float = 0.0
    air_down: float = 0.0
    # Kopf beim Schlafen: "front", "rear", "left", "right" oder None
    head: str | None = None

    @property
    def has_air(self) -> bool:
        return self.air_up > 0 or self.air_down > 0

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
    air: dict[str, float] = field(default_factory=dict)  # Luftfederung hl/hr in cm

    @property
    def residual(self) -> float:
        return math.hypot(self.residual_pitch, self.residual_roll)

    def head_tilt(self, head: str | None) -> float:
        """Restneigung in Schlafrichtung (Grad, > 0: Kopf höher als Füße)."""
        return {
            "front": self.residual_pitch,
            "rear": -self.residual_pitch,
            "right": self.residual_roll,
            "left": -self.residual_roll,
        }.get(head or "", 0.0)

    def residual_text(self, head: str | None = None) -> str:
        """Restneigung mit Richtung, z. B. "vorne 0,9° tiefer, rechts 0,4° tiefer"."""

        def part(value: float, high: str, low: str) -> str | None:
            if abs(value) < 0.05:
                return None
            return f"{low if value > 0 else high} {abs(value):.1f}° tiefer".replace(".", ",")

        parts = [
            p
            for p in (
                part(self.residual_pitch, "vorne", "hinten"),
                part(self.residual_roll, "rechts", "links"),
            )
            if p
        ]
        text = ", ".join(parts) if parts else "eben"
        if head and parts:
            tilt = self.head_tilt(head)
            if abs(tilt) >= 0.05:
                word = "höher" if tilt > 0 else "tiefer"
                text += f" (Kopf {abs(tilt):.1f}° {word})".replace(".", ",")
        return text

    @property
    def total_blocks(self) -> int:
        return sum(self.blocks.values())

    def text(self, block_height: float) -> str:
        parts = [
            f"{WHEEL_NAMES[w]}: {n} {'Block' if n == 1 else 'Blöcke'} ({n * block_height:.1f} cm)"
            for w, n in self.blocks.items()
            if n > 0
        ]
        air = [
            f"Luftfederung {WHEEL_NAMES[w].lower()} {v:+.1f} cm"
            for w, v in self.air.items()
            if abs(v) >= 0.05
        ]
        if not parts and not air:
            return "Keine Blöcke nötig"
        return ", ".join([*parts, *air]) if parts else "Keine Blöcke, " + ", ".join(air)


def _air_adjust(vehicle: Vehicle, heights: dict[str, float]) -> tuple[float, float]:
    """Beste Höhenänderung der Luftfederung hinten links/rechts (cm).

    Die Ausgleichsebene hängt linear von den beiden Werten ab, die Restneigung
    ist also eine konvexe Funktion. Koordinatenabstieg mit Begrenzung auf den
    Federweg findet das Minimum in wenigen Schritten.
    """
    lo, hi = -vehicle.air_down, vehicle.air_up
    front = (heights["vl"] + heights["vr"]) / 2.0
    p0 = front - (heights["hl"] + heights["hr"]) / 2.0  # >0: vorne höher
    r0 = (heights["vr"] + heights["hr"] - heights["vl"] - heights["hl"]) / 2.0  # >0: rechts höher
    wp, wr = 1.0 / vehicle.wheelbase**2, 1.0 / vehicle.track**2
    a = b = 0.0  # a = hinten links, b = hinten rechts
    for _ in range(30):
        # f = wp*(p0 - (a+b)/2)^2 + wr*(r0 + (b-a)/2)^2, jeweils nach a bzw. b minimiert
        a = min(hi, max(lo, (wp * (2 * p0 - b) + wr * (2 * r0 + b)) / (wp + wr)))
        b = min(hi, max(lo, (wp * (2 * p0 - a) - wr * (2 * r0 - a)) / (wp + wr)))
    return a, b


# Die Schlafrichtung entscheidet nur zwischen Varianten, deren Restneigung
# höchstens so viel schlechter ist als die beste (Grad), und nur wenn der Kopf
# dadurch mindestens so viel höher liegt.
HEAD_MARGIN = 0.2
# Bleibt höchstens so viel Neigung (Grad), gilt der Van als praktisch eben und
# die Variante mit den wenigsten Blöcken gewinnt. 0,2° sind auf 4 m etwa 1,4 cm.
BLOCK_MARGIN = 0.2


def best_block_plan(vehicle: Vehicle, pitch: float, roll: float) -> BlockPlan:
    """Sucht die Blockverteilung mit der kleinsten Restneigung.

    Probiert jede Auswahl von bis zu ``stacks`` Rädern mit 0..blocks_per_stack
    Blöcken. Mit Luftfederung wird für jede Verteilung zusätzlich die beste
    Höhe hinten links/rechts im Federweg berechnet. Bei gleicher Restneigung
    (Toleranz 0,01°) gewinnt die Variante mit weniger Blöcken. Bleiben mehrere
    Varianten unter BLOCK_MARGIN, gewinnt die mit den wenigsten Blöcken.

    Ist eine Schlafrichtung gesetzt, wird statt der besten eine Variante
    gewählt, die höchstens HEAD_MARGIN schlechter ist und den Kopf mindestens
    HEAD_MARGIN höher legt. Ziel bleibt also immer möglichst gerade, und fast
    gleiche Varianten springen nicht hin und her.
    """
    base = wheel_heights(vehicle, pitch, roll)
    stacks = max(0, min(vehicle.stacks, len(WHEELS)))
    plans: list[BlockPlan] = []
    for wheels in combinations(WHEELS, stacks):
        for counts in product(range(vehicle.blocks_per_stack + 1), repeat=stacks):
            blocks = {w: 0 for w in WHEELS}
            for w, n in zip(wheels, counts, strict=True):
                blocks[w] = n
            heights = {
                w: base[w] + blocks[w] * vehicle.block_height for w in WHEELS
            }
            air: dict[str, float] = {}
            if vehicle.has_air:
                a, b = _air_adjust(vehicle, heights)
                heights["hl"] += a
                heights["hr"] += b
                air = {"hl": round(a, 1), "hr": round(b, 1)}
            rp, rr = plane_tilt(vehicle, heights)
            plans.append(
                BlockPlan(blocks=dict(blocks), residual_pitch=rp, residual_roll=rr, air=air)
            )
    straightest = min(plans, key=lambda p: (round(p.residual, 2), p.total_blocks))
    # Steht der Van danach ohnehin praktisch eben (unter BLOCK_MARGIN), gewinnt
    # die Variante mit den wenigsten Blöcken. Sonst zählt nur: so gerade wie möglich.
    limit = max(round(straightest.residual, 2) + 0.005, BLOCK_MARGIN)
    best = min(
        (p for p in plans if p.residual <= limit),
        key=lambda p: (p.total_blocks, round(sum(abs(v) for v in p.air.values()), 1), p.residual),
    )
    if not vehicle.head:
        return best

    def head_low(p: BlockPlan) -> float:
        return max(0.0, -p.head_tilt(vehicle.head))

    near = [
        p
        for p in plans
        if p.residual <= straightest.residual + HEAD_MARGIN
        and head_low(p) <= head_low(best) - HEAD_MARGIN
    ]
    if not near:
        return best
    return min(near, key=lambda p: (round(head_low(p), 1), round(p.residual, 2), p.total_blocks))
