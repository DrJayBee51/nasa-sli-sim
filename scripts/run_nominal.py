"""Nominal flight in both engines, with a full USLI requirement check.

    python scripts/run_nominal.py
    python scripts/run_nominal.py --ballast max --site home_field
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slisim import analysis, or_bridge as orb, report, requirements as rq  # noqa: E402
from slisim import rocketpy_model as rpm, units as U  # noqa: E402
from slisim.config import Site, Vehicle  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "output"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vehicle", default=None, help="path to vehicle YAML")
    ap.add_argument("--site", default=None, help="site key from config/sites.yaml")
    ap.add_argument("--ballast", default="min", choices=["min", "max", "both"],
                    help="req 2.20.7.4 requires compliance at BOTH extremes")
    ap.add_argument("--skip-rocketpy", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    vehicle = Vehicle.from_yaml(args.vehicle)
    site = Site.from_yaml(args.site)
    out_dir = Path(args.out)

    print(f"Vehicle : {vehicle.name}  [{vehicle.status}]")
    print(f"Site    : {site.name}")
    print(f"Length  : {U.m_to_in(vehicle.total_length_m):.1f} in"
          f"   Diameter: {U.m_to_in(vehicle.diameter_m):.2f} in")
    print()

    cases = {"min": [vehicle.ballast_min_kg], "max": [vehicle.ballast_max_kg],
             "both": [vehicle.ballast_min_kg, vehicle.ballast_max_kg]}[args.ballast]

    overall_ok = True
    for ballast in cases:
        label = f"ballast {U.kg_to_lb(ballast):.2f} lb"
        print("=" * 104)
        print(f"  {label}")
        print("=" * 104)

        doc, rocket, _mount, motor = orb.build_document(vehicle, ballast)
        ork = out_dir / f"{vehicle.name.lower().replace(' ', '_')}_{U.kg_to_lb(ballast):.0f}lb.ork"
        orb.save_ork(doc, ork)
        motor_info = orb.motor_summary(motor)
        print(f"  Motor   : {motor_info['designation']} ({motor_info['manufacturer']})"
              f"  {motor_info['total_impulse_ns']:.0f} N-s,"
              f" {motor_info['propellant_mass_kg']:.3f} kg propellant")
        print(f"  Saved   : {ork}")
        print()

        or_res = orb.run_simulation(orb.make_simulation(doc, rocket, site),
                                    rocket, keep_series=True)
        results = {"OpenRocket": or_res}

        if not args.skip_rocketpy:
            power_on, power_off = rpm.export_drag_curves(or_res)
            mass_props = rpm.export_mass_properties(rocket, orb.ensure_jvm())
            env = rpm.build_environment(site)
            rk = rpm.build_rocket(vehicle, motor, mass_props, power_on, power_off)
            rp_res = rpm.extract(rpm.build_flight(rk, env, site), rk, motor)
            results["RocketPy"] = rp_res

            cmp_df = analysis.compare(or_res.to_row(), rp_res.to_row())
            print("  OpenRocket vs RocketPy")
            print("  " + "-" * 84)
            print(f"  {'quantity':<24s} {'units':<6s} {'OpenRocket':>12s}"
                  f" {'RocketPy':>12s} {'diff':>10s} {'%':>8s}")
            for _, r in cmp_df.iterrows():
                print(f"  {r['quantity']:<24s} {r['units']:<6s} {r['OpenRocket']:12.2f}"
                      f" {r['RocketPy']:12.2f} {r['difference']:10.2f} {r['percent']:7.1f}%")
            print()

        checks = rq.check_all(or_res, vehicle, motor_info, ballast)
        print(rq.format_table(checks))
        print()
        # WARN means "compliant but costing points" (e.g. the mass score);
        # only an outright FAIL is a requirement violation.
        overall_ok &= not any(c.status is rq.Status.FAIL for c in checks)

        suffix = f"_{U.kg_to_lb(ballast):.0f}lb"
        report.plot_flight_profile(results, out_dir, f"flight_profile{suffix}.png")
        report.plot_stability(results, out_dir, f"stability{suffix}.png")
        if len(results) > 1:
            report.plot_comparison(cmp_df, out_dir, f"engine_comparison{suffix}.png")
        print(f"  Figures written to {out_dir}")
        print()

    print("=" * 104)
    print("  RESULT:", "all requirements satisfied" if overall_ok
          else "ONE OR MORE REQUIREMENTS NOT SATISFIED")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
