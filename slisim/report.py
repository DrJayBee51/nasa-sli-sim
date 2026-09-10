"""Report-ready plots and tables.

Figures are sized and labeled for a design review document, not for a
notebook: readable axis labels with units, requirement limits drawn as
annotated lines, and no reliance on color alone to carry meaning.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import requirements as rq  # noqa: E402
from . import units as U  # noqa: E402

PASS_C, FAIL_C, NEUTRAL, ACCENT = "#2E7D32", "#C62828", "#37474F", "#1565C0"


def _style(ax, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(True, alpha=0.25, linewidth=0.6)
    ax.tick_params(labelsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def _save(fig, out_dir: Path, name: str) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
#  Flight profile (PDR/CDR/FRR: "altitude, velocity, acceleration vs time")
# ---------------------------------------------------------------------------
def plot_flight_profile(results: dict[str, object], out_dir: Path,
                        name: str = "flight_profile.png") -> Path:
    """Altitude / velocity / acceleration vs time, overlaying both engines.

    This single figure covers the handbook's first Mission Performance
    Predictions bullet and simultaneously shows the cross-validation.
    """
    fig, axes = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    styles = {"OpenRocket": dict(color=ACCENT, lw=1.8, ls="-"),
              "RocketPy": dict(color=FAIL_C, lw=1.5, ls="--")}

    for label, res in results.items():
        s = getattr(res, "series", None)
        if not s:
            continue
        st = styles.get(label, dict(lw=1.4))
        t = s["time_s"]
        axes[0].plot(t, U.m_to_ft(s["altitude_m"]), label=label, **st)
        axes[1].plot(t, U.mps_to_fps(np.abs(s["velocity_total_mps"])), label=label, **st)
        axes[2].plot(t, s["acceleration_mps2"] / U.G0, label=label, **st)

    _style(axes[0], "Flight profile", "", "Altitude AGL (ft)")
    axes[0].axhspan(rq.APOGEE_MIN_FT, rq.APOGEE_MAX_FT, color=PASS_C, alpha=0.10)
    axes[0].axhline(rq.APOGEE_MIN_FT, color=PASS_C, lw=0.9, ls=":")
    axes[0].axhline(rq.APOGEE_MAX_FT, color=PASS_C, lw=0.9, ls=":")
    axes[0].text(0.99, rq.APOGEE_MAX_FT, " req 2.1 window ", ha="right", va="bottom",
                 fontsize=7.5, color=PASS_C, transform=axes[0].get_yaxis_transform())
    axes[0].legend(fontsize=8, frameon=False)

    _style(axes[1], "", "", "Speed (fps)")
    _style(axes[2], "", "Time (s)", "Acceleration (g)")
    fig.align_ylabels(axes)
    return _save(fig, out_dir, name)


def plot_stability(results: dict[str, object], out_dir: Path,
                   name: str = "stability.png") -> Path:
    """Static margin and CP/CG vs time (handbook: 'show stability margin')."""
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for label, res in results.items():
        s = getattr(res, "series", None)
        if not s or "stability_cal" not in s:
            continue
        t = s["time_s"]
        axes[0].plot(t, s["stability_cal"], color=ACCENT, lw=1.6, label=label)
        if "cg_m" in s and "cp_m" in s:
            axes[1].plot(t, U.m_to_in(s["cg_m"]), color=ACCENT, lw=1.5, label="CG")
            axes[1].plot(t, U.m_to_in(s["cp_m"]), color=FAIL_C, lw=1.5, ls="--", label="CP")

    axes[0].axhline(rq.MIN_STABILITY_CAL, color=FAIL_C, lw=1.1, ls=":")
    axes[0].text(0.99, rq.MIN_STABILITY_CAL, " req 2.11 minimum ", ha="right",
                 va="bottom", fontsize=7.5, color=FAIL_C,
                 transform=axes[0].get_yaxis_transform())
    _style(axes[0], "Static stability margin", "", "Margin (calibers)")
    _style(axes[1], "", "Time (s)", "Position from nose (in)")
    axes[1].legend(fontsize=8, frameon=False)
    axes[1].invert_yaxis()
    return _save(fig, out_dir, name)


# ---------------------------------------------------------------------------
#  Monte Carlo
# ---------------------------------------------------------------------------
def plot_apogee_distribution(df: pd.DataFrame, out_dir: Path, target_ft: float,
                             name: str = "apogee_distribution.png") -> Path:
    ok = df[df.get("ok", True) == True]  # noqa: E712
    a = ok["apogee_ft"]

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(a, bins=40, color=ACCENT, alpha=0.75, edgecolor="white", linewidth=0.5)
    ax.axvspan(rq.APOGEE_MIN_FT, rq.APOGEE_MAX_FT, color=PASS_C, alpha=0.10,
               label="req 2.1 window (4,000-6,000 ft)")
    for x, c, ls, lbl in [
        (target_ft, "black", "-", f"declared target ({target_ft:,.0f} ft)"),
        (a.median(), FAIL_C, "--", f"median ({a.median():,.0f} ft)"),
        (a.quantile(0.05), NEUTRAL, ":", "5th / 95th percentile"),
        (a.quantile(0.95), NEUTRAL, ":", None),
    ]:
        ax.axvline(x, color=c, ls=ls, lw=1.4, label=lbl)

    p_win = float(((a >= rq.APOGEE_MIN_FT) & (a <= rq.APOGEE_MAX_FT)).mean())
    _style(ax, f"Apogee dispersion, N={len(a)}   |   P(in window) = {p_win:.1%}",
           "Apogee (ft AGL)", "Cases")
    ax.legend(fontsize=8, frameon=False)
    return _save(fig, out_dir, name)


def plot_landing_scatter(df: pd.DataFrame, out_dir: Path, ellipse: dict | None = None,
                         name: str = "landing_dispersion.png") -> Path:
    """Landing scatter against the 2,500 ft recovery radius (req 3.10)."""
    ok = df[df.get("ok", True) == True]  # noqa: E712
    x, y = ok["landing_x_ft"], ok["landing_y_ft"]
    inside = ok["drift_ft"] <= rq.MAX_DRIFT_FT

    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    ax.scatter(x[inside], y[inside], s=9, color=ACCENT, alpha=0.55, label="within limit")
    if (~inside).any():
        ax.scatter(x[~inside], y[~inside], s=14, color=FAIL_C, alpha=0.85,
                   label="exceeds 2,500 ft")

    circle = plt.Circle((0, 0), rq.MAX_DRIFT_FT, fill=False, color=FAIL_C,
                        lw=1.6, ls="--", label="req 3.10: 2,500 ft radius")
    ax.add_patch(circle)
    ax.plot(0, 0, marker="^", ms=11, color="black", label="launch pad")

    if ellipse:
        from matplotlib.patches import Ellipse
        ax.add_patch(Ellipse(
            (ellipse["mean_x_ft"], ellipse["mean_y_ft"]),
            2 * ellipse["semi_major_ft"], 2 * ellipse["semi_minor_ft"],
            angle=ellipse["angle_deg"], fill=False, color=PASS_C, lw=1.6,
            label=f"{ellipse['n_sigma']:.0f}-sigma ellipse"))

    lim = max(rq.MAX_DRIFT_FT * 1.1, float(ok["drift_ft"].max()) * 1.15)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    _style(ax, f"Landing dispersion, N={len(ok)}   |   {inside.mean():.1%} within limit",
           "East of pad (ft)", "North of pad (ft)")
    ax.legend(fontsize=8, frameon=False, loc="upper left")
    return _save(fig, out_dir, name)


def plot_sensitivity(sens: pd.DataFrame, out_dir: Path, output_label: str,
                     name: str = "sensitivity.png") -> Path:
    fig, ax = plt.subplots(figsize=(8, max(3.0, 0.42 * len(sens))))
    colors = [FAIL_C if v < 0 else ACCENT for v in sens["spearman_rho"]]
    ax.barh(sens["input"], sens["spearman_rho"], color=colors, alpha=0.85)
    ax.axvline(0, color="black", lw=0.9)
    ax.invert_yaxis()
    _style(ax, f"What drives {output_label}", "Spearman rank correlation", "")
    ax.set_xlim(-1, 1)
    return _save(fig, out_dir, name)


def plot_comparison(cmp_df: pd.DataFrame, out_dir: Path,
                    name: str = "engine_comparison.png") -> Path:
    """Percent difference per quantity, OpenRocket as the reference."""
    fig, ax = plt.subplots(figsize=(8.5, max(3.0, 0.45 * len(cmp_df))))
    colors = [PASS_C if abs(p) <= 5 else (ACCENT if abs(p) <= 10 else FAIL_C)
              for p in cmp_df["percent"]]
    ax.barh(cmp_df["quantity"], cmp_df["percent"], color=colors, alpha=0.9)
    ax.axvline(0, color="black", lw=1.0)
    for x, c in [(5, PASS_C), (-5, PASS_C), (10, NEUTRAL), (-10, NEUTRAL)]:
        ax.axvline(x, color=c, lw=0.8, ls=":")
    ax.invert_yaxis()
    _style(ax, "RocketPy vs OpenRocket (OpenRocket = reference)",
           "Difference (%)", "")
    return _save(fig, out_dir, name)


# ---------------------------------------------------------------------------
#  Markdown assembly
# ---------------------------------------------------------------------------
def _md_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |",
             "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            cells.append(floatfmt.format(v) if isinstance(v, (int, float, np.floating))
                         and not isinstance(v, bool) else str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_markdown(path: Path, title: str, sections: list[tuple[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [f"# {title}", ""]
    for heading, content in sections:
        if heading:
            body.append(f"## {heading}")
            body.append("")
        body.append(content)
        body.append("")
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    return _md_table(df, floatfmt)
