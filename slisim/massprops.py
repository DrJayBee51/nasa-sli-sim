"""Mass-properties worksheets: config/mass/*.csv.

One row per part: its mass, and where it sits measured from the front of the
section it is in.  A SECTION row closes each section with its length and that
section's totals, and an AGGREGATE block combines the sections into the
vehicle.  USER_GUIDE section 2.10 describes the layout for the people filling
it in.

The derived cells -- positions from the nose tip, moments, every total -- are
stored so a student can follow the arithmetic, and are trusted only after
`read()` recomputes them.  Writing and checking both go through `table()`, so
the generator and the checker cannot disagree about what a correct sheet is.

Rounding is half-up, the way a spreadsheet's ROUND() does it, and every total
sums the values as printed, so a column adds up exactly as it reads.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

COLUMNS = ["section", "component", "kind", "mass_lb", "length_in",
           "section_front_in", "from_section_front_in", "from_nose_tip_in",
           "moment_lb_in", "source", "note"]
NUMERIC = ("mass_lb", "length_in", "section_front_in", "from_section_front_in",
           "from_nose_tip_in", "moment_lb_in")

#  What a part counts toward.  `section` says where it physically is; `kind` says
#  which part of the vehicle model it belongs to, so a parachute packed in the
#  payload tube is still the main.  `tethered` is structure that rides in its
#  section on the pad but lands on its own tether (req 3.2).
KINDS = ("structure", "tethered", "fins", "main", "drogue", "shock_cord")
SOURCES = ("weighed", "cad", "vendor", "override", "ork", "estimated", "CONFIRM")

SECTION, AGGREGATE, TOTAL = "SECTION", "AGGREGATE", "VEHICLE TOTAL"
#  Mass to three decimals: a rail button is 0.002 lb, and two would drop it.
MASS_DP, STATION_DP = Decimal("0.001"), Decimal("0.01")


def q(x, dp: Decimal) -> Decimal:
    """Half-up -- how a spreadsheet rounds.  Python's round() is banker's."""
    return Decimal(x).quantize(dp, rounding=ROUND_HALF_UP)


@dataclass
class Part:
    section: str
    component: str
    kind: str
    mass_lb: Decimal
    from_front_in: Decimal      # from the front of its own section
    source: str
    note: str = ""


@dataclass
class Sheet:
    sections: list[tuple[str, Decimal]]     # (name, length_in), nose to tail
    parts: list[Part]

    def fronts(self) -> dict[str, Decimal]:
        """Each section's front station from the nose tip: the lengths before it."""
        out, x = {}, Decimal(0)
        for name, length in self.sections:
            out[name] = x
            x += length
        return out


def table(sheet: Sheet) -> list[list | None]:
    """Every row of the worksheet with its derived cells filled in.

    None marks a blank separator line.
    """
    fronts = sheet.fronts()
    rows: list[list | None] = []
    totals = []
    for name, length in sheet.sections:
        front, mass, moment = fronts[name], Decimal(0), Decimal(0)
        for p in (p for p in sheet.parts if p.section == name):
            x = front + p.from_front_in
            m = q(p.mass_lb * x, MASS_DP)
            rows.append([name, p.component, p.kind, p.mass_lb, "", "",
                         p.from_front_in, x, m, p.source, p.note])
            mass += p.mass_lb
            moment += m
        cg = q(moment / mass, STATION_DP) if mass else ""
        rows.append([name, SECTION, "", mass, length, front,
                     cg - front if mass else "", cg, moment, "", ""])
        rows.append(None)
        totals.append((name, mass, length, front, cg, moment))

    for name, mass, length, front, cg, moment in totals:
        rows.append([AGGREGATE, name, "", mass, length, front, "", cg, moment, "", ""])
    mass = sum(t[1] for t in totals)
    moment = sum(t[5] for t in totals)
    rows.append([AGGREGATE, TOTAL, "", mass, sum(t[2] for t in totals), "", "",
                 q(moment / mass, STATION_DP) if mass else "", moment, "",
                 "dry: no motor, no ballast"])
    return rows


def write(sheet: Sheet, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS)
        for row in table(sheet):
            w.writerow([] if row is None else row)


def _dec(text: str) -> Decimal | None:
    try:
        return Decimal(text.strip())
    except (InvalidOperation, AttributeError):
        return None


