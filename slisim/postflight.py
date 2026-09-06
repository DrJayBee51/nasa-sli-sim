"""Post-flight analysis: fit drag from real altimeter data.

The FRR requires, verbatim:

    "Estimate the drag coefficient of the full-scale rocket utilizing launch
     data. Use this value to run a post-flight simulation."
    "Update your simulated flight model with launch day condition data and
     compare the predicted flight performance to the actual flight data."

This module does both.  It is also the single highest-value analysis in the
framework, because the pre-flight drag uncertainty (7% in uncertainty.yaml) is
the dominant contributor to apogee scatter.  Replacing that guess with a fitted
value typically halves the predicted apogee spread, which directly improves the
altitude score that requirement 2.3 pays out on.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

from . import units as U
from .config import Site, Vehicle


# ---------------------------------------------------------------------------
#  Altimeter ingest
# ---------------------------------------------------------------------------
#  Column aliases seen on the altimeters teams actually fly.
_TIME_KEYS = ["time", "time (s)", "t", "seconds", "flight_time"]
_ALT_KEYS = ["altitude", "altitude (ft)", "alt", "height", "agl",
             "altitude(feet)", "baro altitude", "altitude_ft"]
_VEL_KEYS = ["velocity", "velocity (ft/s)", "speed", "vel", "velocity_fps"]


def _match(columns: list[str], keys: list[str]) -> str | None:
    lowered = {c.lower().strip(): c for c in columns}
    for k in keys:
        if k in lowered:
            return lowered[k]
    for k in keys:  # substring fallback
        for lc, orig in lowered.items():
            if k in lc:
                return orig
    return None


@dataclass
class FlightData:
    """Measured flight data, normalised to SI internally."""

    time_s: np.ndarray
    altitude_m: np.ndarray
    velocity_mps: np.ndarray | None
    source: str
    units_detected: str

    @property
    def apogee_m(self) -> float:
        return float(np.nanmax(self.altitude_m))

    @property
    def apogee_time_s(self) -> float:
        return float(self.time_s[int(np.nanargmax(self.altitude_m))])

    def summary(self) -> dict[str, float]:
        return {
            "apogee_ft": U.m_to_ft(self.apogee_m),
            "apogee_time_s": self.apogee_time_s,
            "flight_time_s": float(self.time_s[-1] - self.time_s[0]),
            "descent_time_s": float(self.time_s[-1] - self.apogee_time_s),
            "samples": int(self.time_s.size),
            "sample_rate_hz": float(
                self.time_s.size / max(1e-9, self.time_s[-1] - self.time_s[0])),
        }


def load_altimeter_csv(path: str | Path, altitude_units: str = "auto",
                       time_column: str | None = None,
                       altitude_column: str | None = None) -> FlightData:
    """Read a PerfectFlite / StratoLogger / Eggtimer / RRC3 style CSV.

    Altimeter exports vary wildly, so columns are auto-detected and the
    altitude unit is inferred from magnitude unless stated.  A 5,000 ft flight
    reads ~5000 in feet and ~1524 in metres, which is unambiguous for any SLI
    vehicle, but pass `altitude_units` explicitly if you would rather not rely
    on that.
    """
    path = Path(path)
    df = pd.read_csv(path, comment="#", skip_blank_lines=True)
    df.columns = [str(c).strip() for c in df.columns]

    tcol = time_column or _match(list(df.columns), _TIME_KEYS)
    acol = altitude_column or _match(list(df.columns), _ALT_KEYS)
    if tcol is None or acol is None:
        raise ValueError(
            f"Could not find time/altitude columns in {path.name}. "
            f"Columns present: {list(df.columns)}. "
            "Pass time_column= and altitude_column= explicitly."
        )
    vcol = _match(list(df.columns), _VEL_KEYS)

    t = pd.to_numeric(df[tcol], errors="coerce").to_numpy(dtype=float)
    a = pd.to_numeric(df[acol], errors="coerce").to_numpy(dtype=float)
    good = np.isfinite(t) & np.isfinite(a)
    t, a = t[good], a[good]

    if altitude_units == "auto":
        # SLI apogees are 3,500-6,500 ft; in metres that is 1,067-1,981.
        units = "ft" if np.nanmax(a) > 2500 else "m"
    else:
        units = altitude_units
    alt_m = U.ft_to_m(a) if units == "ft" else a
    alt_m = alt_m - np.median(alt_m[: max(3, len(alt_m) // 200)])  # zero the pad

    vel = None
    if vcol is not None:
        v = pd.to_numeric(df[vcol], errors="coerce").to_numpy(dtype=float)[good]
        vel = U.fps_to_mps(v) if units == "ft" else v

    return FlightData(time_s=t - t[0], altitude_m=alt_m, velocity_mps=vel,
                      source=path.name, units_detected=units)


# ---------------------------------------------------------------------------
#  Drag fit
# ---------------------------------------------------------------------------
@dataclass
class CdFitResult:
    cd_scale: float
    fitted_apogee_ft: float
    measured_apogee_ft: float
    residual_ft: float
    baseline_apogee_ft: float
    rmse_ft: float
    n_iterations: int
    bracket: tuple[float, float]

    def report(self) -> str:
        return (
            f"  Cd scale factor      : {self.cd_scale:.4f}  "
            f"({(self.cd_scale - 1) * 100:+.1f}% vs the pre-flight model)\n"
            f"  Measured apogee      : {self.measured_apogee_ft:,.0f} ft\n"
            f"  Pre-flight prediction: {self.baseline_apogee_ft:,.0f} ft "
            f"({self.baseline_apogee_ft - self.measured_apogee_ft:+,.0f} ft error)\n"
            f"  Post-fit prediction  : {self.fitted_apogee_ft:,.0f} ft "
            f"({self.residual_ft:+,.0f} ft residual)\n"
            f"  Ascent RMSE          : {self.rmse_ft:,.0f} ft\n"
            f"  Optimiser iterations : {self.n_iterations}"
        )


def fit_cd_scale(vehicle: Vehicle, site: Site, measured: FlightData,
                 launch_overrides: dict | None = None,
                 bracket: tuple[float, float] = (0.6, 1.8),
                 ballast_kg: float = 0.0,
                 match: str = "apogee") -> CdFitResult:
    """Find the drag scale factor that reproduces the measured flight.

    A single multiplicative scale on Cd(Mach) is fitted rather than a full
    curve.  With one altimeter trace there is not enough information to resolve
    Cd as a function of Mach -- attempting it would fit noise.  A scale factor
    is what the flight data can actually support, and it is what the FRR bullet
    asks for.

    `match="apogee"` fits apogee only (robust, works with a coarse trace).
    `match="ascent"` fits the whole ascent profile by RMSE (uses more of the
    data, needs a clean trace at >= 10 Hz).
    """
    from . import or_bridge as orb
    from . import rocketpy_model as rpm

    ov = dict(launch_overrides or {})
    measured_apogee_m = measured.apogee_m

    doc, rocket, _mount, motor = orb.build_document(vehicle, ballast_kg)
    baseline = orb.run_simulation(orb.make_simulation(doc, rocket, site, ov),
                                  rocket, keep_series=True)
    power_on, power_off = rpm.export_drag_curves(baseline)
    mass_props = rpm.export_mass_properties(rocket, orb.ensure_jvm())

    calls = {"n": 0}

    def simulate(scale: float):
        calls["n"] += 1
        env = rpm.build_environment(site, ov)
        rk = rpm.build_rocket(vehicle, motor, mass_props, power_on, power_off,
                              drag_scale=scale)
        fl = rpm.build_flight(rk, env, site, ov)
        return rpm.extract(fl, rk, motor, keep_series=True)

    def cost(scale: float) -> float:
        res = simulate(float(scale))
        if match == "ascent":
            s = res.series
            asc = s["time_s"] <= res.time_to_apogee_s
            pred = np.interp(measured.time_s, s["time_s"][asc], s["altitude_m"][asc],
                             left=np.nan, right=np.nan)
            m = np.isfinite(pred) & (measured.time_s <= measured.apogee_time_s)
            if m.sum() < 5:
                return abs(res.apogee_m - measured_apogee_m)
            return float(np.sqrt(np.mean((pred[m] - measured.altitude_m[m]) ** 2)))
        return abs(res.apogee_m - measured_apogee_m)

    opt = minimize_scalar(cost, bounds=bracket, method="bounded",
                          options={"xatol": 1e-3})
    best = float(opt.x)
    final = simulate(best)

    # Ascent RMSE reported regardless of which objective was optimised, so the
    # two modes stay comparable.
    s = final.series
    asc = s["time_s"] <= final.time_to_apogee_s
    pred = np.interp(measured.time_s, s["time_s"][asc], s["altitude_m"][asc],
                     left=np.nan, right=np.nan)
    m = np.isfinite(pred) & (measured.time_s <= measured.apogee_time_s)
    rmse = float(np.sqrt(np.mean((pred[m] - measured.altitude_m[m]) ** 2))) if m.sum() > 3 \
        else float("nan")

    return CdFitResult(
        cd_scale=best,
        fitted_apogee_ft=U.m_to_ft(final.apogee_m),
        measured_apogee_ft=U.m_to_ft(measured_apogee_m),
        residual_ft=U.m_to_ft(final.apogee_m - measured_apogee_m),
        baseline_apogee_ft=U.m_to_ft(baseline.apogee_m),
        rmse_ft=U.m_to_ft(rmse) if np.isfinite(rmse) else float("nan"),
        n_iterations=calls["n"],
        bracket=bracket,
    )


def measured_descent_rates(measured: FlightData,
                           main_deploy_alt_m: float) -> dict[str, float]:
    """Descent rates under drogue and main, straight from the altimeter trace.

    These feed the FRR kinetic-energy table with MEASURED rather than simulated
    numbers, which is what the review panel would rather see.
    """
    t, z = measured.time_s, measured.altitude_m
    apogee_i = int(np.nanargmax(z))
    t_d, z_d = t[apogee_i:], z[apogee_i:]
    if t_d.size < 5:
        return {}

    under_drogue = z_d > main_deploy_alt_m * 1.15
    under_main = (z_d < main_deploy_alt_m * 0.85) & (z_d > 15.0)

    def rate(mask) -> float:
        """Descent rate as the slope of a straight-line fit over the window.

        Point-by-point differentiation is unusable here.  A barometric
        altimeter carries a few feet of noise, and at a 20 Hz sample rate that
        is ~100 fps of noise in every finite difference -- which swamps a 15 fps
        descent under the main entirely.  Descent under a steady parachute is
        linear in time, so a least-squares slope over the window uses every
        sample and is essentially immune to that noise.
        """
        if mask.sum() < 3:
            return float("nan")
        slope = np.polyfit(t_d[mask], z_d[mask], 1)[0]
        return float(abs(slope))

    return {
        "drogue_fps": U.mps_to_fps(rate(under_drogue)),
        "main_fps": U.mps_to_fps(rate(under_main)),
        "descent_time_s": float(t_d[-1] - t_d[0]),
        "apogee_ft": U.m_to_ft(measured.apogee_m),
    }


def kinetic_energy_table(vehicle: Vehicle, descent_rate_mps: float,
                         ballast_kg: float = 0.0) -> pd.DataFrame:
    """The FRR kinetic-energy table, per independent section."""
    rows = []
    for name, mass in vehicle.landing_section_masses_kg(ballast_kg).items():
        ke = 0.5 * mass * descent_rate_mps ** 2 / U.J_PER_FTLBF
        rows.append({
            "section": name,
            "landing_mass_lb": U.kg_to_lb(mass),
            "descent_rate_fps": U.mps_to_fps(descent_rate_mps),
            "kinetic_energy_ftlbf": ke,
            "limit_ftlbf": 75.0,
            "margin_ftlbf": 75.0 - ke,
            "status": "PASS" if ke <= 75.0 else "FAIL",
        })
    return pd.DataFrame(rows)
