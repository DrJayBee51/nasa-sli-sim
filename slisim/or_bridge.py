"""Headless OpenRocket bridge.

Drives the real OpenRocket 24.12 solver from Python through JPype, so the
cross-check against RocketPy uses the *same engine the team uses in the GUI*
rather than a re-implementation of it.

Two notes for anyone extending this:

1.  The widely-cited ``orhelper`` package does NOT work with OpenRocket 23.09+.
    OpenRocket renamed its packages from ``net.sf.openrocket`` to
    ``info.openrocket.core``, and orhelper 0.1.3 still imports the old names.
    It also boots through the Swing ``GuiModule``.  We instead use
    ``OpenRocketCore.initialize(PluginModule())``, which is the supported
    headless entry point and needs no display.

2.  JPype allows exactly one JVM per OS process.  ``ensure_jvm()`` is
    idempotent; Monte Carlo parallelism therefore uses *processes*, each of
    which boots its own JVM (~2 s once, then ~0.7 s per simulation).
"""

from __future__ import annotations

import math
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from . import units as U
from .config import Site, Vehicle

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_JAR = REPO_ROOT / "vendor" / "OpenRocket-24.12.jar"

_JVM_STARTED = False
_or: Any = None  # the info.openrocket.core package handle


# ---------------------------------------------------------------------------
#  JVM lifecycle
# ---------------------------------------------------------------------------
_JAVA_SEARCH = [
    "C:/Program Files/Microsoft",
    "C:/Program Files/Eclipse Adoptium",
    "C:/Program Files/Java",
    "C:/Program Files/Amazon Corretto",
    "C:/Program Files/Zulu",
    "/usr/lib/jvm",
    "/Library/Java/JavaVirtualMachines",
]


MIN_JAVA_MAJOR = 17


def _major_from_version(version: str) -> int | None:
    """Major version from a Java version string.

    Handles both schemes: "17.0.20.1" -> 17, and the pre-9 "1.8.0_402" -> 8.
    """
    m = re.match(r"(\d+)(?:\.(\d+))?", version.strip())
    if not m:
        return None
    major = int(m.group(1))
    if major == 1 and m.group(2):      # 1.8.0_402 style
        return int(m.group(2))
    return major


def java_major(home: str | Path) -> int | None:
    """Major Java version of the runtime at `home`, or None if undeterminable.

    Checked in order of cost: the `release` file every modern distribution
    ships, then asking the runtime itself.  Returning None means "cannot tell",
    and callers treat that as acceptable rather than rejecting a JDK that may
    be perfectly good.
    """
    home = Path(home)

    release = home / "release"
    if release.is_file():
        try:
            for line in release.read_text(errors="ignore").splitlines():
                if line.startswith("JAVA_VERSION="):
                    return _major_from_version(line.split("=", 1)[1].strip().strip('"'))
        except OSError:
            pass

    java = home / "bin" / ("java.exe" if os.name == "nt" else "java")
    if java.is_file():
        try:
            # -version writes to stderr on every JVM old enough to matter here.
            proc = subprocess.run([str(java), "-version"], capture_output=True,
                                  text=True, timeout=15)
            m = re.search(r'version "([^"]+)"', (proc.stderr or "") + (proc.stdout or ""))
            if m:
                return _major_from_version(m.group(1))
        except (OSError, subprocess.SubprocessError):
            pass

    return None


def find_java_home() -> str | None:
    """Locate a JDK 17+ so students never have to set JAVA_HOME by hand.

    An existing JAVA_HOME is honored but *verified*: a machine with an older
    Java left over from some other tool would otherwise send that version to
    JPype, and OpenRocket 24.12 fails deep inside the JVM with
    UnsupportedClassVersionError instead of anything actionable.  A JAVA_HOME
    that is too old is skipped in favor of a newer JDK found on disk.
    """
    env_home = os.environ.get("JAVA_HOME")
    if env_home and Path(env_home, "bin").exists():
        major = java_major(env_home)
        if major is None or major >= MIN_JAVA_MAJOR:
            return env_home

    candidates: list[Path] = []
    for root in _JAVA_SEARCH:
        rp = Path(root)
        if not rp.is_dir():
            continue
        for child in rp.iterdir():
            name = child.name.lower()
            if not child.is_dir() or ("jdk" not in name and "jre" not in name):
                continue
            # macOS bundles nest the real home one level down.
            home = child / "Contents" / "Home"
            candidates.append(home if home.is_dir() else child)

    def version_key(p: Path) -> int:
        digits = ""
        for ch in p.name:
            if ch.isdigit():
                digits += ch
            elif digits:
                break
        return int(digits) if digits else 0

    # Newest first, but anything below 17 will not run OpenRocket 24.12.
    for cand in sorted(candidates, key=version_key, reverse=True):
        if version_key(cand) >= 17 and (cand / "bin").is_dir():
            return str(cand)
    return None


