"""Self-check for report.plot_input_distributions.

    python scripts/check_input_plots.py

Exercises the parts of the figure that are logic rather than drawing: which
parameters count as dispersed, the per-engine filter, and the sigma annotation.
Exits 0 if every check passes, 1 on the first failure, so it is usable in CI.

Deliberately not pytest: this project ships no test framework, and a plain
script runs with nothing installed beyond requirements.txt.  Renders go to a
temporary directory and are deleted; run run_montecarlo.py if you want figures
to keep.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from PIL import Image  # noqa: E402

from slisim import montecarlo as mc, report  # noqa: E402

# The full dispersible set, matching config/uncertainty.yaml.  Hard-coded rather
# than loaded so a YAML edit cannot quietly weaken these checks.
PARAMS = ["dry_mass", "cg_shift", "drag_coefficient",
          "motor_total_impulse", "motor_burn_time", "motor_dry_mass",
          "rail_angle_deg", "rail_direction_deg", "wind_speed_mps",
          "wind_direction_deg", "temperature_k", "pressure_pa",
          "drogue_cd", "main_cd", "main_deploy_altitude_ft",
          "drogue_deploy_delay_s"]


def _frame(n: int = 40, frozen: tuple[str, ...] = ()) -> pd.DataFrame:
    """A stand-in Monte Carlo result: dispersed inputs, plus `frozen` pinned."""
    rng = np.random.default_rng(7)
    df = pd.DataFrame({f"in_{p}": rng.normal(1.0, 0.05, n) for p in PARAMS})
    for p in frozen:
        df[f"in_{p}"] = 1.0
    df["ok"] = True
    df["apogee_ft"] = rng.normal(4500, 120, n)
    return df


def _check_every_dispersed_parameter_plots(out: Path) -> None:
    png = report.plot_input_distributions(_frame(), out, name="all.png")
    assert png.exists(), "no file written"
    assert png.stat().st_size > 5000, f"suspiciously small render: {png.stat().st_size} B"


def _check_frozen_parameters_are_omitted(out: Path) -> None:
    """A pinned parameter has no distribution, so it must not get a panel."""
    frozen = ("dry_mass", "main_cd")
    df = _frame(frozen=frozen)
    full = Image.open(report.plot_input_distributions(df, out, name="f_all.png"))
    fewer = Image.open(report.plot_input_distributions(_frame(frozen=frozen + ("cg_shift", "drogue_cd")),
                                                      out, name="f_more.png"))
    # Vehicle drops to one panel and Recovery to two, so the grid narrows.
    assert fewer.size[0] <= full.size[0], "freezing more parameters did not narrow the figure"


def _check_openrocket_plots_only_launch_conditions(out: Path) -> None:
    """OpenRocket consumes six parameters; the rest must not be drawn as if used."""
    df = _frame()
    wide = report.plot_input_distributions(df, out, engine="rocketpy", name="rp.png")
    narrow = report.plot_input_distributions(df, out, engine="openrocket", name="or.png")
    # Six panels wrap to two rows, sixteen to five, so the filtered figure is shorter.
    assert Image.open(narrow).size[1] < Image.open(wide).size[1], \
        "openrocket figure is as tall as the rocketpy one; the engine filter is not applied"
    assert len(mc.OPENROCKET_PARAMETERS) == 6, \
        f"expected 6 OpenRocket parameters, found {len(mc.OPENROCKET_PARAMETERS)}"


def _check_all_nominal_is_an_error(out: Path) -> None:
    """Every parameter pinned means nothing to plot -- say so, don't emit a blank."""
    try:
        report.plot_input_distributions(_frame(frozen=tuple(PARAMS)), out, name="empty.png")
    except ValueError as exc:
        assert "nominal" in str(exc), f"unhelpful message: {exc}"
    else:
        raise AssertionError("expected ValueError when nothing is dispersed")


def _check_null_sigma_annotation(out: Path) -> None:
    """wind_* carry `sigma: null` in the YAML; formatting must not crash on it."""
    unc = {"wind_speed_mps": {"distribution": "truncnormal", "sigma": None},
           "dry_mass": {"distribution": "normal", "relative": True, "sigma": 0.015}}
    assert report.plot_input_distributions(_frame(), out, unc, name="sigma.png").exists()


def main() -> int:
    checks = [v for k, v in sorted(globals().items()) if k.startswith("_check_")]
    failed = 0
    # A temporary directory keeps output/ clean; these renders are never artifacts.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        for check in checks:
            name = check.__name__.removeprefix("_check_")
            try:
                check(out)
                print(f"  pass  {name}")
            except AssertionError as exc:
                print(f"  FAIL  {name}: {exc}")
                failed += 1

    print(f"\n{len(checks) - failed} of {len(checks)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
