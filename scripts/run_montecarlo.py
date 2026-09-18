"""Monte Carlo dispersion analysis.

    python scripts/run_montecarlo.py -n 1000
    python scripts/run_montecarlo.py -n 500 --engine openrocket
    python scripts/run_montecarlo.py -n 2000 --ballast max --site home_field

Disperse a subset of the inputs to isolate what one variable does to the
flight -- everything not selected is held at its nominal value:

    python scripts/run_montecarlo.py --list-parameters
    python scripts/run_montecarlo.py -n 1000 --only drag_coefficient
    python scripts/run_montecarlo.py -n 1000 --only wind_speed_mps,wind_direction_deg
    python scripts/run_montecarlo.py -n 1000 --freeze drag_coefficient
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Puts the project root on the import path so `python scripts/run_montecarlo.py`
# works without installing the package first.  It has to run before the slisim
# imports below, which is what the `noqa: E402` markers acknowledge.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slisim import analysis, montecarlo, or_bridge as orb, report, units as U  # noqa: E402
from slisim.config import Site, Vehicle, load_uncertainty, output_dir  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "output"


def _refresh_latest(run_dir: Path) -> None:
    """Point `<vehicle>/mc/latest/` at the run just written.

    A timestamped directory per run means the newest results have a different
    path every time, which is awkward to document and to remember.  `latest/`
    is a fixed path that always holds the most recent campaign.

    Copied, not symlinked: a symlink needs Developer Mode or an elevated shell
    on Windows, and failing to publish the newest run is worse than the disk.
    """
    latest = run_dir.parent / "latest"
    if latest.exists():
        shutil.rmtree(latest)
    shutil.copytree(run_dir, latest)
    print(f"  Wrote {latest}{os.sep}  (copy of this run)")


def _sigma_record(unc: dict) -> str:
    """The dispersions this run actually used, for the report.

    Recorded because the run directory's name cannot capture them: two
    campaigns identical except for an edited sigma would be indistinguishable
    afterwards, and "which uncertainty.yaml produced this" is exactly the
    question a reviewer asks.
    """
    lines = []
    for name, spec in sorted(unc.items()):
        dist = spec.get("distribution", "normal")
        if dist == "uniform":
            spread = f"uniform[{spec['low']:g}, {spec['high']:g}]"
        else:
            sigma = spec.get("sigma")
            spread = f"{dist}, sigma={'site' if sigma is None else f'{sigma:g}'}"
            if spec.get("relative"):
                spread += " (relative)"
        lines.append(f"| `{name}` | {spread} |")
    return "| Parameter | Dispersion |\n|---|---|\n" + "\n".join(lines)


def _names(arg: str | None) -> list[str] | None:
    """Parse a comma- and/or space-separated parameter list."""
    if not arg:
        return None
    return [n for n in arg.replace(",", " ").split() if n]


def _subset_tag(only: list[str] | None, freeze: list[str] | None) -> str:
    """Filename suffix so a subset run never overwrites the full campaign."""
    if only:
        kind, names = "only", only
    elif freeze:
        kind, names = "except", freeze
    else:
        return ""
    if len(names) > 3:
        return f"_{kind}{len(names)}"
    return "_" + kind + "-" + "+".join(sorted(names))


def _list_parameters(unc: dict) -> int:
    print("Parameters available to --only / --freeze (config/uncertainty.yaml):")
    print()
    for name, spec in unc.items():
        dist = spec.get("distribution", "normal")
        if dist == "uniform":
            spread = f"uniform[{spec['low']:g}, {spec['high']:g}]"
        else:
            sig = spec.get("sigma")
            sig = "site" if sig is None else f"{sig:g}"
            spread = f"{dist}, sigma={sig}"
            if spec.get("relative"):
                spread += " (relative)"
        mark = "  " if name in montecarlo.OPENROCKET_PARAMETERS else " *"
        print(f" {mark} {name:<26} {spread}")
    print()
    print(" * RocketPy only -- OpenRocket disperses launch conditions only.")
    return 0


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
    sel = ap.add_mutually_exclusive_group()
    sel.add_argument("--only", default=None, metavar="P1,P2",
                     help="disperse ONLY these parameters; hold the rest nominal")
    sel.add_argument("--freeze", default=None, metavar="P1,P2",
                     help="hold these parameters nominal; disperse the rest")
    ap.add_argument("--list-parameters", action="store_true",
                    help="print the dispersible parameter names and exit")
    args = ap.parse_args()

    if args.list_parameters:
        return _list_parameters(load_uncertainty())

    # Narrow the uncertainty set to what --only / --freeze asked for, then reject
    # the two combinations that would run but tell you nothing.  Exit 2 (not 1)
    # keeps "you asked for something impossible" distinct from a requirement FAIL.
    only, freeze = _names(args.only), _names(args.freeze)
    try:
        unc = montecarlo.select_parameters(load_uncertainty(), only, freeze)
    except KeyError as exc:
        print(f"error: {exc.args[0]}")
        return 2
    dispersed = montecarlo.dispersed_parameters(unc)
    held = [k for k in unc if k not in dispersed]
    if not dispersed:
        print("error: every parameter is held nominal; nothing to disperse")
        return 2
    if args.engine == "openrocket" and not (
            set(dispersed) & montecarlo.OPENROCKET_PARAMETERS):
        print("error: OpenRocket disperses launch conditions only, and none of "
              f"{', '.join(dispersed)} is one.")
        print("       Every case would be identical. Use --engine rocketpy, "
              "or see --list-parameters.")
        return 2

    vehicle   = Vehicle.from_yaml(args.vehicle)
    site      = Site.from_yaml(args.site)
    out_dir   = output_dir(args.out, vehicle, "mc")
    ballast   = vehicle.ballast_min_kg if args.ballast == "min" else vehicle.ballast_max_kg
    target_ft = U.m_to_ft(vehicle.target_apogee_m)
    # Local time, not UTC: students compare these against their own lab clock.
    # Seconds included because editing one sigma and re-running takes well under
    # a minute, and that is exactly the pair you least want collapsed together.
    args.run_stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    print(f"Vehicle : {vehicle.name}  [{vehicle.status}]")
    print(f"Site    : {site.name}")
    print(f"Engine  : {args.engine}   N={args.samples}   seed={args.seed}"
          f"   ballast={U.kg_to_lb(ballast):.2f} lb")
    if only or freeze:
        print(f"Varying : {', '.join(dispersed)}")
        print(f"Nominal : {', '.join(held)}")
    print()

    df = montecarlo.run_montecarlo(
        vehicle, site, n=args.samples, engine=args.engine,
        ballast_kg=ballast, seed=args.seed, workers=args.workers,
        uncertainty=unc,
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
    #  Each campaign gets its own timestamped directory.  The tag below records
    #  engine, N, ballast and the subset, but NOT the sigmas: two runs that
    #  differ only in an edited uncertainty.yaml would otherwise write the same
    #  filenames, and the second would erase the first.  Comparing dispersion
    #  configurations is a normal thing to do, so it must not be destructive.
    run_dir = out_dir / f"{args.run_stamp}_n{args.samples}_{args.engine}"
    run_dir.mkdir(parents=True, exist_ok=True)
    tag = (f"{args.engine}_n{args.samples}_{args.ballast}"
           f"{_subset_tag(only, freeze)}")
    csv = run_dir / f"montecarlo_{tag}.csv"
    df.to_csv(csv, index=False)

    report.plot_apogee_distribution(df, run_dir, target_ft, f"apogee_dist_{tag}.png")
    report.plot_landing_scatter(df, run_dir, ell, f"landing_{tag}.png")
    report.plot_sensitivity(sens.head(12), run_dir, "apogee", f"sensitivity_{tag}.png")
    report.plot_input_distributions(df, run_dir, unc, args.engine, f"inputs_{tag}.png")

    report.write_markdown(
        run_dir / f"montecarlo_{tag}.md",
        f"Monte Carlo dispersion - {vehicle.name}",
        [
            ("Configuration",
             f"- Engine: `{args.engine}`\n"
             f"- Samples: {args.samples} (seed {args.seed}, reproducible)\n"
             f"- Site: {site.name}\n"
             f"- Ballast: {U.kg_to_lb(ballast):.2f} lb\n"
             f"- Motor: {motor_info['designation']} "
             f"({motor_info['total_impulse_ns']:.0f} N-s)\n"
             f"- Dispersed: {', '.join(dispersed)}\n"
             f"- Held nominal: {', '.join(held) or 'none'}\n"
             f"- Failed cases: {failed}"),
            ("Dispersions used", _sigma_record(unc)),
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
             f"![sensitivity](sensitivity_{tag}.png)\n\n"
             f"![sampled inputs](inputs_{tag}.png)"),
        ],
    )
    print(f"  Wrote {csv}")
    print(f"  Wrote {run_dir / f'montecarlo_{tag}.md'}")
    _refresh_latest(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
