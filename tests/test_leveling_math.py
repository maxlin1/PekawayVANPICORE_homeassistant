"""Tests für den Rechenkern der Nivellierung (ohne Home Assistant)."""

from __future__ import annotations

import importlib.util
import math
import random
import sys
import types
from pathlib import Path

import pytest

# Rechenkern direkt laden, ohne das HA-Paket vanpi_core zu importieren
ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "vanpi_core" / "leveling"
pkg = types.ModuleType("leveling")
pkg.__path__ = [str(ROOT)]
sys.modules["leveling"] = pkg
for name in ("geometry", "filter", "drive_calibration"):
    spec = importlib.util.spec_from_file_location(f"leveling.{name}", ROOT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"leveling.{name}"] = mod
    spec.loader.exec_module(mod)

from leveling.drive_calibration import (  # noqa: E402
    CalibrationError,
    DriveRecorder,
    average_directions,
)
from leveling.filter import AdaptiveVectorFilter, Debounce  # noqa: E402
from leveling.geometry import (  # noqa: E402
    AXIS_VECTORS,
    Orientation,
    OrientationError,
    Vehicle,
    best_block_plan,
    lift_per_wheel,
    normalize,
    twist,
)

VAN_A = Vehicle(wheelbase=431.8, track=173.5, block_height=2.1, stacks=2, blocks_per_stack=3)


def rot_matrix(yaw: float, pitch: float, roll: float):
    """Drehmatrix (Grad) im rechtshändigen System x vorne, y links, z oben."""
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    cr, sr = math.cos(math.radians(roll)), math.sin(math.radians(roll))
    # Pitch: Front hoch = Drehung um y, so dass x nach oben kippt
    rz = [[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]]
    ry = [[cp, 0, -sp], [0, 1, 0], [sp, 0, cp]]
    # Drehung um x: y (links) kippt nach oben
    rx = [[1, 0, 0], [0, cr, -sr], [0, sr, cr]]

    def mul(a, b):
        return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    return mul(rz, mul(ry, rx))


def apply(m, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))


def transpose(m):
    return [[m[j][i] for j in range(3)] for i in range(3)]


# Einbaulage: Sensor -> Fahrzeug (beliebige feste Drehung)
MOUNTS = {
    "liegend": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    "hochkant": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
    "gedreht_155": rot_matrix(155, 0, 0),
    "schief": rot_matrix(37, 70, -20),
    # Wie bei Max: Board steht hochkant, Sensor-Z zeigt nach vorne
    "hochkant_z_vorne": [[0, 0, 1], [1, 0, 0], [0, 1, 0]],
    "kopfueber": rot_matrix(0, 0, 180),
    "quer_90": rot_matrix(90, 0, 0),
    "quer_270": rot_matrix(270, 0, 0),
    "hochkant_seitlich": rot_matrix(0, 0, 90),
}


def sensor_reading(mount, pitch, roll, extra_vehicle=(0.0, 0.0, 0.0)):
    """Was der Sensor misst, wenn das Fahrzeug um pitch/roll geneigt ist."""
    # Rechte Seite hoch heißt: linke Achse (y) kippt nach unten
    veh_to_world = rot_matrix(0, pitch, -roll)
    up_world = (0.0, 0.0, 1.0)
    up_vehicle = apply(transpose(veh_to_world), up_world)
    f_vehicle = tuple(u + e for u, e in zip(up_vehicle, extra_vehicle))
    # Sensor-Koordinaten = mount^T * Fahrzeug
    return apply(transpose(mount), f_vehicle)


def forward_in_sensor(mount):
    return apply(transpose(mount), (1.0, 0.0, 0.0))


@pytest.mark.parametrize("mount_name", list(MOUNTS))
@pytest.mark.parametrize(("pitch", "roll"), [(0, 0), (2, 0), (0, -3), (4, 2.5), (-6, 5)])
def test_angles_any_mount(mount_name, pitch, roll):
    mount = MOUNTS[mount_name]
    up = sensor_reading(mount, 0, 0)
    ori = Orientation.from_vectors(up, forward_in_sensor(mount))
    p, r = ori.angles(sensor_reading(mount, pitch, roll))
    assert p == pytest.approx(pitch, abs=0.05)
    assert r == pytest.approx(roll, abs=0.05)


