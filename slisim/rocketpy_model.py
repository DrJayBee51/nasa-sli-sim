"""RocketPy model, built from the same YAML spec as the OpenRocket model.

WHAT IS ACTUALLY INDEPENDENT
----------------------------
The handbook asks teams to "present data from a different calculation method
to verify that original results are accurate" and to "discuss any differences".
That is only an honest claim if you know which parts differ.  Here:

  Independent between the two tools
    * flight dynamics: RocketPy integrates full 6-DOF rigid-body equations
      with an LSODA solver; OpenRocket uses its own RK4 stepper
    * normal force / CP: each runs its own Barrowman implementation over its
      own geometry description
    * atmosphere, wind, and gravity models
    * numerical integration, event detection, and parachute dynamics

  Shared on purpose (so the comparison isolates the dynamics)
    * the thrust curve, exported from OpenRocket's bundled motor database
    * the mass and CG -- from the vehicle's mass worksheet, which builds the
      OpenRocket model too (or OpenRocket's mass calculator, without one)
    * the inertia, from the worksheet when there is one; OpenRocket then
      flies its own shape-based estimate, and run_crossvalidate prints both
    * the drag coefficient curve Cd(Mach)

The drag curve is shared because RocketPy has no parasitic-drag model of its
own -- ``power_off_drag`` is a required *input*, not something it derives from
geometry.  Any framework claiming RocketPy independently validates OpenRocket's
drag is wrong.  What RocketPy independently validates is everything the drag
feeds into.  To break that last dependency, fit Cd from real flight data with
``scripts/fit_cd.py`` and pass the result in as ``cd_curve_override``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from . import units as U
from .config import Site, Vehicle

_NOSE_KIND = {
    "ogive": "ogive", "conical": "conical", "ellipsoid": "elliptical",
    "haack": "von karman", "parabolic": "parabolic", "power": "powerseries",
}


# ---------------------------------------------------------------------------
#  Pulling shared inputs out of OpenRocket
# ---------------------------------------------------------------------------
def export_thrust_curve(motor) -> np.ndarray:
    """(time, thrust) samples straight from OpenRocket's motor database."""
    t = np.asarray([float(x) for x in motor.getTimePoints()])
    f = np.asarray([float(x) for x in motor.getThrustPoints()])
    return np.column_stack([t, f])


def export_drag_curves(or_result) -> tuple[np.ndarray, np.ndarray]:
    """Build Cd(Mach) for powered and coasting ascent from an OpenRocket run.

    Sampling OpenRocket's own simulated drag is better than re-deriving it:
    it already contains the friction, pressure, and base-drag terms, including
    the base-drag change at burnout that a static Barrowman sweep would miss.

    Only the ascent is used -- after apogee the reported Cd is the parachute's,
    not the airframe's.
    """
    s = or_result.series
    if not s:
        raise ValueError("export_drag_curves needs an ORResult with keep_series=True")

    t, mach, cd = s["time_s"], s["mach"], s["drag_coefficient"]
    thrust = s["thrust_n"]
    ascent = t <= or_result.time_to_apogee_s
    usable = ascent & (mach > 0.05) & np.isfinite(cd) & (cd > 0)

    def curve(mask: np.ndarray, fallback: float) -> np.ndarray:
        m, c = mach[mask], cd[mask]
        if m.size < 2:
            return np.array([[0.0, fallback], [1.0, fallback]])
        order = np.argsort(m)
        m, c = m[order], c[order]
        # Collapse duplicate Mach values; RocketPy interpolates and dislikes ties.
        m_u, idx = np.unique(np.round(m, 4), return_index=True)
        # Quantise Cd for the same reason the Mach axis is rounded above, but
        # for reproducibility rather than for ties.  OpenRocket's output is not
        # bit-identical between runs -- summation order inside the JVM varies,
        # so Cd moves by ~5e-13 -- and RocketPy's adaptive solver amplifies that
        # to ~1e-5 in drift by the time the vehicle lands.  Six decimals is nine
        # orders of magnitude finer than a drag coefficient means anything, and
        # it makes the curve, and therefore the whole RocketPy result, repeat.
        c_u = np.round(np.asarray([c[order_i] for order_i in idx]), 6)
        # Anchor at Mach 0 so RocketPy never extrapolates below the data.
        if m_u[0] > 0.0:
            m_u = np.insert(m_u, 0, 0.0)
            c_u = np.insert(c_u, 0, c_u[0])
        return np.column_stack([m_u, c_u])

    power_on = curve(usable & (thrust > 1.0), 0.45)
    power_off = curve(usable & (thrust <= 1.0), 0.45)
    return power_on, power_off


