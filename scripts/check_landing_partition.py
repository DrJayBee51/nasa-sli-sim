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


def rejects(tmp: Path, body: str, why: str) -> str | None:
    """A bad internal_bodies entry must raise at load, not load and mislead."""
    base = Path("config/vehicles/fullscale_model_a.yaml").read_text(encoding="utf-8")
    assert "internal_bodies:" in base, "fixture vehicle no longer has internal_bodies"
    head, _, tail = base.partition("internal_bodies:")
    # Replace the block up to the next top-level comment banner.
    tail = tail[tail.index("\n# ---"):]
    tmp.write_text(head + "internal_bodies:\n" + body + tail, encoding="utf-8")
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
