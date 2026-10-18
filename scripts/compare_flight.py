"""Overlay a flight's telemetry on the simulation of that flight (FRR section V).

    python scripts/compare_flight.py data/flights/subscale_1.csv --vehicle config/vehicles/subscale.yaml
    python scripts/compare_flight.py data/flights/fullscale.csv --wind 11 --temp-f 64 --ballast-lb 1.5
    python scripts/compare_flight.py log.csv --map accel_z_g="Accel Axial" --map gyro_z_dps="Roll"

    "Update your simulated flight model with launch day condition data and
     compare the predicted flight performance to the actual flight data."

Flies the vehicle in RocketPy with the launch-day conditions given, puts the
log and the simulation on one clock (both cross 100 ft AGL at the same
instant), and writes:

* `comparison_<log>.png` -- altitude, axial acceleration, body rates and the
  ground track, simulated over measured, for whichever channels the log has.
* `comparison_<log>.csv` -- the log with the simulation interpolated onto its
  timestamps beside each channel (`sim_*`), for your own analysis.

Channels are found by name (postflight.TELEMETRY_FIELDS); --map names any the
logger calls something else.  The simulated altitude compared is the
barometric one -- standard atmosphere from simulated pressure, as an altimeter
computes it -- and the acceleration is specific force in body axes, which is
what an accelerometer measures.

Lateral IMU axes depend on how the board is mounted and rolled, so lateral
acceleration and the two lateral rates are compared as magnitudes; the axial
channel and roll rate are compared directly.  An axial channel that reads
negative under thrust is a board mounted upside down, and is flipped (said so
on screen).  Body-frame channels end at the first deployment: the simulation
treats descent as a point mass, so it has no attitude to compare after that.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from slisim import or_bridge as orb, postflight, report, rocketpy_model as rpm, units as U  # noqa: E402
from slisim.config import Site, Vehicle, output_dir  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "output"


def simulate(vehicle: Vehicle, site: Site, ballast_kg: float, ov: dict) -> pd.DataFrame:
    """The launch-day flight in RocketPy, as state_history."""
    doc, rocket, _m, motor = orb.build_document(vehicle, ballast_kg)
    base = orb.run_simulation(orb.make_simulation(doc, rocket, site, ov), rocket,
                              keep_series=True)
    on, off = rpm.export_drag_curves(base)
    rk = rpm.build_rocket(vehicle, motor,
                          rpm.mass_properties(vehicle, rocket, orb.ensure_jvm(), ballast_kg),
                          on, off)
    return rpm.state_history(rpm.build_flight(rk, rpm.build_environment(site, ov), site, ov))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="the flight computer's CSV export")
    ap.add_argument("--vehicle", default=None)
    ap.add_argument("--site", default=None)
    ap.add_argument("--ballast-lb", type=float, default=0.0, help="ballast actually flown")
    ap.add_argument("--map", action="append", default=[], metavar="FIELD=COLUMN",
                    help="name the log column for a field, e.g. accel_z_g=\"AccelZ\"")
    ap.add_argument("--altitude-units", default="auto", choices=["auto", "ft", "m"])
    ap.add_argument("--wind", type=float, default=None, help="wind speed, mph")
    ap.add_argument("--wind-dir", type=float, default=None, help="degrees FROM")
    ap.add_argument("--temp-f", type=float, default=None)
    ap.add_argument("--pressure-inhg", type=float, default=None)
    ap.add_argument("--rail-angle", type=float, default=None, help="degrees off vertical")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    mapping = {}
    for item in args.map:
        field, sep, col = item.partition("=")
        if not sep:
            print(f"error: --map {item!r} needs FIELD=COLUMN")
            return 2
        mapping[field.strip()] = col.strip()

    vehicle = Vehicle.from_yaml(args.vehicle)
    site = Site.from_yaml(args.site)
    log = postflight.load_telemetry(args.csv, mapping, args.altitude_units)
    ov = postflight.launch_overrides(args.wind, args.wind_dir, args.temp_f,
                                     args.pressure_inhg, args.rail_angle)

    print(f"Log     : {log.attrs['source']}  ({len(log)} rows, altitude in "
          f"{log.attrs['altitude_units']})")
    for field, col in log.attrs["columns"].items():
        print(f"  {field:<14s} <- {col!r}")
    print(f"Vehicle : {vehicle.name}   ballast {args.ballast_lb:.2f} lb")
    print("Launch-day conditions: " + (", ".join(f"{k}={v:.3g}" for k, v in ov.items())
                                       or "none given; using the site nominal"))
    print("Flying the model ...")
    sim = simulate(vehicle, site, U.lb_to_kg(args.ballast_lb), ov)

    # One clock: shift the log so both cross 100 ft AGL together.
    t0_log = postflight.launch_time(log["time_s"], log["altitude_ft"])
    t0_sim = postflight.launch_time(sim["time_s"], sim["baro_altitude_ft"])
    log["t_sim_s"] = log["time_s"] - t0_log + t0_sim

    if "accel_z_g" in log:
        boost = (log["t_sim_s"] > t0_sim) & (log["t_sim_s"] < t0_sim + 0.5)
        if np.nanmedian(log.loc[boost, "accel_z_g"]) < 0:
            log["accel_z_g"] = -log["accel_z_g"]
            print("  note: axial acceleration reads negative under thrust -- board "
                  "mounted upside down? Flipped for the comparison.")

    sim_at = lambda col: np.interp(log["t_sim_s"], sim["time_s"], sim[col],  # noqa: E731
                                   left=np.nan, right=np.nan)
    pairs = {"altitude_ft": "baro_altitude_ft", "accel_z_g": "accel_z_g",
             "gyro_z_dps": "gyro_z_dps", "latitude_deg": "latitude_deg",
             "longitude_deg": "longitude_deg"}
    for meas, simcol in pairs.items():
        if meas in log:
            log[f"sim_{meas}"] = sim_at(simcol)
    sim["lateral_accel_g"] = np.hypot(sim["accel_x_g"], sim["accel_y_g"])
    sim["lateral_rate_dps"] = np.hypot(sim["gyro_x_dps"], sim["gyro_y_dps"])
    if {"accel_x_g", "accel_y_g"} <= set(log):
        log["lateral_accel_g"] = np.hypot(log["accel_x_g"], log["accel_y_g"])
        log["sim_lateral_accel_g"] = sim_at("lateral_accel_g")
    if {"gyro_x_dps", "gyro_y_dps"} <= set(log):
        log["lateral_rate_dps"] = np.hypot(log["gyro_x_dps"], log["gyro_y_dps"])
        log["sim_lateral_rate_dps"] = sim_at("lateral_rate_dps")

    # --- summary
    apo_sim = sim["baro_altitude_ft"].max()
    rows = [("Apogee (baro)", "ft", apo_sim, log["altitude_ft"].max()),
            ("Time to apogee", "s", sim.loc[sim["baro_altitude_ft"].idxmax(), "time_s"],
             log.loc[log["altitude_ft"].idxmax(), "t_sim_s"])]
    if "accel_z_g" in log:
        rows.append(("Max axial acceleration", "g", sim["accel_z_g"].max(),
                     log["accel_z_g"].max()))
    gps = {"latitude_deg", "longitude_deg"} <= set(log)
    if gps:
        lat0, lon0 = site.latitude, site.longitude
        se, sn = postflight.local_ft(sim["latitude_deg"], sim["longitude_deg"], lat0, lon0)
        fix = log[["latitude_deg", "longitude_deg"]].dropna()
        le, ln = postflight.local_ft(fix["latitude_deg"], fix["longitude_deg"],
                                     fix["latitude_deg"].iloc[0], fix["longitude_deg"].iloc[0])
        rows.append(("Landing distance from pad", "ft", float(np.hypot(se[-1], sn[-1])),
                     float(np.hypot(le[-1], ln[-1]))))
    summary = pd.DataFrame(rows, columns=["quantity", "units", "simulated", "measured"])
    summary["difference"] = summary["measured"] - summary["simulated"]
    print()
    print(report.table(summary, "{:.2f}"))

    # --- figure: one panel per channel the log has
    apogee_t = float(sim.loc[sim["baro_altitude_ft"].idxmax(), "time_s"])
    panels = [("Altitude", "ft", "altitude_ft", "baro_altitude_ft", None)]
    if "accel_z_g" in log:
        panels.append(("Axial acceleration", "g", "accel_z_g", "accel_z_g", apogee_t))
    if "lateral_accel_g" in log:
        panels.append(("Lateral acceleration (magnitude)", "g", "lateral_accel_g",
                       "lateral_accel_g", apogee_t))
    if "gyro_z_dps" in log:
        panels.append(("Roll rate", "deg/s", "gyro_z_dps", "gyro_z_dps", apogee_t))
    if "lateral_rate_dps" in log:
        panels.append(("Pitch/yaw rate (magnitude)", "deg/s", "lateral_rate_dps",
                       "lateral_rate_dps", apogee_t))
    n = len(panels) + gps
    fig, axes = plt.subplots(n, 1, figsize=(9, 2.8 * n), squeeze=False)
    for ax, (title, unit, meas, simcol, t_end) in zip(axes[:, 0], panels):
        keep = log["t_sim_s"] <= (t_end + 2.0 if t_end else np.inf)
        keep_s = sim["time_s"] <= (t_end + 2.0 if t_end else np.inf)
        ax.plot(log.loc[keep, "t_sim_s"], log.loc[keep, meas], color=report.NEUTRAL,
                lw=0.9, alpha=0.8, label="measured")
        ax.plot(sim.loc[keep_s, "time_s"], sim.loc[keep_s, simcol], color=report.ACCENT,
                lw=1.6, label="simulated")
        report._style(ax, title, "Time from ignition (s)", unit)
        ax.legend(fontsize=8, frameon=False)
    if gps:
        ax = axes[-1, 0]
        ax.plot(le, ln, color=report.NEUTRAL, lw=0.9, label="measured (GPS)")
        ax.plot(se, sn, color=report.ACCENT, lw=1.6, label="simulated")
        ax.plot(0, 0, "k^", ms=6, label="pad")
        ax.set_aspect("equal", adjustable="datalim")
        report._style(ax, "Ground track", "East of pad (ft)", "North of pad (ft)")
        ax.legend(fontsize=8, frameon=False)
    fig.tight_layout()

    out_dir = output_dir(args.out, vehicle, "postflight")
    stem = Path(args.csv).stem
    png = report._save(fig, out_dir, f"comparison_{stem}.png")
    csv = out_dir / f"comparison_{stem}.csv"
    log.to_csv(csv, index=False, float_format="%.6g")
    print()
    print(f"  Wrote {png}")
    print(f"  Wrote {csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