def export_mass_properties(rocket, or_module) -> dict[str, float]:
    """Structure-only mass, CG, and inertia, from OpenRocket's mass calculator.

    'Structure' means the rocket with no motor at all, which is exactly what
    RocketPy's ``mass`` / ``center_of_mass_without_motor`` / ``inertia`` want.
    """
    cfg = rocket.getSelectedConfiguration()
    body = or_module.masscalc.MassCalculator.calculateStructure(cfg)
    return {
        "mass_kg": float(body.getMass()),
        "cg_from_nose_m": float(body.getCM().x),
        "I_long": float(body.getLongitudinalInertia()),
        "I_rot": float(body.getRotationalInertia()),
    }


def mass_properties(vehicle, rocket, or_module,
                    ballast_kg: float = 0.0) -> dict[str, float]:
    """The nominal structure mass, CG and inertia RocketPy flies.

    A vehicle with a mass worksheet flies the sheet's numbers -- its inertia
    is the team's (CAD or weighed), which OpenRocket can only estimate from
    shapes.  A vehicle without a sheet flies OpenRocket's.  Monte Carlo draws
    go through from_state instead.

    The sheet and OpenRocket are built from the same numbers, so their mass
    and CG must agree; a disagreement means one of them is not reading what
    the other is, and every result downstream would be quietly inconsistent.
    """
    orp = export_mass_properties(rocket, or_module)
    if vehicle.mass_sheet is None:
        return orp
    from . import massprops

    sheet, _ = massprops.read(vehicle.mass_sheet)
    nominal = massprops.state(sheet, None, U.kg_to_lb(ballast_kg),
                              vehicle.ballast_location)
    d_lb = U.kg_to_lb(orp["mass_kg"]) - nominal["mass_lb"]
    d_in = U.m_to_in(orp["cg_from_nose_m"]) - nominal["cg_in"]
    if abs(d_lb) > 0.01 or abs(d_in) > 0.05:
        print(f"  WARNING: {vehicle.mass_sheet.name} and OpenRocket disagree: "
              f"mass {d_lb:+.3f} lb, CG {d_in:+.2f} in (OpenRocket - sheet)")
    return {**from_state(nominal), "or_I_long": orp["I_long"], "or_I_rot": orp["I_rot"]}


def from_state(state: dict) -> dict[str, float]:
    """massprops.state (lb, in) as build_rocket's SI mass_props."""
    in2 = U.in_to_m(1.0) ** 2
    return {
        "mass_kg": U.lb_to_kg(state["mass_lb"]),
        "cg_from_nose_m": U.in_to_m(state["cg_in"]),
        "I_long": U.lb_to_kg(state["inertia_pitch"]) * in2,
        "I_rot": U.lb_to_kg(state["inertia_roll"]) * in2,
    }