def test_axis_choice_vertical_rejected():
    up = (0.0, 0.0, 1.0)
    with pytest.raises(OrientationError):
        Orientation.from_vectors(up, AXIS_VECTORS["+z"])


def test_lift_full_not_half():
    # 2 Grad Front tiefer: vorne muss um Radstand*tan(2°) = 15,1 cm hoch
    lift = lift_per_wheel(VAN_A, -2.0, 0.0)
    assert lift["vl"] == pytest.approx(15.08, abs=0.05)
    assert lift["vr"] == pytest.approx(15.08, abs=0.05)
    assert lift["hl"] == pytest.approx(0.0, abs=1e-6)


def test_lift_roll_sign():
    # Rechte Seite höher -> links anheben
    lift = lift_per_wheel(VAN_A, 0.0, 1.0)
    assert lift["vl"] > 0 and lift["hl"] > 0
    assert lift["vr"] == pytest.approx(0.0, abs=1e-6)


def test_block_plan_level_needs_nothing():
    plan = best_block_plan(VAN_A, 0.1, -0.1)
    assert plan.total_blocks == 0
    assert plan.text(2.1) == "Keine Blöcke nötig"


def test_block_plan_left_low():
    # Links ca. 4,2 cm tiefer: 2 Blöcke unter beide linken Räder
    roll = math.degrees(math.atan(4.2 / VAN_A.track))
    plan = best_block_plan(VAN_A, 0.0, roll)
    assert plan.blocks == {"vl": 2, "vr": 0, "hl": 2, "hr": 0}
    assert plan.residual < 0.05


def test_block_plan_front_low():
    pitch = -math.degrees(math.atan(6.3 / VAN_A.wheelbase))
    plan = best_block_plan(VAN_A, pitch, 0.0)
    assert plan.blocks["vl"] == 3 and plan.blocks["vr"] == 3
    assert plan.residual < 0.05


def test_block_plan_corner_low_only_two_stacks():
    # Vorne links tief: mit 2 Stapeln bestes Ergebnis besser als ohne Blöcke
    pitch, roll = -0.8, 1.0
    plan = best_block_plan(VAN_A, pitch, roll)
    assert sum(1 for n in plan.blocks.values() if n) <= 2
    assert plan.residual < math.hypot(pitch, roll)
    assert plan.blocks["vl"] > 0


def test_block_plan_limits():
    plan = best_block_plan(VAN_A, -8.0, 0.0)  # zu steil für 3 Blöcke
    assert max(plan.blocks.values()) <= 3
    assert plan.residual > 1.0


def test_filter_quiet_and_responsive():
    rnd = random.Random(1)
    f = AdaptiveVectorFilter()
    base = normalize((0.0, 0.0, 1.0))
    dt = 0.05
    out = None
    for _ in range(100):  # 5 s Rauschen + gelegentliche Ausreißer
        noise = tuple(rnd.gauss(0, 0.01) for _ in range(3))
        sample = tuple(b + n for b, n in zip(base, noise))
        if rnd.random() < 0.05:
            sample = (sample[0] + 0.3, sample[1], sample[2])
        out = f.update(sample, dt)
    ori = Orientation.from_vectors(base, (1.0, 0.0, 0.0))
    p, r = ori.angles(out)
    assert abs(p) < 0.3 and abs(r) < 0.3
    # Schritt um 3° Längsneigung muss nach 1 s fast vollständig da sein
    tilted = (math.sin(math.radians(3)), 0.0, math.cos(math.radians(3)))
    for _ in range(20):
        out = f.update(tilted, dt)
    p, _ = ori.angles(out)
    assert p == pytest.approx(3.0, abs=0.2)


def test_debounce():
    d = Debounce(2.0)
    assert d.update(True, 0.0) is True
    assert d.update(False, 1.0) is True
    assert d.update(False, 2.5) is True
    assert d.update(False, 3.1) is False


