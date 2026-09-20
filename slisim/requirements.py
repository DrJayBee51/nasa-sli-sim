"""USLI requirement checks, 2027 Student Launch Handbook.

Every check below cites the handbook paragraph it enforces so a reviewer (or a
student writing the verification matrix) can trace it back.  These are the
COLLEGE/UNIVERSITY requirements; the middle/high-school ruleset in the same
handbook has different altitude and impulse limits and is not implemented.

Design note: a check returns a *margin*, not just a boolean.  Monte Carlo then
gives a probability of compliance rather than a yes/no on one nominal run,
which is the whole reason for pairing RocketPy with OpenRocket.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from . import units as U
from .config import Vehicle

# Width of every horizontal rule the scripts print, so the requirement table
# and the banners around it line up.  Import this rather than repeating it.
TABLE_WIDTH = 104


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    NA = "N/A"


@dataclass
class Check:
    req: str          # handbook paragraph number
    title: str
    status: Status
    value: float | None
    limit: str        # human-readable limit
    units: str
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (Status.PASS, Status.NA)

    def __str__(self) -> str:
        val = "-" if self.value is None else f"{self.value:.2f}"
        return f"[{self.status.value:4s}] {self.req:8s} {self.title:38s} {val:>10s} {self.units:<8s} (limit {self.limit})"


# ---------------------------------------------------------------------------
#  Individual requirements
# ---------------------------------------------------------------------------
APOGEE_MIN_FT, APOGEE_MAX_FT = 4000.0, 6000.0
APOGEE_ZERO_LO_FT, APOGEE_ZERO_HI_FT = 3500.0, 6500.0
MAX_IMPULSE_NS = 5120.0
MIN_STABILITY_CAL = 2.0
MIN_TWR = 5.0
MIN_RAIL_EXIT_FPS = 52.0
MAX_MACH = 1.0
MAX_BALLAST_FRACTION = 0.10
MIN_MAIN_DEPLOY_FT = 500.0
MAX_APOGEE_DELAY_S = 2.0
MAX_KE_FTLBF = 75.0
MAX_DRIFT_FT = 2500.0
MAX_DESCENT_S = 100.0

# Req 2.15: subscale shall use at least a class E (mid-power) motor.  Impulse
# classes double: class n spans (1.25 * 2**(n-1), 1.25 * 2**n] N-s, so E ends at
# 40 and begins just above 20.
MIN_SUBSCALE_IMPULSE_NS = 20.0
# Req 2.16: subscale shall not exceed 75% of full-scale length AND diameter.
MAX_SUBSCALE_FRACTION = 0.75


def impulse_class(total_impulse_ns: float) -> str:
    """Motor letter class for an impulse in N-s ('J', 'L', ...).

    Returns '-' below class A rather than raising: an unclassifiable impulse is
    a data problem for the caller to report, not an exception mid-table.
    """
    if total_impulse_ns <= 1.25:
        return "-"
    n = math.ceil(math.log2(total_impulse_ns / 1.25))
    return chr(ord("A") + n - 1) if 1 <= n <= 26 else "-"


def check_apogee(apogee_ft: float) -> Check:
    """Req 2.1 - apogee between 4,000 and 6,000 ft AGL."""
    if APOGEE_MIN_FT <= apogee_ft <= APOGEE_MAX_FT:
        st, note = Status.PASS, ""
    elif APOGEE_ZERO_LO_FT <= apogee_ft <= APOGEE_ZERO_HI_FT:
        st, note = Status.WARN, "outside 4k-6k: altitude points lost, still scored"
    else:
        st, note = Status.FAIL, "outside 3.5k-6.5k: ZERO altitude points, no Altitude Award"
    return Check("2.1", "Apogee window", st, apogee_ft,
                 f"{APOGEE_MIN_FT:.0f}-{APOGEE_MAX_FT:.0f}", "ft AGL", note)


def check_target_altitude(apogee_ft: float, target_ft: float) -> Check:
    """Req 2.3 - scored on closeness to the target declared at CDR.

    This is a SCORING requirement, not a constraint: missing the declared
    target costs altitude points but violates nothing.  It therefore never
    escalates past WARN, so that "0 FAIL" keeps meaning "fully compliant".
    """
    err = apogee_ft - target_ft
    st = Status.PASS if abs(err) <= 100 else Status.WARN
    note = "scoring is proportional; +/-100 ft is a strong result"
    if abs(err) > 300:
        note += (f" -- {abs(err):.0f} ft off would cost significant points;"
                 " re-declare the target or trim with ballast")
    return Check("2.3", "Error vs declared target", st, err,
                 f"target {target_ft:.0f}", "ft", note)


def check_impulse(total_impulse_ns: float) -> Check:
    """Req 2.9 - total impulse must not exceed 5,120 N-s (L class)."""
    st = Status.PASS if total_impulse_ns <= MAX_IMPULSE_NS else Status.FAIL
    return Check("2.9", "Total impulse", st, total_impulse_ns,
                 f"<= {MAX_IMPULSE_NS:.0f}", "N-s")


def check_stability(stability_cal: float) -> Check:
    """Req 2.11 - minimum static stability margin of 2.0 on the pad."""
    st = Status.PASS if stability_cal >= MIN_STABILITY_CAL else Status.FAIL
    return Check("2.11", "Static stability on pad", st, stability_cal,
                 f">= {MIN_STABILITY_CAL:.1f}", "cal",
                 "evaluated at Mach 0.3, matching OpenRocket's GUI convention")


def check_thrust_to_weight(twr: float) -> Check:
    """Req 2.12 - minimum thrust-to-weight of 5.0:1."""
    st = Status.PASS if twr >= MIN_TWR else Status.FAIL
    return Check("2.12", "Thrust-to-weight", st, twr, f">= {MIN_TWR:.1f}", ":1",
                 "average thrust / on-pad weight (the stricter reading)")


def check_rail_exit(rail_exit_fps: float) -> Check:
    """Req 2.14 - minimum 52 fps at rail exit."""
    st = Status.PASS if rail_exit_fps >= MIN_RAIL_EXIT_FPS else Status.FAIL
    return Check("2.14", "Rail exit velocity", st, rail_exit_fps,
                 f">= {MIN_RAIL_EXIT_FPS:.0f}", "fps")


def check_mach(max_mach: float) -> Check:
    """Req 2.20.6 - the vehicle shall not exceed Mach 1."""
    st = Status.PASS if max_mach < MAX_MACH else Status.FAIL
    return Check("2.20.6", "Maximum Mach", st, max_mach, f"< {MAX_MACH:.1f}", "-")


def check_ballast(ballast_kg: float, unballasted_kg: float) -> Check:
    """Req 2.20.7 - ballast shall not exceed 10% of un-ballasted mass."""
    frac = ballast_kg / unballasted_kg if unballasted_kg else 0.0
    st = Status.PASS if frac <= MAX_BALLAST_FRACTION else Status.FAIL
    return Check("2.20.7", "Ballast fraction", st, frac * 100.0, "<= 10", "%",
                 f"{U.kg_to_lb(ballast_kg):.2f} lb on {U.kg_to_lb(unballasted_kg):.2f} lb un-ballasted")


def check_mass_score(launch_mass_lb: float) -> Check:
    """Req 2.21 - mass scoring, measured without propellant at Hardware Check.

    Scoring mass excludes propellant and energetics but INCLUDES the payload
    and the motor case with closures.
    """
    if launch_mass_lb < 30.0:
        st, pts = Status.PASS, 5
    elif launch_mass_lb <= 40.0:
        st, pts = Status.WARN, 3
    else:
        st, pts = Status.FAIL, 0
    return Check("2.21", "Mass score", st, launch_mass_lb, "<30 lb = 5 pts", "lb",
                 f"{pts} of 5 points (30-40 lb = 3, >40 lb = 0)")


def check_main_deploy(main_deploy_ft: float) -> Check:
    """Req 3.1.1 - main parachute deployed no lower than 500 ft."""
    st = Status.PASS if main_deploy_ft >= MIN_MAIN_DEPLOY_FT else Status.FAIL
    return Check("3.1.1", "Main deploy altitude", st, main_deploy_ft,
                 f">= {MIN_MAIN_DEPLOY_FT:.0f}", "ft AGL")


def check_apogee_delay(delay_s: float) -> Check:
    """Req 3.1.2 - the apogee event shall contain no more than 2 s of delay."""
    st = Status.PASS if delay_s <= MAX_APOGEE_DELAY_S else Status.FAIL
    return Check("3.1.2", "Apogee event delay", st, delay_s,
                 f"<= {MAX_APOGEE_DELAY_S:.1f}", "s")


def check_kinetic_energy(section_masses_kg: dict[str, float],
                         vertical_mps: float,
                         total_mps: float | None = None) -> list[Check]:
    """Req 3.2 - each independent section <= 75 ft-lbf of KE at landing.

    Which velocity belongs in ``1/2 m v^2`` is a real modeling decision, and
    it changes parachute sizing by a full chute size:

    * ``vertical_mps`` - the descent rate.  This is what the handbook's FRR
      table asks for ("descent rate under both drogue and main parachutes")
      and what essentially every team reports.  It is the PASS/FAIL basis here.
    * ``total_mps``    - descent rate and horizontal drift in quadrature.  In a
      10 mph wind the horizontal component rivals the descent rate, so this
      roughly doubles the computed energy.  Reported as an advisory, because a
      section really does arrive carrying it.

    Sizing to the vertical rate is defensible and conventional; knowing how
    little margin that leaves against the total is the useful part.
    """
    out: list[Check] = []
    for name, mass in section_masses_kg.items():
        ke = U.j_to_ftlbf(0.5 * mass * vertical_mps ** 2)
        st = Status.PASS if ke <= MAX_KE_FTLBF else Status.FAIL
        note = f"{U.kg_to_lb(mass):.2f} lb at {U.mps_to_fps(vertical_mps):.1f} fps descent rate"
        if total_mps is not None:
            ke_tot = U.j_to_ftlbf(0.5 * mass * total_mps ** 2)
            note += (f"; incl. horizontal drift = {ke_tot:.1f} ft-lbf"
                     f" ({'over' if ke_tot > MAX_KE_FTLBF else 'under'} 75)")
        out.append(Check("3.2", f"KE at landing: {name}", st, ke,
                         f"<= {MAX_KE_FTLBF:.0f}", "ft-lbf", note))
    return out


def check_drift(drift_ft: float) -> Check:
    """Req 3.10 - recovery area limited to a 2,500 ft radius from the pads."""
    st = Status.PASS if drift_ft <= MAX_DRIFT_FT else Status.FAIL
    return Check("3.10", "Drift from pad", st, drift_ft,
                 f"<= {MAX_DRIFT_FT:.0f}", "ft")


def check_descent_time(descent_s: float) -> Check:
    """Req 3.11 - descent time limited to 100 s, apogee to touchdown."""
    st = Status.PASS if descent_s <= MAX_DESCENT_S else Status.FAIL
    return Check("3.11", "Descent time", st, descent_s,
                 f"<= {MAX_DESCENT_S:.0f}", "s")


# ---------------------------------------------------------------------------
#  Mass-budget closure (FRR section V)
# ---------------------------------------------------------------------------
def check_mass_closure(vehicle: Vehicle, ballast_kg: float, propellant_kg: float,
                       motor_case_kg: float, simulated_launch_mass_kg: float,
                       tol_kg: float = 0.05) -> Check:
    """The FRR requires the mass bookkeeping to add up exactly.

    "The sum of the propellant mass, recovery components, and individual
     section landing masses shall equal the gross lift-off mass."

    A mismatch here means the spec's landing_sections do not partition the
    vehicle -- a spec bug that would otherwise surface as an unexplained
    discrepancy in the report.
    """
    sections = sum(vehicle.landing_section_masses_kg(ballast_kg).values())
    booked = sections + vehicle.recovery_mass_kg() + propellant_kg + motor_case_kg
    err = booked - simulated_launch_mass_kg
    st = Status.PASS if abs(err) <= tol_kg else Status.FAIL
    unassigned = vehicle.unassigned_members()
    note = f"booked {U.kg_to_lb(booked):.3f} lb vs simulated {U.kg_to_lb(simulated_launch_mass_kg):.3f} lb"
    if unassigned:
        note += f"; UNASSIGNED to any landing section: {unassigned}"
    return Check("FRR-V", "Mass budget closure", st, U.kg_to_lb(err), "= 0", "lb", note)


# ---------------------------------------------------------------------------
#  Full sweep
# ---------------------------------------------------------------------------
def check_subscale_motor(total_impulse_ns: float) -> Check:
    """Req 2.15 - subscale shall use at least a class E (mid-power) motor."""
    cls = impulse_class(total_impulse_ns)
    ok = total_impulse_ns > MIN_SUBSCALE_IMPULSE_NS
    return Check(
        req="2.15", title="Subscale motor >= class E",
        status=Status.PASS if ok else Status.FAIL,
        value=total_impulse_ns, limit="> 20 N-s (class E)", units="N-s",
        note=f"class {cls}",
    )


def check_subscale_scale(subscale: Vehicle, full: Vehicle | None) -> list[Check]:
    """Req 2.16 - subscale shall not exceed 75% of full-scale length AND diameter.

    Two checks rather than one: a subscale can satisfy the diameter limit and
    breach the length limit, and a single combined verdict would hide which.
    """
    if full is None:
        note = "set `scales_from:` to the full-scale vehicle file to verify"
        return [Check(req="2.16", title="Subscale <= 75% of full-scale",
                      status=Status.WARN, value=None,
                      limit="<= 75%", units="", note=note)]

    out = []
    for label, sub_v, full_v, units in (
        ("length", subscale.total_length_m, full.total_length_m, "%"),
        ("diameter", subscale.diameter_m, full.diameter_m, "%"),
    ):
        frac = sub_v / full_v if full_v else float("inf")
        out.append(Check(
            req="2.16", title=f"Subscale {label} <= 75% of full-scale",
            status=Status.PASS if frac <= MAX_SUBSCALE_FRACTION else Status.FAIL,
            value=100.0 * frac, limit="<= 75%", units=units,
            note=f"vs {full.name}",
        ))
    return out


#  Requirements written against "the launch vehicle" govern the competition
#  vehicle, so they do not apply to a subscale demonstration flight.  Req 3.1 is
#  explicit -- "The full-scale launch vehicle shall stage the deployment..." --
#  and 3.1.1/3.1.2 are its sub-items.
#  FRR-V is deliberately absent: mass-budget closure is a self-consistency check
#  on the vehicle file, not a handbook requirement, so it governs any vehicle.
_FULL_SCALE_ONLY = {
    "2.1", "2.3", "2.9", "2.12", "2.20.6", "2.20.7", "2.21",
    "3.1.1", "3.1.2", "3.2", "3.10", "3.11",
}
#  Not required of a subscale by the handbook, but an RSO still cares and a
#  student should still see the number, so these are reported and demoted to a
#  warning rather than blanked out.
_SUBSCALE_ADVISORY = {"2.11", "2.14"}


def _for_subscale(check: Check) -> Check:
    """Re-scope one full-scale check for a subscale flight."""
    if check.req in _FULL_SCALE_ONLY:
        return Check(req=check.req, title=check.title, status=Status.NA,
                     value=check.value, limit=check.limit, units=check.units,
                     note="full-scale requirement; not scored on subscale")
    if check.req in _SUBSCALE_ADVISORY and check.status is Status.FAIL:
        return Check(req=check.req, title=check.title, status=Status.WARN,
                     value=check.value, limit=check.limit, units=check.units,
                     note="advisory on subscale: not required, but the RSO will ask")
    return check


def check_all(result, vehicle: Vehicle, motor: dict[str, Any],
              ballast_kg: float = 0.0) -> list[Check]:
    """Run every implemented requirement against one simulation result.

    `result` is an ORResult or an RPResult -- both expose `.to_row()`.
    `motor` is the dict from `or_bridge.motor_summary`.
    """
    r = result.to_row()
    checks: list[Check] = [
        check_apogee(r["apogee_ft"]),
        check_target_altitude(r["apogee_ft"], U.m_to_ft(vehicle.target_apogee_m)),
        check_impulse(motor["total_impulse_ns"]),
        check_stability(r["stability_pad_cal"]),
        check_thrust_to_weight(r["thrust_to_weight"]),
        check_rail_exit(r["rail_exit_fps"]),
        check_mach(r["max_mach"]),
        check_ballast(ballast_kg, vehicle.unballasted_pad_mass_kg()),
        check_mass_score(r["launch_mass_lb"] - U.kg_to_lb(motor["propellant_mass_kg"])),
        check_main_deploy(U.m_to_ft(vehicle.main["deploy_altitude_m"])),
        check_apogee_delay(vehicle.drogue["deploy_delay_s"]),
    ]
    checks += check_kinetic_energy(
        vehicle.landing_section_masses_kg(ballast_kg),
        vertical_mps=result.landing_vertical_mps,
        total_mps=result.ground_hit_velocity_mps,
    )
    checks += [
        check_drift(r["drift_ft"]),
        check_descent_time(r["descent_time_s"]),
        check_mass_closure(
            vehicle, ballast_kg,
            motor["propellant_mass_kg"], motor["burnout_mass_kg"],
            result.launch_mass_kg,
        ),
    ]

    if vehicle.is_subscale:
        checks = [_for_subscale(c) for c in checks]
        checks.append(check_subscale_motor(motor["total_impulse_ns"]))
        checks += check_subscale_scale(vehicle, vehicle.scale_reference())

    return checks


def summarize(checks: list[Check]) -> dict[str, int]:
    out = {s.value: 0 for s in Status}
    for c in checks:
        out[c.status.value] += 1
    return out


def format_table(checks: list[Check]) -> str:
    lines = [
        "  STATUS  REQ      REQUIREMENT                                 VALUE UNITS    LIMIT",
        "-" * TABLE_WIDTH,
    ]
    for c in checks:
        val = "-" if c.value is None else f"{c.value:10.2f}"
        lines.append(f"  {c.status.value:6s}  {c.req:8s} {c.title:<40s} {val} {c.units:<8s} {c.limit}")
        if c.note:
            lines.append(f"          {'':8s} `-- {c.note}")
    s = summarize(checks)
    lines.append("-" * TABLE_WIDTH)
    tally = f"  {s['PASS']} pass, {s['WARN']} warn, {s['FAIL']} FAIL"
    # Only shown when something was skipped, so the full-scale table is unchanged.
    if s["N/A"]:
        tally += f", {s['N/A']} N/A"
    lines.append(tally)
    return "\n".join(lines)