# ---------------------------------------------------------------------------
#  Result
# ---------------------------------------------------------------------------
@dataclass
class RPResult:
    apogee_m: float
    max_velocity_mps: float
    max_acceleration_mps2: float
    max_mach: float
    rail_exit_velocity_mps: float
    time_to_apogee_s: float
    flight_time_s: float
    descent_time_s: float
    ground_hit_velocity_mps: float
    landing_vertical_mps: float
    descent_rate_drogue_mps: float
    descent_rate_main_mps: float
    drift_m: float
    landing_x_m: float
    landing_y_m: float
    stability_on_pad_cal: float
    stability_rail_exit_cal: float
    cg_on_pad_m: float
    cp_on_pad_m: float
    launch_mass_kg: float
    burnout_mass_kg: float
    thrust_to_weight: float
    series: dict[str, np.ndarray] = field(default_factory=dict)

    def to_row(self) -> dict[str, float]:
        return {
            "apogee_ft": U.m_to_ft(self.apogee_m),
            "max_velocity_fps": U.mps_to_fps(self.max_velocity_mps),
            "max_accel_g": self.max_acceleration_mps2 / U.G0,
            "max_mach": self.max_mach,
            "rail_exit_fps": U.mps_to_fps(self.rail_exit_velocity_mps),
            "time_to_apogee_s": self.time_to_apogee_s,
            "flight_time_s": self.flight_time_s,
            "descent_time_s": self.descent_time_s,
            "ground_hit_fps": U.mps_to_fps(self.ground_hit_velocity_mps),
            "landing_vertical_fps": U.mps_to_fps(self.landing_vertical_mps),
            "descent_rate_drogue_fps": U.mps_to_fps(self.descent_rate_drogue_mps),
            "descent_rate_main_fps": U.mps_to_fps(self.descent_rate_main_mps),
            "drift_ft": U.m_to_ft(self.drift_m),
            "landing_x_ft": U.m_to_ft(self.landing_x_m),
            "landing_y_ft": U.m_to_ft(self.landing_y_m),
            "stability_pad_cal": self.stability_on_pad_cal,
            "stability_rail_exit_cal": self.stability_rail_exit_cal,
            "launch_mass_lb": U.kg_to_lb(self.launch_mass_kg),
            "thrust_to_weight": self.thrust_to_weight,
        }


# ---------------------------------------------------------------------------
#  Build + fly
# ---------------------------------------------------------------------------
#  ISA troposphere constants, used to extend the launch-day ground conditions
#  upward the same way OpenRocket does.
_LAPSE_K_PER_M = 0.0065
_R_AIR = 287.053
_ISA_EXPONENT = U.G0 / (_R_AIR * _LAPSE_K_PER_M)   # ~5.2559


def _isa_profiles(elevation_m: float, t0_k: float, p0_pa: float,
                  top_m: float = 9000.0, n: int = 120):
    """Temperature and pressure vs ASL height, anchored at the launch site.

    RocketPy's ``custom_atmosphere`` treats a SCALAR pressure as a constant at
    every altitude.  That is not merely inaccurate -- it makes
    ``barometric_height`` degenerate, so any altitude-triggered parachute fires
    the instant the rocket starts descending.  Supplying real profiles is
    required for correctness, not just fidelity.
    """
    h = np.linspace(elevation_m, max(top_m, elevation_m + 1000.0), n)
    dt = h - elevation_m
    temperature = t0_k - _LAPSE_K_PER_M * dt
    pressure = p0_pa * (1.0 - _LAPSE_K_PER_M * dt / t0_k) ** _ISA_EXPONENT
    return (np.column_stack([h, temperature]).tolist(),
            np.column_stack([h, pressure]).tolist())


def build_environment(site: Site, overrides: dict | None = None):
    from rocketpy import Environment

    o = overrides or {}
    env = Environment(
        latitude=site.latitude,
        longitude=site.longitude,
        elevation=site.elevation_m,
    )
    wind_speed = o.get("wind_speed_mps", site.wind_speed_mps)
    wind_dir = o.get("wind_direction_deg", site.wind_direction_deg)
    # Meteorological convention: the direction the wind blows FROM, so the
    # velocity vector points the opposite way.
    theta = math.radians(wind_dir)
    u = -wind_speed * math.sin(theta)   # east component
    v = -wind_speed * math.cos(theta)   # north component

    temperature, pressure = _isa_profiles(
        site.elevation_m,
        o.get("temperature_k", site.temperature_k),
        o.get("pressure_pa", site.pressure_pa),
    )
    env.set_atmospheric_model(
        type="custom_atmosphere",
        pressure=pressure,
        temperature=temperature,
        wind_u=u,
        wind_v=v,
    )
    return env


