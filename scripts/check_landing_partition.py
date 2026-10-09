"""Check that landing sections partition the vehicle, tethered bodies included.

    python scripts/check_landing_partition.py

Req 3.2 caps kinetic energy per independent section, so the landing masses must
account for the whole vehicle exactly once.  An `internal_bodies` entry moves
mass out of its parent section into a piece of its own, and that subtraction is
the part worth guarding: get it wrong and the pieces still sum to the right
total, because whatever one piece gains another loses.  The mass budget closes,
every number looks plausible, and a kinetic-energy check passes on a section
that is lighter than the real thing.

Checks every vehicle in config/vehicles/, then the two ways a bad
`internal_bodies` entry can be written.  Exits 0 if all hold, 1 otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slisim import units as U  # noqa: E402
from slisim.config import Vehicle, available_vehicles  # noqa: E402

TOL_KG = 1e-9


def check(vehicle: Vehicle, ballast_kg: float) -> list[str]:
    bad = []
    pieces = vehicle.landing_section_masses_kg(ballast_kg)

    # Every piece of a real vehicle weighs something.  A negative or zero piece
    # means mass was moved out of a section that did not have it to give.
    for name, kg in pieces.items():
        if kg <= 0:
            bad.append(f"landing section {name!r} weighs {U.kg_to_lb(kg):.3f} lb")

    # The pieces must equal the structure they came from.  structure_mass_kg is
    # computed from the sections themselves and knows nothing about tethered
    # bodies, so it is an independent account of the same mass.
    got, want = sum(pieces.values()), vehicle.structure_mass_kg(ballast_kg)
    if abs(got - want) > TOL_KG:
        bad.append(f"pieces sum to {U.kg_to_lb(got):.4f} lb but the structure is "
                   f"{U.kg_to_lb(want):.4f} lb")

    if vehicle.unassigned_members():
        bad.append(f"not in any landing section: {vehicle.unassigned_members()}")
    return bad


#  The smallest vehicle that loads, for exercising a bad internal_bodies entry.
#  Self-contained so it does not depend on how any real vehicle declares its
#  tethered bodies -- a worksheet-backed vehicle has no yaml block to edit.
FIXTURE = """\
name: "partition fixture"
airframe: {outer_diameter_in: 4.0, wall_thickness_in: 0.1}
nose_cone: {shape: ogive, length_in: 12.0, wall_thickness_in: 0.1, mass_lb: 1.0}
sections:
  - {name: "Payload Airframe", length_in: 20.0, mass_lb: 8.0}
fins: {count: 3, root_chord_in: 6.0, tip_chord_in: 3.0, sweep_in: 3.0,
       height_in: 4.0, thickness_in: 0.1, mass_lb: 0.5}
motor: {search: "K1100T", mount_inner_diameter_in: 2.2, mount_length_in: 12.0}
recovery:
  drogue: {diameter_in: 12.0, cd: 1.5}
  main: {diameter_in: 48.0, cd: 2.2}
landing_sections:
  - {name: "all", members: ["nose_cone", "Payload Airframe", "fins", "Payload"]}
internal_bodies:
"""


def rejects(tmp: Path, body: str, why: str) -> str | None:
    """A bad internal_bodies entry must raise at load, not load and mislead."""
    tmp.write_text(FIXTURE + body, encoding="utf-8")
    try:
        Vehicle.from_yaml(tmp)
    except ValueError:
        return None
    return f"accepted a vehicle whose {why}"


def main() -> int:
    bad: list[str] = []

    for path in available_vehicles():
        v = Vehicle.from_yaml(path)
        for label, ballast in (("min", v.ballast_min_kg), ("max", v.ballast_max_kg)):
            for line in check(v, ballast):
                bad.append(f"{path.name} [ballast {label}]: {line}")
        n = len(v.internal_bodies)
        print(f"  {'pass' if not bad else '....'}  {path.name:<28}"
              f"{len(v.landing_sections)} landing sections, {n} tethered")

    tmp = Path(".check_landing_partition.tmp.yaml")
    try:
        for body, why in (
            ('  - name: "Payload"\n    inside: "Payload Airframe"\n'
             '    mass_lb: 99.0\n',
             "tethered body outweighs its parent section"),
            ('  - name: "Payload"\n    inside: "No Such Tube"\n'
             '    mass_lb: 6.0\n',
             "tethered body names a section that does not exist"),
        ):
            if (msg := rejects(tmp, body, why)):
                bad.append(msg)
    finally:
        tmp.unlink(missing_ok=True)

    if bad:
        print()
        for line in bad:
            print(f"  FAIL  {line}")
        return 1
    print("  pass  bad internal_bodies entries are rejected at load")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