def _simulate_drive(mount, dt=0.05):
    """Stand 1,5 s, anfahren 0,25 g 3 s, rollen 2 s, bremsen 0,4 g bis Stand."""
    rnd = random.Random(7)
    rec = DriveRecorder()
    t = 0.0
    phases = [(1.5, 0.0), (3.0, 0.25), (2.0, 0.0), (1.9, -0.4), (1.0, 0.0)]
    for duration, a in phases:
        for _ in range(int(duration / dt)):
            noise = tuple(rnd.gauss(0, 0.01) for _ in range(3))
            reading = sensor_reading(mount, 0.5, -0.3, extra_vehicle=(a, 0.0, 0.0))
            rec.add(t, tuple(r + n for r, n in zip(reading, noise)))
            t += dt
    return rec


@pytest.mark.parametrize("mount_name", list(MOUNTS))
def test_drive_calibration_finds_forward_with_sign(mount_name):
    mount = MOUNTS[mount_name]
    rec = _simulate_drive(mount)
    fwd = rec.result()
    expected = normalize(forward_in_sensor(mount))
    angle = math.degrees(math.acos(max(-1, min(1, sum(a * b for a, b in zip(fwd, expected))))))
    assert angle < 3.0


def test_drive_calibration_too_weak():
    rec = DriveRecorder()
    for i in range(200):
        rec.add(i * 0.05, (0.0, 0.0, 1.0))
    with pytest.raises(CalibrationError):
        rec.result()


def test_average_directions():
    mean, spread = average_directions([(1.0, 0.05, 0.0), (1.0, -0.05, 0.0)])
    assert mean[0] == pytest.approx(1.0, abs=0.01)
    assert spread == pytest.approx(math.degrees(math.atan(0.05)), abs=0.1)


def _simulate(mount, phases, dt=0.05, seed=3):
    rnd = random.Random(seed)
    rec = DriveRecorder()
    t = 0.0
    for duration, a, bias in phases:
        for _ in range(int(duration / dt)):
            noise = tuple(rnd.gauss(0, 0.01) for _ in range(3))
            reading = sensor_reading(mount, 0.0, 0.0, extra_vehicle=(a + bias, 0.0, 0.0))
            rec.add(t, tuple(r + n for r, n in zip(reading, noise, strict=True)))
            t += dt
    return rec


def _angle_to_forward(fwd, mount):
    expected = normalize(forward_in_sensor(mount))
    c = sum(a * b for a, b in zip(fwd, expected, strict=True))
    return math.degrees(math.acos(max(-1, min(1, c))))


@pytest.mark.parametrize("mount_name", list(MOUNTS))
def test_drive_calibration_long_cruise_downhill(mount_name):
    """Langes Rollen bergab (konstanter Fehler) darf das Vorzeichen nicht kippen."""
    mount = MOUNTS[mount_name]
    phases = [(1.5, 0.0, 0.0), (3.0, 0.25, 0.0), (25.0, 0.0, -0.05), (2.0, -0.4, 0.0), (1.0, 0.0, 0.0)]
    fwd = _simulate(mount, phases).result()
    assert _angle_to_forward(fwd, mount) < 5.0


def test_drive_calibration_stop_pressed_late():
    """Lange stehen nach dem Bremsen ist kein Problem."""
    mount = MOUNTS["gedreht_155"]
    phases = [(1.5, 0.0, 0.0), (2.5, 0.3, 0.0), (3.0, 0.0, 0.0), (1.5, -0.5, 0.0), (20.0, 0.0, 0.0)]
    assert _angle_to_forward(_simulate(mount, phases).result(), mount) < 5.0


def test_drive_calibration_started_too_early():
    mount = MOUNTS["liegend"]
    phases = [(0.5, 0.0, 0.0), (3.5, 0.25, 0.0), (2.0, 0.0, 0.0), (1.9, -0.4, 0.0), (1.0, 0.0, 0.0)]
    with pytest.raises(CalibrationError):
        _simulate(mount, phases).result()


@pytest.mark.parametrize("mount_name", list(MOUNTS))
def test_drive_calibration_several_cycles_one_recording(mount_name):
    """Mehrfach anfahren und bremsen in einer Aufnahme, mit Pausen."""
    mount = MOUNTS[mount_name]
    cycle = [(2.5, 0.25, 0.0), (2.0, 0.0, 0.0), (1.6, -0.4, 0.0), (2.0, 0.0, 0.0)]
    phases = [(1.5, 0.0, 0.0), *cycle, *cycle, *cycle]
    assert _angle_to_forward(_simulate(mount, phases).result(), mount) < 5.0