def build_motor(vehicle: Vehicle, or_motor, scale_impulse: float = 1.0,
                scale_burn_time: float = 1.0, scale_dry_mass: float = 1.0):
    """A RocketPy GenericMotor carrying OpenRocket's exact thrust curve.

    GenericMotor rather than SolidMotor: OpenRocket's database stores a thrust
    curve and mass points, not grain geometry, so inventing grain dimensions to
    satisfy SolidMotor would fabricate data the team does not have.
    """
    from rocketpy import GenericMotor

    curve = export_thrust_curve(or_motor)
    # Total impulse is the integral of thrust over time, so stretching the time
    # axis changes impulse too.  Thrust is divided by the same factor to hold
    # impulse fixed, which keeps `motor_burn_time` and `motor_total_impulse` in
    # uncertainty.yaml genuinely independent instead of silently compounding.
    if scale_burn_time != 1.0:
        curve[:, 0] *= scale_burn_time
        curve[:, 1] /= scale_burn_time
    if scale_impulse != 1.0:
        curve[:, 1] *= scale_impulse

    burn_time = float(curve[-1, 0])
    prop_mass = float(or_motor.getLaunchMass() - or_motor.getBurnoutMass())
    dry_mass = float(or_motor.getBurnoutMass()) * scale_dry_mass
    radius = float(or_motor.getDiameter()) / 2.0
    length = float(or_motor.getLength())
    # The motor's CG from the database, as an offset from its midpoint (the
    # origin here; positive toward the forward closure).  A reload is rarely
    # balanced at its middle -- the K1800ST's CG is 1.8 in aft of it -- and
    # centring 6 lb of motor there would put RocketPy's CG 0.4 in forward of
    # OpenRocket's, a tenth of a caliber of stability that does not exist.
    cg = length / 2.0 - float(or_motor.getLaunchCGx())

    return GenericMotor(
        thrust_source=curve,
        burn_time=burn_time,
        chamber_radius=radius * 0.95,
        chamber_height=length * 0.85,
        chamber_position=cg,            # relative to the motor's own origin
        propellant_initial_mass=prop_mass,
        nozzle_radius=radius * 0.6,
        dry_mass=dry_mass,
        center_of_dry_mass_position=cg,
        nozzle_position=-length / 2.0,
        coordinate_system_orientation="nozzle_to_combustion_chamber",
    )


