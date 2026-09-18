"""Check that plot_inputs.py regenerates a campaign's inputs exactly.

    python scripts/check_plot_inputs.py

plot_inputs.py draws samples itself instead of reading a campaign CSV, which is
only sound if the same (seed, N, site, uncertainty) reproduces the campaign's
draws.  This flies 20 real cases and compares.

Exits 0 if the draws match, 1 otherwise.  Run it after touching draw_sample,
run_montecarlo's sampling loop, or plot_inputs' replica of it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402

from slisim import montecarlo as mc  # noqa: E402
from slisim.config import Site, Vehicle, load_uncertainty  # noqa: E402

N, SEED = 20, 4242


def main() -> int:
    vehicle = Vehicle.from_yaml(None)
    site = Site.from_yaml(None)
    unc = load_uncertainty()

    print(f"Flying {N} cases (seed {SEED}) ...")
    df = mc.run_montecarlo(vehicle, site, n=N, engine="rocketpy",
                           ballast_kg=vehicle.ballast_min_kg, seed=SEED,
                           workers=2, uncertainty=unc, progress=False)
    flown = df.sort_values("index")

    # plot_inputs.py's loop, verbatim.
    rng = np.random.default_rng(SEED)
    regenerated = []
    for _ in range(N):
        sample = mc.draw_sample(unc, site, rng)
        rng.integers(0, 2 ** 31 - 1)
        regenerated.append(sample)

    # Compare in memory, never through a CSV: to_csv shortens floats, which
    # costs ~1e-13 of relative precision and would mask a real divergence.
    worst, worst_param = 0.0, ""
    for param in [c[len("in_"):] for c in flown.columns if c.startswith("in_")]:
        a = flown[f"in_{param}"].to_numpy()
        b = np.array([s[param] for s in regenerated])
        if a.shape != b.shape:
            print(f"  FAIL {param}: {a.shape} flown vs {b.shape} regenerated")
            return 1
        if not np.array_equal(a, b):
            rel = float(np.abs((a - b) / np.where(a == 0, 1, a)).max())
            if rel > worst:
                worst, worst_param = rel, param

    if worst:
        print(f"  FAIL  draws diverge; worst is {worst_param} at {worst:.2e} relative")
        print("        plot_inputs.py no longer reproduces a campaign -- check that")
        print("        its loop still consumes the rng exactly as run_montecarlo does")
        return 1

    print(f"  pass  all 16 parameters bit-identical across {N} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
