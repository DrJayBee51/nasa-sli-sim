"""Monte Carlo dispersion analysis.

    python scripts/run_montecarlo.py -n 1000
    python scripts/run_montecarlo.py -n 500 --engine openrocket
    python scripts/run_montecarlo.py -n 2000 --ballast max --site home_field
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slisim import analysis, montecarlo, or_bridge as orb, report, units as U  # noqa: E402
from slisim.config import Site, Vehicle  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "output"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", "--samples", type=int, default=500)
    ap.add_argument("--engine", default="rocketpy", choices=["rocketpy", "openrocket"])
    ap.add_argument("--vehicle", default=None)
    ap.add_argument("--site", default=None)
    ap.add_argument("--ballast", default="min", choices=["min", "max"])
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    vehicle = Vehicle.from_yaml(args.vehicle)
    site = Site.from_yaml(args.site)
    out_dir = Path(args.out)
    ballast = vehicle.ballast_min_kg if args.ballast == "min" else vehicle.ballast_max_kg
    target_ft = U.m_to_ft(vehicle.target_apogee_m)

    print(f"Vehicle : {vehicle.name}  [{vehicle.status}]")
    print(f"Site    : {site.name}")
    print(f"Engine  : {args.engine}   N={args.samples}   seed={args.seed}"
          f"   ballast={U.kg_to_lb(ballast):.2f} lb")
    print()

    df = montecarlo.run_montecarlo(
        vehicle, site, n=args.samples, engine=args.engine,
        ballast_kg=ballast, seed=args.seed, workers=args.workers,
    )

    failed = int((~df["ok"].astype(bool)).sum())
    if failed:
        print(f"\n  WARNING: {failed} of {len(df)} cases failed to simulate")
        for err in df.loc[~df["ok"].astype(bool), "error"].value_counts().head(3).items():
            print(f"    {err[1]:4d} x  {err[0][:90]}")
    print()

    motor_info = orb.motor_summary(orb.find_motor(
        vehicle.motor_search, vehicle.motor_manufacturer,
        vehicle.motor_mount_inner_radius_m * 2))

    # --- outputs
    stats = analysis.describe(df)
    print("  DISPERSION SUMMARY")
    print(report.table(stats.reset_index().rename(columns={"index": "quantity"}), "{:.2f}"))
    print()

    comp = analysis.compliance(df, vehicle, motor_info, ballast)
    print("  REQUIREMENT COMPLIANCE PROBABILITY")
    print(report.table(comp, "{:.3f}"))
    print()

    rec = analysis.recommend_target(df)
    print("  DECLARED TARGET ALTITUDE (req 2.3)")
    print(f"    Recommended declaration : {rec['recommended_target_ft']:,.0f} ft")
    print(f"    Median / mean           : {rec['median_ft']:,.0f} / {rec['mean_ft']:,.0f} ft")
    print(f"    Std deviation           : {rec['std_ft']:,.0f} ft")
    print(f"    95% CI                  : [{rec['ci95_low_ft']:,.0f},"
          f" {rec['ci95_high_ft']:,.0f}] ft")
    print(f"    P(4,000-6,000 ft)       : {rec['p_in_window']:.1%}")
    print(f"    P(scores at all)        : {rec['p_scoring']:.1%}")
    print(f"    Currently declared      : {target_ft:,.0f} ft")
    print()

    ell = analysis.landing_ellipse(df)
    print("  LANDING DISPERSION (req 3.10)")
    print(f"    {ell['n_sigma']:.0f}-sigma ellipse       : "
          f"{ell['semi_major_ft']:,.0f} x {ell['semi_minor_ft']:,.0f} ft"
          f" at {ell['angle_deg']:.0f} deg")
    print(f"    95th pct drift          : {ell['p95_drift_ft']:,.0f} ft")
    print(f"    Max drift               : {ell['max_drift_ft']:,.0f} ft")
    print(f"    Within 2,500 ft         : {ell['frac_within_2500ft']:.1%}")
    print()

    sens = analysis.sensitivity(df, "apogee_ft")
    print("  SENSITIVITY OF APOGEE TO INPUTS (Spearman rho)")
    print(report.table(sens.head(10), "{:.3f}"))
    print()

    # --- artifacts
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.engine}_n{args.samples}_{args.ballast}"
    csv = out_dir / f"montecarlo_{tag}.csv"
    df.to_csv(csv, index=False)

    report.plot_apogee_distribution(df, out_dir, target_ft, f"apogee_dist_{tag}.png")
    report.plot_landing_scatter(df, out_dir, ell, f"landing_{tag}.png")
    report.plot_sensitivity(sens.head(12), out_dir, "apogee", f"sensitivity_{tag}.png")

    report.write_markdown(
        out_dir / f"montecarlo_{tag}.md",
        f"Monte Carlo dispersion - {vehicle.name}",
        [
            ("Configuration",
             f"- Engine: `{args.engine}`\n"
             f"- Samples: {args.samples} (seed {args.seed}, reproducible)\n"
             f"- Site: {site.name}\n"
             f"- Ballast: {U.kg_to_lb(ballast):.2f} lb\n"
             f"- Motor: {motor_info['designation']} "
             f"({motor_info['total_impulse_ns']:.0f} N-s)\n"
             f"- Failed cases: {failed}"),
            ("Dispersion summary",
             report.table(stats.reset_index().rename(columns={"index": "quantity"}), "{:.2f}")),
            ("Requirement compliance", report.table(comp, "{:.3f}")),
            ("Recommended target altitude",
             f"**{rec['recommended_target_ft']:,.0f} ft** "
             f"(95% CI [{rec['ci95_low_ft']:,.0f}, {rec['ci95_high_ft']:,.0f}] ft; "
             f"P(in window) = {rec['p_in_window']:.1%})"),
            ("Sensitivity", report.table(sens, "{:.3f}")),
            ("Figures",
             f"![apogee](apogee_dist_{tag}.png)\n\n"
             f"![landing](landing_{tag}.png)\n\n"
             f"![sensitivity](sensitivity_{tag}.png)"),
        ],
    )
    print(f"  Wrote {csv}")
    print(f"  Wrote {out_dir / f'montecarlo_{tag}.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