def build_rocket(vehicle: Vehicle, or_motor, mass_props: dict[str, float],
                 power_on_drag, power_off_drag,
                 dry_mass_scale: float = 1.0,
                 drag_scale: float = 1.0, drogue_cd_scale: float = 1.0,
                 main_cd_scale: float = 1.0, main_deploy_shift_m: float = 0.0,
                 drogue_delay_shift_s: float = 0.0,
                 impulse_scale: float = 1.0, burn_time_scale: float = 1.0,
                 motor_dry_mass_scale: float = 1.0):
    """Assemble the RocketPy rocket.

    Coordinates use ``nose_to_tail`` so every position is measured from the
    nose tip, positive aft -- identical to OpenRocket's convention.  This
    removes a whole class of sign errors when comparing CG/CP between tools.
    """
    from rocketpy import Function, Rocket

    def scaled(curve, k):
        """Scale a Cd(Mach) table and wrap it as a RocketPy Function.

        RocketPy 1.13 rejects a bare array here; it wants a Function, a
        callable, a CSV path, or a constant.  Extrapolation is pinned to
        'constant' so a Monte Carlo sample that flies slightly faster than the
        nominal run cannot walk off the end of the table into a nonsense Cd.
        """
        c = np.array(curve, dtype=float, copy=True)
        c[:, 1] *= k
        return Function(
            c,
            inputs="Mach Number",
            outputs="Drag Coefficient",
            interpolation="linear",
            extrapolation="constant",
        )

    rocket = Rocket(
        radius=vehicle.outer_radius_m,
        mass=mass_props["mass_kg"] * dry_mass_scale,
        inertia=(mass_props["I_long"] * dry_mass_scale,
                 mass_props["I_long"] * dry_mass_scale,
                 mass_props["I_rot"] * dry_mass_scale),
        power_off_drag=scaled(power_off_drag, drag_scale),
        power_on_drag=scaled(power_on_drag, drag_scale),
        center_of_mass_without_motor=mass_props["cg_from_nose_m"],
        coordinate_system_orientation="nose_to_tail",
    )

    # Aft end of the last body tube, NOT overall length: a boat tail lengthens
    # the vehicle without moving the fin can or the motor.  With no transitions
    # the two are identical, so existing vehicles are unaffected.
    total_len = vehicle.body_end_m
    motor_len = float(or_motor.getLength())
    # Motor center of mass sits just forward of the aft end, allowing overhang.
    rocket.add_motor(
        build_motor(vehicle, or_motor,
                    scale_impulse=impulse_scale,
                    scale_burn_time=burn_time_scale,
                    scale_dry_mass=motor_dry_mass_scale),
        position=total_len - motor_len / 2.0 + vehicle.motor_overhang_m,
    )

    rocket.add_nose(
        length=vehicle.nose_length_m,
        kind=_NOSE_KIND.get(vehicle.nose_shape.lower(), "ogive"),
        position=0.0,
    )
    rocket.add_trapezoidal_fins(
        n=vehicle.fin_count,
        root_chord=vehicle.fin_root_chord_m,
        tip_chord=vehicle.fin_tip_chord_m,
        span=vehicle.fin_height_m,
        position=total_len - vehicle.fin_offset_from_aft_m - vehicle.fin_root_chord_m,
        cant_angle=vehicle.fin_cant_deg,
        sweep_length=vehicle.fin_sweep_m,
    )
    rocket.set_rail_buttons(
        upper_button_position=total_len - vehicle.fin_root_chord_m - 0.30,
        lower_button_position=total_len - vehicle.fin_root_chord_m,
    )

    # --- transitions.  RocketPy calls any diameter change a "tail" whether it
    #  narrows or flares; `position` is the station of its forward face.
    station = vehicle.nose_length_m
    ends = {}
    for sec in vehicle.sections:
        station += sec.length_m
        ends[sec.name] = station
    for tr in vehicle.transitions:
        rocket.add_tail(
            top_radius=tr.fore_radius_m,
            bottom_radius=tr.aft_radius_m,
            length=tr.length_m,
            position=ends.get(tr.after_section, vehicle.body_end_m),
        )

    # --- recovery.  cd_s is Cd * reference area, RocketPy's parameterisation.
    drogue = vehicle.drogue
    main = vehicle.main
    main_alt_agl = main["deploy_altitude_m"] + main_deploy_shift_m

    rocket.add_parachute(
        name=drogue["name"],
        cd_s=drogue["cd"] * drogue["area_m2"] * drogue_cd_scale,
        trigger="apogee",
        sampling_rate=105,
        lag=max(0.0, drogue["deploy_delay_s"] + drogue_delay_shift_s),
    )

    # A bare float trigger means "deploy at this height AGL while descending",
    # which is exactly what a barometric altimeter does.  RocketPy's trigger
    # height is already above ground level, so no elevation term belongs here.
    rocket.add_parachute(
        name=main["name"],
        cd_s=main["cd"] * main["area_m2"] * main_cd_scale,
        trigger=main_alt_agl,
        sampling_rate=105,
        lag=0.0,
    )
    return rocket


def build_flight(rocket, env, site: Site, overrides: dict | None = None):
    from rocketpy import Flight

    o = overrides or {}
    rail_angle = o.get("rail_angle_deg", 5.0)
    # RocketPy's `inclination` is measured from horizontal; the rail angle in
    # the handbook and in OpenRocket is measured from vertical.
    inclination = 90.0 - rail_angle

    return Flight(
        rocket=rocket,
        environment=env,
        rail_length=o.get("rail_length_m", site.rail_length_m),
        inclination=inclination,
        heading=o.get("rail_direction_deg", 0.0),
        max_time=o.get("max_time", 600),
    )


