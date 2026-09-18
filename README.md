# NASA Student Launch — Simulation Framework (2026–2027)

OpenRocket **and** RocketPy driven from one vehicle definition, with Monte Carlo
dispersion and automated USLI requirement checking.

Built against the *2027 Student Launch Handbook & Request for Proposal*, which
NASA publishes at <https://www.nasa.gov/stem/studentlaunch/home/index.html>.
Every requirement check cites its handbook paragraph. **The college/university ruleset is implemented**, not the
middle/high-school one — the altitude window and impulse limit differ between them.

---

## Why both tools

The handbook asks for this directly. In Mission Performance Predictions — which
appears in the PDR, CDR, *and* FRR criteria:

> *"Present data from a different calculation method to verify that original results are accurate."*
> *"Discuss any differences between the different calculations."*
> *"Perform multiple simulations to verify that results are precise."*

Most teams answer the third bullet by running OpenRocket five times with
different wind speeds. Sampling declared uncertainty distributions instead turns
each requirement into a *probability of compliance*, which is a much stronger
claim to defend in a review.

### What is actually independent between the two tools

This matters more than it sounds, and getting it wrong makes the whole
cross-validation claim false.

| | Independent | Shared by construction |
|---|---|---|
| Flight dynamics | ✅ RocketPy 6-DOF/LSODA vs OpenRocket RK4 | |
| CP / normal force | ✅ each over its own geometry description | |
| Fin lift model | ✅ RocketPy: Diederich planform correlation + Prandtl–Glauert. OpenRocket: extended Barrowman. Genuinely different theories | |
| Descent solver | ✅ OpenRocket: Euler 3-DOF. RocketPy: 3-DOF with added mass + Coriolis | |
| Atmosphere, wind, event detection | ✅ | |
| Thrust curve | | ⚠️ exported from OpenRocket's database |
| Mass, CG, inertia | | ⚠️ from OpenRocket's mass calculator |
| **Drag coefficient Cd(Mach)** | | ⚠️ **sampled from OpenRocket's run** |

The drag curve is shared because **RocketPy has no parasitic-drag model** —
`power_off_drag` is a required *input*, not something it derives from geometry.
Any framework claiming RocketPy independently validates OpenRocket's drag
estimate is wrong. What RocketPy independently validates is everything the drag
*feeds into*.

To break that last dependency, fit Cd against real flight data
(`scripts/fit_cd.py`). That is also the single highest-value analysis here:
drag and motor impulse are the two dominant drivers of apogee scatter (Spearman
ρ ≈ −0.53 and +0.61 over 1,000 cases). Motor scatter is fixed at the factory;
drag is the one of the two a team can actually shrink, so replacing the
pre-flight guess with a measured value substantially tightens the predicted
apogee — which is exactly what the req 2.3 altitude score pays out on.

---

## Documentation

Four companion documents live in [`docs/`](docs/):

- **[Setup Guide](docs/SETUP_GUIDE.md)** — what the framework is and why,
  installation on Windows/macOS/Linux from nothing, a verification run, and
  installation troubleshooting. Written for someone who has never used a Python
  virtual environment.
- **[User Guide](docs/USER_GUIDE.md)** — a guided first run, how to define
  your vehicle, launch sites, Monte Carlo dispersion, how to read the output,
  the season workflow, troubleshooting, and a command reference.
- **[Framework Tour](docs/FRAMEWORK_TOUR.md)** — a guided tour of how the code
  is structured, for new team members: read a piece, run it, break it on
  purpose, and finish by contributing a real requirement check.
- **[Flight Dynamics Background](docs/FLIGHT_DYNAMICS.md)** — the physics both
  tools implement, with working equations and full derivations: Barrowman
  normal force and CP, the drag buildup, static and dynamic stability, the
  6-DOF equations of motion, weathercocking, descent dynamics, and the design
  theory behind each USLI requirement.

---

## Setup