def ensure_jvm(jar_path: str | Path | None = None, heap: str = "2g",
               quiet: bool = True) -> Any:
    """Boot the JVM and initialise OpenRocket's core. Idempotent."""
    global _JVM_STARTED, _or
    if _JVM_STARTED:
        return _or

    # Resolve JAVA_HOME on every start, not just when it is unset: an existing
    # value may point at a Java too old for OpenRocket, and JPype would prefer
    # it over a perfectly good newer JDK sitting next to it.
    stale_note = ""
    home = find_java_home()
    if home:
        os.environ["JAVA_HOME"] = home
    else:
        env_home = os.environ.get("JAVA_HOME")
        env_major = java_major(env_home) if env_home else None
        if env_major is not None and env_major < MIN_JAVA_MAJOR:
            # Drop it for this process only, so JPype can look elsewhere (the
            # Windows registry, PATH) instead of loading a JVM we know is too
            # old.  The user's own environment is untouched.
            os.environ.pop("JAVA_HOME", None)
            stale_note = (
                f"\nJAVA_HOME points at Java {env_major} ({env_home}),"
                f" which cannot run OpenRocket 24.12.\n"
                "Set it to a JDK 17+ install, or remove it if another is on PATH."
            )

    import jpype
    import jpype.imports

    jar = Path(jar_path or os.environ.get("OPENROCKET_JAR") or DEFAULT_JAR)
    if not jar.exists():
        raise FileNotFoundError(
            f"OpenRocket jar not found at {jar}.\n"
            "Download it with:\n"
            "  curl -L -o sim/vendor/OpenRocket-24.12.jar \\\n"
            "    https://github.com/openrocket/openrocket/releases/download/"
            "release-24.12/OpenRocket-24.12.jar"
        )

    args = ["-Djava.awt.headless=true", f"-Xmx{heap}"]
    if quiet:
        # OpenRocket logs every integration step at DEBUG otherwise.
        args.append("-Dlogback.configurationFile=" + _quiet_logback())

    if not jpype.isJVMStarted():
        try:
            jvm = jpype.getDefaultJVMPath()
        except Exception as exc:  # noqa: BLE001 - re-raised with guidance
            raise RuntimeError(
                "No Java 17+ runtime found. OpenRocket 24.12 needs one.\n"
                "  Windows: winget install Microsoft.OpenJDK.17\n"
                "  macOS  : brew install --cask temurin17\n"
                "  Linux  : sudo apt install openjdk-17-jdk\n"
                "Then re-run, or set JAVA_HOME explicitly." + stale_note
            ) from exc
        jpype.startJVM(jvm, *args, classpath=[str(jar)], convertStrings=True)

    # Whatever JPype ended up loading, check it before touching OpenRocket's
    # classes.  Otherwise a too-old JVM surfaces as UnsupportedClassVersionError
    # from deep inside the JVM, which tells a student nothing.
    running = str(jpype.java.lang.System.getProperty("java.specification.version"))
    running_major = _major_from_version(running)
    if running_major is not None and running_major < MIN_JAVA_MAJOR:
        raise RuntimeError(
            f"Java {running_major} is running, but OpenRocket 24.12 needs "
            f"{MIN_JAVA_MAJOR} or newer.\n"
            f"  JVM: {jpype.getDefaultJVMPath()}\n"
            "  Windows: winget install Microsoft.OpenJDK.17\n"
            "  macOS  : brew install --cask temurin17\n"
            "  Linux  : sudo apt install openjdk-17-jdk\n"
            "Then point JAVA_HOME at it, or remove JAVA_HOME if a newer JDK is "
            "already on PATH." + stale_note
        )

    core = jpype.JPackage("info").openrocket.core
    if not core.startup.OpenRocketCore.isInitialized():
        core.startup.OpenRocketCore.initialize(core.plugin.PluginModule())

    _or = core
    _JVM_STARTED = True
    return _or