def extract(flight, rocket, or_motor, keep_series: bool = True) -> RPResult:
    """Pull the same quantities out of RocketPy that the OpenRocket side gives."""
    t = np.asarray(flight.time)
    z = np.asarray([flight.z(x) for x in t]) - flight.env.elevation
    vz = np.asarray([flight.vz(x) for x in t])
    speed = np.asarray([flight.speed(x) for x in t])
    mach = np.asarray([flight.mach_number(x) for x in t])
    ax = np.asarray([flight.acceleration(x) for x in t])
    x = np.asarray([flight.x(x_) for x_ in t])
    y = np.asarray([flight.y(x_) for x_ in t])

    apogee_t = float(flight.apogee_time)
    flight_t = float(t[-1])

    # Deployment times, in the order the chutes actually fired.
    deploys = sorted(float(e[0]) for e in flight.parachute_events) if \
        getattr(flight, "parachute_events", None) else []

    def steady(t0: float, t1: float) -> float:
        if t1 <= t0:
            return float("nan")
        lo = t0 + 0.2 * (t1 - t0)
        sel = (t >= lo) & (t <= t1)
        return float(np.median(np.abs(vz[sel]))) if sel.any() else float("nan")

    drogue_rate = main_rate = float("nan")
    if len(deploys) >= 2:
        drogue_rate = steady(deploys[0], deploys[1])
        main_rate = steady(deploys[1], flight_t)
    elif len(deploys) == 1:
        main_rate = steady(deploys[0], flight_t)

    launch_mass = float(rocket.total_mass(0.0))
    burnout_mass = float(rocket.total_mass(float(or_motor.getBurnTimeEstimate())))
    avg_thrust = float(or_motor.getAverageThrustEstimate())
    twr = avg_thrust / (launch_mass * U.G0) if launch_mass else 0.0

    # Static margin: RocketPy reports it in calibers as a function of time.
    stab_pad = float(rocket.stability_margin(0.3, 0.0))
    try:
        rail_t = float(flight.out_of_rail_time)
        stab_rail = float(flight.stability_margin(rail_t))
    except Exception:  # noqa: BLE001 - diagnostic only
        rail_t, stab_rail = 0.0, float("nan")

    cg = float(rocket.center_of_mass(0.0))
    cp = float(rocket.cp_position(0.3)) if callable(getattr(rocket, "cp_position", None)) \
        else float(rocket.cp_position)

    res = RPResult(
        apogee_m=float(flight.apogee) - flight.env.elevation,
        max_velocity_mps=float(flight.max_speed),
        # Ascent only, matching the OpenRocket side: see the note there.
        max_acceleration_mps2=float(np.nanmax(ax[t <= apogee_t]))
        if np.any(t <= apogee_t) else float(flight.max_acceleration),
        max_mach=float(flight.max_mach_number),
        rail_exit_velocity_mps=float(flight.out_of_rail_velocity),
        time_to_apogee_s=apogee_t,
        flight_time_s=flight_t,
        descent_time_s=flight_t - apogee_t,
        ground_hit_velocity_mps=float(abs(flight.impact_velocity)),
        landing_vertical_mps=abs(float(vz[-1])),
        descent_rate_drogue_mps=drogue_rate,
        descent_rate_main_mps=main_rate,
        drift_m=float(math.hypot(x[-1], y[-1])),
        landing_x_m=float(x[-1]),
        landing_y_m=float(y[-1]),
        stability_on_pad_cal=stab_pad,
        stability_rail_exit_cal=stab_rail,
        cg_on_pad_m=cg,
        cp_on_pad_m=cp,
        launch_mass_kg=launch_mass,
        burnout_mass_kg=burnout_mass,
        thrust_to_weight=twr,
    )
    if keep_series:
        res.series = {
            "time_s": t, "altitude_m": z, "velocity_z_mps": vz,
            "velocity_total_mps": speed, "acceleration_mps2": ax,
            "mach": mach, "position_x_m": x, "position_y_m": y,
        }
    return res


#  Body-frame columns that stop being physical once a parachute opens: RocketPy
#  flies the descent as a point mass under the canopy, so attitude and rates
#  after deployment are leftovers, not predictions.
ASCENT_ONLY = ("accel_x_g", "accel_y_g", "accel_z_g",
               "gyro_x_dps", "gyro_y_dps", "gyro_z_dps",
               "q0", "q1", "q2", "q3", "attitude_deg", "angle_of_attack_deg",
               "precession_deg", "nutation_deg", "spin_deg")


