"""Check that every derived cell in a mass-properties worksheet still adds up.

    python scripts/check_mass_csv.py

The worksheets in `config/mass/` carry derived columns -- `moment_lb_in` on every
row, and the mass/CG/moment of each `SUBTOTAL` and `AGGREGATE` row -- because a
student should be able to read the arithmetic rather than take a loader's word
for it.  Derived data in a hand-edited file goes stale: change one mass and the
moment beside it is quietly wrong, and so is every total above it.

This recomputes all of it.  Run it after editing a worksheet.  Exits 0 if every
cell agrees, 1 otherwise, so it also works as a pre-commit check.

Rounding is half-up, matching what a spreadsheet shows, and totals sum the
*printed* values -- the column adds up exactly as it reads on the page, which is
the whole point of showing the arithmetic.

Mass and moment carry three decimals, not two: a rail button is 0.002 lb and
two decimals would round it to nothing.
"""

from __future__ import annotations

import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from slisim.config import CONFIG_DIR  # noqa: E402

MASS_DIR = CONFIG_DIR / "mass"
#  `ork` and `override` are what scripts/ork_to_mass_csv.py emits: OpenRocket
#  computed the mass from a material density, or a human typed it in (an override,
#  or a mass component whose mass IS its definition).  They are real provenance
#  and distinct from `estimated` -- an `ork` mass moves once the part is built.
SOURCES = {"weighed", "vendor", "override", "ork", "estimated", "CONFIRM"}
AGG, SUB, TOTAL = "AGGREGATE", "SUBTOTAL", "VEHICLE TOTAL"

#  Mass and moment to three decimals: a rail button is 0.002 lb, and two
#  decimals would print it as 0.00 and drop it from the budget.
MASS_DP, STATION_DP = Decimal("0.001"), Decimal("0.01")


def q(x, dp: Decimal) -> Decimal:
    """Half-up to `dp` -- how a spreadsheet rounds, not how Python does."""
    return Decimal(x).quantize(dp, rounding=ROUND_HALF_UP)


def check_file(path: Path) -> list[str]:
    """Every disagreement in one worksheet, as human-readable lines."""
    # dtype=str so we compare the cells as printed.  Parsing to float first
    # would hide a cell that reads 26.32 where the arithmetic gives 26.33.
    df = pd.read_csv(path, comment="#", dtype=str).fillna("")
    bad: list[str] = []

    def dec(row, col) -> Decimal | None:
        try:
            return Decimal(row[col].strip())
        except Exception:
            bad.append(f"{row['section']} / {row['component']}: {col} "
                       f"{row[col]!r} is not a number")
            return None

    def expect(where: str, col: str, got: Decimal, want: Decimal) -> None:
        if got != want:
            bad.append(f"{where}: {col} reads {got} but recomputes to {want}")

    rows = [r for _, r in df.iterrows()]
    parts = {}        # section -> list of part rows
    subtotals = {}    # section -> subtotal row
    aggregate = {}    # section name -> aggregate row
    total = None

    for r in rows:
        sec, comp = r["section"].strip(), r["component"].strip()
        if sec == AGG:
            if comp == TOTAL:
                total = r
            else:
                aggregate[comp] = r
        elif comp == SUB:
            if sec in subtotals:
                bad.append(f"{sec}: more than one {SUB} row")
            subtotals[sec] = r
        else:
            parts.setdefault(sec, []).append(r)

    # --- part rows: moment = mass * station -----------------------------
    for sec, rs in parts.items():
        for r in rs:
            m, x, mo = dec(r, "mass_lb"), dec(r, "station_in"), dec(r, "moment_lb_in")
            if None in (m, x, mo):
                continue
            expect(f"{sec} / {r['component'].strip()}", "moment_lb_in", mo,
                   q(m * x, MASS_DP))
            src = r["source"].strip()
            if src not in SOURCES:
                bad.append(f"{sec} / {r['component'].strip()}: source {src!r} "
                           f"is not one of {sorted(SOURCES)}")

    # --- subtotal rows: the section's mass, moment, and CG ---------------
    for sec, rs in parts.items():
        if sec not in subtotals:
            bad.append(f"{sec}: no {SUB} row")
            continue
        s = subtotals[sec]
        M = sum(q(dec(r, "mass_lb") or 0, MASS_DP) for r in rs)
        Mo = sum(q(dec(r, "moment_lb_in") or 0, MASS_DP) for r in rs)
        sm, sx, smo = dec(s, "mass_lb"), dec(s, "station_in"), dec(s, "moment_lb_in")
        if None in (sm, sx, smo):
            continue
        expect(f"{sec} / {SUB}", "mass_lb", sm, M)
        expect(f"{sec} / {SUB}", "moment_lb_in", smo, Mo)
        if M:
            expect(f"{sec} / {SUB}", "station_in (= CG)", sx, q(Mo / M, STATION_DP))

    for sec in subtotals:
        if sec not in parts:
            bad.append(f"{sec}: {SUB} row with no parts above it")

    # --- aggregate table: the subtotals, one level up -------------------
    for sec, s in subtotals.items():
        if sec not in aggregate:
            bad.append(f"{AGG}: {sec} is missing; every section belongs here")
            continue
        a = aggregate[sec]
        for col in ("mass_lb", "station_in", "moment_lb_in"):
            got, want = dec(a, col), dec(s, col)
            if got is not None and want is not None:
                expect(f"{AGG} / {sec}", col, got, want)
    for sec in aggregate:
        if sec not in subtotals:
            bad.append(f"{AGG} / {sec}: no section by that name")

    if total is None:
        bad.append(f"{AGG}: no {TOTAL!r} row")
    elif aggregate:
        M = sum(q(dec(a, "mass_lb") or 0, MASS_DP) for a in aggregate.values())
        Mo = sum(q(dec(a, "moment_lb_in") or 0, MASS_DP) for a in aggregate.values())
        tm, tx, tmo = dec(total, "mass_lb"), dec(total, "station_in"), dec(total, "moment_lb_in")
        if None not in (tm, tx, tmo):
            expect(TOTAL, "mass_lb", tm, M)
            expect(TOTAL, "moment_lb_in", tmo, Mo)
            if M:
                expect(TOTAL, "station_in (= CG)", tx, q(Mo / M, STATION_DP))

    return bad


def main() -> int:
    files = sorted(MASS_DIR.glob("*.csv"))
    if not files:
        print(f"No worksheets in {MASS_DIR}")
        return 1

    failed = 0
    for path in files:
        bad = check_file(path)
        if bad:
            failed += 1
            print(f"  FAIL  {path.name}")
            for line in bad:
                print(f"          {line}")
        else:
            print(f"  pass  {path.name}")

    if failed:
        print(f"\n{failed} of {len(files)} worksheets have stale or wrong cells.")
        print("Fix the mass or station, then update the moment and the totals above it.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
