"""Check that every derived cell in a mass-properties worksheet still adds up.

    python scripts/check_mass_csv.py

The worksheets in `config/mass/` store derived cells -- positions from the nose
tip, moments, and every SECTION and AGGREGATE total -- so a student can follow
the arithmetic.  A hand-edited file goes stale: change one mass and the moment
beside it is quietly wrong, and so is every total below it.

This recomputes all of it, using the same code the loader uses
(`slisim.massprops`), so the checker and the simulation cannot disagree about
what a correct sheet is.  Run it after editing a worksheet.  Exits 0 if every
sheet is correct, 1 otherwise.

It also checks `massprops.state`, which the simulation flies: its nominal must
match each sheet's VEHICLE TOTAL, and its Monte Carlo draws must scatter
around the nominal by the sigmas asked for.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from decimal import Decimal as D  # noqa: E402

import numpy as np  # noqa: E402

from slisim import massprops  # noqa: E402
from slisim.config import CONFIG_DIR  # noqa: E402

MASS_DIR = CONFIG_DIR / "mass"


def state_problems(sheet: massprops.Sheet) -> list[str]:
    """Nominal state() vs the sheet's own VEHICLE TOTAL row.

    The sheet rounds each section CG to 0.01 in before combining, which moves
    a printed pitch total by a few hundredths of a percent; state() does not.
    """
    total = massprops.table(sheet)[-1]
    want = {"mass_lb": (total[3], 0.002), "cg_in": (total[9], 0.01),
            "inertia_pitch": (total[11], 0.05 + 5e-4 * float(total[11]))}
    got = massprops.state(sheet)
    return [f"state() {k} = {got[k]:.3f}, VEHICLE TOTAL says {w}"
            for k, (w, tol) in want.items() if abs(got[k] - float(w)) > tol]


def check_draws() -> None:
    """Draws must scatter by the sigmas asked for, and leave a 0 exact."""
    sheet = massprops.Sheet(
        [("A", D(10)), ("B", D(10))],
        [massprops.Part("A", "a", "structure", D(2), D(5), "estimated",
                        inertia_pitch=D(10), inertia_roll=D(1),
                        mass_sigma_pct=D(10), position_sigma_in=D(1)),
         massprops.Part("B", "b", "tethered", D(1), D(5), "estimated")])
    rng = np.random.default_rng(1)
    draws = [massprops.state(sheet, rng) for _ in range(4000)]
    m = np.array([d["mass_lb"] for d in draws])
    a = np.array([d["members"]["nose_cone"] for d in draws])  # first section
    b = np.array([d["members"]["b"] for d in draws])
    assert abs(m.mean() - 3.0) < 0.01, m.mean()
    assert abs(a.std() - 0.2) < 0.01, a.std()          # 10% of 2 lb
    assert b.std() == 0 and b[0] == 1.0                 # sigma 0 stays exact
    assert np.array([d["cg_in"] for d in draws]).std() > 0.3   # position sigma
    nominal = massprops.state(sheet)
    assert nominal["members"] == {"nose_cone": 2.0, "b": 1.0}
    assert massprops.state(sheet, None, 0.5, "B")["members"]["B"] == 0.5


def main() -> int:
    files = sorted(MASS_DIR.glob("*.csv"))
    if not files:
        print(f"No worksheets in {MASS_DIR}")
        return 1

    check_draws()
    failed = 0
    for path in files:
        sheet, problems = massprops.read(path)
        if sheet is not None and not problems:
            problems = state_problems(sheet)
        if problems:
            failed += 1
            print(f"  FAIL  {path.name}")
            for line in problems:
                print(f"          {line}")
        else:
            print(f"  pass  {path.name}")

    if failed:
        print(f"\n{failed} of {len(files)} worksheets have problems.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