def state_history(flight, dt: float = 0.01):
    """Every simulated state, sampled the way a flight computer logs them.

    One row per `dt` seconds from ignition to landing, as a DataFrame.  Beside
    the states themselves (position, velocity, attitude, body rates) it carries
    what each kind of sensor would have *read*, so a telemetry log overlays
    without conversion:

    * `baro_altitude_ft` -- altitude from simulated static pressure through
      the standard atmosphere, relative to the pad, as an altimeter computes
      it.  It differs from true `altitude_agl_ft` when the day is not
      standard, and so does the real altimeter.
    * `accel_*_g` -- specific force in body axes, which is what an
      accelerometer measures: acceleration MINUS gravity, so +1 g along the
      axis on the pad and about -drag/weight in coast, never -1 g.
    * `gyro_*_dps` -- body angular rates.  z is the rocket's long axis (roll);
      x and y are the lateral axes, at an arbitrary roll orientation.
    * `latitude_deg`, `longitude_deg`, `altitude_msl_m` -- what a GPS reports.

    Columns in ASCENT_ONLY are blank after the first deployment.
    """
    import pandas as pd

    f = flight
    t = np.arange(0.0, float(f.t_final), dt)
    ev = lambda fn: np.asarray(fn(t), dtype=float)  # noqa: E731 - vectorised Function call

    z = ev(f.z)
    p = ev(f.pressure)
    g = np.asarray(f.env.gravity(z), dtype=float)
    a_inertial = np.stack([ev(f.ax), ev(f.ay), ev(f.az) + g], axis=1)   # a - g, g = (0,0,-g)
    q = np.stack([ev(f.e0), ev(f.e1), ev(f.e2), ev(f.e3)], axis=1)
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    w, x_, y_, z_ = q.T
    # RocketPy's body-to-inertial matrix (Matrix.transformation); body = K^T @ inertial.
    K = np.array([
        [1 - 2 * (y_**2 + z_**2), 2 * (x_ * y_ - w * z_), 2 * (x_ * z_ + w * y_)],
        [2 * (x_ * y_ + w * z_), 1 - 2 * (x_**2 + z_**2), 2 * (y_ * z_ - w * x_)],
        [2 * (x_ * z_ - w * y_), 2 * (y_ * z_ + w * x_), 1 - 2 * (x_**2 + y_**2)],
    ]).transpose(2, 0, 1)
    f_body = np.einsum("nji,nj->ni", K, a_inertial) / U.G0

    def std_alt_m(pa):
        return 44330.77 * (1.0 - (pa / 101325.0) ** 0.190263)

    rad_s_to_dps = 180.0 / math.pi
    df = pd.DataFrame({
        "time_s": t,
        "phase": "",
        "altitude_agl_ft": U.m_to_ft(z - f.env.elevation),
        "baro_altitude_ft": U.m_to_ft(std_alt_m(p) - std_alt_m(p[0])),
        "pressure_pa": p,
        "latitude_deg": ev(f.latitude),
        "longitude_deg": ev(f.longitude),
        "altitude_msl_m": z,
        "east_ft": U.m_to_ft(ev(f.x)),
        "north_ft": U.m_to_ft(ev(f.y)),
        "vel_east_fps": U.mps_to_fps(ev(f.vx)),
        "vel_north_fps": U.mps_to_fps(ev(f.vy)),
        "vel_up_fps": U.mps_to_fps(ev(f.vz)),
        "speed_fps": U.mps_to_fps(ev(f.speed)),
        "mach": ev(f.mach_number),
        "accel_x_g": f_body[:, 0],
        "accel_y_g": f_body[:, 1],
        "accel_z_g": f_body[:, 2],
        "gyro_x_dps": ev(f.w1) * rad_s_to_dps,
        "gyro_y_dps": ev(f.w2) * rad_s_to_dps,
        "gyro_z_dps": ev(f.w3) * rad_s_to_dps,
        "q0": q[:, 0], "q1": q[:, 1], "q2": q[:, 2], "q3": q[:, 3],
        "attitude_deg": ev(f.attitude_angle),
        "angle_of_attack_deg": ev(f.angle_of_attack),
        "precession_deg": ev(f.psi),
        "nutation_deg": ev(f.theta),
        "spin_deg": ev(f.phi),
    })

    # Phase labels, in the order things happen.
    events = [(0.0, "rail"), (float(f.out_of_rail_time), "powered"),
              (float(f.rocket.motor.burn_out_time), "coast")]
    deploys = sorted((float(e[0]), f"under {e[1].name}")
                     for e in (getattr(f, "parachute_events", None) or []))
    for start, label in sorted(events + deploys):
        df.loc[df["time_s"] >= start, "phase"] = label
    if deploys:
        df.loc[df["time_s"] >= deploys[0][0], list(ASCENT_ONLY)] = np.nan
    return df