# Echte Messwerte eines Vans: Board hochkant, X zeigt nach unten, Z nach vorne
VAN_B_UP = (-0.9737, -0.0071, -0.2277)
VAN_B_FORWARD = (-0.2278, -0.0161, 0.9736)


def test_van_b_x_axis_rejected():
    """+X liegt 77° gegen die Waagerechte, die Projektion zeigte nach hinten."""
    with pytest.raises(OrientationError):
        Orientation.from_vectors(VAN_B_UP, AXIS_VECTORS["+x"])


def test_van_b_front_low_recommends_front():
    ori = Orientation.from_vectors(VAN_B_UP, VAN_B_FORWARD)
    # Front 2° tiefer: "oben" kippt in Fahrzeugsicht nach hinten
    t = math.radians(-2.0)
    measured = tuple(
        math.cos(t) * u + math.sin(t) * f for u, f in zip(ori.up, ori.forward, strict=True)
    )
    pitch, roll = ori.angles(measured)
    assert pitch == pytest.approx(-2.0, abs=0.05)
    plan = best_block_plan(VAN_A, pitch, roll)
    assert plan.blocks["vl"] > 0 and plan.blocks["vr"] > 0
    assert plan.blocks["hl"] == 0 and plan.blocks["hr"] == 0


def test_air_suspension_levels_rear_without_blocks():
    """Hinten rechts 1,5 cm tiefer: Luftfederung gleicht das allein aus."""
    van = Vehicle(wheelbase=403.5, track=180, block_height=4.5, stacks=2,
                  blocks_per_stack=3, air_up=2.5, air_down=2.5)
    # Ebene mit nur HR tiefer gibt es nicht; nehme hinten 1,5 cm tiefer (längs)
    pitch = math.degrees(math.atan(1.5 / van.wheelbase))  # vorne höher
    plan = best_block_plan(van, pitch, 0.0)
    assert plan.total_blocks == 0
    assert plan.air["hl"] == pytest.approx(1.5, abs=0.1)
    assert plan.air["hr"] == pytest.approx(1.5, abs=0.1)
    assert plan.residual < 0.02
    assert "Luftfederung hinten links +1.5 cm" in plan.text(4.5)


def test_air_suspension_limited_and_combined_with_blocks():
    van = Vehicle(wheelbase=403.5, track=180, block_height=4.5, stacks=2,
                  blocks_per_stack=3, air_up=2.0, air_down=2.0)
    no_air = Vehicle(wheelbase=403.5, track=180, block_height=4.5, stacks=2, blocks_per_stack=3)
    # Hang aus einer echten Messung: vorne tiefer, rechts tiefer
    pitch = -math.degrees(math.atan(11.5 / 403.5))
    roll = -math.degrees(math.atan(5.8 / 180))
    plan = best_block_plan(van, pitch, roll)
    assert all(-2.0 <= v <= 2.0 for v in plan.air.values())
    assert plan.residual < best_block_plan(no_air, pitch, roll).residual


def test_head_direction_prefers_head_high():
    """Nicht ganz ausgleichbar: mit Kopf rechts soll rechts eher höher bleiben."""
    van = Vehicle(wheelbase=403.5, track=180, block_height=4.5, stacks=2, blocks_per_stack=3)
    roll = -math.degrees(math.atan(2.25 / 180))  # rechts 2,25 cm tiefer: halber Block
    neutral = best_block_plan(van, 0.0, roll)
    head_right = best_block_plan(
        Vehicle(**{**van.__dict__, "head": "right"}), 0.0, roll
    )
    assert head_right.head_tilt("right") >= 0
    assert head_right.residual <= neutral.residual + 0.1
    head_left = best_block_plan(Vehicle(**{**van.__dict__, "head": "left"}), 0.0, roll)
    assert head_left.head_tilt("left") >= 0


