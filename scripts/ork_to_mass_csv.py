"""Build a mass-properties worksheet from an OpenRocket design.

    python scripts/ork_to_mass_csv.py --ork path/to/design.ork \
                                      --out config/mass/my_vehicle.csv

OpenRocket already knows every component's mass and where it sits -- it computed
them from the materials and geometry in the GUI.  Reading those out beats
transcribing them: a transposed digit in a mass table produces a plausible
number rather than an error, which is the whole failure mode USER_GUIDE section
2.9 warns about.

So this is the one direction the framework can automate.  It walks the .ork,
groups each component into the yaml block it belongs to, and writes the
worksheet `config/mass/` expects -- parts, per-section subtotals, and the
aggregate.  It then prints the `mass_lb` / `cg_*_in` values to paste into the
vehicle yaml, so the two files cannot disagree.

Re-run it whenever the .ork changes, then run check_mass_csv.py.

What it cannot know: `landing_sections` and `internal_bodies` (which joints
separate in flight, and what comes down on its own tether), `ballast`, and
`target_apogee_ft`.  Those are engineering decisions, not geometry -- see
USER_GUIDE section 2.9.

Each row's `source` records where its mass came from:

  override  a human typed it into the .ork -- a mass override, or a mass
            component, whose mass IS its definition.  Measured once the part has
            been weighed; a placeholder until then, and the .ork cannot tell the
            two apart on its own.
  ork       OpenRocket computed it from a material density and the geometry.  It
            will move when the part is actually built.
  CONFIRM   the component's comment in the GUI says so (see below).

So keep the masses in the .ork and regenerate freely: this never overwrites a
measured value, because the measured value lives in the .ork too.  To flag one
that is still a guess, put "placeholder", "CONFIRM" or "TBD" in the component's
comment field in OpenRocket -- that marking survives regeneration, which a hand
edit to the CSV would not.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slisim import or_bridge as orb, units as U  # noqa: E402

MASS_DP, STATION_DP = Decimal("0.001"), Decimal("0.01")

#  Components that are their own yaml block rather than part of a section's mass.
#  A section's mass_lb excludes these by definition, because `fins:`,
#  `recovery:` and `shock_cord_mass_lb` declare them separately.
BLOCK_BY_CLASS = {"ShockCord": "shock_cord"}
#  Components that bound a section: the tube or cone a part sits inside.
STRUCTURAL = ("NoseCone", "BodyTube", "Transition")
#  A mass component has no material or geometry -- its mass is the whole point of
#  it, so it is always a number a human entered, and isMassOverridden() is False.
HUMAN_MASS = ("MassComponent",)
#  Markers a team can put in a component's GUI comment to say the mass is a guess.
UNCONFIRMED = ("confirm", "placeholder", "tbd", "guess", "estimate")


def source_of(component, cls: str) -> tuple[str, str]:
    """Where this component's mass came from, and its GUI comment."""
    comment = str(component.getComment() or "").strip().replace("\n", " ")
    if any(k in comment.lower() for k in UNCONFIRMED):
        return "CONFIRM", comment
    human = cls in HUMAN_MASS or bool(component.isMassOverridden())
    return ("override" if human else "ork"), comment


def q(x, dp: Decimal) -> Decimal:
    return Decimal(x).quantize(dp, rounding=ROUND_HALF_UP)


def walk(c, top=None, subsumed=False):
    """Every component, tagged with its containing section and mass status.

    `subsumed` marks a component whose mass an ancestor already accounts for --
    OpenRocket's "override mass of all subcomponents".  Counting it again would
    double it.  Nothing in Fullscale_Model_A sets that today, but the guard
    belongs here: a team moving to measured overrides is exactly who ticks it.
    """
    cls = str(c.getClass().getSimpleName())
    if cls in STRUCTURAL:
        top = str(c.getName())
    yield c, str(c.getName()), cls, top, subsumed
    sub = subsumed or bool(c.isSubcomponentsOverriddenMass())
    for i in range(c.getChildCount()):
        yield from walk(c.getChild(i), top, sub)


def block_of(name: str, cls: str, top: str | None, nose: str) -> str:
    """Which yaml block a component rolls into."""
    if cls == "Parachute":
        return "drogue" if "drogue" in name.lower() else "main"
    if "FinSet" in cls:
        return "fins"
    if cls in BLOCK_BY_CLASS:
        return BLOCK_BY_CLASS[cls]
    return "nose_cone" if top == nose else (top or "?")


def extract(ork: Path) -> tuple[dict[str, list], list[tuple[str, float, float]]]:
    """Per-block component rows, plus the structural geometry (name, x0, length)."""
    orb.ensure_jvm()
    _doc, rocket = orb.load_ork(str(ork))

    nose = next((n for _, n, cls, _, _ in walk(rocket) if cls == "NoseCone"), "")
    rows: dict[str, list] = defaultdict(list)
    geometry: list[tuple[str, float, float]] = []

    for c, name, cls, top, subsumed in walk(rocket):
        if cls in STRUCTURAL:
            geometry.append((name,
                             U.m_to_in(float(c.getComponentLocations()[0].x)),
                             U.m_to_in(float(c.getLength()))))
        mass_kg = float(c.getMass())
        if mass_kg <= 0 or subsumed:
            continue
        # getMass() already covers every fin in a set and every instance of a
        # multi-instance component, so the instance count must NOT be applied
        # again.  Verified against MassCalculator.calculateStructure.
        station_m = (float(c.getComponentLocations()[0].x)
                     + float(c.getComponentCG().x))
        source, comment = source_of(c, cls)
        rows[block_of(name, cls, top, nose)].append(
            (name, cls, U.kg_to_lb(mass_kg), U.m_to_in(station_m), source, comment))

    return rows, geometry


