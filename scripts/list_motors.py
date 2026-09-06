"""Browse OpenRocket's bundled motor database.

The 2027 handbook lists the motors NASA expects to be reliably available
(req 2.7): K1100T, K2050ST, K1000T, L1520T, L1090W, K1103X, K700W, L850W,
L1940X, L2200G.  Those are flagged below.

    python scripts/list_motors.py L            # all L motors
    python scripts/list_motors.py --nasa       # only the NASA-supported list
    python scripts/list_motors.py L1520 -v
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slisim import or_bridge as orb, requirements as rq  # noqa: E402

NASA_SUPPORTED = ["K1100T", "K2050ST", "K1000T", "L1520T", "L1090W",
                  "K1103X", "K700W", "L850W", "L1940X", "L2200G"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pattern", nargs="?", default="",
                    help="substring of the designation, e.g. 'L15' or 'L'")
    ap.add_argument("--nasa", action="store_true",
                    help="only motors on the NASA-supported availability list")
    ap.add_argument("--manufacturer", default="")
    ap.add_argument("--diameter-mm", type=float, default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    core = orb.ensure_jvm()
    db = core.startup.Application.getThrustCurveMotorSetDatabase()

    wanted = [p.upper() for p in (NASA_SUPPORTED if args.nasa else [args.pattern.upper()])]
    seen: set[str] = set()
    rows = []

    for mset in db.getMotorSets():
        for motor in mset.getMotors():
            desig = str(motor.getDesignation()).upper().replace(" ", "")
            if not any(w in desig for w in wanted):
                continue
            manu = str(motor.getManufacturer())
            if args.manufacturer and args.manufacturer.lower() not in manu.lower():
                continue
            dia_mm = float(motor.getDiameter()) * 1000.0
            if args.diameter_mm and abs(dia_mm - args.diameter_mm) > 1.0:
                continue
            key = f"{manu}|{desig}"
            if key in seen:
                continue
            seen.add(key)
            info = orb.motor_summary(motor)
            info["nasa_list"] = any(n in desig for n in NASA_SUPPORTED)
            info["diameter_mm"] = dia_mm
            rows.append(info)

    rows.sort(key=lambda r: (-r["nasa_list"], r["total_impulse_ns"]))

    hdr = (f"{'':2s} {'designation':<14s} {'manufacturer':<22s} {'impulse':>9s} "
           f"{'burn':>6s} {'avg N':>8s} {'max N':>8s} {'prop kg':>8s} {'dia':>6s}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        over = r["total_impulse_ns"] > rq.MAX_IMPULSE_NS
        flag = "!" if over else ("*" if r["nasa_list"] else " ")
        print(f"{flag:2s} {r['designation']:<14s} {r['manufacturer'][:22]:<22s} "
              f"{r['total_impulse_ns']:9.0f} {r['burn_time_s']:6.2f} "
              f"{r['avg_thrust_n']:8.0f} {r['max_thrust_n']:8.0f} "
              f"{r['propellant_mass_kg']:8.3f} {r['diameter_mm']:5.0f}mm")

    print()
    print(f"  {len(rows)} motors.  * = on the NASA-supported availability list (req 2.7)")
    print(f"                       ! = exceeds the {rq.MAX_IMPULSE_NS:.0f} N-s "
          f"college limit (req 2.9)")
    if not args.verbose:
        print("  Set 'motor.search' in config/vehicle.yaml to a designation above.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
