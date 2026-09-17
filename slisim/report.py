"""Report-ready plots and tables.

Figures are sized and labeled for a design review document, not for a
notebook: readable axis labels with units, requirement limits drawn as
annotated lines, and no reliance on color alone to carry meaning.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import montecarlo as mc  # noqa: E402
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


# Panel layout for plot_input_distributions: one row per group, in the same
# order as config/uncertainty.yaml so the figure reads like the file it came
# from.  A parameter missing from here still plots, under "Other".
INPUT_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Vehicle", ("dry_mass", "cg_shift", "drag_coefficient")),
    ("Motor", ("motor_total_impulse", "motor_burn_time", "motor_dry_mass")),
    ("Launch conditions", ("rail_angle_deg", "rail_direction_deg", "wind_speed_mps",
                           "wind_direction_deg", "temperature_k", "pressure_pa")),
    ("Recovery", ("drogue_cd", "main_cd", "main_deploy_altitude_ft",
                  "drogue_deploy_delay_s")),
]

# Axis units by name suffix.  Parameters declared `relative: true` are sampled
# as multipliers on the nominal, so they are dimensionless and handled first.
_UNIT_BY_SUFFIX = {"_deg": "deg", "_mps": "m/s", "_k": "K", "_pa": "Pa",
                   "_ft": "ft", "_s": "s", "_cd": "x nominal", "_mass": "x nominal"}


def _input_unit(param: str, spec: dict | None) -> str:
    if spec and spec.get("relative"):
        return "x nominal"
    for suffix, unit in _UNIT_BY_SUFFIX.items():
        if param.endswith(suffix):
            return unit
    return ""


def plot_input_distributions(df: pd.DataFrame, out_dir: Path,
                             uncertainty: dict | None = None,
                             engine: str = "rocketpy",
                             name: str = "input_distributions.png") -> Path:
    """Histogram per dispersed input, grouped as in config/uncertainty.yaml.

    This is the figure that shows a reviewer *what was actually sampled*, which
    is the half of a Monte Carlo that dispersion summaries leave out: the output
    tables say the apogee scattered, this says the inputs did, and by how much.
    Where the requested sigma is known it is printed beside the observed one --
    a visible disagreement means the sampler did not do what the YAML asked.

    Parameters held nominal are omitted rather than drawn as a single spike.
    The caption names the first few so a subset run is self-documenting; the
    full list belongs in the report body, which has room for it.

    Under `engine="openrocket"` only the launch conditions are plotted: the
    sampler draws every parameter either way, but `run_openrocket_case` feeds it
    only those six, so plotting the rest would credit them with scatter they did
    not cause.
    """
    ok = df[df.get("ok", True) == True]  # noqa: E712
    ins = {c[len("in_"):]: c for c in df.columns if c.startswith("in_")}

    consumed = mc.OPENROCKET_PARAMETERS if engine == "openrocket" else set(ins)
    ignored = sorted(p for p in ins if p not in consumed)

    # A frozen parameter is pinned to one value, so it has no distribution to
    # draw.  Constant-but-not-frozen cannot happen: every sampler draws floats.
    dispersed = [p for p, col in ins.items()
                 if p in consumed and ok[col].nunique() > 1]
    held = [p for p in ins if p in consumed and p not in dispersed]
    if not dispersed:
        raise ValueError("no dispersed inputs to plot; every parameter is nominal")

    known = {p for _, params in INPUT_GROUPS for p in params}
    groups = [(g, [p for p in params if p in dispersed]) for g, params in INPUT_GROUPS]
    groups.append(("Other", [p for p in dispersed if p not in known]))

    # Wrap a group wider than MAXCOLS onto continuation rows, so one six-panel
    # group cannot set the width of a figure meant for a portrait report page.
    # A subset run with few parameters narrows instead: ncols is the widest row
    # actually drawn, not the cap, so two panels do not sit in a 4-wide grid.
    MAXCOLS = 4
    rows: list[tuple[str, list[str]]] = []
    for group, params in groups:
        for i in range(0, len(params), MAXCOLS):
            rows.append((group if i == 0 else "", params[i:i + MAXCOLS]))
    ncols = max(len(params) for _, params in rows)

    fig, axes = plt.subplots(len(rows), ncols, squeeze=False,
                             figsize=(2.6 * ncols, 2.5 * len(rows)))
    for r, (group, params) in enumerate(rows):
        for c in range(ncols):
            ax = axes[r][c]
            if c >= len(params):
                ax.axis("off")
                continue

            param = params[c]
            v = ok[ins[param]].astype(float)
            spec = (uncertainty or {}).get(param)
            # Sturges-ish, floored so a 50-case pilot run still shows a shape.
            ax.hist(v, bins=min(30, max(8, int(np.sqrt(len(v))))),
                    color=ACCENT, alpha=0.75, edgecolor="white", linewidth=0.5)
            ax.axvline(v.mean(), color=FAIL_C, lw=1.3)

            sigma = f"sd {v.std():.3g}"
            requested = None if spec is None else spec.get("sigma")
            if requested:                      # None, null, or 0.0 -> nothing to compare
                sigma += f" (req {float(requested):.3g})"
            _style(ax, f"{param.replace('_', ' ')}\n{sigma}",
                   _input_unit(param, spec), "")
            # Wide absolute ranges (pressure in Pa) otherwise overprint.
            ax.ticklabel_format(axis="x", style="sci", scilimits=(-3, 4),
                                useOffset=False)
            ax.xaxis.get_offset_text().set_fontsize(7)
            ax.xaxis.set_major_locator(plt.MaxNLocator(nbins=5))
            ax.set_title(ax.get_title(), fontsize=8.5, fontweight="bold")
            ax.tick_params(labelsize=7)
            # Group name rides the leftmost y-label, so the row is labeled once.
            ax.set_ylabel(f"{group}\nCases" if c == 0 else "", fontsize=8.5)

    # Each line wrapped on its own, so the wrapper never breaks a line directly
    # after the "held nominal:" lead-in and leave it dangling.  Width tracks the
    # grid because _save crops with bbox_inches="tight": a caption wider than the
    # panels would widen the entire figure.
    width = max(46, 34 * ncols)
    head = f"Sampled inputs, N={len(ok)} successful cases"
    if engine == "openrocket":
        head += " -- OpenRocket, launch conditions only"
    lines = textwrap.wrap(head, width)
    if ignored:
        lines += textwrap.wrap(f"drawn but not used by this engine: "
                               f"{len(ignored)} vehicle/motor/recovery parameters", width)
    if held:
        # Name a few, then count the rest.  A --only run can hold fourteen
        # parameters nominal, and the full list belongs in the report text
        # rather than in a caption that would crowd out the histograms.
        shown = sorted(held)[:3]
        rest = f" +{len(held) - len(shown)} more" if len(held) > len(shown) else ""
        lines += textwrap.wrap("held nominal: " + ", ".join(shown) + rest, width)

    fig.suptitle("\n".join(lines), fontsize=9.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.03 * len(lines)))
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
