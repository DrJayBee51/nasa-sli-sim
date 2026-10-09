"""Mass-properties worksheets: config/mass/*.csv.

One row per part: its mass, where it sits measured from the front of the
section it is in, its own inertia, and the uncertainty in each.  A SECTION row
closes each section with its length and that section's totals, and an
AGGREGATE block combines the sections into the vehicle.  USER_GUIDE section
2.10 describes the layout for the people filling it in.

The derived cells -- positions from the nose tip, moments, every total -- are
stored so a student can follow the arithmetic, and are trusted only after
`read()` recomputes them.  Writing and checking both go through `table()`, so
the generator and the checker cannot disagree about what a correct sheet is.

Rounding is half-up, the way a spreadsheet's ROUND() does it, and every total
sums the values as printed, so a column adds up exactly as it reads.

Inertia is each part's own, about its own CG, in lb*in^2 -- SolidWorks' Mass
Properties "taken at the center of mass" (Lxx, Lyy, Lzz), with X along the
rocket axis.  Pitch is Lyy (average Lyy and Lzz if they differ), roll is Lxx.
A total's pitch inertia is about that total's CG, by the parallel-axis theorem;
roll needs no offset term, because every part sits on the rocket axis.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

COLUMNS = ["section", "component", "kind", "mass_lb", "mass_sigma_pct",
           "length_in", "section_front_in", "from_section_front_in",
           "position_sigma_in", "from_nose_tip_in", "moment_lb_in",
           "inertia_pitch_lb_in2", "inertia_roll_lb_in2", "inertia_sigma_pct",
           "source", "note"]
NUMERIC = ("mass_lb", "mass_sigma_pct", "length_in", "section_front_in",
           "from_section_front_in", "position_sigma_in", "from_nose_tip_in",
           "moment_lb_in", "inertia_pitch_lb_in2", "inertia_roll_lb_in2",
           "inertia_sigma_pct")

#  What a part counts toward.  `section` says where it physically is; `kind` says
#  which part of the vehicle model it belongs to, so a parachute packed in the
#  payload tube is still the main.  `tethered` is structure that rides in its
#  section on the pad but lands on its own tether (req 3.2).
KINDS = ("structure", "tethered", "fins", "main", "drogue", "shock_cord")
SOURCES = ("weighed", "cad", "vendor", "override", "ork", "estimated", "CONFIRM")

SECTION, AGGREGATE, TOTAL = "SECTION", "AGGREGATE", "VEHICLE TOTAL"
#  Mass to three decimals: a rail button is 0.002 lb, and two would drop it.
MASS_DP, STATION_DP, INERTIA_DP = Decimal("0.001"), Decimal("0.01"), Decimal("0.001")


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
    inertia_pitch: Decimal = Decimal(0)     # own, about own CG, lb*in^2
    inertia_roll: Decimal = Decimal(0)
    mass_sigma_pct: Decimal = Decimal(0)
    position_sigma_in: Decimal = Decimal(0)
    inertia_sigma_pct: Decimal = Decimal(0)


@dataclass
class Sheet:
    sections: list[tuple[str, Decimal]]     # (name, length_in), nose to tail
    parts: list[Part]

    def fronts(self) -> dict[str, Decimal]:
        """Each section's front station from the nose tip: the lengths before it."""
        out, x = {}, Decimal("0.00")
        for name, length in self.sections:
            out[name] = x
            x += length
        return out


def combine(items) -> tuple[Decimal, Decimal | str, Decimal, Decimal, Decimal]:
    """(mass, CG, moment, pitch, roll) of items given as (mass, x, pitch, roll).

    Uses the values as printed, so the totals follow from the cells above them.
    """
    items = list(items)
    mass = sum((m for m, _, _, _ in items), Decimal(0))
    moment = sum((q(m * x, MASS_DP) for m, x, _, _ in items), Decimal(0))
    if not mass:
        return mass, "", moment, Decimal(0), Decimal(0)
    cg = q(moment / mass, STATION_DP)
    pitch = q(sum((ip + m * (x - cg) ** 2 for m, x, ip, _ in items), Decimal(0)),
              INERTIA_DP)
    roll = sum((ir for _, _, _, ir in items), Decimal(0))
    return mass, cg, moment, pitch, roll


def table(sheet: Sheet) -> list[list | None]:
    """Every row of the worksheet with its derived cells filled in.

    None marks a blank separator line.
    """
    fronts = sheet.fronts()
    rows: list[list | None] = []
    totals = []
    for name, length in sheet.sections:
        front, items = fronts[name], []
        for p in (p for p in sheet.parts if p.section == name):
            x = front + p.from_front_in
            rows.append([name, p.component, p.kind, p.mass_lb, p.mass_sigma_pct,
                         "", "", p.from_front_in, p.position_sigma_in, x,
                         q(p.mass_lb * x, MASS_DP), p.inertia_pitch, p.inertia_roll,
                         p.inertia_sigma_pct, p.source, p.note])
            items.append((p.mass_lb, x, p.inertia_pitch, p.inertia_roll))
        mass, cg, moment, pitch, roll = combine(items)
        rows.append([name, SECTION, "", mass, "", length, front,
                     cg - front if mass else "", "", cg, moment, pitch, roll,
                     "", "", ""])
        rows.append(None)
        totals.append((name, mass, length, front, cg, moment, pitch, roll))

    for name, mass, length, front, cg, moment, pitch, roll in totals:
        rows.append([AGGREGATE, name, "", mass, "", length, front, "", "", cg,
                     moment, pitch, roll, "", "", ""])
    mass, cg, moment, pitch, roll = combine(
        (t[1], t[4], t[6], t[7]) for t in totals if t[1])
    rows.append([AGGREGATE, TOTAL, "", mass, "", sum(t[2] for t in totals), "",
                 "", "", cg, moment, pitch, roll, "", "",
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
    if len(missing) == len(COLUMNS):
        return None, [f"line 1 is not the column-name row (it starts "
                      f"{','.join(header)[:40]!r}); the first line must be "
                      f"{','.join(COLUMNS)}"]
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
        where = f"line {ln}, {sec} / {comp}"
        if kind not in KINDS:
            problems.append(f"{where}: kind {kind!r} is not one of {list(KINDS)}")
        if source not in SOURCES:
            problems.append(f"{where}: source {source!r} is not one of {list(SOURCES)}")

        def number(name, minimum=None):
            v = _dec(cell(r, name))
            if v is None:
                problems.append(f"{where}: {name} {cell(r, name)!r} is not a number"
                                + (" (a sigma of 0 means exact)" if "sigma" in name else ""))
                return Decimal(0)
            if minimum is not None and v < minimum:
                problems.append(f"{where}: {name} {v} is below {minimum}")
            return v

        parts.append(Part(
            sec, comp, kind,
            mass_lb=number("mass_lb", 0),
            from_front_in=number("from_section_front_in"),
            source=source, note=cell(r, "note"),
            inertia_pitch=number("inertia_pitch_lb_in2", 0),
            inertia_roll=number("inertia_roll_lb_in2", 0),
            mass_sigma_pct=number("mass_sigma_pct", 0),
            position_sigma_in=number("position_sigma_in", 0),
            inertia_sigma_pct=number("inertia_sigma_pct", 0),
        ))
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
