# Setup and User Guide

**NASA Student Launch — Dual-Engine Simulation Framework**
Season 2026–2027 · College/University (USLI) ruleset

This guide takes you from a laptop with nothing installed to running a
1,000-case Monte Carlo dispersion analysis and reading the results. It assumes
no prior experience with Python virtual environments, Java, or either
simulation tool. Every command is written out in full for Windows, macOS, and
Linux.

Read Part 1 once. Work through Part 3 at a keyboard — it takes about 30 minutes
and it is the fastest way to understand what the framework does.

The companion document, [`FLIGHT_DYNAMICS.md`](FLIGHT_DYNAMICS.md), explains the
physics behind everything here.

---

## Table of contents

- [Part 1 — What this is and why](#part-1--what-this-is-and-why)
- [Part 2 — Installation](#part-2--installation)
- [Part 3 — Guided first run](#part-3--guided-first-run)
- [Part 4 — Defining your vehicle](#part-4--defining-your-vehicle)
- [Part 5 — Launch sites](#part-5--launch-sites)
- [Part 6 — Uncertainty and Monte Carlo](#part-6--uncertainty-and-monte-carlo)
- [Part 7 — Reading the output](#part-7--reading-the-output)
- [Part 8 — Season workflow](#part-8--season-workflow)
- [Part 9 — Troubleshooting](#part-9--troubleshooting)
- [Part 10 — Command reference](#part-10--command-reference)
- [Appendix A — Cheat sheet](#appendix-a--cheat-sheet)
- [Appendix B — Glossary](#appendix-b--glossary)

---

# Part 1 — What this is and why

## 1.1 The problem this solves

The handbook asks, in the Mission Performance Predictions section of the PDR,
the CDR, *and* the FRR:

> *"Present data from a different calculation method to verify that original
> results are accurate."*
> *"Discuss any differences between the different calculations."*
> *"Perform multiple simulations to verify that results are precise."*

Most teams satisfy the third bullet by running OpenRocket four or five times
with different wind speeds and putting the numbers in a table. That is a weak
answer, and a reviewer can tell. It shows that the *simulation* is repeatable;
it says nothing about whether the *vehicle* is.

The real question a reviewer is asking is: **given that you do not know your
rocket's mass to better than half a pound, its drag to better than a few
percent, or the wind on launch day at all — how confident are you that you will
land inside the 4,000–6,000 ft window?**

That is a probability, not a number. Producing it requires:

1. Declaring what you are uncertain about, and by how much.
2. Sampling those uncertainties hundreds of times.
3. Running a flight simulation for each sample.
4. Reporting the resulting distribution.

That is a Monte Carlo analysis, and it is what this framework automates.

## 1.2 Why two simulators

**OpenRocket** is the tool the team designs in. It has a GUI, a component
tree, a motor database, and it is what everyone at a launch understands. Its
weakness for this purpose is that scripting hundreds of dispersed runs through
the GUI is impractical.

**RocketPy** is a Python library. It has no GUI and no component database, but
it is trivially scriptable, and its flight dynamics are an independent
implementation — different equations of motion, a different integrator, a
different fin aerodynamics model.

Using both gets you two things at once:

- **Monte Carlo capability** (RocketPy, fast and scriptable).
- **The "different calculation method" the handbook asks for** — provided you
  are honest about which parts are genuinely independent. See §1.4.

## 1.3 How the framework is organised

The central design decision is that **`config/vehicle.yaml` is the single
source of truth.** From that one file the framework generates:

- a RocketPy model, built in memory, and
- a real `.ork` file you can open in the OpenRocket GUI.

```
                   config/vehicle.yaml
                    (you edit this)
                           |
              +------------+------------+
              |                         |
        or_bridge.py             rocketpy_model.py
              |                         |
     OpenRocket 24.12            RocketPy 1.13
     (headless, via Java)        (pure Python)
              |                         |
              +------------+------------+
                           |
              requirements.py  (USLI checks)
              montecarlo.py    (dispersion)
              analysis.py      (statistics)
              report.py        (figures, tables)
```

There is no second place to keep in sync. If the two models ever disagreed
about the rocket's mass, that would be a bug in the framework, not a modelling
choice.

## 1.4 What is genuinely independent — read this before writing a report

This matters more than it sounds. Claiming your two tools independently
validate each other, when they share inputs, is a claim a sharp reviewer can
dismantle.

| Quantity | Independent? | Why |
|---|---|---|
| Flight dynamics integration | **Yes** | RocketPy: 6-DOF, LSODA. OpenRocket: 6-DOF, RK4 |
| Centre of pressure / normal force | **Yes** | Each runs its own Barrowman-family model over its own geometry |
| Fin lift model | **Yes** | RocketPy uses Diederich planform correlation + Prandtl–Glauert; OpenRocket uses its own extended Barrowman |
| Atmosphere and wind | **Yes** | Separate implementations |
| Descent solver | **Yes** | Different schemes entirely (see `FLIGHT_DYNAMICS.md` §9.5) |
| Thrust curve | **No — shared** | Exported from OpenRocket's motor database |
| Mass, CG, inertia | **No — shared** | Taken from OpenRocket's mass calculator |
| **Drag coefficient Cd(Mach)** | **No — shared** | Sampled from an OpenRocket run |

**Why drag is shared:** RocketPy has no parasitic-drag model at all.
`power_off_drag` is a *required input*, not something RocketPy derives from
geometry. There is no version of this framework in which RocketPy independently
confirms OpenRocket's drag estimate — that would require a third source.

**What to write instead:** "The two tools independently confirm the trajectory,
stability, and recovery dynamics that follow from a shared drag estimate. The
drag estimate itself was validated separately against flight data from the
Vehicle Demonstration Flight." Then do exactly that with `fit_cd.py` (Part 8).

This is not a limitation to hide. It is the correct scope of the claim, and
stating it precisely is worth more in a review than overstating it.

---

# Part 2 — Installation

## 2.1 What you are installing, and why

| Component | Why it is needed |
|---|---|
| **Python 3.12 or 3.13** | Runs the framework. **Not 3.14** — RocketPy's dependency stack does not yet have complete wheels for it. |
| **A virtual environment** (venv) | An isolated folder of Python packages, so this project's pinned versions cannot break other Python work on your machine, and so everyone on the team has identical versions. |
| **Java JDK 17 or newer** | OpenRocket is a Java program. The framework runs its real solver headlessly, so a Java runtime must be present. You do not write any Java. |
| **`OpenRocket-24.12.jar`** | The OpenRocket engine itself, ~80 MB. Not committed to the repository because of its size. |
| **OpenRocket GUI** (optional but recommended) | For opening the `.ork` files the framework generates, and for ordinary design work. |

A note on why a *JDK* rather than just a JRE: modern OpenRocket distributions
bundle a private runtime that the framework cannot reliably locate, so
installing a JDK is the dependable route.

## 2.2 Windows

Open **PowerShell**. You do not need Administrator except where noted.

**Step 1 — Python 3.13**

```powershell
winget install --id Python.Python.3.13 --scope user
```

Close and reopen PowerShell, then verify:

```powershell
py -0p
```

You should see a line containing `3.13`. If `winget` is unavailable, download
the installer from <https://www.python.org/downloads/> and **tick "Add
python.exe to PATH"** during installation.

**Step 2 — Java JDK 17** (this one will prompt for Administrator)

```powershell
winget install --id Microsoft.OpenJDK.17
```

Close and reopen PowerShell, then verify:

```powershell
java -version
```

Expect `openjdk version "17..."` or higher. If `java` is not recognised after
reopening the terminal, see [§9.2](#92-java-not-found).

**Step 3 — Create the virtual environment**

```powershell
cd A:\Projects\NASA_SLI\sim
py -3.13 -m venv .venv
```

**Step 4 — Install the Python packages**

```powershell
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
```

This downloads roughly 200 MB and takes a few minutes.

> **On activation.** You may see guides tell you to run
> `.venv\Scripts\Activate.ps1` first. You do not need to. Calling
> `.venv\Scripts\python` directly does the same thing and avoids PowerShell
> execution-policy problems entirely. Every command in this guide uses the
> direct form. If you *want* activation, run
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then
> `.venv\Scripts\Activate.ps1`.

**Step 5 — Download the OpenRocket engine**

```powershell
curl.exe -L -o vendor\OpenRocket-24.12.jar `
  https://github.com/openrocket/openrocket/releases/download/release-24.12/OpenRocket-24.12.jar
```

Note `curl.exe`, not `curl` — in PowerShell the bare word is an alias for
`Invoke-WebRequest`, which will not work here.

Verify the size is about 80 MB:

```powershell
(Get-Item vendor\OpenRocket-24.12.jar).Length / 1MB
```

## 2.3 macOS

Open **Terminal**. These instructions use [Homebrew](https://brew.sh); install
it first if you do not have it.

```bash
# Step 1 - Python 3.13
brew install python@3.13

# Step 2 - Java JDK 17
brew install --cask temurin@17
java -version          # expect 17 or higher

# Step 3 - virtual environment
cd /path/to/NASA_SLI/sim
python3.13 -m venv .venv

# Step 4 - packages
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

# Step 5 - OpenRocket engine
curl -L -o vendor/OpenRocket-24.12.jar \
  https://github.com/openrocket/openrocket/releases/download/release-24.12/OpenRocket-24.12.jar
```

On Apple Silicon, if Java fails to start, confirm you installed the ARM build:
`java -XshowSettings:properties -version 2>&1 | grep os.arch` should report
`aarch64`.

## 2.4 Linux

**Debian / Ubuntu:**

```bash
sudo apt update
sudo apt install python3.13 python3.13-venv openjdk-17-jdk curl
```

If your distribution has no `python3.13` package, `python3.12` works equally
well — substitute it everywhere below.

**Fedora / RHEL:**

```bash
sudo dnf install python3.13 java-17-openjdk-devel curl
```

**Arch:**

```bash
sudo pacman -S python jdk17-openjdk curl
```

Then, on any distribution:

```bash
cd /path/to/NASA_SLI/sim
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
curl -L -o vendor/OpenRocket-24.12.jar \
  https://github.com/openrocket/openrocket/releases/download/release-24.12/OpenRocket-24.12.jar
```

## 2.5 The OpenRocket GUI (optional)

Download the installer for your platform from
<https://openrocket.info/downloads.html>. **Use version 24.12** so the GUI
matches the engine the framework drives — otherwise a file the framework writes
may open with subtly different results.

## 2.6 Verifying the installation

Run the built-in nominal analysis:

```powershell
.venv\Scripts\python scripts\run_nominal.py          # Windows
```
```bash
.venv/bin/python scripts/run_nominal.py              # macOS / Linux
```

The first run takes about 30 seconds — most of that is the JVM starting and
OpenRocket loading its 1,088-motor database. You should see a comparison table,
then a requirement table ending in:

```
  15 pass, 1 warn, 0 FAIL

  RESULT: all requirements satisfied
```

If you got that, you are done. If not, go to [Part 9](#part-9--troubleshooting).

> **Shorthand from here on.** The rest of this guide writes `python` for
> whichever of `.venv\Scripts\python` or `.venv/bin/python` applies to your
> machine. Always use the one inside `.venv` — a bare `python` will use your
> system Python and fail with `ModuleNotFoundError`.

---

# Part 3 — Guided first run

Work through this at a keyboard. Roughly 30 minutes.

## 3.1 The nominal flight

```bash
python scripts/run_nominal.py
```

This builds the vehicle from `config/vehicle.yaml`, writes a `.ork`, flies it in
both engines, and checks every requirement. Three blocks of output:

**Block 1 — the vehicle.**

```
Vehicle : Template Full-Scale  [PLACEHOLDER - not a real design]
Site    : Bragg Farms, Toney AL (NASA Student Launch competition site)
Length  : 103.0 in   Diameter: 6.00 in
  Motor   : L1520T (AeroTech)  3769 N-s, 1.773 kg propellant
  Saved   : ...\output\template_full-scale_0lb.ork
```

That `.ork` is a real OpenRocket file. **Open it in the GUI now** — it is the
quickest way to convince yourself the framework is modelling what you think it
is. You will see the nose cone, three body sections, the fin set, rail buttons,
motor mount, and both parachutes.

**Block 2 — the two engines side by side.**

```
quantity                 units    OpenRocket     RocketPy       diff        %
Apogee                   ft          4534.22      4536.87       2.65      0.1
Max velocity             fps          606.03       606.20       0.17      0.0
Static stability         cal            2.18         2.19       0.01      0.5
Rail exit velocity       fps           78.81        70.42      -8.38    -10.6
Drift from pad           ft          1355.00      1218.70    -136.30    -10.1
```

Apogee agreeing to 0.07% across two independent integrators is a strong result
and is exactly the evidence the handbook's "different calculation method"
bullet is asking for.

The two rows that *don't* agree are expected, and knowing why is the difference
between a good report and a great one:

- **Rail exit velocity (−10.6%).** The two tools define "off the rail"
  differently. OpenRocket releases the vehicle when the forward rail button
  passes the rail tip; RocketPy when the centre of mass has travelled the full
  rail length. RocketPy reads lower, so quoting RocketPy for requirement 2.14
  (≥52 fps) is the conservative choice.
- **Drift (−10%).** This one originates during *ascent*, not descent. The
  descent phases agree to under 2%. RocketPy leaves the rail slower (see
  above), so it enters free flight at a larger angle of attack relative to the
  wind, weathercocks harder, and reaches apogee further upwind. Because net
  drift is the *difference* between an upwind apogee offset and a downwind
  descent, a modest difference in the first shows up amplified in the
  remainder. Quote the Monte Carlo landing ellipse, not either single run.
  Full decomposition in `FLIGHT_DYNAMICS.md` §14.2.

**Block 3 — requirement compliance.** Every check cites its handbook paragraph.

```
  PASS    2.11     Static stability on pad          2.18 cal      >= 2.0
                   `-- evaluated at Mach 0.3, matching OpenRocket's GUI convention
  PASS    3.2      KE at landing: Avionics Bay + Booster   56.06 ft-lbf   <= 75
                   `-- 17.00 lb at 14.6 fps descent rate; incl. horizontal drift = 106.5 ft-lbf (over 75)
```

Read that second note carefully — it is discussed in [§7.3](#73-the-kinetic-energy-subtlety).

Three status levels:

| Status | Meaning |
|---|---|
| `PASS` | Requirement satisfied. |
| `WARN` | Compliant, but costing points (e.g. the mass score) or close to a limit. |
| `FAIL` | Requirement violated. Must be fixed. |

## 3.2 Both ballast configurations

Requirement 2.20.7.4 says *all* requirements must be met at both the minimum
and maximum ballast configurations. One command:

```bash
python scripts/run_nominal.py --ballast both
```

The max-ballast case lands about 340 ft lower. That is ballast doing its job —
it is a trim knob — but it means the altitude you declare at CDR should be
chosen knowing your ballast range, not from the minimum-ballast run alone.

## 3.3 Browsing motors

```bash
python scripts/list_motors.py --nasa
```

Lists the ten motors NASA identified as reliably available for 2027
(requirement 2.7), sorted by total impulse:

```
*  K1100T         AeroTech      1586   1.65      961     1235    0.762    54mm
*  L1520T         AeroTech      3769   2.49     1511     1697    1.773    75mm
*  L2200G         AeroTech      5104   2.27     2243     3102    2.516    75mm
```

`*` marks the NASA list; `!` marks anything over the 5,120 N·s college limit
(requirement 2.9). Note how close the L2200G is to that ceiling — 5,104 N·s.

Search more broadly with `python scripts/list_motors.py L1` or filter with
`--diameter-mm 75`.

## 3.4 The cross-validation report

```bash
python scripts/run_crossvalidate.py
```

Produces `output/crossvalidation.md` — a report-ready document containing the
comparison table, the honest scope statement about what is independent, and a
written discussion of each difference over 5%. Anything differing by more than
5% that is *not* on the known-differences list is flagged as **unexplained**,
which is your cue to investigate before citing the number.

## 3.5 Your first Monte Carlo

```bash
python scripts/run_montecarlo.py -n 200
```

Takes a couple of minutes on a modern laptop (it uses all your cores). The
output has four parts.

**Dispersion summary** — percentiles for every output quantity.

**Requirement compliance as probabilities:**

```
| req | requirement                 | P(pass) | mean     | p05      | p95      |
| 2.1 | Apogee in 4,000-6,000 ft    | 0.985   | 4460.1   | 4068.2   | 4818.4   |
| 2.11| Stability >= 2.0 cal        | 1.000   | 2.204    | 2.108    | 2.328    |
```

This is the payoff. Not "our apogee is 4,533 ft" but **"98.5% of dispersed
cases land inside the required window, with a 95% interval of 4,068 to 4,818
ft."** That is a defensible statement.

**Recommended target altitude:**

```
    Recommended declaration : 4,440 ft
    95% CI                  : [4,068, 4,818] ft
    P(4,000-6,000 ft)       : 98.5%
```

Requirement 2.3 scores you on closeness to the altitude you declare at CDR. The
best declaration is therefore the **centre of your predicted distribution** —
not the nominal run, and not the middle of the legal window.

**Sensitivity** — what actually drives apogee:

```
| drag_coefficient    | -0.613 |
| motor_total_impulse |  0.573 |
| temperature_k       |  0.400 |
| dry_mass            | -0.324 |
```

Spearman rank correlation. Drag dominates. That single fact tells you where to
spend effort: measuring drag from flight data is worth more than shaving grams.

## 3.6 Post-flight analysis, before you have a flight

You do not want the FRR analysis to be the first time anyone runs this code.
Generate synthetic altimeter data with a known drag error baked in:

```bash
python scripts/make_synthetic_flight.py --cd-scale 1.18
```

Then recover it:

```bash
python scripts/fit_cd.py data/flights/synthetic_vdf.csv --wind 9 --temp-f 68
```

```
  Cd scale factor      : 1.1728  (+17.3% vs the pre-flight model)
  Measured apogee      : 4,309 ft
  Pre-flight prediction: 4,545 ft (+236 ft error)
  Post-fit prediction  : 4,308 ft (-0 ft residual)
  Ascent RMSE          : 9 ft
```

The fitter recovered 1.173 against a true 1.180 — 0.6% error. That round-trip
is how you know the tool works before you trust it with real data.

---

# Part 4 — Defining your vehicle

Everything lives in `config/vehicle.yaml`, authored in **inches and pounds**
because that is how the handbook is written and how the team thinks. Conversion
to SI happens once, in `slisim/units.py`.

## 4.1 Airframe and nose cone

```yaml
airframe:
  outer_diameter_in: 6.00
  wall_thickness_in: 0.125
  surface_finish: regular_paint   # smooth | regular_paint | unfinished | rough

nose_cone:
  shape: ogive              # ogive | conical | ellipsoid | haack | parabolic | power
  shape_parameter: 1.0      # 1.0 = tangent ogive; for haack, 0.0 = Von Kármán
  length_in: 26.0
  wall_thickness_in: 0.125
  shoulder_length_in: 3.5   # req 2.5.3: >= 0.5 body diameter
  mass_lb: 2.40
```

`surface_finish` is not cosmetic — it sets the skin-roughness height used in the
skin-friction calculation, and skin friction is about 58% of this vehicle's
total drag. A rough finish costs real altitude.

## 4.2 Body sections

```yaml
sections:
  - name: "Payload Bay"
    length_in: 26.0
    mass_lb: 7.80
```

**`mass_lb` is the as-built section mass**: the airframe *plus everything
permanently inside it* — bulkheads, sled, payload, hardware, fillets, paint. It
does **not** include parachutes, shock cord, or the motor; those are declared
separately so the FRR mass bookkeeping balances.

Two consequences worth understanding:

1. The framework sets these as OpenRocket **mass overrides** rather than
   choosing materials and letting OpenRocket compute masses. A number from a
   scale beats a density estimate. Weigh sections as you build them and update
   this file.
2. The motor mount and rail buttons are mass-overridden to **zero** in the
   generated model, because their mass is already inside your section figures.
   Without that, OpenRocket adds its own material-derived mass on top and the
   FRR mass budget will not close. The framework checks this automatically
   (`FRR-V  Mass budget closure`).

## 4.3 Fins

```yaml
fins:
  count: 3
  root_chord_in: 15.0
  tip_chord_in: 6.00
  sweep_in: 6.00            # axial distance the leading edge sweeps back
  height_in: 7.50           # semi-span, root to tip
  thickness_in: 0.1875
  cant_deg: 0.0
  offset_from_aft_in: 0.50  # trailing edge forward of the aft airframe end
  mass_lb: 3.20             # whole fin can, all fins together
```

```
        |<----------- root_chord ----------->|
        +------------------------------------+   <-- fin root (on airframe)
         \                                   |
          \  <-- sweep -->                   |    height (semi-span)
           \                                 |
            +--------- tip_chord ------------+   <-- fin tip
```

Fins are the main lever on static stability. On the template, going from
12×5×5.5 in to 15×6×7.5 in moved the margin from 1.40 to 2.18 calibers — the
difference between failing and passing requirement 2.11 — at a cost of about 45
ft of apogee.

## 4.4 Motor

```yaml
motor:
  search: "L1520T"              # matched against OpenRocket's motor database
  manufacturer: "AeroTech"
  mount_inner_diameter_in: 2.953   # 75 mm
  mount_length_in: 24.0
  overhang_in: 0.25
  ignition_delay_s: 0.0
```

`search` is a substring match against the 1,088 motor sets bundled inside the
OpenRocket jar — no network access and no per-machine motor files. Use
`list_motors.py` to find the exact designation.

> **The motor is modelled plugged.** Requirement 3.1.3 forbids motor ejection
> as a deployment method, so the framework sets the ejection delay to
> OpenRocket's `PLUGGED` value. Leaving a numeric delay fires an ejection charge
> at burnout, adds a `Tumbling` phase, and silently invalidates your entire
> descent analysis.

## 4.5 Recovery

```yaml
recovery:
  drogue:
    diameter_in: 18.0
    cd: 1.55
    deploy_event: apogee
    deploy_delay_s: 1.0       # req 3.1.2: <= 2.0 s
    mass_lb: 0.45
  main:
    diameter_in: 108.0
    cd: 2.20
    deploy_event: altitude
    deploy_altitude_ft: 600.0 # req 3.1.1: >= 500 ft
    mass_lb: 2.60
  shock_cord_mass_lb: 1.35
```

`cd` is the parachute drag coefficient from the manufacturer's data. It is one
of the least certain numbers in the whole model, which is why
`uncertainty.yaml` disperses it by 10%.

## 4.6 Landing sections

```yaml
landing_sections:
  - name: "Nose + Payload Bay"
    members: ["nose_cone", "Payload Bay"]
  - name: "Avionics Bay + Booster"
    members: ["Avionics Bay", "Booster", "fins"]
```

Requirement 3.2 caps kinetic energy **per independent section**, so the
framework needs to know how the vehicle divides on descent. Valid `members`
names are `nose_cone`, `fins`, and any section name from `sections:`.

These must **partition** the vehicle — every mass assigned exactly once. The
framework reports anything left unassigned, and the `FRR-V` check will fail if
the arithmetic does not close.

## 4.7 Ballast and target

```yaml
ballast:
  min_lb: 0.0
  max_lb: 3.00              # req 2.20.7: <= 10% of un-ballasted mass
  location: "Payload Bay"

target_apogee_ft: 4500.0
```

Always validate with `--ballast both`. Requirement 2.20.7.4 requires compliance
at both extremes, and the extremes differ by hundreds of feet.

---

# Part 5 — Launch sites

`config/sites.yaml`:

```yaml
sites:
  huntsville:
    name: "Bragg Farms, Toney AL"
    latitude: 34.8964
    longitude: -86.6162
    elevation_m: 189.0          # ~620 ft MSL
    rail_length_m: 3.66         # 12 ft 1515 rail, NASA-provided
    nominal:
      wind_speed_mps: 4.5
      wind_direction_deg: 180.0 # direction wind comes FROM
      temperature_k: 291.0
      pressure_pa: 101325.0
    wind_speed_sigma_mps: 2.2
    wind_direction_sigma_deg: 35.0
```

Two points that catch people out:

- **`wind_direction_deg` is meteorological** — the direction the wind blows
  *from*. 180° is a wind out of the south, blowing northward.
- **Elevation matters more than you'd guess.** Apogee is reported AGL, but air
  density is set by absolute altitude. Getting this wrong biases every apogee
  prediction in the same direction.

Add your home field for subscale and demonstration flights, then select with
`--site home_field`.

---

# Part 6 — Uncertainty and Monte Carlo

`config/uncertainty.yaml` is the most intellectually demanding file in the
framework. Every entry is a claim about how well you know something, and every
one should be defensible.

## 6.1 Entry format

```yaml
drag_coefficient:
  distribution: normal
  relative: true      # multiplier on the nominal, rather than an absolute shift
  mean: 1.0
  sigma: 0.070        # 7% one-sigma
```

Supported distributions:

| Distribution | Parameters | Use for |
|---|---|---|
| `normal` | `mean`, `sigma` | Most quantities — sums of many small errors |
| `uniform` | `low`, `high` | Genuinely unknown within a range (e.g. rail azimuth) |
| `truncnormal` | `mean`, `sigma`, `low`, `high` | Normal with a hard physical bound (wind speed ≥ 0) |

`mean: null` or `sigma: null` inherits from the launch site, so wind statistics
live in `sites.yaml` and are not duplicated per analysis.

> **On truncation.** The framework *resamples* out-of-bounds draws rather than
> clipping them. Clipping piles probability mass onto the boundary and biases
> exactly the distribution tails where requirement margins live.

## 6.2 Justifying your sigmas

The shipped values are **defensible starting points, not measurements.**
Replace each one:

| Parameter | Default σ | How to earn a better number |
|---|---|---|
| `dry_mass` | 1.5% | Weigh each section three times; use the observed spread. Then track built-vs-predicted mass all season. |
| `drag_coefficient` | 7% | Compare OpenRocket vs RocketPy, then **fit from flight data** (Part 8). Expect 2–3% afterward. |
| `motor_total_impulse` | 2% | Manufacturer certification data; thrustcurve.org shows lot-to-lot spread. |
| `wind_speed_mps` | site file | Historical data for the field and month. NOAA/Iowa State Mesonet have archives. |
| `main_cd` / `drogue_cd` | 10% | Manufacturer data if published; otherwise keep it wide — this is genuinely uncertain. |
| `main_deploy_altitude_ft` | 25 ft | Altimeter datasheet accuracy plus bay-porting effects. |

**Cite which version of this file produced any number you put in a report.**
A reviewer asking "where does 4,440 ft come from" deserves a traceable answer.

## 6.3 Running

```bash
python scripts/run_montecarlo.py -n 1000                    # RocketPy (fast)
python scripts/run_montecarlo.py -n 200 --engine openrocket # OpenRocket
python scripts/run_montecarlo.py -n 1000 --ballast max
python scripts/run_montecarlo.py -n 1000 --seed 999
```

**How many samples?** Statistical error on a percentile falls as 1/√N.

| N | Use |
|---|---|
| 100–200 | Quick check while iterating on a design |
| 500 | Reasonable for internal work |
| 1,000–2,000 | Report-quality; stable to ~1% on the 5th/95th percentiles |
| 5,000+ | Only if you care about the far tails |

**Reproducibility.** The same `--seed` gives byte-identical results months
later. Record the seed alongside any number you publish.

**The two engines disperse different things.** RocketPy disperses everything —
mass, CG, drag, motor, wind, rail. OpenRocket disperses launch conditions only,
because perturbing mass and drag would mean rebuilding the component tree for
every sample. Use RocketPy for dispersion; use OpenRocket as the independent
check on the trajectory.

---

# Part 7 — Reading the output

Everything lands in `output/`.

| File | Contents |
|---|---|
| `*.ork` | OpenRocket files — open these in the GUI |
| `flight_profile_*.png` | Altitude / velocity / acceleration vs time, both engines |
| `stability_*.png` | Static margin and CP/CG vs time |
| `apogee_dist_*.png` | Apogee histogram with the requirement window |
| `landing_*.png` | Landing scatter against the 2,500 ft radius |
| `sensitivity_*.png` | What drives apogee |
| `crossvalidation.md` | Report-ready engine comparison |
| `montecarlo_*.csv` | Every case, every input and output — for your own analysis |
| `montecarlo_*.md` | Report-ready dispersion summary |

## 7.1 The apogee distribution

Read three things: where the **median** sits relative to your declared target;
whether the **5th–95th percentile band** fits inside the required window; and
whether the distribution is **skewed** (drag and mass errors both push one way,
so a mild left skew is normal — which is why the framework recommends the
median, not the mean, as your declared target).

## 7.2 The landing scatter

Points are individual cases; the dashed circle is the 2,500 ft limit
(requirement 3.10); the ellipse is the 3σ covariance fit. The scatter is
**elongated downwind** — wind direction is dispersed, so the cloud spreads
along the prevailing axis. If any point falls outside the circle, the
`P(pass)` for requirement 3.10 tells you how often.

## 7.3 The kinetic energy subtlety

This is a genuine engineering judgement, not a software detail, and it changes
parachute sizing by a full chute size.

Requirement 3.2 caps each independent section at **75 ft·lbf at landing**. But
which velocity goes into ½mv²?

- **Vertical descent rate.** The handbook's FRR table asks for *"descent rate
  under both drogue and main parachutes"*, and essentially every team reports
  this. **The framework uses it as the pass/fail basis.**
- **Total speed including drift.** Under a parachute the vehicle moves
  horizontally with the wind. In a 10 mph wind that horizontal component rivals
  the descent rate, and since energy goes as v², it roughly **doubles** the
  computed energy.

On the template vehicle, at 14.6 fps descent in a 10 mph wind:

| Section | KE (vertical) | KE (with drift) |
|---|---|---|
| Nose + Payload Bay | 33.6 ft·lbf | 63.9 ft·lbf |
| Avionics Bay + Booster | **56.1 ft·lbf** | **106.5 ft·lbf** |

Both pass on the conventional basis. The heavier section would fail on the
conservative one. The framework prints both on every KE check so the choice is
explicit rather than accidental.

Sizing to the vertical rate is defensible and conventional. Knowing how little
margin that leaves is the useful part — and it is a good thing to raise
yourselves in a review before a panelist raises it for you.

## 7.4 What goes in which report

| Handbook bullet | Where it comes from |
|---|---|
| "Flight profile simulations… altitude, velocity, acceleration vs time" | `flight_profile_*.png` |
| "Stability margin and simulated CP/CG relationship" | `stability_*.png`, requirement table |
| "Kinetic energy at landing for each section" | Requirement table, `postflight_kinetic_energy.csv` |
| "Expected descent time" | Requirement table (3.11) |
| "Data from a different calculation method" | `crossvalidation.md` |
| "Discuss any differences" | `crossvalidation.md` discussion section |
| "Multiple simulations to verify results are precise" | `montecarlo_*.md` |
| "Estimate Cd utilizing launch data" (FRR) | `postflight_cd_fit.md` |

---

# Part 8 — Season workflow

## 8.1 Proposal / early PDR

Get a vehicle into `vehicle.yaml` even if half the numbers are estimates. Mark
`status:` honestly. Run `run_nominal.py --ballast both` on every design
candidate — a motor and airframe trade study is a loop over `motor.search` and
`airframe.outer_diameter_in`.

## 8.2 PDR

Run a 1,000-case Monte Carlo. Report P(in window), not a single apogee. Produce
the cross-validation report. Be explicit about which uncertainties are estimates
— nobody expects measured sigmas at PDR, but they do expect you to know which
are which.

## 8.3 CDR — declaring your target altitude

Requirement 2.3 makes this a scored decision, and it is the highest-leverage
number you will pick all season.

1. Freeze the design as far as you can.
2. Run 2,000 cases at **both** ballast extremes.
3. Declare the **median of the distribution you actually intend to fly**.
4. Plan to use ballast to trim toward that declaration as the built mass firms
   up.

Declaring the nominal-run apogee is a common and costly mistake: the nominal
run is not the centre of the distribution once asymmetric effects are included.

## 8.4 Subscale flight

Build a subscale `vehicle.yaml` (requirements 2.15, 2.16: minimum E impulse,
≤75% of full-scale dimensions). Fly it, then run `fit_cd.py` on the altimeter
data. You will not get the full-scale drag coefficient from a subscale flight —
Reynolds numbers differ — but you *will* validate that your whole modelling
process produces the right answer, which is the real purpose.

## 8.5 Vehicle Demonstration Flight — the important one

The FRR asks, verbatim:

> *"Estimate the drag coefficient of the full-scale rocket utilizing launch
> data. Use this value to run a post-flight simulation."*
> *"Update your simulated flight model with launch day condition data and
> compare the predicted flight performance to the actual flight data."*

Record on launch day: wind speed and direction, temperature, barometric
pressure, rail angle, ballast flown, and the altimeter CSV.

```bash
python scripts/fit_cd.py data/flights/vdf_2027.csv \
    --wind 11 --wind-dir 210 --temp-f 64 --pressure-inhg 29.92 \
    --rail-angle 7 --ballast-lb 2.0 --match ascent
```

Then **fold the result back into `uncertainty.yaml`**:

```yaml
drag_coefficient:
  mean: 1.1728        # <- the fitted value
  sigma: 0.025        # <- was 0.07 before you had data
```

Re-run the Monte Carlo. The apogee spread will shrink substantially, because
drag was your dominant uncertainty. **That is how you improve your altitude
score** — not by simulating more carefully, but by replacing a guess with a
measurement.

## 8.6 FRR

Everything above, using as-built masses. Report measured descent rates from the
altimeter rather than simulated ones — the KE table in `fit_cd.py` output does
this. Demonstrate refinement since CDR; the shrinking uncertainty band is
exactly that story, told quantitatively.

---

# Part 9 — Troubleshooting

## 9.1 `ModuleNotFoundError: No module named 'rocketpy'`

You are using the system Python instead of the venv. Use
`.venv\Scripts\python` (Windows) or `.venv/bin/python` (macOS/Linux) — not a
bare `python`.

If it persists, the venv may not have installed correctly:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

## 9.2 Java not found

```
RuntimeError: No Java 17+ runtime found. OpenRocket 24.12 needs one.
```

The framework searches the standard install locations automatically. If it
still fails, either Java is not installed or it is somewhere unusual. Check:

```bash
java -version
```

If that fails, install a JDK (§2.2–2.4). If it works but the framework does not
see it, set `JAVA_HOME` explicitly:

```powershell
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-17.0.20.101-hotspot"   # Windows, this session
```
```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64                     # Linux
export JAVA_HOME=$(/usr/libexec/java_home -v 17)                        # macOS
```

To make it permanent on Windows, use System Properties → Environment Variables.

**Java 11 or older will not work.** OpenRocket 24.12 requires 17+.

## 9.3 `FileNotFoundError: OpenRocket jar not found`

You skipped step 5, or the download failed. Check the size — a failed download
often leaves a small HTML error page:

```bash
ls -l vendor/OpenRocket-24.12.jar     # should be ~80 MB
```

Re-download with the command in §2.2–2.4. On Windows remember `curl.exe`, not
`curl`.

## 9.4 `UnsupportedClassVersionError`

Your Java is too old. Version 17 or newer is required. Check with
`java -version` and install a newer JDK.

## 9.5 Python 3.14 problems

If installation fails with build errors on numpy, scipy, or netCDF4, check your
version:

```bash
python -V
```

If it says 3.14, that is the cause. Install 3.12 or 3.13 and rebuild the venv:

```bash
rm -rf .venv                       # rmdir /s /q .venv   on Windows
py -3.13 -m venv .venv             # python3.13 -m venv .venv  elsewhere
.venv/bin/python -m pip install -r requirements.txt
```

## 9.6 Monte Carlo cases fail

The script reports failures and the most common errors rather than crashing:

```
  WARNING: 7 of 500 cases failed to simulate
```

A handful of failures out of hundreds is usually a physically extreme sample
(near-zero wind combined with an extreme rail angle, for example). Many
failures means a dispersion is too wide or a configuration is wrong. Inspect
`montecarlo_*.csv` — failed rows carry an `error` column.

## 9.7 The simulation aborts immediately

Symptoms: apogee of 0, `Simulation abort` in the events list. Almost always the
motor is not attached to the flight configuration — check that `motor.search`
matches a real designation with `list_motors.py`, and that
`mount_inner_diameter_in` is large enough for the motor's actual diameter.

## 9.8 Parachutes deploy at apogee in RocketPy

If the main deploys immediately at apogee instead of at its set altitude, the
atmosphere model is degenerate. This is fixed in the framework
(`_isa_profiles()`), but if you modify `build_environment`, never pass a
*scalar* pressure to `custom_atmosphere` — it creates a constant-pressure
atmosphere, which makes barometric height meaningless and fires every
altitude-triggered parachute the moment the rocket noses over.

## 9.9 Descent rates from real altimeter data look absurd

If measured descent rates come out at 60+ fps under a large main, you are
differentiating noisy barometric data point-by-point. A few feet of baro noise
at 20 Hz is roughly 100 fps of noise in every finite difference. The framework
fits a straight line over each descent phase instead. Keep it that way.

## 9.10 The first run is slow

Roughly 30 seconds is normal — the JVM starts and OpenRocket loads its motor
database and 5,231 component presets. Subsequent simulations in the same
process take about 0.7 s. Monte Carlo pays this cost once per worker process,
not once per sample.

## 9.11 Getting a clean slate

```bash
rm -rf .venv output/*
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python scripts/run_nominal.py
```

The `vendor/*.jar` and your `config/` files are untouched by this.

---

# Part 10 — Command reference

### `run_nominal.py`

Nominal flight in both engines with full requirement checking.

| Flag | Default | Meaning |
|---|---|---|
| `--vehicle PATH` | `config/vehicle.yaml` | Alternate vehicle file |
| `--site KEY` | site file default | Launch site |
| `--ballast {min,max,both}` | `min` | Ballast configuration |
| `--skip-rocketpy` | off | OpenRocket only (faster) |
| `--out DIR` | `output/` | Output directory |

Exit code 0 if no requirement FAILs, 1 otherwise — usable in CI.

### `run_montecarlo.py`

| Flag | Default | Meaning |
|---|---|---|
| `-n, --samples N` | 500 | Number of cases |
| `--engine {rocketpy,openrocket}` | `rocketpy` | Which solver |
| `--ballast {min,max}` | `min` | Ballast configuration |
| `--seed N` | 12345 | Random seed — record this |
| `--workers N` | CPU count (max 8) | Parallel processes |
| `--site KEY`, `--vehicle PATH`, `--out DIR` | | As above |

### `run_crossvalidate.py`

| Flag | Default | Meaning |
|---|---|---|
| `--mc N` | 0 | Also disperse N cases through *both* engines |
| `--ballast {min,max}`, `--seed`, `--workers` | | As above |

### `fit_cd.py`

| Flag | Default | Meaning |
|---|---|---|
| `csv` | required | Altimeter CSV |
| `--match {apogee,ascent}` | `apogee` | Fit apogee only, or the whole ascent by RMSE |
| `--wind MPH`, `--wind-dir DEG` | site | Launch-day wind |
| `--temp-f F`, `--pressure-inhg IN` | site | Launch-day atmosphere |
| `--rail-angle DEG` | 5.0 | Rail angle off vertical |
| `--ballast-lb LB` | 0.0 | Ballast actually flown |
| `--altitude-units {auto,ft,m}` | `auto` | Override unit detection |
| `--time-column`, `--altitude-column` | auto | Override column detection |

### `list_motors.py`

| Flag | Meaning |
|---|---|
| `pattern` | Designation substring, e.g. `L15` |
| `--nasa` | Only the NASA-supported availability list |
| `--manufacturer NAME` | Filter by manufacturer |
| `--diameter-mm MM` | Filter by case diameter |

### `make_synthetic_flight.py`

| Flag | Default | Meaning |
|---|---|---|
| `--cd-scale X` | 1.15 | True drag scale to bake in |
| `--noise-ft X` | 6.0 | Barometric noise, 1σ |
| `--rate-hz X` | 20.0 | Sample rate |
| `--wind-mph`, `--temp-f` | | Conditions to simulate |

---

# Appendix A — Cheat sheet

```bash
# Setup (once)
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
curl.exe -L -o vendor\OpenRocket-24.12.jar https://github.com/openrocket/openrocket/releases/download/release-24.12/OpenRocket-24.12.jar

# Daily use
python scripts/run_nominal.py --ballast both      # design check
python scripts/list_motors.py --nasa              # pick a motor
python scripts/run_montecarlo.py -n 1000          # dispersion
python scripts/run_crossvalidate.py               # report table
python scripts/fit_cd.py data/flights/vdf.csv --wind 11 --temp-f 64

# Files you edit
config/vehicle.yaml       the rocket
config/sites.yaml         where you fly
config/uncertainty.yaml   what you don't know

# Files you read
output/*.md               report-ready
output/*.png              figures
output/*.csv              raw data
output/*.ork              open in OpenRocket GUI
```

---

# Appendix B — Glossary

| Term | Meaning |
|---|---|
| **AGL / MSL** | Above Ground Level / Mean Sea Level. Apogee requirements are AGL; air density depends on MSL. |
| **Caliber** | One body diameter. Static margin is expressed in calibers so it scales. |
| **CG / CP** | Centre of gravity / centre of pressure. Stability needs CP behind CG. |
| **Cd·S** | Drag coefficient times reference area. The physically meaningful parachute parameter. |
| **GLOW** | Gross Lift-Off Weight. |
| **Static margin** | (CP − CG) / diameter, in calibers. Requirement 2.11 needs ≥ 2.0. |
| **Rail exit velocity** | Speed leaving the launch rail. Requirement 2.14 needs ≥ 52 fps. |
| **Monte Carlo** | Running many simulations with randomly sampled inputs to get an output distribution. |
| **Spearman ρ** | Rank correlation; measures monotone association without assuming linearity. |
| **6-DOF** | Six degrees of freedom: three translations and three rotations. |
| **venv** | An isolated Python package directory. |
| **JVM / JDK** | Java Virtual Machine / Java Development Kit. OpenRocket is a Java program. |
| **VDF / PDF** | Vehicle / Payload Demonstration Flight. |

---

*Framework verified on Python 3.13.15, RocketPy 1.13.0, OpenRocket 24.12,
Microsoft OpenJDK 17.0.20. Physics background: [`FLIGHT_DYNAMICS.md`](FLIGHT_DYNAMICS.md).*
