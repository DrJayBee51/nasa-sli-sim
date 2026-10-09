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
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from slisim import massprops  # noqa: E402
from slisim.config import CONFIG_DIR  # noqa: E402

MASS_DIR = CONFIG_DIR / "mass"


def main() -> int:
    files = sorted(MASS_DIR.glob("*.csv"))
    if not files:
        print(f"No worksheets in {MASS_DIR}")
        return 1

    failed = 0
    for path in files:
        _sheet, problems = massprops.read(path)
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