def worksheet(rows: dict[str, list], order: list[str], title: str) -> tuple[str, dict]:
    """The CSV text, and each block's rolled-up (mass, cg) for the yaml."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["section", "component", "mass_lb", "station_in",
                "moment_lb_in", "source", "note"])

    blocks = {}
    for sec in order:
        #  Round mass and station FIRST, then take the moment from those.  The
        #  worksheet's whole point is that a student can add the column up by
        #  hand, so every cell must follow from the cells printed beside it --
        #  a moment carried at full precision reads as an arithmetic error.
        parts = [(name, cls, q(m, MASS_DP), q(x, STATION_DP), src, note)
                 for name, cls, m, x, src, note in rows[sec]]
        for name, cls, m, x, src, note in parts:
            w.writerow([sec, name, m, x, q(m * x, MASS_DP), src,
                        f"{cls}; {note}" if note else cls])
        M = sum(m for _, _, m, _, _, _ in parts)
        Mo = sum(q(m * x, MASS_DP) for _, _, m, x, _, _ in parts)
        cg = q(Mo / M, STATION_DP)
        w.writerow([sec, "SUBTOTAL", M, cg, Mo, "",
                    f"CG = {Mo} / {M} = {cg} in from nose tip"])
        w.writerow([])
        blocks[sec] = (M, cg, Mo)

    buf.write("# AGGREGATE -- the section subtotals above combined the same way\n")
    for sec in order:
        M, cg, Mo = blocks[sec]
        w.writerow(["AGGREGATE", sec, M, cg, Mo, ""])
    TM = sum(blocks[s][0] for s in order)
    TMo = sum(blocks[s][2] for s in order)
    TCG = q(TMo / TM, STATION_DP)
    w.writerow(["AGGREGATE", "VEHICLE TOTAL", TM, TCG, TMo, "",
                f"dry mass, no motor or ballast; CG = {TMo} / {TM} = {TCG} in from nose tip"])

    header = f"""# MASS PROPERTIES WORKSHEET -- {title}
#
# GENERATED by scripts/ork_to_mass_csv.py.  Re-run it when the .ork changes.
# As parts get built, replace a mass with the weighed value and set its source to
# `weighed` -- regenerating would overwrite that, so stop regenerating a section
# once it is built.
#
# Per-section mass properties, then the sections combined.  Same arithmetic at
# both levels:   CG = sum(mass * station) / sum(mass)
#
#   section      the yaml block this rolls into: nose_cone | fins | drogue |
#                main | shock_cord | or a name from `sections:` / `transitions:`.
#                AGGREGATE marks the combining table at the bottom.
#   component    one part you can put on a scale.  SUBTOTAL closes a section.
#   mass_lb      TOTAL for the row.  Three decimals: a rail button is 0.002 lb.
#   station_in   from the NOSE TIP, aft positive.  One datum for the whole
#                vehicle.  On a SUBTOTAL row this IS that section CG.
#   moment_lb_in mass_lb * station_in.  DERIVED -- scripts/check_mass_csv.py
#                recomputes every derived cell so none can go stale.
#   source       override = a human typed this mass into the .ork (a mass
#                override, or a mass component whose mass IS its definition);
#                ork = OpenRocket computed it from a material density;
#                CONFIRM = the component's GUI comment says it is a guess.
#   note         the OpenRocket component class, plus the GUI comment if any
#
# The motor is not here (OpenRocket supplies it) and neither is ballast (it is a
# range, not a part).
#
"""
    return header + buf.getvalue(), blocks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ork", required=True)
    ap.add_argument("--out", required=True, help="worksheet CSV to write")
    args = ap.parse_args()

    rows, geometry = extract(Path(args.ork))

    #  Nose-to-tail for the structural blocks, then the parts that hang inside
    #  them, so the worksheet reads in the order a reviewer walks the vehicle.
    structural = [n for n, _, _ in geometry]
    order = (["nose_cone"]
             + [n for n in structural if n in rows and n != structural[0]]
             + [b for b in ("fins", "drogue", "main", "shock_cord") if b in rows])
    missing = [b for b in rows if b not in order]
    if missing:
        print(f"  NOTE: not placed in any block: {missing}")

    text, blocks = worksheet(rows, order, Path(args.ork).stem)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"  wrote {out}  ({sum(len(v) for v in rows.values())} parts, "
          f"{len(order)} blocks)")

    # --- the numbers to paste into the vehicle yaml ---------------------
    front = {n: x0 for n, x0, _ in geometry}
    print("\n  values for the vehicle yaml (CG relative to each block's own datum):\n")
    for sec in order:
        M, cg, _ = blocks[sec]
        if sec == "nose_cone":
            print(f"    nose_cone        mass_lb: {M:<9} cg_from_tip_in: {cg}")
        elif sec in front:
            print(f"    {sec:<16} mass_lb: {M:<9} "
                  f"cg_from_front_in: {q(Decimal(cg) - Decimal(str(front[sec])), STATION_DP)}")
        else:
            #  fins, chutes and cord are positioned by absolute station; for the
            #  recovery blocks the yaml wants the bay they ride in plus an offset
            #  into it, so name the section whose span contains that station.
            bay = max((n for n, x0, _ in geometry if x0 <= float(cg)),
                      key=lambda n: front[n], default=None)
            extra = (f" bay: {bay!r} cg_from_front_in: "
                     f"{q(Decimal(cg) - Decimal(str(front[bay])), STATION_DP)}"
                     if bay and sec != "fins" else "")
            print(f"    {sec:<16} mass_lb: {M:<9} (station {cg} in){extra}")

    print(f"\n  geometry: " + ", ".join(f"{n} {L:.2f} in" for n, _, L in geometry))
    print(f"  overall length: {sum(L for _, _, L in geometry):.2f} in")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
