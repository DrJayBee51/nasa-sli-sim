"""Plot the uncertainty model: every parameter the framework can disperse.

    python scripts/plot_inputs.py
    python scripts/plot_inputs.py -n 2000 --seed 999
    python scripts/plot_inputs.py --engine openrocket   # the six it consumes

One histogram per parameter in config/uncertainty.yaml, in the units the
quantity is actually measured in -- pounds, N-s, feet AGL -- rather than the
multiplier that was drawn.

No flights are run.  A campaign draws all of its samples up front, so the same
`(seed, N, site, uncertainty)` regenerates them exactly; this script does that
and stops, which is why it takes seconds.  Pass the seed a campaign used and
these are the values it flew.

This shows what the framework *can* disperse.  For what one campaign actually
did disperse -- where --only and --freeze have been applied -- use the
inputs_*.png that run_montecarlo.py writes alongside its results.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from slisim import montecarlo, report  # noqa: E402
from slisim.config import Site, Vehicle, load_uncertainty  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "output"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", "--samples", type=int, default=1000,
                    help="draws per parameter (default 1000; costs milliseconds)")
    ap.add_argument("--seed", type=int, default=12345,
                    help="pass a campaign's seed to plot the values it flew")
    ap.add_argument("--engine", default="rocketpy", choices=["rocketpy", "openrocket"],
                    help="openrocket shows only the six launch conditions it consumes")
    ap.add_argument("--vehicle", default=None)
    ap.add_argument("--site", default=None)
    ap.add_argument("--ballast", default="min", choices=["min", "max"])
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--name", default="input_model.png")
    args = ap.parse_args()

    vehicle = Vehicle.from_yaml(args.vehicle)
    site = Site.from_yaml(args.site)
    ballast = (vehicle.ballast_min_kg if args.ballast == "min"
               else vehicle.ballast_max_kg)
    unc = load_uncertainty()          # unfiltered: the whole model, by design

    print(f"Sampling {args.samples} draws of {len(unc)} parameters"
          f"  (seed {args.seed}, site {site.key})")

    # The same loop run_montecarlo uses, including the per-case _seed draw that
    # advances the rng between samples -- omit it and every draw after the first
    # desynchronizes from the campaign this is meant to reproduce.
    rng = np.random.default_rng(args.seed)
    draws = []
    for _ in range(args.samples):
        sample = montecarlo.draw_sample(unc, site, rng)
        rng.integers(0, 2 ** 31 - 1)
        draws.append(sample)
    df = pd.DataFrame(draws).add_prefix("in_")

    # Nominal mass, CG and motor data come from OpenRocket, so this boots the
    # JVM once (~30 s).  It flies nothing.
    print("Reading nominal mass and motor properties from OpenRocket ...")
    nominals = montecarlo.nominal_values(vehicle, site, ballast)

    png = report.plot_input_distributions(df, Path(args.out), unc, args.engine,
                                          args.name, nominals)
    print(f"  Wrote {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