def _quiet_logback() -> str:
    """Write (once) a logback config that silences OpenRocket's DEBUG spew."""
    path = REPO_ROOT / "output" / ".logback-quiet.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            '<configuration>\n'
            '  <appender name="STDERR" class="ch.qos.logback.core.ConsoleAppender">\n'
            '    <target>System.err</target>\n'
            '    <encoder><pattern>%-5level %logger{16} - %msg%n</pattern></encoder>\n'
            '  </appender>\n'
            '  <root level="ERROR"><appender-ref ref="STDERR"/></root>\n'
            '</configuration>\n',
            encoding="utf-8",
        )
    return path.as_uri()


def java_file(path: str | Path):
    import jpype
    return jpype.JClass("java.io.File")(str(Path(path).resolve()))


# ---------------------------------------------------------------------------
#  Motor lookup
# ---------------------------------------------------------------------------
def find_motor(search: str, manufacturer: str = "", diameter_m: float | None = None):
    """Find a ThrustCurveMotor in OpenRocket's bundled database.

    The jar ships ~1088 motor sets, so there is no network dependency and no
    per-machine motor file to keep in sync.
    """
    core = ensure_jvm()
    db = core.startup.Application.getThrustCurveMotorSetDatabase()

    needle = search.upper().replace(" ", "")
    hits = []
    for mset in db.getMotorSets():
        for motor in mset.getMotors():
            desig = str(motor.getDesignation()).upper().replace(" ", "")
            manu = str(motor.getManufacturer())
            if needle not in desig:
                continue
            if manufacturer and manufacturer.lower() not in manu.lower():
                continue
            if diameter_m and abs(float(motor.getDiameter()) - diameter_m) > 0.004:
                continue
            hits.append(motor)

    if not hits:
        raise LookupError(
            f"No motor matching {search!r}"
            + (f" from {manufacturer!r}" if manufacturer else "")
            + ". Run scripts/list_motors.py to browse the database."
        )
    # Prefer an exact designation match, then the longest burn (usually the
    # canonical entry rather than a re-certified variant).
    exact = [m for m in hits if str(m.getDesignation()).upper().replace(" ", "") == needle]
    return (exact or hits)[0]


def motor_summary(motor) -> dict[str, float | str]:
    return {
        "designation": str(motor.getDesignation()),
        "manufacturer": str(motor.getManufacturer()),
        "total_impulse_ns": float(motor.getTotalImpulseEstimate()),
        "burn_time_s": float(motor.getBurnTimeEstimate()),
        "avg_thrust_n": float(motor.getAverageThrustEstimate()),
        "max_thrust_n": float(motor.getMaxThrustEstimate()),
        "propellant_mass_kg": float(motor.getLaunchMass() - motor.getBurnoutMass()),
        "launch_mass_kg": float(motor.getLaunchMass()),
        "burnout_mass_kg": float(motor.getBurnoutMass()),
        "diameter_m": float(motor.getDiameter()),
        "length_m": float(motor.getLength()),
    }


# ---------------------------------------------------------------------------
#  Build a Rocket from the YAML spec
# ---------------------------------------------------------------------------
_SHAPES = {
    "conical": "CONICAL", "ogive": "OGIVE", "ellipsoid": "ELLIPSOID",
    "power": "POWER", "parabolic": "PARABOLIC", "haack": "HAACK",
}
_FINISH = {
    "rough": "ROUGH", "unfinished": "UNFINISHED", "regular_paint": "NORMAL",
    "smooth": "SMOOTH", "polished": "POLISHED",
}


