"""Compare a vehicle file against the OpenRocket design it was transcribed from.

    python scripts/check_against_ork.py --vehicle config/vehicles/full_scale.yaml \
                                        --ork path/to/your_design.ork

Teams design in the OpenRocket GUI and then transcribe into a vehicle file.
Transcription is where digits get transposed and blocks get forgotten, and the
symptom is a plausible-looking number rather than an error.  This builds both
models in the same JVM and compares the four quantities that catch almost
everything: overall length, launch mass, CP and CG.

Read the deltas, do not just look for OK:

  length or mass off   a block was mistyped, or a component was left out of a
                       section's mass_lb
  CP off               geometry: a chord, a span, a nose length, or a missing
                       transition
  CG off but mass and CP right
                       usually not an error.  The schema gives a section a mass
                       but no mass distribution, so section mass sits at the
                       midpoint while the .ork places components at stations.
                       See USER_GUIDE section 2.8.

Exit code is 0 when every delta is inside tolerance, 1 otherwise, so this is
usable in CI once a design is frozen.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Puts the project root on the import path so the script runs uninstalled.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slisim import or_bridge as orb, units as U  # noqa: E402
from slisim.config import Vehicle  # noqa: E402

# Tolerances.  Length and mass should agree to the digit you typed; CP is a
# geometry calculation both sides perform identically, so it should too.  CG is
# given more room because of the mass-distribution approximation above.
TOL = {"length_in": 0.05, "mass_lb": 0.05, "cp_in": 0.10, "cg_in": 0.50}


def _walk(c):
    yield c
    for i in range(c.getChildCount()):
        yield from _walk(c.getChild(i))


def measure(rocket, mach: float = 0.3) -> dict[str, float]:
    """CP, CG, margin and launch mass, at the Mach the GUI reports."""
    core = orb.ensure_jvm()
    cfg = rocket.getSelectedConfiguration()
    cfg.setAllStages()
    conditions = core.aerodynamics.FlightConditions(cfg)
    conditions.setMach(mach)
    conditions.setAOA(0.0)
    warnings = core.logging.WarningSet()

    cp = core.aerodynamics.BarrowmanCalculator().getCP(cfg, conditions, warnings)
    cm = core.masscalc.MassCalculator.calculateLaunch(cfg).getCM()
    caliber = float(cfg.getReferenceLength())
    stage = list(rocket.getChildren())[0]
    return {
        "cp_in": U.m_to_in(float(cp.x)),
        "cg_in": U.m_to_in(float(cm.x)),
        "margin_cal": (float(cp.x) - float(cm.x)) / caliber,
        "mass_lb": U.kg_to_lb(float(cm.weight)),
        "length_in": U.m_to_in(sum(float(c.getLength()) for c in stage.getChildren())),
        "_warnings": [str(w) for w in warnings],
    }


def fin_sets(rocket) -> int:
    return sum(1 for c in _walk(rocket)
               if "FinSet" in str(c.getClass().getSimpleName()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vehicle", required=True, help="the vehicle yaml")
    ap.add_argument("--ork", required=True, help="the .ork it was transcribed from")
    ap.add_argument("--ballast", default="min", choices=["min", "max"])
    ap.add_argument("--mach", type=float, default=0.3)
    args = ap.parse_args()

    vehicle = Vehicle.from_yaml(args.vehicle)
    ballast = (vehicle.ballast_min_kg if args.ballast == "min"
               else vehicle.ballast_max_kg)

    theirs_doc, theirs = orb.load_ork(args.ork)
    ours_doc, ours, _mount, _motor = orb.build_document(vehicle, ballast)

    a, b = measure(theirs, args.mach), measure(ours, args.mach)

    print(f"  .ork    : {args.ork}")
    print(f"  vehicle : {vehicle.name}  ({args.vehicle})")
    print(f"  ballast : {U.kg_to_lb(ballast):.2f} lb     Mach {args.mach}")
    print()

    n_theirs, n_ours = fin_sets(theirs), fin_sets(ours)
    if n_theirs != n_ours:
        print(f"  NOTE: the .ork has {n_theirs} fin set(s), the vehicle file has "
              f"{n_ours}.\n        Every comparison below is affected. A duplicated "
              f"fin set in the .ork\n        inflates CP, margin and mass.\n")

    print(f"  {'quantity':<12}{'.ork':>12}{'yaml':>12}{'delta':>12}   {'tol':>6}")
    print("  " + "-" * 56)
    failures = []
    for key, label in (("length_in", "length in"), ("mass_lb", "mass lb"),
                       ("cp_in", "CP in"), ("cg_in", "CG in")):
        delta = b[key] - a[key]
        ok = abs(delta) <= TOL[key]
        if not ok:
            failures.append(label)
        print(f"  {label:<12}{a[key]:>12.2f}{b[key]:>12.2f}{delta:>+12.2f}   "
              f"{TOL[key]:>6.2f}  {'' if ok else '<-- OFF'}")
    print(f"  {'margin cal':<12}{a['margin_cal']:>12.2f}{b['margin_cal']:>12.2f}"
          f"{b['margin_cal'] - a['margin_cal']:>+12.2f}")

    if b["_warnings"]:
        print("\n  OpenRocket warnings on the generated model:")
        for w in b["_warnings"]:
            print(f"    - {w}")

    print()
    if failures:
        print(f"  {len(failures)} quantity/quantities outside tolerance: "
              f"{', '.join(failures)}")
        return 1
    print("  every quantity within tolerance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
