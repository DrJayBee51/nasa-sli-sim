"""Generate a synthetic altimeter CSV.

Two uses:

1. The team can exercise the whole post-flight pipeline before they have real
   flight data, so the FRR analysis is not being written for the first time the
   week the data arrives.
2. It validates `fit_cd.py`: generate a trace with a KNOWN drag scale, then
   check the fitter recovers it.  A fitter nobody has tested against a known
   answer is not evidence of anything.

    python scripts/make_synthetic_flight.py --cd-scale 1.18 --noise-ft 8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from slisim import or_bridge as orb, rocketpy_model as rpm, units as U  # noqa: E402
from slisim.config import Site, Vehicle  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "flights"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cd-scale", type=float, default=1.15,
                    help="true drag scale to bake into the synthetic flight")
    ap.add_argument("--noise-ft", type=float, default=6.0,
                    help="1-sigma barometric noise")
    ap.add_argument("--rate-hz", type=float, default=20.0)
    ap.add_argument("--wind-mph", type=float, default=9.0)
    ap.add_argument("--temp-f", type=float, default=68.0)
    ap.add_argument("--vehicle", default=None)
    ap.add_argument("--site", default=None)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(OUT / "synthetic_vdf.csv"))
    args = ap.parse_args()

    vehicle = Vehicle.from_yaml(args.vehicle)
    site = Site.from_yaml(args.site)
    rng = np.random.default_rng(args.seed)

    overrides = {
        "wind_speed_mps": U.mph_to_mps(args.wind_mph),
        "temperature_k": U.f_to_k(args.temp_f),
    }

    doc, rocket, _m, motor = orb.build_document(vehicle)
    base = orb.run_simulation(orb.make_simulation(doc, rocket, site, overrides),
                              rocket, keep_series=True)
    power_on, power_off = rpm.export_drag_curves(base)
    mass_props = rpm.export_mass_properties(rocket, orb.ensure_jvm())

    env = rpm.build_environment(site, overrides)
    rk = rpm.build_rocket(vehicle, motor, mass_props, power_on, power_off,
                          drag_scale=args.cd_scale)
    res = rpm.extract(rpm.build_flight(rk, env, site, overrides), rk, motor)

    s = res.series
    t = np.arange(0.0, float(s["time_s"][-1]), 1.0 / args.rate_hz)
    alt_m = np.interp(t, s["time_s"], s["altitude_m"])
    alt_ft = U.m_to_ft(alt_m) + rng.normal(0.0, args.noise_ft, size=t.size)
    vel_fps = U.mps_to_fps(np.interp(t, s["time_s"], s["velocity_z_mps"]))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "Time (s)": np.round(t, 3),
        "Altitude (ft)": np.round(alt_ft, 1),
        "Velocity (ft/s)": np.round(vel_fps, 1),
    }).to_csv(out, index=False)

    print(f"Wrote {out}")
    print(f"  TRUE drag scale baked in : {args.cd_scale:.4f}")
    print(f"  Apogee                   : {U.m_to_ft(res.apogee_m):,.0f} ft")
    print(f"  Baro noise               : {args.noise_ft:.1f} ft 1-sigma "
          f"at {args.rate_hz:.0f} Hz")
    print()
    print("Recover the drag scale with:")
    print(f"  python scripts/fit_cd.py {out} --wind {args.wind_mph} "
          f"--temp-f {args.temp_f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
