"""Load and validate the YAML configuration.

The vehicle spec is authored in imperial units (that is how the handbook and
the team think).  This module parses it, converts to SI once, and exposes
derived quantities -- notably the mass bookkeeping that the FRR requires to
balance exactly.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from . import units as U

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
VEHICLE_DIR = CONFIG_DIR / "vehicles"


def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def default_vehicle_path() -> Path:
    """The vehicle used when no --vehicle is given.

    A team carries several vehicles at once -- full-scale, subscale, and the
    layout options behind a PDR decision -- so they live in config/vehicles/ and
    are chosen per run.  `full_scale.yaml` is the default because it is the one
    every requirement is actually scored against.

    The pre-split `config/vehicle.yaml` still wins if it exists, so a branch or
    working copy from before the move keeps running.
    """
    legacy = CONFIG_DIR / "vehicle.yaml"
    if legacy.is_file():
        return legacy
    return VEHICLE_DIR / "full_scale.yaml"


def available_vehicles() -> list[Path]:
    """Every vehicle definition, for listing in a --help or an error message."""
    return sorted(VEHICLE_DIR.glob("*.yaml"))


def slug(text: str) -> str:
    """A filesystem-safe stem: 'Template Full-Scale' -> 'template_full_scale'.

    Used for the per-vehicle output directory, so two vehicles cannot overwrite
    each other's figures.
    """
    keep = [c.lower() if c.isalnum() else "_" for c in text.strip()]
    return re.sub(r"_+", "_", "".join(keep)).strip("_") or "vehicle"


def output_dir(base: str | Path, vehicle: "Vehicle | None" = None,
               kind: str = "") -> Path:
    """Where one run's files belong: `base/<vehicle>/<kind>`.

    Splitting by vehicle is not tidiness -- most output filenames do not name
    the vehicle, so a subscale run and a full-scale run would otherwise write
    the same `flight_profile_0lb.png` and silently overwrite each other.  That
    is at its worst comparing two PDR layouts, where the mistake looks like a
    result.

    The vehicle level is appended even under an explicit `--out`, so the
    protection cannot be defeated by forgetting a flag.  One rule, always.
    """
    path = Path(base)
    if vehicle is not None:
        path = path / vehicle.slug
    if kind:
        path = path / kind
    return path


# ---------------------------------------------------------------------------
#  Vehicle
# ---------------------------------------------------------------------------
@dataclass
class Section:
    """One body section, nose-to-tail."""

    name: str
    length_m: float
    mass_kg: float
    # Where that mass sits, from the front of the section.  None means "assume
    # it is spread evenly", which puts the CG at the midpoint -- fine until a
    # section carries something heavy and off-centre, such as a payload or a
    # coupler at one end.
    cg_from_front_m: float | None = None

    @property
    def length_in(self) -> float:
        return U.m_to_in(self.length_m)

    @property
    def mass_lb(self) -> float:
        return U.kg_to_lb(self.mass_kg)


VEHICLE_TYPES = ("full_scale", "subscale")


def _vehicle_type(d: dict, path: Path) -> str:
    """Which requirement set governs this vehicle.

    Defaults to `full_scale`, so every existing vehicle file keeps being scored
    against the full requirement set.  A subscale is opted in explicitly rather
    than guessed from the filename: silently downgrading a full-scale vehicle to
    the lenient set because someone renamed a file would hide real failures.
    """
    vt = str(d.get("vehicle_type", "full_scale")).lower()
    if vt not in VEHICLE_TYPES:
        raise ValueError(
            f"{path.name}: vehicle_type {vt!r} is not one of {VEHICLE_TYPES}"
        )
    return vt


@dataclass
class Transition:
    """A change of body diameter: a boat tail, a shoulder, or a flare.

    `after_section` names the section this follows, so the transition travels
    with its neighbour if sections are reordered.  Omit it and the transition
    goes at the aft end, which is where a boat tail lives.
    """

    name: str
    after_section: str | None
    fore_radius_m: float
    aft_radius_m: float
    length_m: float
    shape: str
    shape_parameter: float
    wall_thickness_m: float
    mass_kg: float

    @property
    def length_in(self) -> float:
        return U.m_to_in(self.length_m)

    @property
    def mass_lb(self) -> float:
        return U.kg_to_lb(self.mass_kg)


@dataclass
class Vehicle:
    raw: dict

    name: str
    team: str
    season: str
    status: str
    vehicle_type: str          # full_scale | subscale
    scales_from: str | None    # subscale only: the full-scale it represents
    target_apogee_m: float

    outer_radius_m: float
    wall_thickness_m: float
    surface_finish: str

    nose_shape: str
    nose_shape_parameter: float
    nose_length_m: float
    nose_thickness_m: float
    nose_shoulder_length_m: float
    nose_mass_kg: float
    nose_cg_from_tip_m: float | None

    sections: list[Section]
    transitions: list[Transition]

    fin_count: int
    fin_root_chord_m: float
    fin_tip_chord_m: float
    fin_sweep_m: float
    fin_height_m: float
    fin_thickness_m: float
    fin_cant_deg: float
    fin_offset_from_aft_m: float
    fin_mass_kg: float

    rail_size_in: float

    motor_search: str
    motor_manufacturer: str
    motor_mount_inner_radius_m: float
    motor_mount_length_m: float
    motor_overhang_m: float
    motor_ignition_delay_s: float

    drogue: dict
    main: dict
    shock_cord_mass_kg: float
    shock_cord_bay: str | None
    shock_cord_cg_from_front_m: float | None

    landing_sections: list[dict]

    ballast_min_kg: float
    ballast_max_kg: float
    ballast_location: str

    # ------------------------------------------------------------------
    @classmethod
    def from_yaml(cls, path: str | Path | None = None) -> "Vehicle":
        path = Path(path) if path else default_vehicle_path()
        d = _load_yaml(path)

        af, nc, fn = d["airframe"], d["nose_cone"], d["fins"]
        mo, rc = d["motor"], d["recovery"]
        ba = d.get("ballast") or {}

        def opt_in_to_m(v) -> float | None:
            return None if v is None else U.in_to_m(float(v))

        sections = [
            Section(
                name=s["name"],
                length_m=U.in_to_m(s["length_in"]),
                mass_kg=U.lb_to_kg(s["mass_lb"]),
                cg_from_front_m=opt_in_to_m(s.get("cg_from_front_in")),
            )
            for s in d["sections"]
        ]

        section_names = {s.name for s in sections}
        transitions = []
        for t in d.get("transitions") or []:
            after = t.get("after_section")
            if after is not None and after not in section_names:
                raise ValueError(
                    f"transition {t.get('name', '?')!r} names after_section "
                    f"{after!r}, which is not a section; have {sorted(section_names)}"
                )
            transitions.append(Transition(
                name=t.get("name", "Transition"),
                after_section=after,
                fore_radius_m=U.in_to_m(t["fore_diameter_in"]) / 2.0,
                aft_radius_m=U.in_to_m(t["aft_diameter_in"]) / 2.0,
                length_m=U.in_to_m(t["length_in"]),
                shape=t.get("shape", "conical"),
                shape_parameter=float(t.get("shape_parameter", 1.0)),
                wall_thickness_m=U.in_to_m(
                    t.get("wall_thickness_in", af["wall_thickness_in"])),
                mass_kg=U.lb_to_kg(float(t.get("mass_lb", 0.0))),
            ))

        def chute(key: str) -> dict:
            c = rc[key]
            dia = U.in_to_m(c["diameter_in"])
            alt_ft = c.get("deploy_altitude_ft")
            return {
                "name": c.get("name", key.title()),
                "diameter_m": dia,
                "area_m2": math.pi * (dia / 2.0) ** 2,
                "cd": float(c["cd"]),
                "deploy_event": c.get("deploy_event", "apogee"),
                "deploy_delay_s": float(c.get("deploy_delay_s", 0.0)),
                "deploy_altitude_m": U.ft_to_m(float(alt_ft)) if alt_ft is not None else 0.0,
                "mass_kg": U.lb_to_kg(float(c.get("mass_lb", 0.0))),
                # Which section it rides in, and where.  Unset means "use the
                # conventional bay", which is what every vehicle file did before
                # these keys existed.  A main packed aft instead of forward is
                # worth about an inch of CG on a 26 lb vehicle, so it is worth
                # stating rather than assuming.
                "bay": c.get("bay"),
                "cg_from_front_m": opt_in_to_m(c.get("cg_from_front_in")),
            }

        return cls(
            raw=d,
            name=d["name"],
            team=d.get("team", ""),
            season=d.get("season", ""),
            status=d.get("status", ""),
            vehicle_type=_vehicle_type(d, path),
            scales_from=d.get("scales_from"),
            target_apogee_m=U.ft_to_m(float(d.get("target_apogee_ft", 5000.0))),
            outer_radius_m=U.in_to_m(af["outer_diameter_in"]) / 2.0,
            wall_thickness_m=U.in_to_m(af["wall_thickness_in"]),
            surface_finish=af.get("surface_finish", "regular_paint"),
            nose_shape=nc["shape"],
            nose_shape_parameter=float(nc.get("shape_parameter", 1.0)),
            nose_length_m=U.in_to_m(nc["length_in"]),
            nose_thickness_m=U.in_to_m(nc["wall_thickness_in"]),
            nose_shoulder_length_m=U.in_to_m(nc.get("shoulder_length_in", 0.0)),
            nose_mass_kg=U.lb_to_kg(nc["mass_lb"]),
            nose_cg_from_tip_m=opt_in_to_m(nc.get("cg_from_tip_in")),
            sections=sections,
            transitions=transitions,
            fin_count=int(fn["count"]),
            fin_root_chord_m=U.in_to_m(fn["root_chord_in"]),
            fin_tip_chord_m=U.in_to_m(fn["tip_chord_in"]),
            fin_sweep_m=U.in_to_m(fn["sweep_in"]),
            fin_height_m=U.in_to_m(fn["height_in"]),
            fin_thickness_m=U.in_to_m(fn["thickness_in"]),
            fin_cant_deg=float(fn.get("cant_deg", 0.0)),
            fin_offset_from_aft_m=U.in_to_m(fn.get("offset_from_aft_in", 0.0)),
            fin_mass_kg=U.lb_to_kg(fn["mass_lb"]),
            rail_size_in=float((d.get("rail_guide") or {}).get("rail_size_in", 1.5)),
            motor_search=mo["search"],
            motor_manufacturer=mo.get("manufacturer", ""),
            motor_mount_inner_radius_m=U.in_to_m(mo["mount_inner_diameter_in"]) / 2.0,
            motor_mount_length_m=U.in_to_m(mo["mount_length_in"]),
            motor_overhang_m=U.in_to_m(mo.get("overhang_in", 0.0)),
            motor_ignition_delay_s=float(mo.get("ignition_delay_s", 0.0)),
            drogue=chute("drogue"),
            main=chute("main"),
            shock_cord_mass_kg=U.lb_to_kg(float(rc.get("shock_cord_mass_lb", 0.0))),
            shock_cord_bay=rc.get("shock_cord_bay"),
            shock_cord_cg_from_front_m=opt_in_to_m(rc.get("shock_cord_cg_from_front_in")),
            landing_sections=d.get("landing_sections", []),
            ballast_min_kg=U.lb_to_kg(float(ba.get("min_lb", 0.0))),
            ballast_max_kg=U.lb_to_kg(float(ba.get("max_lb", 0.0))),
            ballast_location=ba.get("location", sections[0].name if sections else ""),
        )

    # --- derived geometry ---------------------------------------------
    @property
    def diameter_m(self) -> float:
        return 2.0 * self.outer_radius_m

    @property
    def reference_area_m2(self) -> float:
        return math.pi * self.outer_radius_m ** 2

    @property
    def body_length_m(self) -> float:
        return sum(s.length_m for s in self.sections)

    @property
    def body_end_m(self) -> float:
        """Station of the aft end of the last body tube, from the nose tip.

        This -- not `total_length_m` -- is what the motor, fins and rail buttons
        are positioned against.  A boat tail lengthens the vehicle but does not
        move the fin can, so referencing overall length would push all three aft
        by the length of the transition.
        """
        return self.nose_length_m + self.body_length_m

    @property
    def total_length_m(self) -> float:
        """Overall length including transitions -- what a reviewer measures."""
        return self.body_end_m + sum(t.length_m for t in self.transitions)

    # --- mass bookkeeping ---------------------------------------------
    #  Deliberately explicit.  The FRR requires that
    #      sum(landing section masses) + propellant + chutes + cord == GLOW
    #  and reviewers do check the arithmetic.
    def structure_mass_kg(self, ballast_kg: float = 0.0) -> float:
        """Everything bolted to the rocket: no chutes, no cord, no motor."""
        return (
            self.nose_mass_kg
            + sum(s.mass_kg for s in self.sections)
            + sum(t.mass_kg for t in self.transitions)
            + self.fin_mass_kg
            + ballast_kg
        )

    @property
    def slug(self) -> str:
        """Filesystem-safe form of `name`, for this vehicle's output directory."""
        return slug(self.name)

    @property
    def is_subscale(self) -> bool:
        return self.vehicle_type == "subscale"

    def scale_reference(self) -> "Vehicle | None":
        """The full-scale vehicle this subscale represents, for req 2.16.

        `scales_from` is a filename in config/vehicles/ (or a path).  Returns
        None when unset, which the 2.16 check reports as unverifiable rather
        than passing -- a check that quietly passes when it cannot run is worse
        than no check.
        """
        if not self.scales_from:
            return None
        p = Path(self.scales_from)
        if not p.is_absolute() and not p.exists():
            p = VEHICLE_DIR / p
        if not p.is_file():
            raise FileNotFoundError(
                f"{self.name}: scales_from {self.scales_from!r} not found "
                f"(looked in {VEHICLE_DIR})"
            )
        return Vehicle.from_yaml(p)

    def recovery_mass_kg(self) -> float:
        return self.drogue["mass_kg"] + self.main["mass_kg"] + self.shock_cord_mass_kg

    def dry_mass_kg(self, ballast_kg: float = 0.0) -> float:
        """On-pad mass excluding the motor entirely (no case, no propellant)."""
        return self.structure_mass_kg(ballast_kg) + self.recovery_mass_kg()

    def unballasted_pad_mass_kg(self) -> float:
        """Basis for the req 2.20.7 limit (ballast <= 10% of un-ballasted mass)."""
        return self.dry_mass_kg(0.0)

    def landing_section_masses_kg(self, ballast_kg: float = 0.0) -> dict[str, float]:
        """Mass of each independent section as it lands (req 3.2).

        Parachutes and shock cord are excluded: the FRR instructs teams to
        subtract them, since they hang outside the airframe on landing.
        """
        by_member = {"nose_cone": self.nose_mass_kg, "fins": self.fin_mass_kg}
        for s in self.sections:
            by_member[s.name] = s.mass_kg
        for t in self.transitions:
            by_member[t.name] = t.mass_kg
        if ballast_kg:
            loc = self.ballast_location
            by_member[loc] = by_member.get(loc, 0.0) + ballast_kg

        return {
            ls["name"]: sum(by_member.get(m, 0.0) for m in ls["members"])
            for ls in self.landing_sections
        }

    def unassigned_members(self) -> list[str]:
        """Named masses not claimed by any landing section (a spec bug)."""
        claimed = {m for ls in self.landing_sections for m in ls["members"]}
        known = ({"nose_cone", "fins"}
                 | {s.name for s in self.sections}
                 | {t.name for t in self.transitions})
        return sorted(known - claimed)


