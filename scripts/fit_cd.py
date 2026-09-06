"""Post-flight drag fit and model update (FRR section V).

    "Estimate the drag coefficient of the full-scale rocket utilizing launch
     data. Use this value to run a post-flight simulation."

Usage:
    python scripts/fit_cd.py data/flights/vdf_2027.csv
    python scripts/fit_cd.py data/flights/vdf.csv --wind 8 --temp-f 71 --match ascent

Also emits the measured kinetic-energy table, which is what the FRR asks teams
to report rather than the simulated one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slisim import postflight, report, units as U  # noqa: E402
from slisim.config import Site, Vehicle  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "output"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="altimeter CSV export")
    ap.add_argument("--vehicle", default=None)
    ap.add_argument("--site", default=None)
    ap.add_argument("--ballast-lb", type=float, default=0.0,
                    help="ballast actually flown")
    ap.add_argument("--match", default="apogee", choices=["apogee", "ascent"],
                    help="fit apogee only, or the whole ascent profile")
    ap.add_argument("--altitude-units", default="auto", choices=["auto", "ft", "m"])
    ap.add_argument("--time-column", default=None)
    ap.add_argument("--altitude-column", default=None)
    # Launch-day conditions: the FRR asks for the model to be updated with these.
    ap.add_argument("--wind", type=float, default=None, help="wind speed, mph")
    ap.add_argument("--wind-dir", type=float, default=None, help="degrees FROM")
    ap.add_argument("--temp-f", type=float, default=None)
    ap.add_argument("--pressure-inhg", type=float, default=None)
    ap.add_argument("--rail-angle", type=float, default=None, help="degrees off vertical")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    vehicle = Vehicle.from_yaml(args.vehicle)
    site = Site.from_yaml(args.site)
    out_dir = Path(args.out)
    ballast_kg = U.lb_to_kg(args.ballast_lb)

    measured = postflight.load_altimeter_csv(
        args.csv, altitude_units=args.altitude_units,
        time_column=args.time_column, altitude_column=args.altitude_column)

    print(f"Flight data : {measured.source}  (altitude read as {measured.units_detected})")
    for k, v in measured.summary().items():
        print(f"  {k:18s} {v:12.2f}")
    print()

    overrides = {}
    if args.wind is not None:
        overrides["wind_speed_mps"] = U.mph_to_mps(args.wind)
    if args.wind_dir is not None:
        overrides["wind_direction_deg"] = args.wind_dir
    if args.temp_f is not None:
        overrides["temperature_k"] = U.f_to_k(args.temp_f)
    if args.pressure_inhg is not None:
        overrides["pressure_pa"] = U.inhg_to_pa(args.pressure_inhg)
    if args.rail_angle is not None:
        overrides["rail_angle_deg"] = args.rail_angle

    if overrides:
        print("Launch-day conditions applied to the model:")
        for k, v in overrides.items():
            print(f"  {k:22s} {v:.3f}")
    else:
        print("No launch-day conditions given; using the site nominal.")
        print("  (The FRR asks for the model to be updated with actual conditions --")
        print("   pass --wind / --temp-f / --pressure-inhg / --rail-angle.)")
    print()

    print(f"Fitting drag scale (objective: {args.match})...")
    fit = postflight.fit_cd_scale(vehicle, site, measured, overrides,
                                  ballast_kg=ballast_kg, match=args.match)
    print(fit.report())
    print()

    rates = postflight.measured_descent_rates(measured, vehicle.main["deploy_altitude_m"])
    if rates:
        print("MEASURED descent rates (from the altimeter, not the simulation):")
        for k, v in rates.items():
            print(f"  {k:18s} {v:10.2f}")
        print()

        main_fps = rates.get("main_fps")
        if main_fps and main_fps == main_fps:  # not NaN
            ke = postflight.kinetic_energy_table(
                vehicle, U.fps_to_mps(main_fps), ballast_kg)
            print("KINETIC ENERGY AT LANDING (req 3.2), from measured descent rate:")
            print(report.table(ke, "{:.2f}"))
            print()
            ke.to_csv(out_dir / "postflight_kinetic_energy.csv", index=False)

    print("NEXT STEP: fold the fitted scale back into config/uncertainty.yaml.")
    print(f"  Set drag_coefficient.mean   = {fit.cd_scale:.4f}")
    print("  Set drag_coefficient.sigma  = 0.02-0.03  (post-flight, was 0.07)")
    print("  Then re-run run_montecarlo.py: the apogee spread should shrink")
    print("  substantially, which is what improves the req 2.3 altitude score.")

    out_dir.mkdir(parents=True, exist_ok=True)
    report.write_markdown(
        out_dir / "postflight_cd_fit.md",
        f"Post-flight drag fit - {vehicle.name}",
        [
            ("Flight data",
             f"- Source: `{measured.source}`\n"
             + "\n".join(f"- {k}: {v:,.2f}" for k, v in measured.summary().items())),
            ("Launch-day conditions",
             "\n".join(f"- {k}: {v:.3f}" for k, v in overrides.items())
             or "_Not supplied; site nominal used._"),
            ("Drag fit", "```\n" + fit.report() + "\n```"),
            ("Measured descent rates",
             "\n".join(f"- {k}: {v:,.2f}" for k, v in rates.items()) or "_n/a_"),
        ],
    )
    print(f"\n  Wrote {out_dir / 'postflight_cd_fit.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
