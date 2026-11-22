"""Kennlinie Spannung -> Füllstand (stückweise linear)."""

from __future__ import annotations


class CurveError(ValueError):
    pass


def parse_curve(text: str) -> list[tuple[float, float]]:
    """'0:0, 0.49:50, 1.6:100' -> [(0.0, 0.0), (0.49, 50.0), (1.6, 100.0)].

    Komma oder Semikolon trennt die Punkte, Doppelpunkt oder '=' trennt
    Spannung und Wert. Dezimalkomma ist erlaubt, wenn die Punkte mit
    Semikolon oder Zeilenumbruch getrennt sind.
    """
    raw = text.strip()
    if not raw:
        raise CurveError("leer")
    sep = ";" if (";" in raw or "\n" in raw) else ","
    parts = [p for p in raw.replace("\n", ";").split(sep) if p.strip()]
    points: list[tuple[float, float]] = []
    for part in parts:
        pair = part.replace("=", ":").split(":")
        if len(pair) != 2:
            raise CurveError(part.strip())
        try:
            v = float(pair[0].strip().replace(",", "."))
            level = float(pair[1].strip().replace(",", "."))
        except ValueError as err:
            raise CurveError(part.strip()) from err
        points.append((v, level))
    points.sort()
    if len(points) < 2:
        raise CurveError("mindestens zwei Punkte")
    if len({v for v, _ in points}) != len(points):
        raise CurveError("doppelte Spannung")
    return points


def format_curve(points: list[tuple[float, float]]) -> str:
    return ", ".join(f"{v:g}:{level:g}" for v, level in points)


def interpolate(points: list[tuple[float, float]], x: float) -> float:
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            return y0 + (x - x0) / (x1 - x0) * (y1 - y0)
    return points[-1][1]