Requires **Git**, **Python 3.12 or 3.13** (not 3.14 yet), and a **Java 17+ JDK**.
Full walkthrough, including what each piece is for:
[`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md).

**Windows (PowerShell)**

```powershell
# 1. Java (needed for the headless OpenRocket engine)
winget install Microsoft.OpenJDK.17

# 2. The project
git clone https://github.com/DrJayBee51/nasa-sli-sim.git
cd nasa-sli-sim

# 3. Python environment
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 4. The OpenRocket engine (80 MB, not committed)
New-Item -ItemType Directory -Force vendor | Out-Null
curl.exe -L -o vendor\OpenRocket-24.12.jar `
  https://github.com/openrocket/openrocket/releases/download/release-24.12/OpenRocket-24.12.jar
```

**macOS / Linux (bash)**

```bash
# 1. Java (needed for the headless OpenRocket engine)
brew install --cask temurin17          # macOS
# sudo apt install openjdk-17-jdk      # Linux

# 2. The project
git clone https://github.com/DrJayBee51/nasa-sli-sim.git
cd nasa-sli-sim

# 3. Python environment
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

# 4. The OpenRocket engine (80 MB, not committed)
mkdir -p vendor
curl -L -o vendor/OpenRocket-24.12.jar \
  https://github.com/openrocket/openrocket/releases/download/release-24.12/OpenRocket-24.12.jar
```

On Windows in **Git Bash**, follow the bash block but keep the Windows layout:
`py -3.13 -m venv .venv`, then `.venv/Scripts/python` — `Scripts`, not `bin`.

Note `curl.exe` in the PowerShell block, not `curl` — the bare word is an alias
for `Invoke-WebRequest`. If step 4 fails with
`curl: (35) schannel: ... CRYPT_E_NO_REVOCATION_CHECK`, you are probably on a
managed network that blocks certificate revocation checks; see
[§3.4 of the Setup Guide](docs/SETUP_GUIDE.md#34-curl-35-schannel--crypt_e_no_revocation_check).

`JAVA_HOME` is auto-detected; set it manually only if you have an unusual layout.
Verify everything with `.venv\Scripts\python scripts\run_nominal.py`
(`.venv/bin/python` on macOS/Linux). Elsewhere this README writes `python` for
the venv's interpreter; a bare system `python` fails with `ModuleNotFoundError`.

---

## Layout

```
sim/
├── config/
│   ├── vehicle.yaml       ← THE single source of truth. Edit this.
│   ├── sites.yaml         ← launch sites and their wind statistics
│   └── uncertainty.yaml   ← Monte Carlo dispersions (justify every sigma)
├── slisim/
│   ├── units.py           imperial ↔ SI, in exactly one place
│   ├── config.py          YAML loading + mass bookkeeping
│   ├── or_bridge.py       headless OpenRocket via JPype
│   ├── rocketpy_model.py  RocketPy model built from the same spec
│   ├── requirements.py    every USLI check, each citing its paragraph
│   ├── montecarlo.py      sampling + parallel driver
│   ├── analysis.py        dispersion stats, compliance rates, sensitivity
│   ├── postflight.py      Cd fit from altimeter data
│   └── report.py          every plot in the framework, and the markdown assembly
├── scripts/               ← run these
└── output/                figures, CSVs, markdown reports
```

`config/vehicles/full_scale.yaml` generates **both** the RocketPy model and a real `.ork`
file you can open in the OpenRocket GUI. There is no second place to keep in
sync, and no chance of the two models quietly describing different rockets.

---

## Usage

```bash
# Nominal flight, both engines, full requirement check, writes a .ork
python scripts/run_nominal.py
python scripts/run_nominal.py --ballast both      # req 2.20.7.4 wants both extremes

# Monte Carlo dispersion
python scripts/run_montecarlo.py -n 1000
python scripts/run_montecarlo.py -n 500 --engine openrocket
python scripts/run_montecarlo.py --list-parameters          # what you can disperse
python scripts/run_montecarlo.py -n 1000 --only drag_coefficient   # one variable at a time

# Cross-validation report (PDR/CDR/FRR "different calculation method" bullet)
python scripts/run_crossvalidate.py
python scripts/run_crossvalidate.py --mc 300      # disperse both engines

# Browse motors (* marks the NASA-supported availability list, req 2.7)
python scripts/list_motors.py --nasa

# Post-flight: fit drag from altimeter data (FRR section V)
python scripts/make_synthetic_flight.py --cd-scale 1.18   # practice data
python scripts/fit_cd.py data/flights/synthetic_vdf.csv --wind 9 --temp-f 68
```

---

## Requirements checked automatically

| Req | Constraint | Where |
|---|---|---|
| 2.1 | Apogee 4,000–6,000 ft AGL (zero points outside 3,500–6,500) | `check_apogee` |
| 2.3 | Error vs the target declared at CDR | `check_target_altitude` |
| 2.9 | Total impulse ≤ 5,120 N·s | `check_impulse` |
| 2.11 | Static stability ≥ 2.0 cal on the pad | `check_stability` |
| 2.12 | Thrust-to-weight ≥ 5.0:1 | `check_thrust_to_weight` |
| 2.14 | Rail exit ≥ 52 fps | `check_rail_exit` |
| 2.20.6 | Mach < 1.0 | `check_mach` |
| 2.20.7 | Ballast ≤ 10% of un-ballasted mass | `check_ballast` |
| 2.21 | Mass scoring (<30 lb = 5 pts, 30–40 = 3, >40 = 0) | `check_mass_score` |
| 3.1.1 | Main deploy ≥ 500 ft | `check_main_deploy` |
| 3.1.2 | Apogee event delay ≤ 2 s | `check_apogee_delay` |
| 3.2 | KE ≤ 75 ft·lbf per independent section | `check_kinetic_energy` |
| 3.10 | Drift ≤ 2,500 ft from the pad | `check_drift` |
| 3.11 | Descent time ≤ 100 s | `check_descent_time` |
| FRR-V | Mass budget closes exactly | `check_mass_closure` |

---

## Three judgement calls worth knowing about

**1. Kinetic energy uses the *vertical* descent rate.** OpenRocket's
`getGroundHitVelocity()` is the *total* speed, which includes horizontal drift.
In a 10 mph wind that drift rivals the descent rate and roughly doubles the
computed energy. The handbook's FRR table asks for "descent rate under both
drogue and main parachutes", so the vertical rate is the PASS/FAIL basis — but
the drift-inclusive number is printed alongside every KE check, because a
section really does arrive carrying it. On the template vehicle, the heavier
section passes at 56 ft·lbf on the vertical basis and would fail at 107 ft·lbf
including drift. Worth a deliberate decision, not a default.

**2. Static stability is evaluated at Mach 0.3.** Requirement 2.11 says "while
sitting on the pad", but a Barrowman CP is undefined at zero airspeed.
Mach 0.3 is OpenRocket's own GUI convention, so the number here matches what
the team sees on screen.

**3. Thrust-to-weight uses *average* thrust.** Peak thrust would be a more
generous reading of req 2.12. Average is the stricter one.

## Known differences between the engines

Both are expected and explained; `run_crossvalidate.py` prints them and flags
anything *not* on this list as unexplained.

- **Rail exit velocity, ~10%.** The two tools define leaving the rail
  differently (forward rail button clearing the tip vs. the CG traveling the
  full rail length). RocketPy reads lower, so it is the conservative number for
  req 2.14.
- **Drift, ~10%.** Originates in *ascent* weathercocking, not descent — the
  descent phases agree to 1.7%. RocketPy's lower rail-exit speed means a larger
  initial angle of attack, so it weathercocks further upwind (691 ft vs 570 ft).
  Net drift is the difference between an upwind apogee offset and a downwind
  descent, so the disagreement is amplified in the remainder. Quote the Monte
  Carlo landing ellipse, not either single run.

Everything else agrees within 5% — typically within 1%, and apogee to 0.1%.

Wind turbulence is **off by default** in OpenRocket runs (matching OpenRocket's
own default). Its pink-noise generator seeds itself independently of
`setRandomSeed`, so enabling it makes results irreproducible. Wind variability
belongs in the Monte Carlo, where the seed genuinely controls the outcome.

---

## Notes for whoever maintains this

- **`orhelper` does not work with OpenRocket 23.09+.** OpenRocket renamed its
  Java packages from `net.sf.openrocket` to `info.openrocket.core`, and
  `orhelper` 0.1.3 still imports the old names. `or_bridge.py` talks to the JVM
  directly through `OpenRocketCore.initialize(PluginModule())`, the supported
  headless entry point. Do not "fix" this by pinning OpenRocket 22.02 — the sim
  engine would then differ from the GUI the team designs in.
- **Section masses in `vehicle.yaml` are as-built** and include internal
  structure. The motor mount and rail buttons are mass-overridden to zero in the
  OpenRocket model so their material mass is not double-counted; without that,
  the FRR mass budget does not close.
- **The motor is modeled PLUGGED** (req 3.1.3 bans motor ejection). Leaving
  OpenRocket's default ejection delay fires a charge at burnout and silently
  invalidates the entire descent analysis.
- **Never hand RocketPy a scalar pressure** for `custom_atmosphere` — it becomes
  a constant-pressure atmosphere, which makes `barometric_height` degenerate and
  fires every altitude-triggered parachute the instant the rocket noses over.
  `_isa_profiles()` builds a real lapse profile anchored at the site.
- **Descent rates from altimeter data need a line fit, not a derivative.** A few
  feet of baro noise at 20 Hz is ~100 fps of noise in every finite difference,
  which completely swamps a 15 fps descent under the main.
- Monte Carlo is reproducible: same `--seed`, same numbers, months later.

---

## Status of the template vehicle

`config/vehicles/full_scale.yaml` is a **placeholder**, not a design — a representative
6", ~40 lb, L1520T-powered vehicle that lands mid-window and passes every
requirement, so the framework can be exercised before the real design exists.
Replace the numbers as the 2026–2027 design matures. The `status:` field in that
file should stop saying `PLACEHOLDER` once it describes something real.

Nominal template performance: **4,534 ft** apogee (OpenRocket) / **4,537 ft**
(RocketPy), 2.18 cal stability, 8.1:1 thrust-to-weight, 78 fps rail exit,
Mach 0.54, 77 s descent, 1,355 ft drift. 15 pass / 1 warn / 0 fail — the warn is
the mass score (39.6 lb loaded scores 3 of 5 points; a 4" airframe would score 5
but leaves less room for the rover payload). That tension is real and worth an
early decision.

The `uncertainty.yaml` sigmas are **defensible starting points, not
measurements**. Replace each with something the team can justify — weigh
sections repeatedly, use manufacturer lot data, use historical site wind — and
cite which version of that file produced any number in a report.
