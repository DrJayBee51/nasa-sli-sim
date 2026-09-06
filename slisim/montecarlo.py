"""Monte Carlo driver.

The handbook asks teams to "perform multiple simulations to verify that results
are precise".  Running OpenRocket five times with different wind speeds answers
that weakly.  Sampling the uncertainty file turns each requirement into a
probability of compliance, which is a far stronger claim to put in a report --
and it is the reason RocketPy is worth adding alongside OpenRocket at all.

Parallelism uses processes, not threads: RocketPy releases the GIL poorly and,
more importantly, JPype permits exactly one JVM per process, so an OpenRocket
Monte Carlo has to fan out across processes regardless.  Each worker builds the
vehicle once and reuses it, so the JVM start-up cost is paid once per worker
rather than once per sample.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Iterator

import numpy as np
import pandas as pd

from . import units as U
from .config import Site, Vehicle, load_uncertainty


# ---------------------------------------------------------------------------
#  Sampling
# ---------------------------------------------------------------------------
def _draw_one(spec: dict, rng: np.random.Generator,
              site_mean: float | None = None,
              site_sigma: float | None = None) -> float:
    """Draw a single value from one uncertainty.yaml entry.

    `mean: null` / `sigma: null` mean "inherit from the launch site", which
    keeps wind statistics in sites.yaml where they belong instead of
    duplicating them per-analysis.
    """
    dist = spec.get("distribution", "normal")
    mean = spec.get("mean")
    sigma = spec.get("sigma")
    if mean is None:
        mean = site_mean if site_mean is not None else 0.0
    if sigma is None:
        sigma = site_sigma if site_sigma is not None else 0.0

    if dist == "normal":
        return float(rng.normal(mean, sigma))
    if dist == "uniform":
        return float(rng.uniform(spec["low"], spec["high"]))
    if dist == "truncnormal":
        lo = spec.get("low", -np.inf)
        hi = spec.get("high", np.inf)
        # Resample rather than clip: clipping piles probability mass onto the
        # bounds and quietly biases the tails that requirement margins live in.
        for _ in range(100):
            v = float(rng.normal(mean, sigma))
            if lo <= v <= hi:
                return v
        return float(np.clip(rng.normal(mean, sigma), lo, hi))
    raise ValueError(f"unknown distribution {dist!r}")


def draw_sample(unc: dict, site: Site, rng: np.random.Generator) -> dict[str, float]:
    """One full set of perturbations."""
    site_means = {
        "wind_speed_mps": site.wind_speed_mps,
        "wind_direction_deg": site.wind_direction_deg,
        "temperature_k": site.temperature_k,
        "pressure_pa": site.pressure_pa,
    }
    site_sigmas = {
        "wind_speed_mps": site.wind_speed_sigma_mps,
        "wind_direction_deg": site.wind_direction_sigma_deg,
    }
    out: dict[str, float] = {}
    for key, spec in unc.items():
        out[key] = _draw_one(spec, rng, site_means.get(key), site_sigmas.get(key))
    return out


# ---------------------------------------------------------------------------
#  Worker-side model cache
# ---------------------------------------------------------------------------
_CACHE: dict[tuple, Any] = {}


def _prepare(vehicle: Vehicle, site: Site, ballast_kg: float) -> dict[str, Any]:
    """Build the OpenRocket model once per worker and derive shared inputs.

    Keyed on the vehicle's CONTENT, not its identity: every task arriving in a
    worker carries a freshly unpickled Vehicle, so an id()-based key would miss
    on every single sample and rebuild the whole OpenRocket model each time.
    """
    key = (
        json.dumps(vehicle.raw, sort_keys=True, default=str),
        round(ballast_kg, 9),
        site.key,
    )
    if key in _CACHE:
        return _CACHE[key]

    from . import or_bridge as orb
    from . import rocketpy_model as rpm

    doc, rocket, _mount, motor = orb.build_document(vehicle, ballast_kg)
    nominal = orb.run_simulation(orb.make_simulation(doc, rocket, site),
                                 rocket, keep_series=True)
    power_on, power_off = rpm.export_drag_curves(nominal)
    prepared = {
        "doc": doc,
        "rocket": rocket,
        "motor": motor,
        "motor_info": orb.motor_summary(motor),
        "mass_props": rpm.export_mass_properties(rocket, orb.ensure_jvm()),
        "power_on": power_on,
        "power_off": power_off,
        "nominal": nominal,
    }
    _CACHE[key] = prepared
    return prepared


def _overrides_from(sample: dict[str, float]) -> dict[str, float]:
    """Translate a sample into launch-condition overrides both engines accept."""
    return {
        "wind_speed_mps": max(0.0, sample.get("wind_speed_mps", 0.0)),
        "wind_direction_deg": sample.get("wind_direction_deg", 0.0),
        "temperature_k": sample.get("temperature_k", 288.15),
        "pressure_pa": sample.get("pressure_pa", 101325.0),
        "rail_angle_deg": sample.get("rail_angle_deg", 5.0),
        "rail_direction_deg": sample.get("rail_direction_deg", 0.0),
    }


def run_rocketpy_case(vehicle: Vehicle, site: Site, sample: dict[str, float],
                      ballast_kg: float = 0.0) -> dict[str, float]:
    """One dispersed RocketPy flight."""
    from . import rocketpy_model as rpm

    prep = _prepare(vehicle, site, ballast_kg)
    ov = _overrides_from(sample)

    env = rpm.build_environment(site, ov)
    rocket = rpm.build_rocket(
        vehicle, prep["motor"], prep["mass_props"],
        prep["power_on"], prep["power_off"],
        dry_mass_scale=sample.get("dry_mass", 1.0),
        cg_shift_m=sample.get("cg_shift", 0.0),
        drag_scale=sample.get("drag_coefficient", 1.0),
        drogue_cd_scale=sample.get("drogue_cd", 1.0),
        main_cd_scale=sample.get("main_cd", 1.0),
        main_deploy_shift_m=U.ft_to_m(sample.get("main_deploy_altitude_ft", 0.0)),
        drogue_delay_shift_s=sample.get("drogue_deploy_delay_s", 0.0),
        impulse_scale=sample.get("motor_total_impulse", 1.0),
        burn_time_scale=sample.get("motor_burn_time", 1.0),
        motor_dry_mass_scale=sample.get("motor_dry_mass", 1.0),
    )
    flight = rpm.build_flight(rocket, env, site, ov)
    return rpm.extract(flight, rocket, prep["motor"], keep_series=False).to_row()


def run_openrocket_case(vehicle: Vehicle, site: Site, sample: dict[str, float],
                        ballast_kg: float = 0.0) -> dict[str, float]:
    """One dispersed OpenRocket flight.

    Only launch conditions are dispersed here.  Perturbing mass and drag would
    mean rebuilding the component tree per sample, which costs more than it
    buys -- RocketPy is the engine for vehicle-parameter dispersion, and
    OpenRocket is the independent check on the trajectory itself.
    """
    from . import or_bridge as orb

    prep = _prepare(vehicle, site, ballast_kg)
    ov = _overrides_from(sample)
    ov["random_seed"] = int(sample.get("_seed", 0)) % (2 ** 31 - 1)
    sim = orb.make_simulation(prep["doc"], prep["rocket"], site, ov)
    return orb.run_simulation(sim, prep["rocket"], keep_series=False).to_row()


def _worker(args) -> dict[str, float]:
    vehicle, site, sample, ballast_kg, engine, index = args
    try:
        if engine == "openrocket":
            row = run_openrocket_case(vehicle, site, sample, ballast_kg)
        else:
            row = run_rocketpy_case(vehicle, site, sample, ballast_kg)
        row["ok"] = True
    except Exception as exc:  # noqa: BLE001 - a failed case must not kill the run
        row = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    row["index"] = index
    row.update({f"in_{k}": v for k, v in sample.items() if not k.startswith("_")})
    return row


# ---------------------------------------------------------------------------
#  Driver
# ---------------------------------------------------------------------------
def run_montecarlo(vehicle: Vehicle, site: Site, n: int = 500,
                   engine: str = "rocketpy", ballast_kg: float = 0.0,
                   seed: int = 12345, workers: int | None = None,
                   uncertainty: dict | None = None,
                   progress: bool = True) -> pd.DataFrame:
    """Run `n` dispersed flights and return one row per case.

    A fixed `seed` makes the whole campaign reproducible, which matters: a
    reviewer asking "where did 4,712 ft come from" should be able to get the
    identical number back months later.
    """
    unc = uncertainty if uncertainty is not None else load_uncertainty()
    rng = np.random.default_rng(seed)

    samples = []
    for i in range(n):
        s = draw_sample(unc, site, rng)
        s["_seed"] = int(rng.integers(0, 2 ** 31 - 1))
        samples.append(s)

    workers = workers or max(1, min(os.cpu_count() or 1, 8))
    tasks = [(vehicle, site, s, ballast_kg, engine, i) for i, s in enumerate(samples)]

    rows: list[dict] = []
    if workers == 1:
        for t in tasks:
            rows.append(_worker(t))
            if progress and len(rows) % 25 == 0:
                print(f"  {len(rows)}/{n}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_worker, t) for t in tasks]
            for done, fut in enumerate(as_completed(futures), 1):
                rows.append(fut.result())
                if progress and done % 25 == 0:
                    print(f"  {done}/{n}", flush=True)

    df = pd.DataFrame(rows).sort_values("index").reset_index(drop=True)
    df.attrs["engine"] = engine
    df.attrs["seed"] = seed
    df.attrs["n"] = n
    df.attrs["ballast_kg"] = ballast_kg
    df.attrs["site"] = site.key
    return df
