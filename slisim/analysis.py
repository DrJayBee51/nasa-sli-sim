"""Statistics over a Monte Carlo campaign, and requirement compliance rates.

The single most useful output here is `compliance()`: instead of "our simulated
apogee is 4,533 ft", the team can write "4,533 ft nominal, 95% CI [4,180,
4,890], P(within the 4,000-6,000 ft window) = 0.97".  That is a materially
stronger claim in a design review, and it is defensible because the inputs are
declared in uncertainty.yaml rather than assumed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import requirements as rq
from . import units as U
from .config import Vehicle


# ---------------------------------------------------------------------------
#  Descriptive statistics
# ---------------------------------------------------------------------------
def describe(df: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    """Percentile summary of the interesting outputs."""
    ok = df[df.get("ok", True) == True]  # noqa: E712 - pandas mask needs ==
    cols = columns or [
        "apogee_ft", "max_velocity_fps", "max_mach", "max_accel_g",
        "rail_exit_fps", "stability_pad_cal", "descent_time_s", "drift_ft",
        "landing_vertical_fps", "descent_rate_drogue_fps", "descent_rate_main_fps",
        "launch_mass_lb", "thrust_to_weight",
    ]
    cols = [c for c in cols if c in ok.columns]
    out = ok[cols].agg(["mean", "std", "min", "max"]).T
    for q in (0.05, 0.50, 0.95):
        out[f"p{int(q * 100):02d}"] = ok[cols].quantile(q)
    return out[["mean", "std", "min", "p05", "p50", "p95", "max"]]


def confidence_interval(series: pd.Series, level: float = 0.95) -> tuple[float, float]:
    a = (1.0 - level) / 2.0
    return float(series.quantile(a)), float(series.quantile(1.0 - a))


# ---------------------------------------------------------------------------
#  Requirement compliance as probabilities
# ---------------------------------------------------------------------------
def compliance(df: pd.DataFrame, vehicle: Vehicle, motor: dict,
               ballast_kg: float = 0.0) -> pd.DataFrame:
    """Fraction of Monte Carlo cases satisfying each scalar requirement."""
    ok = df[df.get("ok", True) == True].copy()  # noqa: E712
    n = len(ok)
    if n == 0:
        raise ValueError("no successful Monte Carlo cases to analyse")

    target_ft = U.m_to_ft(vehicle.target_apogee_m)
    rows = []

    def add(req: str, title: str, mask: pd.Series, series: pd.Series, limit: str):
        lo, hi = confidence_interval(series)
        rows.append({
            "req": req, "requirement": title,
            "P(pass)": float(mask.mean()),
            "mean": float(series.mean()),
            "p05": lo, "p95": hi,
            "limit": limit,
        })

    add("2.1", "Apogee in 4,000-6,000 ft",
        (ok["apogee_ft"] >= rq.APOGEE_MIN_FT) & (ok["apogee_ft"] <= rq.APOGEE_MAX_FT),
        ok["apogee_ft"], "4000-6000 ft")
    add("2.1", "Apogee scores (3,500-6,500 ft)",
        (ok["apogee_ft"] >= rq.APOGEE_ZERO_LO_FT) & (ok["apogee_ft"] <= rq.APOGEE_ZERO_HI_FT),
        ok["apogee_ft"], "3500-6500 ft")
    add("2.3", "Within 100 ft of declared target",
        (ok["apogee_ft"] - target_ft).abs() <= 100.0,
        ok["apogee_ft"] - target_ft, f"target {target_ft:.0f} ft")
    add("2.11", "Stability >= 2.0 cal",
        ok["stability_pad_cal"] >= rq.MIN_STABILITY_CAL,
        ok["stability_pad_cal"], ">= 2.0 cal")
    add("2.12", "Thrust-to-weight >= 5.0",
        ok["thrust_to_weight"] >= rq.MIN_TWR,
        ok["thrust_to_weight"], ">= 5.0")
    add("2.14", "Rail exit >= 52 fps",
        ok["rail_exit_fps"] >= rq.MIN_RAIL_EXIT_FPS,
        ok["rail_exit_fps"], ">= 52 fps")
    add("2.20.6", "Mach < 1.0",
        ok["max_mach"] < rq.MAX_MACH, ok["max_mach"], "< 1.0")
    add("3.10", "Drift <= 2,500 ft",
        ok["drift_ft"] <= rq.MAX_DRIFT_FT, ok["drift_ft"], "<= 2500 ft")
    add("3.11", "Descent time <= 100 s",
        ok["descent_time_s"] <= rq.MAX_DESCENT_S, ok["descent_time_s"], "<= 100 s")

    # Kinetic energy, per independent section (req 3.2).
    if "landing_vertical_fps" in ok.columns:
        v_mps = ok["landing_vertical_fps"] / U.FT_PER_M
        for name, mass in vehicle.landing_section_masses_kg(ballast_kg).items():
            ke = 0.5 * mass * v_mps ** 2 / U.J_PER_FTLBF
            add("3.2", f"KE <= 75 ft-lbf: {name}",
                ke <= rq.MAX_KE_FTLBF, ke, "<= 75 ft-lbf")

    out = pd.DataFrame(rows)
    out.attrs["n"] = n
    out.attrs["n_failed"] = int(len(df) - n)
    return out


# ---------------------------------------------------------------------------
#  Landing dispersion
# ---------------------------------------------------------------------------
def landing_ellipse(df: pd.DataFrame, n_sigma: float = 3.0) -> dict[str, float]:
    """Fit a covariance ellipse to the landing scatter.

    Reported as the semi-axes and rotation of the `n_sigma` ellipse, plus the
    fraction of cases inside the 2,500 ft recovery radius (req 3.10).
    """
    ok = df[df.get("ok", True) == True]  # noqa: E712
    x = ok["landing_x_ft"].to_numpy()
    y = ok["landing_y_ft"].to_numpy()
    cov = np.cov(np.vstack([x, y]))
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    return {
        "mean_x_ft": float(x.mean()),
        "mean_y_ft": float(y.mean()),
        "semi_major_ft": float(n_sigma * np.sqrt(vals[0])),
        "semi_minor_ft": float(n_sigma * np.sqrt(vals[1])),
        "angle_deg": float(np.degrees(np.arctan2(vecs[1, 0], vecs[0, 0]))),
        "n_sigma": n_sigma,
        "max_drift_ft": float(ok["drift_ft"].max()),
        "p95_drift_ft": float(ok["drift_ft"].quantile(0.95)),
        "frac_within_2500ft": float((ok["drift_ft"] <= rq.MAX_DRIFT_FT).mean()),
    }


# ---------------------------------------------------------------------------
#  Sensitivity
# ---------------------------------------------------------------------------
def sensitivity(df: pd.DataFrame, output: str = "apogee_ft") -> pd.DataFrame:
    """Rank inputs by how strongly they drive an output.

    Uses Spearman rank correlation, so a monotone but nonlinear driver (wind
    speed on drift, say) is not understated the way Pearson would understate it.
    Tells the team where shrinking an uncertainty would actually pay off.
    """
    ok = df[df.get("ok", True) == True]  # noqa: E712
    inputs = [c for c in ok.columns if c.startswith("in_")]
    rows = []
    for c in inputs:
        if ok[c].nunique() < 2:
            continue
        rho = ok[[c, output]].corr(method="spearman").iloc[0, 1]
        rows.append({
            "input": c[3:],
            "spearman_rho": float(rho),
            "abs_rho": abs(float(rho)),
        })
    out = pd.DataFrame(rows).sort_values("abs_rho", ascending=False)
    return out.drop(columns="abs_rho").reset_index(drop=True)


# ---------------------------------------------------------------------------
#  Target-altitude selection (req 2.3)
# ---------------------------------------------------------------------------
def recommend_target(df: pd.DataFrame) -> dict[str, float]:
    """Suggest the altitude to declare at CDR.

    The score rewards closeness to the declared target, so the best declaration
    is the CENTER of the predicted distribution, not the nominal run and not
    the middle of the legal window.  The median is used rather than the mean
    because apogee distributions are mildly left-skewed (drag and mass errors
    both push one way).
    """
    ok = df[df.get("ok", True) == True]  # noqa: E712
    apogee = ok["apogee_ft"]
    median = float(apogee.median())
    lo, hi = confidence_interval(apogee, 0.95)
    return {
        "recommended_target_ft": round(median / 10.0) * 10.0,
        "median_ft": median,
        "mean_ft": float(apogee.mean()),
        "std_ft": float(apogee.std()),
        "ci95_low_ft": lo,
        "ci95_high_ft": hi,
        "p_in_window": float(((apogee >= rq.APOGEE_MIN_FT) &
                              (apogee <= rq.APOGEE_MAX_FT)).mean()),
        "p_scoring": float(((apogee >= rq.APOGEE_ZERO_LO_FT) &
                            (apogee <= rq.APOGEE_ZERO_HI_FT)).mean()),
    }


# ---------------------------------------------------------------------------
#  OpenRocket vs RocketPy comparison
# ---------------------------------------------------------------------------
COMPARE_FIELDS = [
    ("apogee_ft", "Apogee", "ft"),
    ("max_velocity_fps", "Max velocity", "fps"),
    ("max_mach", "Max Mach", "-"),
    ("max_accel_g", "Max acceleration", "g"),
    ("rail_exit_fps", "Rail exit velocity", "fps"),
    ("time_to_apogee_s", "Time to apogee", "s"),
    ("stability_pad_cal", "Static stability", "cal"),
    ("descent_time_s", "Descent time", "s"),
    ("descent_rate_drogue_fps", "Descent rate (drogue)", "fps"),
    ("descent_rate_main_fps", "Descent rate (main)", "fps"),
    ("landing_vertical_fps", "Landing descent rate", "fps"),
    ("drift_ft", "Drift from pad", "ft"),
    ("launch_mass_lb", "Launch mass", "lb"),
]


def compare(or_row: dict, rp_row: dict) -> pd.DataFrame:
    """Side-by-side table answering the handbook's 'different method' bullet."""
    rows = []
    for key, label, unit in COMPARE_FIELDS:
        a, b = or_row.get(key), rp_row.get(key)
        if a is None or b is None or not np.isfinite(a) or not np.isfinite(b):
            continue
        diff = b - a
        pct = 100.0 * diff / a if a else float("nan")
        rows.append({
            "quantity": label, "units": unit,
            "OpenRocket": a, "RocketPy": b,
            "difference": diff, "percent": pct,
        })
    return pd.DataFrame(rows)
