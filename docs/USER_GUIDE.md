# User Guide

**NASA Student Launch — Dual-Engine Simulation Framework**
Season 2026–2027 · College/University (USLI) ruleset

This guide covers using the framework once it is installed: a guided first
run, defining your vehicle, launch sites, Monte Carlo dispersion, reading the
output, and how the tools fit the season's milestones. If you have not
installed it yet, start with the [Setup Guide](SETUP_GUIDE.md). Everything here
assumes its verification step (§2.8) passes.

Work through Part 1 at a keyboard — it takes about 30 minutes and it is the
fastest way to understand what the framework does.

Every step here is a command typed into a terminal and run from the project
folder, and every result is text in the terminal or a file written to
`output/`. See
[Before you start](SETUP_GUIDE.md#before-you-start-this-is-a-command-line-tool)
in the Setup Guide if that is unfamiliar.

**Where to type the commands.** The easiest place is the terminal built into
VS Code (Ctrl+`), because the file tree, the editor, and the commands then
share one window — you can edit `vehicle.yaml`, run a flight, and open the
resulting figure without leaving it. Set that up in
[§2.6 of the Setup Guide](SETUP_GUIDE.md#26-visual-studio-code-recommended).
Any other terminal works identically; nothing below depends on VS Code.

> **Shorthand.** This guide writes `python` for whichever of
> `.venv\Scripts\python` (Windows PowerShell), `.venv/Scripts/python` (Git Bash
> on Windows), or `.venv/bin/python` (macOS/Linux) applies to your machine. In
> VS Code's terminal, with the interpreter selected, a bare `python` already
> *is* that one — the prompt shows `(.venv)`. Everywhere else, a bare `python`
> uses your system Python and fails with `ModuleNotFoundError`.

Two further companions: [`FRAMEWORK_TOUR.md`](FRAMEWORK_TOUR.md) walks through
how the code is structured, and [`FLIGHT_DYNAMICS.md`](FLIGHT_DYNAMICS.md)
explains the physics behind everything here.

---

## Table of contents

- [Part 1 — Guided first run](#part-1--guided-first-run)
- [Part 2 — Defining your vehicle](#part-2--defining-your-vehicle)
- [Part 3 — Launch sites](#part-3--launch-sites)
- [Part 4 — Uncertainty and Monte Carlo](#part-4--uncertainty-and-monte-carlo)
- [Part 5 — Reading the output](#part-5--reading-the-output)
- [Part 6 — Season workflow](#part-6--season-workflow)
- [Part 7 — Troubleshooting](#part-7--troubleshooting)
- [Part 8 — Command reference](#part-8--command-reference)
- [Appendix A — Cheat sheet](#appendix-a--cheat-sheet)
- [Appendix B — Glossary](#appendix-b--glossary)

---

# Part 1 — Guided first run

Work through this at a keyboard. Roughly 30 minutes.

## 1.1 The nominal flight

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
quickest way to convince yourself the framework is modeling what you think it
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
  passes the rail tip; RocketPy when the center of mass has traveled the full
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

Read that second note carefully — it is discussed in [§5.3](#53-the-kinetic-energy-subtlety).

Three status levels:

| Status | Meaning |
|---|---|
| `PASS` | Requirement satisfied. |
| `WARN` | Compliant, but costing points (e.g. the mass score) or close to a limit. |
| `FAIL` | Requirement violated. Must be fixed. |

## 1.2 Both ballast configurations

Requirement 2.20.7.4 says *all* requirements must be met at both the minimum
and maximum ballast configurations. One command:

```bash
python scripts/run_nominal.py --ballast both
```

The max-ballast case lands about 340 ft lower. That is ballast doing its job —
it is a trim knob — but it means the altitude you declare at CDR should be
chosen knowing your ballast range, not from the minimum-ballast run alone.

## 1.3 Browsing motors

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

## 1.4 The cross-validation report

```bash
python scripts/run_crossvalidate.py
```

Produces `output/crossvalidation.md` — a report-ready document containing the
comparison table, the honest scope statement about what is independent, and a
written discussion of each difference over 5%. Anything differing by more than
5% that is *not* on the known-differences list is flagged as **unexplained**,
which is your cue to investigate before citing the number.

## 1.5 Your first Monte Carlo

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
best declaration is therefore the **center of your predicted distribution** —
not the nominal run, and not the middle of the legal window.

**Sensitivity** — what actually drives apogee (1,000 cases, seed 12345):

```
| motor_total_impulse |  0.605 |
| drag_coefficient    | -0.528 |
| dry_mass            | -0.267 |
| wind_speed_mps      | -0.226 |
| rail_angle_deg      | -0.159 |
| temperature_k       |  0.098 |
```

Spearman rank correlation. Motor impulse and drag dominate — and of those two,
motor scatter is fixed at the factory while drag is something you can measure.
That is where the effort belongs: fitting drag from flight data is worth more
than shaving grams.

Run this at **1,000 cases or more before you quote it**. At 60–200 cases the
ranking is not just noisier, it is wrong — development runs put `temperature_k`
third at 0.40, where 1,000 cases settle it at 0.10. Always record the sample
size and seed next to any sensitivity number you publish.

## 1.6 Post-flight analysis, before you have a flight

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

# Part 2 — Defining your vehicle

Everything lives in `config/vehicle.yaml`, authored in **inches and pounds**
because that is how the handbook is written and how the team thinks. Conversion
to SI happens once, in `slisim/units.py`.

## 2.1 Airframe and nose cone

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

## 2.2 Body sections

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

## 2.3 Fins

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

## 2.4 Motor

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

> **The motor is modeled plugged.** Requirement 3.1.3 forbids motor ejection
> as a deployment method, so the framework sets the ejection delay to
> OpenRocket's `PLUGGED` value. Leaving a numeric delay fires an ejection charge
> at burnout, adds a `Tumbling` phase, and silently invalidates your entire
> descent analysis.

## 2.5 Recovery

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

## 2.6 Landing sections

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

## 2.7 Ballast and target

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

# Part 3 — Launch sites

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

# Part 4 — Uncertainty and Monte Carlo

`config/uncertainty.yaml` is the most intellectually demanding file in the
framework. Every entry is a claim about how well you know something, and every
one should be defensible.

## 4.1 Entry format

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

## 4.2 Justifying your sigmas

The shipped values are **defensible starting points, not measurements.**
Replace each one:

| Parameter | Default σ | How to earn a better number |
|---|---|---|
| `dry_mass` | 1.5% | Weigh each section three times; use the observed spread. Then track built-vs-predicted mass all season. |
| `drag_coefficient` | 7% | Compare OpenRocket vs RocketPy, then **fit from flight data** (Part 6). Expect 2–3% afterward. |
| `motor_total_impulse` | 2% | Manufacturer certification data; thrustcurve.org shows lot-to-lot spread. |
| `wind_speed_mps` | site file | Historical data for the field and month. NOAA/Iowa State Mesonet have archives. |
| `main_cd` / `drogue_cd` | 10% | Manufacturer data if published; otherwise keep it wide — this is genuinely uncertain. |
| `main_deploy_altitude_ft` | 25 ft | Altimeter datasheet accuracy plus bay-porting effects. |

**Cite which version of this file produced any number you put in a report.**
A reviewer asking "where does 4,440 ft come from" deserves a traceable answer.

## 4.3 Running

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

# Part 5 — Reading the output

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
| `montecarlo_*.csv` | Every case, every input and output — for your own analysis (the Rainbow CSV extension makes these readable in VS Code) |
| `montecarlo_*.md` | Report-ready dispersion summary |

## 5.1 The apogee distribution

Read three things: where the **median** sits relative to your declared target;
whether the **5th–95th percentile band** fits inside the required window; and
whether the distribution is **skewed** (drag and mass errors both push one way,
so a mild left skew is normal — which is why the framework recommends the
median, not the mean, as your declared target).

## 5.2 The landing scatter

Points are individual cases; the dashed circle is the 2,500 ft limit
(requirement 3.10); the ellipse is the 3σ covariance fit. The scatter is
**elongated downwind** — wind direction is dispersed, so the cloud spreads
along the prevailing axis. If any point falls outside the circle, the
`P(pass)` for requirement 3.10 tells you how often.

## 5.3 The kinetic energy subtlety

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

## 5.4 What goes in which report

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

# Part 6 — Season workflow

## 6.1 Proposal / early PDR

Get a vehicle into `vehicle.yaml` even if half the numbers are estimates. Mark
`status:` honestly. Run `run_nominal.py --ballast both` on every design
candidate — a motor and airframe trade study is a loop over `motor.search` and
`airframe.outer_diameter_in`.

## 6.2 PDR

Run a 1,000-case Monte Carlo. Report P(in window), not a single apogee. Produce
the cross-validation report. Be explicit about which uncertainties are estimates
— nobody expects measured sigmas at PDR, but they do expect you to know which
are which.

## 6.3 CDR — declaring your target altitude

Requirement 2.3 makes this a scored decision, and it is the highest-leverage
number you will pick all season.

1. Freeze the design as far as you can.
2. Run 2,000 cases at **both** ballast extremes.
3. Declare the **median of the distribution you actually intend to fly**.
4. Plan to use ballast to trim toward that declaration as the built mass firms
   up.

Declaring the nominal-run apogee is a common and costly mistake: the nominal
run is not the center of the distribution once asymmetric effects are included.

## 6.4 Subscale flight

Build a subscale `vehicle.yaml` (requirements 2.15, 2.16: minimum E impulse,
≤75% of full-scale dimensions). Fly it, then run `fit_cd.py` on the altimeter
data. You will not get the full-scale drag coefficient from a subscale flight —
Reynolds numbers differ — but you *will* validate that your whole modeling
process produces the right answer, which is the real purpose.

## 6.5 Vehicle Demonstration Flight — the important one

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

## 6.6 FRR

Everything above, using as-built masses. Report measured descent rates from the
altimeter rather than simulated ones — the KE table in `fit_cd.py` output does
this. Demonstrate refinement since CDR; the shrinking uncertainty band is
exactly that story, told quantitatively.

---

# Part 7 — Troubleshooting

Installation and environment errors — `ModuleNotFoundError`, Java not found, a
missing OpenRocket jar, Python 3.14 build failures, a slow first run — are
covered in [Part 3 of the Setup Guide](SETUP_GUIDE.md#part-3--troubleshooting-the-installation).
This part covers problems that appear once the framework is running.

## 7.1 Monte Carlo cases fail

The script reports failures and the most common errors rather than crashing:

```
  WARNING: 7 of 500 cases failed to simulate
```

A handful of failures out of hundreds is usually a physically extreme sample
(near-zero wind combined with an extreme rail angle, for example). Many
failures means a dispersion is too wide or a configuration is wrong. Inspect
`montecarlo_*.csv` — failed rows carry an `error` column.

## 7.2 The simulation aborts immediately

Symptoms: apogee of 0, `Simulation abort` in the events list. Almost always the
motor is not attached to the flight configuration — check that `motor.search`
matches a real designation with `list_motors.py`, and that
`mount_inner_diameter_in` is large enough for the motor's actual diameter.

## 7.3 Parachutes deploy at apogee in RocketPy

If the main deploys immediately at apogee instead of at its set altitude, the
atmosphere model is degenerate. This is fixed in the framework
(`_isa_profiles()`), but if you modify `build_environment`, never pass a
*scalar* pressure to `custom_atmosphere` — it creates a constant-pressure
atmosphere, which makes barometric height meaningless and fires every
altitude-triggered parachute the moment the rocket noses over.

## 7.4 Descent rates from real altimeter data look absurd

If measured descent rates come out at 60+ fps under a large main, you are
differentiating noisy barometric data point-by-point. A few feet of baro noise
at 20 Hz is roughly 100 fps of noise in every finite difference. The framework
fits a straight line over each descent phase instead. Keep it that way.

---

# Part 8 — Command reference

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
# Setup (once): see SETUP_GUIDE.md

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
| **CG / CP** | Center of gravity / center of pressure. Stability needs CP behind CG. |
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