def test_head_direction_never_much_worse():
    """Fall von Max: Kopf rechts darf die Restneigung nicht deutlich verschlechtern."""
    # fehlt vorne links 17,8 cm, vorne rechts 23,4 cm, hinten rechts 5,6 cm
    pitch = math.degrees(math.atan(-(17.8 + 23.4 - 5.6) / 2 / 403.5))
    roll = math.degrees(math.atan(-(23.4 + 5.6 - 17.8) / 2 / 180))
    van = Vehicle(403.5, 180, 4.5, 2, 3, air_up=2, air_down=2)
    neutral = best_block_plan(van, pitch, roll)
    head = best_block_plan(Vehicle(**{**van.__dict__, "head": "right"}), pitch, roll)
    assert head.residual <= neutral.residual + 0.2
    assert head.head_tilt("right") >= neutral.head_tilt("right")
    assert head.blocks["vl"] == 2  # VL1 legt den Kopf nur 0,08° höher: kein Grund zu wechseln
    assert head.residual_text("right") == "vorne 0,9° tiefer, rechts 0,4° tiefer (Kopf 0,4° tiefer)"


@pytest.mark.parametrize("mount_name", list(MOUNTS))
@pytest.mark.parametrize("head", [None, "right"])
def test_front_right_low_any_mount(mount_name, head):
    """Van hängt nach vorne und rechts: Blöcke vorne, rechts mehr, in jeder Einbaulage."""
    mount = MOUNTS[mount_name]
    ori = Orientation.from_vectors(sensor_reading(mount, 0, 0), forward_in_sensor(mount))
    pitch, roll = ori.angles(sensor_reading(mount, -2.53, -1.78))
    assert pitch < -2.4
    assert roll < -1.7
    van = Vehicle(403.5, 180, 4.5, 2, 3, air_up=2, air_down=2, head=head)
    plan = best_block_plan(van, pitch, roll)
    assert plan.blocks["vr"] == 3
    assert plan.blocks["vl"] >= 1
    assert plan.blocks["hl"] == plan.blocks["hr"] == 0
    assert all(-2 <= v <= 2 for v in plan.air.values())
    assert plan.residual < 1.3


def test_fewest_blocks_when_practically_level():
    """Saftkiste-Werte von Max: 1,0° vorne tiefer, 1,5° links tiefer.

    Vorher: VL 3 + VR 1 und Luftfederung hoch (0,02°). VL 2 allein würde den
    Rahmen um fast 9 cm verwinden, also VL 2 + VR 1 mit Luftfederung.
    """
    van = Vehicle(403.5, 180, 4.5, 2, 3, air_up=2, air_down=2, head="right")
    plan = best_block_plan(van, -1.0, 1.5)
    assert plan.blocks == {"vl": 2, "vr": 1, "hl": 0, "hr": 0}
    assert plan.residual < 0.2


def _changes(van, plan):
    lifted = {w: n * van.block_height for w, n in plan.blocks.items()}
    for w, v in plan.air.items():
        lifted[w] += v
    return lifted


def test_no_big_twist_single_wheel():
    """Max am 23.11.: 1,1° vorne tiefer, 2,7° links tiefer.

    Vorher: 3 Blöcke nur vorne links (13,5 cm Verwindung), der Van stand schief.
    Jetzt: Blöcke links vorne und hinten, Verwindung höchstens 3 cm.
    """
    van = Vehicle(403.5, 180, 4.5, 2, 3, air_up=2, air_down=2, head="right")
    plan = best_block_plan(van, -1.1, 2.7)
    assert abs(twist(_changes(van, plan))) <= 3.0
    assert plan.blocks["vl"] >= 1 and plan.blocks["hl"] >= 1
    assert plan.blocks["vr"] == plan.blocks["hr"] == 0


@pytest.mark.parametrize(("pitch", "roll"), [(-3, 2), (2.5, -1), (-1, -3), (4, 4), (0.5, 0.2)])
def test_twist_limit_always_kept(pitch, roll):
    for air in (0, 2):
        van = Vehicle(403.5, 180, 4.5, 2, 3, air_up=air, air_down=air)
        plan = best_block_plan(van, pitch, roll)
        assert abs(twist(_changes(van, plan))) <= 3.0 + 1e-9