def build_document(vehicle: Vehicle, ballast_kg: float = 0.0):
    """Construct an OpenRocketDocument from the vehicle spec.

    Component masses are set with ``setOverrideMass`` rather than by picking
    materials and letting OpenRocket compute them.  That is deliberate: the
    team weighs real sections on a scale, and an as-built mass is worth far
    more than a density estimate.  It also guarantees the OpenRocket and
    RocketPy models carry byte-identical masses.
    """
    core = ensure_jvm()
    import jpype
    RC = core.rocketcomponent
    AxialMethod = jpype.JClass("info.openrocket.core.rocketcomponent.position.AxialMethod")
    Shape = jpype.JClass("info.openrocket.core.rocketcomponent.Transition$Shape")
    DeployEvent = jpype.JClass(
        "info.openrocket.core.rocketcomponent.DeploymentConfiguration$DeployEvent")
    Finish = jpype.JClass("info.openrocket.core.rocketcomponent.ExternalComponent$Finish")

    rocket = RC.Rocket()
    rocket.setName(vehicle.name)

    stage = RC.AxialStage()
    stage.setName("Sustainer")
    rocket.addChild(stage)

    finish = getattr(Finish, _FINISH.get(vehicle.surface_finish, "NORMAL"))

    # --- nose cone
    nose = RC.NoseCone()
    nose.setName("Nose Cone")
    nose.setShapeType(getattr(Shape, _SHAPES[vehicle.nose_shape.lower()]))
    nose.setShapeParameter(vehicle.nose_shape_parameter)
    nose.setLength(vehicle.nose_length_m)
    nose.setBaseRadius(vehicle.outer_radius_m)
    nose.setThickness(vehicle.nose_thickness_m)
    nose.setShoulderRadius(vehicle.outer_radius_m - vehicle.wall_thickness_m)
    nose.setShoulderLength(vehicle.nose_shoulder_length_m)
    nose.setShoulderThickness(vehicle.wall_thickness_m)
    nose.setFinish(finish)
    nose.setOverrideMass(vehicle.nose_mass_kg)
    nose.setMassOverridden(True)
    stage.addChild(nose)

    # --- body sections
    tubes = {}
    for sec in vehicle.sections:
        tube = RC.BodyTube()
        tube.setName(sec.name)
        tube.setLength(sec.length_m)
        tube.setOuterRadius(vehicle.outer_radius_m)
        tube.setThickness(vehicle.wall_thickness_m)
        tube.setFinish(finish)
        mass = sec.mass_kg + (ballast_kg if sec.name == vehicle.ballast_location else 0.0)
        tube.setOverrideMass(mass)
        tube.setMassOverridden(True)
        stage.addChild(tube)
        tubes[sec.name] = tube

    if not tubes:
        raise ValueError("vehicle.yaml defines no body sections")
    booster = list(tubes.values())[-1]

    # --- fins on the aft-most tube
    fins = RC.TrapezoidFinSet()
    fins.setName("Fin Set")
    fins.setFinCount(vehicle.fin_count)
    fins.setFinShape(
        vehicle.fin_root_chord_m, vehicle.fin_tip_chord_m,
        vehicle.fin_sweep_m, vehicle.fin_height_m, vehicle.fin_thickness_m,
    )
    fins.setCantAngle(math.radians(vehicle.fin_cant_deg))
    fins.setAxialMethod(AxialMethod.BOTTOM)
    fins.setAxialOffset(-vehicle.fin_offset_from_aft_m)
    fins.setFinish(finish)
    fins.setOverrideMass(vehicle.fin_mass_kg)
    fins.setMassOverridden(True)
    booster.addChild(fins)

    # --- rail buttons
    button = RC.RailButton()
    button.setName("Rail Buttons")
    button.setAxialMethod(AxialMethod.BOTTOM)
    button.setAxialOffset(-vehicle.fin_root_chord_m)
    button.setInstanceCount(2)
    # Zeroed: the section mass_lb values in vehicle.yaml are AS-BUILT and
    # already include internal structure like buttons and the motor mount.
    # Without this, OpenRocket adds its own material-derived mass on top and
    # the FRR mass budget no longer closes.
    button.setOverrideMass(0.0)
    button.setMassOverridden(True)
    booster.addChild(button)

    # --- motor mount
    mount = RC.InnerTube()
    mount.setName("Motor Mount")
    mount.setOuterRadius(vehicle.motor_mount_inner_radius_m + 0.0015)
    mount.setInnerRadius(vehicle.motor_mount_inner_radius_m)
    mount.setLength(vehicle.motor_mount_length_m)
    mount.setAxialMethod(AxialMethod.BOTTOM)
    mount.setAxialOffset(0.0)
    mount.setMotorMount(True)
    mount.setMotorOverhang(vehicle.motor_overhang_m)
    mount.setOverrideMass(0.0)      # see the rail-button note above
    mount.setMassOverridden(True)
    booster.addChild(mount)

    # --- recovery devices
    #  Drogue rides in the section forward of the av-bay; main forward of that.
    #  Exact bay assignment barely moves the trajectory but does move the CG,
    #  so it is modeled rather than lumped.
    def add_chute(spec: dict, parent, offset_frac: float):
        chute = RC.Parachute()
        chute.setName(spec["name"])
        chute.setDiameter(spec["diameter_m"])
        chute.setCD(spec["cd"])
        chute.setCDAutomatic(False)
        chute.setRadius(vehicle.outer_radius_m * 0.85)
        chute.setLength(vehicle.outer_radius_m)
        chute.setOverrideMass(spec["mass_kg"])
        chute.setMassOverridden(True)
        chute.setAxialMethod(AxialMethod.TOP)
        chute.setAxialOffset(parent.getLength() * offset_frac)
        cfg = chute.getDeploymentConfigurations().getDefault()
        if spec["deploy_event"] == "altitude":
            cfg.setDeployEvent(DeployEvent.ALTITUDE)
            cfg.setDeployAltitude(spec["deploy_altitude_m"])
        else:
            cfg.setDeployEvent(DeployEvent.APOGEE)
        cfg.setDeployDelay(spec["deploy_delay_s"])
        parent.addChild(chute)
        return chute

    add_chute(vehicle.main, list(tubes.values())[0], 0.55)
    add_chute(vehicle.drogue, booster, 0.10)

    # --- shock cord, lumped at the av-bay
    if vehicle.shock_cord_mass_kg > 0:
        cord = RC.MassComponent()
        cord.setName("Shock Cord + Hardware")
        cord.setComponentMass(vehicle.shock_cord_mass_kg)
        cord.setLength(vehicle.outer_radius_m)
        cord.setRadius(vehicle.outer_radius_m * 0.7)
        cord.setAxialMethod(AxialMethod.MIDDLE)
        cord.setAxialOffset(0.0)
        mid = list(tubes.values())[len(tubes) // 2]
        mid.addChild(cord)

    # --- flight configuration + motor
    #  A named FlightConfigurationId must exist before a motor can be bound to
    #  the mount; the rocket's default "selected" configuration is not one.
    FCID = jpype.JClass("info.openrocket.core.rocketcomponent.FlightConfigurationId")
    config_id = FCID()
    config = rocket.createFlightConfiguration(config_id)
    rocket.setSelectedConfiguration(config_id)

    motor = find_motor(vehicle.motor_search, vehicle.motor_manufacturer,
                       vehicle.motor_mount_inner_radius_m * 2.0)
    mcfg = core.motor.MotorConfiguration(mount, config_id)
    mcfg.setMotor(motor)
    # Requirement 3.1.3 forbids motor ejection as a deployment method, so the
    # motor is modeled PLUGGED.  Leaving the default delay in place fires an
    # ejection charge at burnout and silently invalidates the whole descent.
    Motor = jpype.JClass("info.openrocket.core.motor.Motor")
    mcfg.setEjectionDelay(float(Motor.PLUGGED_DELAY))
    mcfg.setIgnitionDelay(vehicle.motor_ignition_delay_s)
    mount.setMotorConfig(mcfg, config_id)
    mount.setMotorMount(True)

    config.setAllStages()
    config.setName(f"{motor.getDesignation()}")

    DocFactory = jpype.JClass("info.openrocket.core.document.OpenRocketDocumentFactory")
    doc = DocFactory.createDocumentFromRocket(rocket)

    return doc, rocket, mount, motor


def save_ork(doc, path: str | Path) -> Path:
    """Write the document to a .ork the team can open in the OpenRocket GUI."""
    core = ensure_jvm()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    core.file.GeneralRocketSaver().save(java_file(path), doc)
    return path


def load_ork(path: str | Path):
    """Load a team-authored .ork instead of generating one from YAML."""
    core = ensure_jvm()
    doc = core.file.GeneralRocketLoader(java_file(path)).load()
    return doc, doc.getRocket()


# ---------------------------------------------------------------------------
#  Simulation
# ---------------------------------------------------------------------------
@dataclass
class ORResult:
    """Everything the requirement checks and the report need, in SI."""

    apogee_m: float
    max_velocity_mps: float
    max_acceleration_mps2: float
    max_mach: float
    rail_exit_velocity_mps: float
    time_to_apogee_s: float
    flight_time_s: float
    descent_time_s: float
    ground_hit_velocity_mps: float      # TOTAL speed at impact (includes drift)
    landing_vertical_mps: float         # vertical descent rate at impact
    descent_rate_drogue_mps: float      # steady-state rate under drogue
    descent_rate_main_mps: float        # steady-state rate under main
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
    warnings: list[str] = field(default_factory=list)
    events: list[tuple[str, float]] = field(default_factory=list)
    series: dict[str, np.ndarray] = field(default_factory=dict)

    def to_row(self) -> dict[str, float]:
        """Flat, imperial-facing row for dataframes and report tables."""
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


def static_stability(rocket, mach: float = 0.3) -> tuple[float, float, float]:
    """Static margin on the pad, in calibers, at a given Mach.

    Requirement 2.11 says "while sitting on the pad", but a Barrowman CP is
    undefined at exactly zero airspeed, so OpenRocket's own GUI evaluates at a
    reference Mach (0.3 by default).  We do the same, and the caller can sweep
    Mach if a reviewer asks.

    Returns (margin_calibers, cg_m, cp_m), both positions from the nose tip.
    """
    core = ensure_jvm()
    cfg = rocket.getSelectedConfiguration()
    conditions = core.aerodynamics.FlightConditions(cfg)
    conditions.setMach(mach)
    conditions.setAOA(0.0)
    warnings = core.logging.WarningSet()

    cp = core.aerodynamics.BarrowmanCalculator().getCP(cfg, conditions, warnings)
    launch = core.masscalc.MassCalculator.calculateLaunch(cfg)
    cg_x = float(launch.getCM().x)
    cp_x = float(cp.x)
    caliber = float(cfg.getReferenceLength() if hasattr(cfg, "getReferenceLength")
                    else rocket.getSelectedConfiguration().getReferenceLength())
    return (cp_x - cg_x) / caliber, cg_x, cp_x


def make_simulation(doc, rocket, site: Site, overrides: dict | None = None):
    """Create a Simulation with SimulationOptions from the site + overrides.

    `overrides` keys (all SI, all optional):
        wind_speed_mps, wind_direction_deg, wind_turbulence,
        temperature_k, pressure_pa, rail_angle_deg, rail_direction_deg,
        rail_length_m, random_seed, time_step
    """
    core = ensure_jvm()
    o = overrides or {}

    sim = core.document.Simulation(doc, rocket)
    sim.setName("slisim")
    opts = sim.getOptions()

    opts.setLaunchLatitude(site.latitude)
    opts.setLaunchLongitude(site.longitude)
    opts.setLaunchAltitude(site.elevation_m)
    opts.setLaunchRodLength(o.get("rail_length_m", site.rail_length_m))
    opts.setLaunchRodAngle(math.radians(o.get("rail_angle_deg", 5.0)))
    opts.setLaunchRodDirection(math.radians(o.get("rail_direction_deg", 0.0)))
    opts.setLaunchIntoWind(False)  # we control direction explicitly

    opts.setWindSpeedAverage(o.get("wind_speed_mps", site.wind_speed_mps))
    opts.setWindDirection(math.radians(o.get("wind_direction_deg", site.wind_direction_deg)))
    # Turbulence intensity defaults to 0, matching OpenRocket's own default.
    #
    # It is deliberately NOT enabled by default.  OpenRocket's pink-noise wind
    # model seeds itself independently of SimulationOptions.setRandomSeed, so
    # any non-zero turbulence makes results irreproducible -- repeated runs of
    # an identical configuration scatter drift by several percent, and a number
    # quoted in a report could not be regenerated.  Wind variability belongs in
    # the Monte Carlo, where wind speed and direction are dispersed explicitly
    # and the seed genuinely controls the outcome.
    #
    # Pass wind_turbulence explicitly to enable it for a one-off study.
    opts.setWindTurbulenceIntensity(o.get("wind_turbulence", 0.0))

    opts.setISAAtmosphere(False)
    opts.setLaunchTemperature(o.get("temperature_k", site.temperature_k))
    opts.setLaunchPressure(o.get("pressure_pa", site.pressure_pa))

    if "time_step" in o:
        opts.setTimeStep(o["time_step"])

    # Seed the wind-turbulence generator explicitly.  OpenRocket otherwise
    # draws a fresh seed per simulation, which makes a "nominal" run
    # irreproducible -- apogee and especially drift wander by a few tenths of a
    # percent and several percent respectively between identical invocations.
    # Monte Carlo passes its own per-sample seed; everything else gets a fixed
    # default so a result quoted in a report can be regenerated exactly.
    opts.setRandomSeed(int(o.get("random_seed", 1)))

    return sim


def run_simulation(sim, rocket, keep_series: bool = True) -> ORResult:
    """Execute one OpenRocket simulation and pull everything out of it."""
    core = ensure_jvm()
    FDT = core.simulation.FlightDataType

    sim.simulate()
    fd = sim.getSimulatedData()
    branch = fd.getBranch(0)

    def series(dtype) -> np.ndarray:
        vals = branch.get(dtype)
        return np.asarray([float(v) for v in vals]) if vals is not None else np.array([])

    t = series(FDT.TYPE_TIME)
    alt = series(FDT.TYPE_ALTITUDE)
    stab = series(FDT.TYPE_STABILITY)
    px = series(FDT.TYPE_POSITION_X)
    py = series(FDT.TYPE_POSITION_Y)

    events = [(str(e.getType()), float(e.getTime())) for e in branch.getEvents()]

    # --- rail-exit stability: the first sample after launch-rod clearance
    stab_rail = float("nan")
    clear_t = next((tm for name, tm in events if "CLEARANCE" in name.upper()), None)
    if clear_t is not None and len(t) and len(stab):
        idx = int(np.searchsorted(t, clear_t))
        if idx < len(stab):
            stab_rail = float(stab[idx])

    # --- masses and thrust-to-weight
    cfg = rocket.getSelectedConfiguration()
    launch_mass = float(core.masscalc.MassCalculator.calculateLaunch(cfg).getMass())
    burnout_mass = float(core.masscalc.MassCalculator.calculateBurnout(cfg).getMass())
    thrust = series(FDT.TYPE_THRUST_FORCE)
    # Requirement 2.12 is conventionally read as AVERAGE thrust over weight;
    # we report the average because that is the stricter of the two.
    burn = thrust[thrust > 1.0]
    avg_thrust = float(burn.mean()) if burn.size else 0.0
    twr = avg_thrust / (launch_mass * U.G0) if launch_mass else 0.0

    static_cal, cg_x, cp_x = static_stability(rocket)

    apogee_t = float(fd.getTimeToApogee())
    flight_t = float(fd.getFlightTime())
    land_x = float(px[-1]) if px.size else 0.0
    land_y = float(py[-1]) if py.size else 0.0

    # --- descent rates.
    #  The handbook's FRR table asks for "descent rate under both drogue and
    #  main parachutes", i.e. the VERTICAL rate.  OpenRocket's
    #  getGroundHitVelocity() is the total speed and therefore includes the
    #  horizontal drift, which in a 10 mph wind is comparable to the descent
    #  rate itself.  Both are reported: vertical for the standard kinetic
    #  energy table, total as the conservative upper bound.
    vz = series(FDT.TYPE_VELOCITY_Z)
    deploy_times = sorted(tm for name, tm in events
                          if "DEPLOY" in name.upper() and "DEVICE" in name.upper())
    land_vz = abs(float(vz[-1])) if vz.size else float("nan")

    def steady_rate(t0: float, t1: float) -> float:
        if not vz.size or t1 <= t0:
            return float("nan")
        # Skip the first 20% of the window so the inflation transient is
        # excluded, then take the median of the remainder.
        lo, hi = t0 + 0.2 * (t1 - t0), t1
        sel = (t >= lo) & (t <= hi)
        return float(np.median(np.abs(vz[sel]))) if sel.any() else float("nan")

    drogue_rate = main_rate = float("nan")
    if len(deploy_times) >= 2:
        drogue_rate = steady_rate(deploy_times[0], deploy_times[1])
        main_rate = steady_rate(deploy_times[1], flight_t)
    elif len(deploy_times) == 1:
        main_rate = steady_rate(deploy_times[0], flight_t)

    # Max acceleration is taken over the ASCENT only.  The handbook wants this
    # to "verify the vehicle is robust enough to withstand the expected loads",
    # which is a boost-phase question; including the descent lets the parachute
    # inflation spike dominate, and the two engines model that spike very
    # differently, making the cross-check meaningless.
    accel = series(FDT.TYPE_ACCELERATION_TOTAL)
    ascent = t <= apogee_t if len(t) else np.array([], dtype=bool)
    max_accel = float(np.nanmax(accel[ascent])) if accel.size and ascent.any() \
        else float(fd.getMaxAcceleration())

    res = ORResult(
        apogee_m=float(fd.getMaxAltitude()),
        max_velocity_mps=float(fd.getMaxVelocity()),
        max_acceleration_mps2=max_accel,
        max_mach=float(fd.getMaxMachNumber()),
        rail_exit_velocity_mps=float(fd.getLaunchRodVelocity()),
        time_to_apogee_s=apogee_t,
        flight_time_s=flight_t,
        descent_time_s=flight_t - apogee_t,
        ground_hit_velocity_mps=float(fd.getGroundHitVelocity()),
        landing_vertical_mps=land_vz,
        descent_rate_drogue_mps=drogue_rate,
        descent_rate_main_mps=main_rate,
        drift_m=math.hypot(land_x, land_y),
        landing_x_m=land_x,
        landing_y_m=land_y,
        stability_on_pad_cal=static_cal,
        stability_rail_exit_cal=stab_rail,
        cg_on_pad_m=cg_x,
        cp_on_pad_m=cp_x,
        launch_mass_kg=launch_mass,
        burnout_mass_kg=burnout_mass,
        thrust_to_weight=twr,
        warnings=[str(w) for w in fd.getWarningSet()],
        events=events,
    )

    if keep_series:
        res.series = {
            "time_s": t,
            "altitude_m": alt,
            "velocity_z_mps": series(FDT.TYPE_VELOCITY_Z),
            "velocity_total_mps": series(FDT.TYPE_VELOCITY_TOTAL),
            "acceleration_mps2": series(FDT.TYPE_ACCELERATION_TOTAL),
            "mach": series(FDT.TYPE_MACH_NUMBER),
            "stability_cal": stab,
            "cg_m": series(FDT.TYPE_CG_LOCATION),
            "cp_m": series(FDT.TYPE_CP_LOCATION),
            "drag_coefficient": series(FDT.TYPE_DRAG_COEFF),
            # Drag buildup, so the team can see WHERE the drag comes from
            # rather than only its total.  Skin friction dominates at low Mach
            # on a long slender airframe; base drag grows sharply after burnout
            # when the motor stops filling the base area.
            "friction_drag": series(FDT.TYPE_FRICTION_DRAG_COEFF),
            "pressure_drag": series(FDT.TYPE_PRESSURE_DRAG_COEFF),
            "base_drag": series(FDT.TYPE_BASE_DRAG_COEFF),
            "axial_drag": series(FDT.TYPE_AXIAL_DRAG_COEFF),
            "thrust_n": thrust,
            "mass_kg": series(FDT.TYPE_MASS),
            "position_x_m": px,
            "position_y_m": py,
        }
    return res


def simulate(vehicle: Vehicle, site: Site, ballast_kg: float = 0.0,
             overrides: dict | None = None, keep_series: bool = True,
             ork_path: str | Path | None = None) -> ORResult:
    """Build -> (optionally save) -> simulate, in one call."""
    doc, rocket, _mount, _motor = build_document(vehicle, ballast_kg)
    if ork_path:
        save_ork(doc, ork_path)
    sim = make_simulation(doc, rocket, site, overrides)
    return run_simulation(sim, rocket, keep_series=keep_series)