def read(path: Path) -> tuple[Sheet | None, list[str]]:
    """Parse a worksheet and recompute every derived cell.

    Returns the sheet and a list of problems, each naming the line a student
    would look at in Excel.  The sheet is None when the inputs themselves are
    unreadable; when only derived cells disagree it is returned, because the
    inputs are what the simulation uses.
    """
    problems: list[str] = []
    # utf-8-sig, because Excel's "CSV UTF-8" puts a byte-order mark first.
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = [h.strip() for h in next(reader, [])]
        lines = [(reader.line_num, r) for r in reader if any(c.strip() for c in r)]

    missing = [c for c in COLUMNS if c not in header]
    if missing:
        return None, [f"line 1: missing column(s) {missing}; expected {COLUMNS}"]
    col = {c: header.index(c) for c in COLUMNS}

    def cell(row, name):
        i = col[name]
        return row[i].strip() if i < len(row) else ""

    sections: list[tuple[str, Decimal]] = []
    parts: list[Part] = []
    current = None
    seen_aggregate = False
    for ln, r in lines:
        sec, comp = cell(r, "section"), cell(r, "component")
        if sec == AGGREGATE:
            seen_aggregate = True
            continue
        if seen_aggregate:
            problems.append(f"line {ln}: {sec} / {comp} comes after the AGGREGATE block")
            continue
        if comp == SECTION:
            if sec != current:
                problems.append(f"line {ln}: SECTION row for {sec!r} has no parts above it")
            length = _dec(cell(r, "length_in"))
            if length is None or length <= 0:
                problems.append(f"line {ln}: {sec} length_in {cell(r, 'length_in')!r} "
                                f"is not a positive number")
                length = Decimal(0)
            sections.append((sec, length))
            current = None
            continue
        if current is None:
            if any(sec == name for name, _ in sections):
                problems.append(f"line {ln}: {sec!r} appears twice; keep each "
                                f"section's parts together above its SECTION row")
            current = sec
        elif sec != current:
            problems.append(f"line {ln}: {sec!r} starts before {current!r} "
                            f"has its SECTION row")
            current = sec
        kind, source = cell(r, "kind"), cell(r, "source")
        mass, x = _dec(cell(r, "mass_lb")), _dec(cell(r, "from_section_front_in"))
        where = f"line {ln}, {sec} / {comp}"
        if kind not in KINDS:
            problems.append(f"{where}: kind {kind!r} is not one of {list(KINDS)}")
        if source not in SOURCES:
            problems.append(f"{where}: source {source!r} is not one of {list(SOURCES)}")
        if mass is None or mass < 0:
            problems.append(f"{where}: mass_lb {cell(r, 'mass_lb')!r} is not a number >= 0")
        if x is None:
            problems.append(f"{where}: from_section_front_in "
                            f"{cell(r, 'from_section_front_in')!r} is not a number")
        parts.append(Part(sec, comp, kind, mass or Decimal(0), x or Decimal(0),
                          source, cell(r, "note")))
    if current is not None:
        problems.append(f"{current!r} has no SECTION row closing it")
    if not sections:
        problems.append("no sections")
    if problems:
        return None, problems

    sheet = Sheet(sections, parts)
    expected = [row for row in table(sheet) if row is not None]
    for want, (ln, got) in zip(expected, lines):
        label = (cell(got, "section"), cell(got, "component"))
        if label != (want[0], want[1]):
            problems.append(f"line {ln}: expected {want[0]} / {want[1]} here, "
                            f"found {label[0]} / {label[1]}")
            break
        for name in NUMERIC:
            w, text = want[COLUMNS.index(name)], cell(got, name)
            if w == "":
                if text:
                    problems.append(f"line {ln}, {label[0]} / {label[1]}: "
                                    f"{name} should be blank")
            elif _dec(text) != w:
                problems.append(f"line {ln}, {label[0]} / {label[1]}: {name} "
                                f"reads {text or 'blank'} but works out to {w}")
    else:
        if len(expected) != len(lines):
            problems.append(f"the AGGREGATE block should have {len(sections) + 1} "
                            f"rows: one per section, then {TOTAL}")
    return sheet, problems


def rollup(sheet: Sheet) -> dict:
    """Mass and CG for each section and each non-structure kind, unrounded.

    Stations are inches from the nose tip.  A section's mass is its structure
    and tethered parts -- what the airframe carries -- while fins and recovery
    gear are totalled by kind, wherever they are packed.
    """
    fronts = sheet.fronts()

    def total(parts):
        m = sum(float(p.mass_lb) for p in parts)
        mx = sum(float(p.mass_lb) * float(fronts[p.section] + p.from_front_in)
                 for p in parts)
        return m, (mx / m if m else None)

    sections = {}
    for name, length in sheet.sections:
        mass, cg = total([p for p in sheet.parts if p.section == name
                          and p.kind in ("structure", "tethered")])
        sections[name] = {"length_in": float(length), "front_in": float(fronts[name]),
                          "mass_lb": mass, "cg_in": cg}
    kinds = {}
    for kind in ("fins", "main", "drogue", "shock_cord"):
        parts = [p for p in sheet.parts if p.kind == kind]
        if parts:
            mass, cg = total(parts)
            kinds[kind] = {"mass_lb": mass, "cg_in": cg}
    tethered = [(p.component, p.section, float(p.mass_lb))
                for p in sheet.parts if p.kind == "tethered"]
    return {"sections": sections, "kinds": kinds, "tethered": tethered}