# ---------------------------------------------------------------------------
#  Site
# ---------------------------------------------------------------------------
@dataclass
class Site:
    key: str
    name: str
    latitude: float
    longitude: float
    elevation_m: float
    rail_length_m: float
    wind_speed_mps: float
    wind_direction_deg: float
    temperature_k: float
    pressure_pa: float
    wind_speed_sigma_mps: float
    wind_direction_sigma_deg: float

    @classmethod
    def from_yaml(cls, key: str | None = None, path: str | Path | None = None) -> "Site":
        path = Path(path) if path else CONFIG_DIR / "sites.yaml"
        d = _load_yaml(path)
        key = key or d.get("default")
        if key not in d["sites"]:
            raise KeyError(f"site {key!r} not in {path}; have {list(d['sites'])}")
        s = d["sites"][key]
        n = s["nominal"]
        return cls(
            key=key,
            name=s["name"],
            latitude=float(s["latitude"]),
            longitude=float(s["longitude"]),
            elevation_m=float(s["elevation_m"]),
            rail_length_m=float(s["rail_length_m"]),
            wind_speed_mps=float(n["wind_speed_mps"]),
            wind_direction_deg=float(n["wind_direction_deg"]),
            temperature_k=float(n["temperature_k"]),
            pressure_pa=float(n["pressure_pa"]),
            wind_speed_sigma_mps=float(s.get("wind_speed_sigma_mps", 2.0)),
            wind_direction_sigma_deg=float(s.get("wind_direction_sigma_deg", 30.0)),
        )


def load_uncertainty(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else CONFIG_DIR / "uncertainty.yaml"
    return _load_yaml(path)
