"""OpenRocket vs RocketPy cross-validation report.

Answers three Mission Performance Predictions bullets that appear verbatim in
the PDR, CDR, and FRR criteria:

    "Present data from a different calculation method to verify that original
     results are accurate."
    "Discuss any differences between the different calculations."
    "Perform multiple simulations to verify that results are precise."

Usage:
    python scripts/run_crossvalidate.py
    python scripts/run_crossvalidate.py --mc 300      # also disperse both engines
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from slisim import analysis, montecarlo, or_bridge as orb, report  # noqa: E402
from slisim import rocketpy_model as rpm, units as U  # noqa: E402
from slisim.config import Site, Vehicle  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "output"

# Differences the two engines are EXPECTED to show, with the reason.  Listing
# them up front is the difference between "our tools disagree" and "our tools
# agree everywhere they model the same thing".
KNOWN_DIFFERENCES = {
    "Rail exit velocity": (
        "Different definitions of leaving the rail. OpenRocket releases the "
        "vehicle when the forward rail button passes the rail tip; RocketPy "
        "when the centre of mass has travelled the full rail length. The "
        "effective travel therefore differs by roughly the button spacing. "
        "RocketPy reads lower, so treating it as the governing number for "
        "req 2.14 is the conservative choice."
    ),
    "Drift from pad": (
        "Ascent weathercocking, not descent. The descent phases agree to about "
        "2%: both tools drift downwind at nearly the same rate for nearly the "
        "same time. The difference is that RocketPy leaves the rail slower "
        "(see rail exit velocity), so it enters free flight at a larger angle "
        "of attack relative to the wind, weathercocks harder, and reaches "
        "apogee further UPWIND -- roughly 690 ft vs 570 ft in a 10 mph wind. "
        "Net drift is the difference between an upwind apogee offset and a "
        "downwind descent, so a modest weathercocking difference produces a "
        "proportionally larger difference in the small number left over. "
        "Quote the Monte Carlo landing ellipse, not either single run."
    ),
    "Descent rate (drogue)": (
        "Drogue descent is the least converged part of either model: at high "
        "descent rate the vehicle is tumbling and neither tool resolves that. "
        "Treat agreement here as coincidental and validate against flight data."
    ),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vehicle", default=None)
    ap.add_argument("--site", default=None)
    ap.add_argument("--ballast", default="min", choices=["min", "max"])
    ap.add_argument("--mc", type=int, default=0,
                    help="also run N dispersed cases through BOTH engines")
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    vehicle = Vehicle.from_yaml(args.vehicle)
    site = Site.from_yaml(args.site)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)   # gitignored; absent in a fresh clone
    ballast = vehicle.ballast_min_kg if args.ballast == "min" else vehicle.ballast_max_kg

    print(f"Vehicle : {vehicle.name}")
    print(f"Site    : {site.name}")
    print()

    # --- nominal, both engines
    doc, rocket, _mount, motor = orb.build_document(vehicle, ballast)
    or_res = orb.run_simulation(orb.make_simulation(doc, rocket, site),
                                rocket, keep_series=True)
    power_on, power_off = rpm.export_drag_curves(or_res)
    mass_props = rpm.export_mass_properties(rocket, orb.ensure_jvm())
    rk = rpm.build_rocket(vehicle, motor, mass_props, power_on, power_off)
    rp_res = rpm.extract(rpm.build_flight(rk, rpm.build_environment(site), site), rk, motor)

    cmp_df = analysis.compare(or_res.to_row(), rp_res.to_row())
    print("  NOMINAL COMPARISON")
    print(report.table(cmp_df, "{:.2f}"))
    print()

    agree = cmp_df[cmp_df["percent"].abs() <= 5.0]
    disagree = cmp_df[cmp_df["percent"].abs() > 5.0]
    print(f"  {len(agree)} of {len(cmp_df)} quantities agree within 5%.")
    if len(disagree):
        print("  Quantities differing by more than 5%:")
        for _, r in disagree.iterrows():
            print(f"    - {r['quantity']}: {r['percent']:+.1f}%")
            reason = KNOWN_DIFFERENCES.get(r["quantity"])
            print(f"        {reason if reason else 'UNEXPLAINED - investigate before citing.'}")
    print()

    sections = [
        ("What is actually independent",
         "The two tools share the thrust curve, mass properties, and drag "
         "coefficient curve by construction, so those are *not* independently "
         "validated. What is independent: the flight dynamics integration "
         "(RocketPy 6-DOF/LSODA vs OpenRocket RK4), each tool's own Barrowman "
         "CP calculation over its own geometry description, the atmosphere and "
         "wind models, and event detection. A claim that the two tools "
         "independently confirm the drag estimate would be false; use "
         "`scripts/fit_cd.py` on real flight data for that."),
        ("Nominal comparison", report.table(cmp_df, "{:.2f}")),
        ("Discussion of differences",
         "\n".join(
             f"**{r['quantity']}** ({r['percent']:+.1f}%): "
             f"{KNOWN_DIFFERENCES.get(r['quantity'], 'Unexplained - investigate.')}"
             for _, r in disagree.iterrows()
         ) or "All quantities agree within 5%."),
    ]

    # --- optional dispersed comparison
    if args.mc:
        print(f"  Running {args.mc} dispersed cases through BOTH engines...")
        rows = []
        for engine in ("rocketpy", "openrocket"):
            df = montecarlo.run_montecarlo(vehicle, site, n=args.mc, engine=engine,
                                           ballast_kg=ballast, seed=args.seed,
                                           workers=args.workers, progress=False)
            ok = df[df["ok"].astype(bool)]
            for col in ("apogee_ft", "max_velocity_fps", "descent_time_s", "drift_ft"):
                if col in ok.columns:
                    rows.append({"engine": engine, "quantity": col,
                                 "mean": ok[col].mean(), "std": ok[col].std(),
                                 "p05": ok[col].quantile(0.05),
                                 "p95": ok[col].quantile(0.95)})
        mc_df = pd.DataFrame(rows)
        print()
        print("  DISPERSED COMPARISON (both engines, identical seed)")
        print(report.table(mc_df, "{:.2f}"))
        sections.append(("Dispersed comparison", report.table(mc_df, "{:.2f}")))
        mc_df.to_csv(out_dir / "crossvalidation_montecarlo.csv", index=False)

    fig = report.plot_comparison(cmp_df, out_dir, "crossvalidation.png")
    report.plot_flight_profile({"OpenRocket": or_res, "RocketPy": rp_res},
                               out_dir, "crossvalidation_profile.png")
    sections.append(("Figures",
                     "![comparison](crossvalidation.png)\n\n"
                     "![profile](crossvalidation_profile.png)"))

    cmp_df.to_csv(out_dir / "crossvalidation.csv", index=False)
    md = report.write_markdown(out_dir / "crossvalidation.md",
                               f"OpenRocket vs RocketPy - {vehicle.name}", sections)
    print(f"  Wrote {md}")
    print(f"  Wrote {fig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
