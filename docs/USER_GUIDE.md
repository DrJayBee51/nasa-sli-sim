# User Guide

**NASA Student Launch — Dual-Engine Simulation Framework**
Season 2026–2027 · College/University (USLI) ruleset

This guide covers using the framework once it is installed: starting a
session, a guided first run, defining your vehicle, launch sites, Monte Carlo
dispersion, reading the output, and troubleshooting. It is meant to be the only
document you need day to day. The [Setup Guide](SETUP_GUIDE.md) is for
installing the framework once; when its verification step (§2.9) passes, come
here and stay here.

Every step is a command typed into a terminal, and every result is text in the
terminal or a file written to `output/`. Commands are given for both
**PowerShell** and **Git Bash** wherever the two differ. Where only one block is
shown, it works unchanged in either — which, once the environment is active
([§0.3](#03-activate-the-environment)), is almost everywhere.

**Start with Part 0 every session.** It is four commands, and skipping one of
them is behind nearly every "it worked yesterday" problem.

Work through Part 1 at a keyboard: about 30 minutes, and the fastest way to
understand what the framework does.

Two further companions: [`FRAMEWORK_TOUR.md`](FRAMEWORK_TOUR.md) walks through
how the code is structured, and [`FLIGHT_DYNAMICS.md`](FLIGHT_DYNAMICS.md)
explains the physics behind everything here.

---

## Table of contents

- [Part 0 — Starting a session](#part-0--starting-a-session)
- [Part 1 — Guided first run](#part-1--guided-first-run)
- [Part 2 — Defining your vehicle](#part-2--defining-your-vehicle)
- [Part 3 — Launch sites](#part-3--launch-sites)
- [Part 4 — Uncertainty and Monte Carlo](#part-4--uncertainty-and-monte-carlo)
- [Part 5 — Reading the output](#part-5--reading-the-output)
- [Part 6 — Troubleshooting](#part-6--troubleshooting)
- [Part 7 — Command reference](#part-7--command-reference)
- [Appendix A — Cheat sheet](#appendix-a--cheat-sheet)
- [Appendix B — Glossary](#appendix-b--glossary)

---

# Part 0 — Starting a session

Do these four things every time you sit down: open a terminal, go to the
project folder, activate the environment, and pull the team's latest work. The
whole routine is in [§0.6](#06-the-whole-routine).

## 0.1 Open a terminal

**In VS Code (recommended).** Open the project *folder* (File → Open Folder),
then press **Ctrl+`** (the backtick key, above Tab). The terminal opens in the
project folder, beside the file tree and the editor, so you can edit a vehicle
file, run a flight and open the figure without leaving the window. To choose
the shell, click the **˅** beside the **+** in the terminal panel: *PowerShell*
is the Windows default, and *Git Bash* appears once Git for Windows is
installed.

**Outside VS Code.** On Windows, open *PowerShell* or *Git Bash* from the Start
menu. On macOS or Linux, open *Terminal*; it behaves like Git Bash throughout
this guide, except where a separate macOS/Linux line is given.

**Which shell am I in?** Look at the prompt:

| Prompt looks like | Shell |
|---|---|
| `PS C:\Users\you\nasa-sli-sim>` | PowerShell |
| `you@LAPTOP MINGW64 /c/Users/you/nasa-sli-sim` then `$` on the next line | Git Bash |
| `you@mac nasa-sli-sim %` or `$` | macOS / Linux |

Both Windows shells work equally well. Pick one and use its blocks; the only
mistake is copying a command from the other shell's block.

## 0.2 Go to the project folder

Every command runs from the **project folder**: the one containing `scripts/`,
`config/` and `slisim/`. VS Code's terminal starts there. Anywhere else, move
there with `cd`, using the path where you cloned the repository (the paths below
are placeholders):

PowerShell:

```powershell
cd C:\Users\you\nasa-sli-sim
```

Git Bash:

```bash
cd /c/Users/you/nasa-sli-sim
```

Git Bash spells `C:\Users` as `/c/Users` and uses forward slashes. In either
shell, put a path containing spaces in quotes: `cd "C:\My Projects\nasa-sli-sim"`.
If you are unsure of the path, open the folder in File Explorer and copy it from
the address bar — PowerShell takes it exactly as copied.

Check you are in the right place (works in both shells):

```bash
ls scripts
```

You should see `run_nominal.py` and the other scripts. If `ls` reports the
folder does not exist, you are one level off: your copy may sit inside a larger
folder (for example in a `sim/` subfolder), so `cd` into it.

> **Why it matters.** Running from the wrong folder fails outright —
> `can't open file '...\scripts\run_nominal.py': [Errno 2] No such file or directory`.
> Pointing at the script from outside (`python sim/scripts/run_nominal.py`)
> starts, but every relative path you give it, like
> `--vehicle config/vehicles/full_scale.yaml`, is then looked for in the wrong
> place. Run from the project folder and every command in this guide works as
> written.

## 0.3 Activate the environment

The framework's packages — RocketPy, the OpenRocket bridge, PyYAML — are
installed in a private Python inside the project, the **virtual environment**
in `.venv/`. Your computer's own Python does not have them. Activating the
environment makes `python` mean that private copy for the rest of the terminal
session:

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Git Bash:

```bash
source .venv/Scripts/activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

The prompt now starts with **`(.venv)`**. That is the sign to look for before
running anything. Confirm it (identical in every shell):

```bash
python -c "import sys; print(sys.executable)"
```

The path printed must be inside the project's `.venv` folder, for example
`C:\Users\you\nasa-sli-sim\.venv\Scripts\python.exe`. If it points anywhere
else, the environment is not active.

Four things to know:

- **Activation lasts for one terminal.** A new tab, a new window, or a
  restarted VS Code needs it again. `deactivate` turns it off by hand.
- **VS Code can do it for you.** Press Ctrl+Shift+P, run
  `Python: Select Interpreter`, and pick the entry containing `.venv`. Every
  terminal opened *after* that starts activated, showing `(.venv)`. A terminal
  opened before the selection does not change; open a new one with **+**.
- **PowerShell may refuse the first time**, with
  `Activate.ps1 cannot be loaded because running scripts is disabled on this system`.
  That is Windows' default script policy. Allow scripts you run yourself, once
  per computer, then activate again:

  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
  ```

- **Activation is a convenience, not a requirement.** Without it, type the
  environment's Python by its full path instead of `python`:
  `.venv\Scripts\python` (PowerShell), `.venv/Scripts/python` (Git Bash), or
  `.venv/bin/python` (macOS/Linux). For example,
  `.venv\Scripts\python scripts\run_nominal.py`. Windows keeps it in `Scripts`
  in both shells; `bin` is macOS and Linux only.

> **This guide writes `python` everywhere.** With the environment active, that
> is exactly what you type. A bare `python` in a terminal that is *not*
> activated runs your computer's own Python, which fails at the first import:
>
> ```
> ModuleNotFoundError: No module named 'yaml'
> ```
>
> (or `'rocketpy'`, or `'numpy'` — whichever it reaches first). Nothing is
> broken; activate and run it again.

**Slashes.** Paths after `python`, like `scripts/run_nominal.py` or
`config/vehicles/full_scale.yaml`, are read by Python, which accepts forward
slashes on every system. That is why the commands in this guide use `/` and
work unchanged in PowerShell. Only commands PowerShell itself runs, like `cd`,
need care, and those are given in both forms.

## 0.4 Get the team's latest work, and save your own

Several people edit the same vehicle files, and git keeps that orderly. These
commands are identical in PowerShell and Git Bash:

```bash
git pull                       # start with everyone else's latest work
# ... edit config/vehicles/full_scale.yaml, run some analyses ...
git status                     # what did I change?
git diff                       # exactly what, line by line
git add config/vehicles/full_scale.yaml   # choose what goes in this snapshot
git commit -m "Raise fin span to 7.5 in for stability margin"
git push                       # share it
```

**Pull before you start, push when you stop.** Most git trouble comes from
skipping the first. `git status` changes nothing and usually tells you what to
type next, so use it whenever you are unsure.

**Say why in the message.** "Raise fin span to 7.5 in for stability margin"
tells a teammate the story; "update" does not. The *what* is already in the
diff.

**Name the files you add.** Don't use `git add .` or `git add -A`: they sweep up
stray files. `output/`, `.venv/` and the OpenRocket jar are already excluded,
and everything in `output/` can be regenerated from the configs, so commit
configs, never results.

In VS Code, the Source Control panel (Ctrl+Shift+G) does the same with buttons:
it lists changed files, shows a diff when you click one, stages with **+**,
takes the message in the box at the top, and pulls and pushes with **Sync**.

**Trying something that might not work** — a new fin set, a different motor —
goes on a branch, so `main` always runs:

```bash
git switch -c yourname/fin-trade      # create a branch and move onto it
git push -u origin yourname/fin-trade # first push; later just `git push`
git switch main                       # back to the shared version
```

Merge it into `main` through a pull request on GitHub when it is good, or
simply switch back to `main` if it is not.

**When git reports a conflict**, two people changed the same lines. Git marks
the spot in the file:

```
<<<<<<< HEAD
    height_in: 7.50
=======
    height_in: 8.00
>>>>>>> yourname/fin-trade
```

Keep the version you want, delete the three marker lines, then `git add` the
file and `git commit`. VS Code shows *Accept Current / Accept Incoming / Accept
Both* buttons over each conflict, which is easier than editing by hand.

**Undoing things:**

| Situation | Command |
|---|---|
| Throw away my changes to one file | `git restore config/vehicles/full_scale.yaml` |
| Unstage a file I added by mistake | `git restore --staged <file>` |
| Set my work aside for a moment | `git stash`, later `git stash pop` |
| See how a file changed over time | `git log -p config/vehicles/full_scale.yaml` |

`git restore` discards work permanently, so read `git status` first. Once
something is committed it can be recovered; before that, it cannot.

## 0.5 Opening the results

Runs write figures (`.png`), tables (`.md`), data (`.csv`) and OpenRocket files
(`.ork`) under `output/`, and print where they went. No plot windows pop up. The
easiest way to open them is to click them in VS Code's file tree: `.png` and
`.md` open right there, and `.csv` reads well with the Rainbow CSV extension.
From the terminal, open a file with your computer's default program:

PowerShell:

```powershell
start output\template_full_scale\nominal\flight_profile_0lb.png
```

Git Bash:

```bash
start output/template_full_scale/nominal/flight_profile_0lb.png
```

macOS: `open` in place of `start`. Linux: `xdg-open`.

A `.ork` file opens in the OpenRocket app (version 24.12), which is how you
check the framework is modeling the rocket you think it is.

## 0.6 The whole routine

PowerShell:

```powershell
cd C:\Users\you\nasa-sli-sim
.venv\Scripts\Activate.ps1
git pull
python scripts/run_nominal.py
```

Git Bash:

```bash
cd /c/Users/you/nasa-sli-sim
source .venv/Scripts/activate
git pull
python scripts/run_nominal.py
```

In VS Code with `.venv` selected, the first two lines happen on their own: open
a terminal, check for `(.venv)`, then `git pull`.

If something fails before a simulation even starts, see
[§6.0](#60-environment-errors).

---

# Part 1 — Guided first run

Work through this at a keyboard. Roughly 30 minutes.

## 1.1 The nominal flight

```bash
python scripts/run_nominal.py
```

This builds the vehicle from `config/vehicles/full_scale.yaml`, writes a `.ork`,
flies it in
both engines, and checks every requirement. Three blocks of output:

**Block 1 — the vehicle.**

```
Vehicle : Template Full-Scale  [PLACEHOLDER - not a real design]
Site    : Bragg Farms, Toney AL (NASA Student Launch competition site)
Length  : 93.0 in   Diameter: 6.00 in
  Motor   : L1520T (AeroTech)  3769 N-s, 1.773 kg propellant
  Saved   : ...\output\template_full_scale\nominal\template_full-scale_0lb.ork
```

That `.ork` is a real OpenRocket file. **Open it in the GUI now** — it is the
quickest way to convince yourself the framework is modeling what you think it
is. You will see the nose cone, two body tubes, the boat tail, the fin set,
rail buttons, motor mount, and both parachutes.

**Block 2 — the two engines side by side.**

```
quantity                 units    OpenRocket     RocketPy       diff        %
Apogee                   ft          5263.28      5266.02       2.73      0.1
Max velocity             fps          716.40       716.47       0.07      0.0
Static stability         cal            2.36         2.36       0.00      0.1
Rail exit velocity       fps           88.62        77.78     -10.84    -12.2
Drift from pad           ft          1467.66      1326.33    -141.33     -9.6
```

Apogee agreeing to 0.05% across two independent integrators is a strong result
and is exactly the evidence the handbook's "different calculation method"
bullet is asking for.

The two rows that *don't* agree are expected, and knowing why is the difference
between a good report and a great one:

- **Rail exit velocity (−12.2%).** The two tools define "off the rail"
  differently. OpenRocket releases the vehicle when the forward rail button
  passes the rail tip; RocketPy when the center of mass has traveled the full
  rail length. RocketPy reads lower, so quoting RocketPy for requirement 2.14
  (≥52 fps) is the conservative choice.
- **Drift (−9.6%).** This one originates during *ascent*, not descent. The
  descent phases agree to under 2%. RocketPy leaves the rail slower (see
  above), so it enters free flight at a larger angle of attack relative to the
  wind, weathercocks harder, and reaches apogee further upwind. Because net
  drift is the *difference* between an upwind apogee offset and a downwind
  descent, a modest difference in the first shows up amplified in the
  remainder. Quote the Monte Carlo landing ellipse, not either single run.
  Full decomposition in `FLIGHT_DYNAMICS.md` §14.2.

**Block 3 — requirement compliance.** Every check cites its handbook paragraph.

```
  PASS    2.11     Static stability on pad          2.36 cal      >= 2.0
                   `-- evaluated at Mach 0.3, matching OpenRocket's GUI convention
  PASS    3.2      KE at landing: Booster + Boattail   40.16 ft-lbf   <= 75
                   `-- 11.64 lb at 14.9 fps descent rate; incl. horizontal drift = 79.6 ft-lbf (over 75)
```

Read that second note carefully — it is discussed in [§5.3](#53-the-kinetic-energy-subtlety).
The booster's 11.64 lb includes the spent motor case, which lands with it.

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

The max-ballast case lands about 245 ft lower. That is ballast doing its job —
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

Produces `output/<vehicle>/crossvalidation/crossvalidation.md` — a report-ready
document containing the comparison table, the honest scope statement about what
is independent, and a written discussion of each difference over 5%. Anything
differing by more than 5% that is *not* on the known-differences list is flagged
as **unexplained**, which is your cue to investigate before citing the number.

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
| 2.1 | Apogee in 4,000-6,000 ft    | 1.000   | 5141.1   | 4704.7   | 5591.4   |
| 2.11| Stability >= 2.0 cal        | 1.000   | 2.358    | 2.350    | 2.367    |
```

This is the payoff. Not "our apogee is 5,263 ft" but **"every one of 1,000
dispersed cases lands inside the required window, with a 95% interval of 4,705
to 5,591 ft."** That is a defensible statement.

That stability row is suspiciously tight — 2.350 to 2.367 — and the run opened
with a banner saying why: the shipped mass worksheet has every sigma at 0, so
mass and CG never vary. Fill in the sigma columns (§2.10) before quoting a
stability or kinetic-energy probability.

**Recommended target altitude:**

```
    Recommended declaration : 5,130 ft
    95% CI                  : [4,705, 5,591] ft
    P(4,000-6,000 ft)       : 100.0%
```

Requirement 2.3 scores you on closeness to the altitude you declare at CDR. The
best declaration is therefore the **center of your predicted distribution** —
not the nominal run, and not the middle of the legal window.

**Sensitivity** — what actually drives apogee (1,000 cases, seed 12345):

```
| drag_coefficient    | -0.626 |
| motor_total_impulse |  0.533 |
| wind_speed_mps      | -0.256 |
| temperature_k       |  0.190 |
| rail_angle_deg      | -0.141 |
| pressure_pa         | -0.067 |
```

Spearman rank correlation. Drag and motor impulse dominate — and of those two,
motor scatter is fixed at the factory while drag is something you can measure.
That is where the effort belongs: fitting drag from flight data is worth more
than shaving grams.

Run this at **1,000 cases or more before you quote it**. At 60–200 cases the
ranking is not just noisier, it is wrong — on the reference vehicle,
development runs put `temperature_k` third at 0.40, where 1,000 cases settle it
far lower (`FLIGHT_DYNAMICS.md` §13.4). Always record the sample
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
  Cd scale factor      : 1.1757  (+17.6% vs the pre-flight model)
  Measured apogee      : 4,929 ft
  Pre-flight prediction: 5,279 ft (+351 ft error)
  Post-fit prediction  : 4,929 ft (-0 ft residual)
  Ascent RMSE          : 9 ft
```

The fitter recovered 1.176 against a true 1.180 — 0.4% error. That round-trip
is how you know the tool works before you trust it with real data.

## 1.7 Comparing telemetry to the model

The same command also wrote `data/flights/synthetic_telemetry.csv`: what a
flight computer with a barometric altimeter, an IMU and a GPS would have logged
on that flight, sensor noise included, with its clock started 2 s before
ignition. It is practice data for the comparison you will make after the
subscale and full-scale flights:

```bash
python scripts/compare_flight.py data/flights/synthetic_telemetry.csv --wind 9 --temp-f 68
```

```
| quantity                  | units | simulated | measured | difference |
| Apogee (baro)             | ft    | 5193.84   | 4840.50  | -353.34    |
| Time to apogee            | s     | 17.47     | 16.63    | -0.84      |
| Max axial acceleration    | g     | 11.55     | 11.47    | -0.08      |
| Landing distance from pad | ft    | 1305.21   | 1232.25  | -72.97     |
```

It flies the model at the launch-day conditions you give (the same flags as
`fit_cd.py`), puts the log and the simulation on one clock, and writes to
`output/<vehicle>/postflight/`:

- **`comparison_<log>.png`**: simulated over measured for each channel the log
  has (altitude, axial acceleration, lateral acceleration, roll rate,
  pitch/yaw rate, and the GPS ground track).
- **`comparison_<log>.csv`**: the log with the simulation interpolated onto its
  timestamps (`sim_*` beside each channel), for your own plots and statistics.

**Read the figure for the physics, not just the gap.** The practice log has
18% more drag than the model, and it shows everywhere drag acts: apogee
353 ft low and 0.8 s early, and coast deceleration visibly stronger than the
model's. Boost acceleration, which drag barely affects, matches. A real
mismatch has a signature like that, and the signature tells you which input
is wrong. Here, `fit_cd.py` is the fix.

**Things that are not model errors:**

- **The clocks.** Flight computers start at power-on or launch detection;
  the simulation starts at ignition. The script aligns them where both cross
  100 ft above the pad, so the x-axis is time from ignition. At sharp
  transients, ignition and burnout, expect the two to be off by a sample or
  so.
- **Altitude.** The simulated line is *barometric* altitude: simulated
  pressure run through the standard atmosphere, which is how an altimeter
  computes it. On a non-standard day, it reads a few percent different from
  true height, exactly as the real altimeter does. Compare like with like.
- **Acceleration.** An accelerometer measures specific force: about +1 g
  along the rocket on the pad, about −2 g at burnout, and near 0 at apogee,
  never −1 g in free fall. The simulated column is computed the same way. A
  log whose axial channel reads negative under thrust is from a board mounted
  upside down; the script notices and flips it.
- **Lateral axes.** Lateral IMU axes depend on how the board is mounted and
  rolled, so lateral acceleration and pitch/yaw rate are compared as
  magnitudes. The simulated rocket is perfectly symmetric, so its roll rate is
  zero; a real one rolls a little from fin build tolerance.
- **After the parachutes open,** the body-frame channels stop. The
  simulation flies the descent as a point mass under the canopy, so it has no
  attitude to compare there. Altitude and GPS continue to landing.

**Real logs.** Columns are found by name (`Accel Z`, `Gyro X`, `Latitude`, and
common variants, units in parentheses ignored). Accelerations are taken in g
and rates in deg/s unless the header says `(m/s^2)` or `(rad/s)`. A logger that
names things differently gets `--map`:

```bash
python scripts/compare_flight.py data/flights/subscale_1.csv --map accel_z_g="AccelAxial" --map gyro_z_dps="RollRate"
```

The fields are `time_s`, `altitude_ft`, `accel_x_g`, `accel_y_g`, `accel_z_g`
(the rocket's long axis), `gyro_x_dps`, `gyro_y_dps`, `gyro_z_dps` (roll),
`latitude_deg` and `longitude_deg`. Only time and altitude are required. The
script prints which column it used for each field, so check that first.

**Every simulated state, not just these.** Each `run_nominal.py` writes
`output/<vehicle>/nominal/flight_states_<ballast>lb.csv`, the whole simulated
flight at 100 Hz. It has position and GPS coordinates, velocity, Mach, body
rates, attitude (quaternion, Euler angles, angle of attack), body-frame
acceleration, pressure and barometric altitude, and a `phase` column (rail,
powered, coast, under each parachute). It opens in Excel. Use it for anything
the comparison figure does not plot.

---

# Part 2 — Defining your vehicle

Vehicles live in `config/vehicles/`, authored in **inches and pounds** because
that is how the handbook is written and how the team thinks. Conversion to SI
happens once, in `slisim/units.py`.

## 2.0 Carrying several vehicles at once

You will not have one rocket. You will have the full-scale, the subscale that
requirements 2.15 and 2.16 oblige you to fly, and — around PDR — two or three
layout options you are deciding between. All of them exist at the same time, so
each one is a file:

```
config/vehicles/
├── full_scale.yaml        the design you are scored on (the default)
├── subscale.yaml          req 2.15/2.16: >= E impulse, <= 75% scale
├── pdr_option_a.yaml      4-fin trade
└── pdr_option_b.yaml      3-fin trade
```

Every script takes `--vehicle`; with no flag you get `full_scale.yaml`:

```bash
python scripts/run_nominal.py
python scripts/run_nominal.py --vehicle config/vehicles/subscale.yaml
```

**Use files, not branches.** A branch says "this replaces that", which is true
of a code experiment and false of your vehicles: subscale and full-scale coexist
all season, and neither ever merges into the other. On separate branches you
cannot plot two PDR options against each other without checking out, running,
stashing, and switching; a mass correction has to be cherry-picked into every
branch by hand; and `git log config/vehicles/subscale.yaml` stops being able to
tell you what the subscale weighed at CDR. Branches are still right for trying a
change to the *code*.

To add one, copy the closest existing file and edit it:

```bash
cp config/vehicles/full_scale.yaml config/vehicles/pdr_option_b.yaml
```

`cp` works as written in both shells (PowerShell understands it as
`Copy-Item`). Copying the file in VS Code's file tree works too. If the vehicle
uses a mass worksheet (§2.10), copy that as well and point the new file's
`mass_properties:` at the copy, so the two designs can change independently.

Change `name:` first. **Output directories are derived from that name**, so two
vehicles sharing a name overwrite each other — which is the one mistake this
layout exists to prevent (§5.0).

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

This and the other mass keys in §2.1–2.6 are how a vehicle file holds masses
*without* a worksheet (`reference_2026_09.yaml` works this way). With a mass
worksheet (§2.10) — what `full_scale.yaml` uses — the sections, their lengths
and every mass come from the worksheet instead, and the yaml leaves them out.

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

## 2.4 Transitions

A transition is a change of body diameter — a boat tail, a shoulder, or a
flare. Skip this section entirely if your vehicle is a constant-diameter tube
nose-to-tail; `transitions:` defaults to empty.

```yaml
transitions:
  - name: "Boattail"
    after_section: "Booster"   # optional; omit it and the transition sits at the aft end
    fore_diameter_in: 5.15
    aft_diameter_in: 2.95
    length_in: 2.50
    shape: ogive                # conical | ogive | ellipsoid | haack | parabolic | power
    shape_parameter: 1.0
    wall_thickness_in: 0.079
    mass_lb: 0.137
```

> **`transitions` is a list, even with a single entry.** Leave off the
> leading `-` and `name: "Boattail"` becomes its own list item read as plain
> text, not part of a mapping — the framework then rejects it with a clear
> error naming the bad entry, rather than silently dropping the transition.

## 2.5 Motor

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

## 2.6 Recovery

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

## 2.7 Landing sections

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

## 2.8 Ballast and target

```yaml
ballast:
  min_lb: 0.0
  max_lb: 3.00              # req 2.20.7: <= 10% of un-ballasted mass
  location: "Payload Bay"

target_apogee_ft: 4500.0
```

Always validate with `--ballast both`. Requirement 2.20.7.4 requires compliance
at both extremes, and the extremes differ by hundreds of feet.

## 2.9 From an OpenRocket design to a vehicle file

You will not author a vehicle file from nothing. You will draw the rocket in the
OpenRocket GUI first — that is where fin shapes and component fits get worked
out — and then transcribe it. The framework runs the other direction
(`vehicle.yaml` generates the `.ork`), so this is the one step it cannot do for
you, and it is where the mistakes happen: a transposed digit produces a
plausible number, not an error.

Work through the blocks in the order below. Every value comes from a component
in the OpenRocket tree, so keep the GUI open beside the file.

| yaml block | OpenRocket source |
|---|---|
| `airframe` | any body tube: outer diameter, wall thickness, finish |
| `nose_cone` | the nose cone: shape, length, shoulder length, wall thickness |
| `sections` | each body tube, nose-to-tail: length and mass |
| `transitions` | each transition: name, after_section, fore/aft diameter, length, shape |
| `fins` | the fin set: chords, sweep, span, thickness, cant |
| `motor` | the motor mount inner tube: inner diameter, length |
| `recovery` | each parachute: diameter, Cd, deploy event and altitude |
| `landing_sections` | **not in the .ork** — which joints separate in flight |

### The mass rule, which is where transcription goes wrong

OpenRocket shows you two numbers for a component: its **own** mass, and its mass
**with everything inside it**. The yaml wants neither, quite.

> A section's `mass_lb` is that section plus everything permanently inside it,
> **excluding** the fins, the parachutes, the shock cord, and the motor — because
> those are declared in their own blocks.

Take the rolled total and you count the fins and parachutes twice. That mistake
is worth **0.22 lb on the subscale**, and it is invisible: every number still
looks reasonable, the file still loads, the simulation still runs. Only the mass
budget moves.

Concretely, for a booster tube containing a motor mount, two centering rings, a
bulkhead, the main parachute, shock cord, and the fin set:

```
OpenRocket "with contents"  1.308 lb     <- do NOT use
  less fin set              0.180        declared in `fins:`
  less main parachute       0.018        declared in `recovery:`
  less shock cord           0.002        declared in `shock_cord_mass_lb:`
                            -----
section mass_lb             1.108 lb     <- use this
```

Everything else inside — the mount, the rings, the bulkhead — stays in, because
it is permanently part of that section and it is what lands.

### Check the transcription against the source

Do not eyeball it. Build both models and compare:

```bash
python scripts/check_against_ork.py --vehicle config/vehicles/full_scale.yaml --ork path/to/your_design.ork
```

Keep it on one line. Splitting a long command across lines needs a different
character in each shell — `\` at the end of a line in Git Bash, a backtick
`` ` `` in PowerShell — and the wrong one gives a confusing error, so this guide
never splits commands.

It reports overall length, launch mass, CP and CG side by side, and exits
non-zero when anything is outside tolerance. Read the deltas rather than looking
for a pass, because each one points somewhere different:

| What is off | What it means |
|---|---|
| **length** or **mass** | A block was mistyped, or the mass rule above was missed. |
| **CP** | Geometry: a chord, a span, a nose length — or a transition you forgot to declare. |
| **CG**, with mass and CP correct | Usually not an error. See below. |

It also warns when the `.ork` and the yaml disagree on how many fin sets exist,
which is worth having: a fin set duplicated in the GUI sits invisibly on top of
the original and inflates CP, margin and mass all at once.

### When CG does not match but mass and CP do

Length, mass and CP come straight from numbers you typed. CG does not — it
depends on *where* that mass sits, and by default the framework makes two
assumptions:

- a section's mass is spread evenly, putting its CG at the midpoint;
- the main rides in the forward-most section and the drogue in the booster.

Both are conventional and both are often wrong. A section carrying a payload at
one end, or a design that packs the main aft, will come out with the right mass
in the wrong place. On one full-scale the two together put CG **1.15 in forward,
reading 2.43 caliber against a true 2.20** — optimistic, on a scored
requirement, near the 2.0 limit of requirement 2.11.

Say where the mass is and the assumption goes away:

```yaml
nose_cone:
  mass_lb: 0.766
  cg_from_tip_in: 10.84       # the shell plus its bulkhead, not the midpoint

sections:
  - name: "Payload Bay"
    length_in: 20.00
    mass_lb: 10.671
    cg_from_front_in: 10.24   # measured from the front of THIS section

recovery:
  main:
    mass_lb: 1.085
    bay: "Booster"            # which section it is packed in
    cg_from_front_in: 2.00
  shock_cord_mass_lb: 0.990
  shock_cord_bay: "Drogue Bay"
  shock_cord_cg_from_front_in: 6.10
```

Every one of these is optional, and leaving them out keeps the old behaviour, so
adding them to an existing file changes nothing until you fill them in. Applied
to the full-scale above, they brought CG to within **0.03 in** and margin to
within **0.01 caliber** of the source design.

Read the values off the OpenRocket component analysis. Do not compute them by
hand — you will be transcribing a number you already have.

Shock cord is lumped into one bay rather than strung between sections, so if
yours is split across several, give the combined mass and the station where the
combination balances.

### What the schema deliberately cannot represent

Three limits worth knowing before you fight the file:

**One surface finish per airframe.** If the GUI has polished forward tubes and
painted aft ones, pick the rougher. Being conservative on drag is the right way
to be wrong.

**One fin set.** Canards or strakes cannot be expressed. Nothing in the USLI
ruleset needs them, and OpenRocket cannot compute a 2-fin set anyway — Barrowman
assumes an axisymmetric set and returns zero normal force otherwise.

### Things the .ork simply does not know

Two blocks have no source in the GUI and are engineering decisions you supply:

- **`landing_sections`** — which joints separate in flight, and therefore what
  lands as one piece. This drives the kinetic-energy check of requirement 3.2,
  which is scored. Guessing it wrong produces a confidently wrong answer.
- **`target_apogee_ft`** — declared at CDR under requirement 2.3.

Mark anything you assume. A `# CONFIRM` comment costs nothing and stops an
assumption being read as data three months later.

## 2.10 The mass worksheet

Once a design has more than a handful of parts, keep its masses in a
**worksheet** — a CSV in `config/mass/` that opens in Excel — and point the
vehicle file at it:

```yaml
mass_properties: full_scale.csv   # in config/mass/
```

The worksheet then supplies every length, mass and position: the nose cone's,
each body section's, each transition's, the fins', and the recovery hardware's.
The yaml keeps only shapes, the motor, parachute sizes and decisions. A value in
**both** files is an error, not an override — a stale `mass_lb` left in the yaml
would read as data, and nobody could tell which number flew. Both example
vehicles (`full_scale.yaml`, `fullscale_model_a.yaml`) work this way; a vehicle
file with masses typed into the yaml (§2.1–2.6) still works too.

### One row per part

```
section,component,kind,mass_lb,mass_sigma_pct,length_in,section_front_in,from_section_front_in,position_sigma_in,from_nose_tip_in,moment_lb_in,inertia_pitch_lb_in2,inertia_roll_lb_in2,inertia_sigma_pct,source,note
Payload Airframe,Payload,tethered,4.500,0,,,8.00,0,32.00,144.000,...,0,CONFIRM,placeholder
Payload Airframe,Main Parachute,main,2.600,0,,,15.00,0,39.00,101.400,...,0,vendor,
Payload Airframe,SECTION,,15.800,,36.00,24.00,17.57,,41.57,656.800,...
```

| Column | You fill in | Meaning |
|---|---|---|
| `section` | yes | The tube the part physically sits in. Sections run nose to tail: the nose cone first, then the body tubes, then any transition, which follows the tube above it. |
| `component` | yes | One thing you can put on a scale. |
| `kind` | yes | What it counts toward: `structure`, `tethered`, `fins`, `main`, `drogue`, `shock_cord`. A main packed in the payload tube is still `main`. |
| `mass_lb` | yes | The part's mass. |
| `from_section_front_in` | yes | The part's CG, measured from the front of **its own** section. Moving a section does not move its parts. |
| `inertia_pitch_lb_in2`, `inertia_roll_lb_in2` | yes | The part's own inertia about its own CG (below). |
| `*_sigma_*` | yes | Its uncertainty (below). 0 means exact. |
| `source` | yes | `weighed`, `cad`, `vendor`, `override`, `ork`, `estimated`, or `CONFIRM`. `CONFIRM` means nobody has stood behind the number yet. |
| everything else | no | Derived: positions from the nose tip, moments, and the `SECTION` and `AGGREGATE` totals. They are stored so you can follow the arithmetic, and checked rather than trusted. |

A `SECTION` row closes each section with its length; the `AGGREGATE` block at the
bottom combines the sections into the dry vehicle (no motor, no ballast). The
motor comes from OpenRocket's database and ballast is a range in the yaml, so
neither appears here.

A **`tethered`** part — a payload that rides in its tube on the pad but lands on
its own tether — counts toward its section's flight mass and becomes its own
piece at landing. Name it in `landing_sections:` by its `component`.

After any edit, run:

```bash
python scripts/check_mass_csv.py
```

It recomputes every derived cell and names the line to fix, so a changed mass
with a stale moment beside it cannot slip through. Excel's "CSV UTF-8" format
is fine.

### Inertia

The simulation flies the worksheet's inertia, not OpenRocket's. OpenRocket can
only estimate inertia from component shapes; your CAD knows where the mass
actually is. Take each part's values from SolidWorks' Mass Properties
"**taken at the center of mass**", with X along the rocket axis: pitch is `Lyy`
(average `Lyy` and `Lzz` if they differ) and roll is `Lxx`, in lb·in². The totals
apply the parallel-axis theorem for you. Until CAD exists, OpenRocket's
per-component values are a reasonable start — Model A's are — and
`run_crossvalidate.py` prints the worksheet's totals beside OpenRocket's own
estimate so you can see how far apart they are.

### The sigma columns

Each part carries its own uncertainty, and every Monte Carlo case draws each
part independently:

| Column | Draw | Example |
|---|---|---|
| `mass_sigma_pct` | mass × (1 + N(0, σ/100)) | `5` = 5% one-sigma |
| `position_sigma_in` | CG position + N(0, σ) inches | `0.5` |
| `inertia_sigma_pct` | both inertias × (1 + N(0, σ/100)) | `10` |

Each case then rebuilds the dry mass, CG and inertia from its draws, so a heavy
payload moves the CG and the inertia together the way real hardware does, and
the kinetic-energy check of requirement 3.2 uses the pieces that actually flew.
A single "dry mass ±1.5%" cannot do either. The three totals show up in the
Monte Carlo input plot and sensitivity table as `mass_lb`, `cg_in` and
`inertia_pitch_lb_in2`.

**The shipped worksheets have every sigma at 0**, and `run_montecarlo.py` prints
a banner saying the campaign has no mass dispersion until you change that. A
campaign without it is not wrong, but its stability and KE probabilities are
too optimistic, so do not quote one at a review. Choose sigmas from how each
number was obtained:

| `source` | Reasonable mass σ | Position σ |
|---|---|---|
| `weighed` | 1–2% (scale resolution, epoxy still to come) | 0.25 in |
| `vendor` | 3–5% | 0.5 in |
| `cad` | 5% | 0.25 in |
| `ork`, `estimated` | 10% | 1 in |
| `CONFIRM` | 20–30% | 2 in |

Tighten them as parts are built and weighed; that is the point of carrying them
per part. To see what mass uncertainty alone does to the flight, disperse it by
itself (§4.4):

```bash
python scripts/run_montecarlo.py -n 1000 --only mass_properties
```

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
| `mass_properties` | per part, in the worksheet (0 as shipped) | §2.10: set each part's sigma from its `source`, and tighten as parts are weighed. |
| `dry_mass` | 0 | A blanket multiplier on the whole dry mass, on top of the per-part draws. Use it only for a vehicle file with no worksheet, or as an allowance for mass nobody has itemized yet (epoxy, paint, wiring). |
| `drag_coefficient` | 7% | Compare OpenRocket vs RocketPy, then **fit from flight data** with `fit_cd.py`. Expect 2–3% afterward. |
| `motor_total_impulse` | 2% | Manufacturer certification data; thrustcurve.org shows lot-to-lot spread. |
| `wind_speed_mps` | site file | Historical data for the field and month. NOAA/Iowa State Mesonet have archives. |
| `main_cd` / `drogue_cd` | 10% | Manufacturer data if published; otherwise keep it wide — this is genuinely uncertain. |
| `main_deploy_altitude_ft` | 25 ft | Altimeter datasheet accuracy plus bay-porting effects. |

**Cite which version of this file produced any number you put in a report.**
A reviewer asking "where does 5,130 ft come from" deserves a traceable answer.

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

**Reproducibility.** The same `--seed` reproduces the same campaign months
later. Record the seed alongside any number you publish.

One honest caveat, because a reviewer may notice it. OpenRocket's own output is
not bit-identical between runs: summation order inside the JVM varies, which
moves its numbers by about one part in 10¹². You will see it as the last printed
digit of an OpenRocket result changing — apogee by ~0.01 ft — and never as a
changed pass/fail or a shifted statistic. The RocketPy side *is* bit-identical,
because the drag curve it is handed is quantised before it gets there; without
that, the solver amplifies OpenRocket's last-bit jitter to about 1e-5 by
landing. Quote results to the precision they deserve — four significant figures
is generous for an apogee prediction — and this never arises.

**The two engines disperse different things.** RocketPy disperses everything —
mass, CG, drag, motor, wind, rail. OpenRocket disperses launch conditions only,
because perturbing mass and drag would mean rebuilding the component tree for
every sample. Use RocketPy for dispersion; use OpenRocket as the independent
check on the trajectory.

## 4.4 Dispersing one parameter at a time

A full campaign answers "how much might we miss by?". It does not answer "how
much of that is the drag we do not know?" — every input moves at once, so no
single histogram belongs to any one of them. `--only` and `--freeze` narrow the
set; everything not selected is held at its nominal value.

```bash
python scripts/run_montecarlo.py --list-parameters             # the names
python scripts/run_montecarlo.py -n 1000 --only drag_coefficient
python scripts/run_montecarlo.py -n 1000 --only wind_speed_mps,wind_direction_deg
python scripts/run_montecarlo.py -n 1000 --freeze drag_coefficient
```

| Flag | Meaning |
|---|---|
| `--only P1,P2` | Disperse exactly these; hold every other parameter nominal |
| `--freeze P1,P2` | Hold these nominal; disperse everything else |
| `--list-parameters` | Print the names, their distributions, and which engine uses them |

**What this is good for.**

- *Showing a single effect.* `--only drag_coefficient` makes the apogee
  histogram a picture of drag uncertainty and nothing else. The Spearman
  correlation comes back at exactly ±1.00, which is a useful sanity check that
  the parameter is wired through the model at all.
- *Budgeting the error.* Run `--only` once per parameter at a fixed seed and
  collect the apogee standard deviations. They add roughly in quadrature to the
  full-campaign sigma, which turns the sensitivity bar chart into a variance
  budget in feet — a far easier thing to defend at CDR than a rank correlation.
- *Answering "what if we measured this better?"* `--freeze drag_coefficient` is
  the campaign you would have if drag were known perfectly. The difference
  between that spread and the full one is the value of doing the Cd fit in
  a post-flight Cd fit, in feet of apogee.

**Held nominal means nominal, not absent.** A frozen parameter is still drawn,
pinned to its nominal value: relative multipliers to 1.0, shifts to 0.0, and
wind, temperature and pressure to the *site's* nominal conditions from
`sites.yaml`. Freezing the wind flies the site's mean wind, not a dead calm.
The one arbitrary case is `rail_direction_deg`, which is uniform over the full
circle and has no mean; frozen, it takes the midpoint (180°).

**Every output says what was dispersed.** The filenames carry an `_only-...` or
`_except-...` tag and the markdown report lists both sets, so a subset run
cannot be mistaken later for a full campaign. Only a full campaign supports a
compliance probability — P(pass) from a run with one input dispersed is the
probability given that nothing else is uncertain, which is not a claim any
review will accept.

**OpenRocket.** It only sees the six launch-condition parameters, so
`--only drag_coefficient --engine openrocket` would run N identical flights.
The script refuses that rather than printing a distribution with no width.

---

# Part 5 — Reading the output

## 5.0 Where things land

`output/` is organized by vehicle, then by what produced the files:

```
output/
├── full_scale/
│   ├── nominal/                          run_nominal.py
│   ├── crossvalidation/                  run_crossvalidate.py
│   ├── input_model.png                   plot_inputs.py
│   └── mc/                               run_montecarlo.py
│       ├── 2026-09-18_143458_n1000_rocketpy/
│       ├── 2026-09-18_151203_n1000_rocketpy/
│       └── latest/        <- a copy of the most recent run
└── subscale/
    └── ...
```

**Why the vehicle level exists.** Most output filenames do not name the vehicle
— `flight_profile_0lb.png` is the same string whichever rocket you flew — so
without it a subscale run would overwrite your full-scale figures. That is at
its worst when comparing two PDR layouts, where the mistake does not look like
an error; it looks like a result.

**Why each Monte Carlo gets a dated folder.** The folder name records the time,
case count, and engine, but nothing about `uncertainty.yaml`. Edit one sigma,
re-run with the same flags, and the old campaign would otherwise be gone —
exactly when you are trying to compare dispersion configurations. Each run's
`montecarlo_*.md` lists the dispersions it used, so two folders are always
distinguishable after the fact.

`latest/` is a copy, not a symlink, so it works without Developer Mode on
Windows. Reference it when you want "the newest results" and the dated folder
when you mean one specific campaign.

| File | Contents |
|---|---|
| `*.ork` | OpenRocket files — open these in the GUI |
| `flight_profile_*.png` | Altitude / velocity / acceleration vs time, both engines |
| `stability_*.png` | Static margin and CP/CG vs time |
| `apogee_dist_*.png` | Apogee histogram with the requirement window |
| `landing_*.png` | Landing scatter against the 2,500 ft radius |
| `sensitivity_*.png` | What drives apogee |
| `inputs_*.png` | Histogram per parameter this campaign dispersed |
| `input_model.png` | Histogram per parameter the framework *can* disperse (`plot_inputs.py`) |
| `crossvalidation.md` | Report-ready engine comparison |
| `montecarlo_*.csv` | Every case, every input and output — for your own analysis (the Rainbow CSV extension makes these readable in VS Code) |
| `montecarlo_*.md` | Report-ready dispersion summary, including the dispersions used |

Every one of those PNGs is drawn by a function in `slisim/report.py`. Section
5.4 explains how they are put together and 5.5 how to change them.

### Comparing two vehicles

Because the paths differ and the filenames do not, comparing is just two runs:

```bash
python scripts/run_nominal.py --vehicle config/vehicles/pdr_option_a.yaml
python scripts/run_nominal.py --vehicle config/vehicles/pdr_option_b.yaml
```

```
output/pdr_option_a/nominal/flight_profile_0lb.png
output/pdr_option_b/nominal/flight_profile_0lb.png
```

Open both in VS Code and use split view, or put them side by side in the trade
study. Nothing was overwritten, and neither run needed a `--out` flag.

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

On the template vehicle, at 14.9 fps descent in a 10 mph wind:

| Section | KE (vertical) | KE (with drift) |
|---|---|---|
| Nose Cone | 7.9 ft·lbf | 15.7 ft·lbf |
| Payload | 15.5 ft·lbf | 30.8 ft·lbf |
| Payload Airframe | 25.5 ft·lbf | 50.6 ft·lbf |
| Booster + Boattail | **40.2 ft·lbf** | **79.6 ft·lbf** |

All four pass on the conventional basis. The booster would fail on the
conservative one. The framework prints both on every KE check so the choice is
explicit rather than accidental.

The booster is the heaviest piece partly because **the spent motor case lands
with it** — 4.1 lb of the L1520T's 8.0 lb launch mass. The framework adds the
case's burnout mass to whichever landing section holds the aft body tube. Leave
it out of a hand calculation and that section's energy comes out low by
roughly a third.

In a Monte Carlo campaign, each case uses its own landing masses: the per-part
mass draws from the worksheet (§2.10), and the motor case scaled by that case's
`motor_dry_mass` draw.

Sizing to the vertical rate is defensible and conventional. Knowing how little
margin that leaves is the useful part — and it is a good thing to raise
yourselves in a review before a panelist raises it for you.

## 5.4 How the figures are defined

Every figure in `output/` is produced by one function in **`slisim/report.py`**.
There is no plotting anywhere else in the framework — not in the scripts, not in
the engine bridges — so that is the only file you need to open.

| Function | Produces | Called by |
|---|---|---|
| `plot_flight_profile` | `flight_profile_*.png` | `run_nominal.py`, `run_crossvalidate.py` |
| `plot_stability` | `stability_*.png` | `run_nominal.py` |
| `plot_apogee_distribution` | `apogee_dist_*.png` | `run_montecarlo.py` |
| `plot_landing_scatter` | `landing_*.png` | `run_montecarlo.py` |
| `plot_sensitivity` | `sensitivity_*.png` | `run_montecarlo.py` |
| `plot_input_distributions` | `inputs_*.png`, `input_model.png` | `run_montecarlo.py`, `plot_inputs.py` |
| `plot_comparison` | `engine_comparison*.png`, `crossvalidation.png` | `run_nominal.py`, `run_crossvalidate.py` |

**The input histograms are the one figure about the *inputs* rather than the
results.** One histogram per parameter, grouped as in `config/uncertainty.yaml`,
each showing the quantity the parameter actually perturbs — pounds, N·s, feet
AGL, inches from the nose — rather than the multiplier that was drawn. Each
panel prints the observed standard deviation against the sigma the YAML asked
for; if those disagree by more than sampling noise, the run did not do what the
file said.

`drag_coefficient` is the exception, and stays dimensionless: it scales an
entire Cd-vs-Mach curve, so there is no single absolute value to report.

The same function serves two questions, depending on who calls it:

| | Written by | Shows |
|---|---|---|
| `inputs_*.png` | `run_montecarlo.py` | what **that campaign** dispersed — `--only` and `--freeze` applied, parameters held nominal left out |
| `input_model.png` | `plot_inputs.py` | every parameter the framework **can** disperse, straight from `uncertainty.yaml` |

Under `--engine openrocket` both show only the six launch conditions, because
those are the only ones that engine consumes
([§4.4](#44-dispersing-one-parameter-at-a-time)).

**They all have the same four-step shape.** `plot_sensitivity` is the shortest,
so read that one first — the others differ only in how much drawing happens
in step 2:

```python
def plot_sensitivity(sens: pd.DataFrame, out_dir: Path, output_label: str,
                     name: str = "sensitivity.png") -> Path:
    fig, ax = plt.subplots(figsize=(8, max(3.0, 0.42 * len(sens))))   # 1. make it
    colors = [FAIL_C if v < 0 else ACCENT for v in sens["spearman_rho"]]
    ax.barh(sens["input"], sens["spearman_rho"], color=colors, alpha=0.85)
    ax.axvline(0, color="black", lw=0.9)                              # 2. draw it
    ax.invert_yaxis()
    _style(ax, f"What drives {output_label}", "Spearman rank correlation", "")
    ax.set_xlim(-1, 1)                                                # 3. style it
    return _save(fig, out_dir, name)                                  # 4. save it
```

Steps 1, 3 and 4 are nearly identical everywhere. Step 2 is the only part that
knows anything about rockets.

**Two shared helpers do the work of steps 3 and 4.** Both sit at the top of
`report.py`, and changing either one restyles *every* figure at once — which is
usually what you want, and is much safer than editing six functions by hand.

- `_style(ax, title, xlabel, ylabel)` sets the title weight and font sizes, the
  axis labels, the grid, the tick size, and hides the top and right spines.
- `_save(fig, out_dir, name)` creates the directory, writes the PNG at 160 dpi
  with a tight bounding box, closes the figure, and returns the path. Closing
  matters: a script that makes a dozen figures without closing them will warn
  about too many open figures and hold onto the memory.

**Four colors, named once.** The module defines

```python
PASS_C, FAIL_C, NEUTRAL, ACCENT = "#2E7D32", "#C62828", "#37474F", "#1565C0"
```

and every function uses those names rather than literal hex strings. Green means
"meets the requirement", red means "violates it, or is the comparison series",
blue is the data itself, grey is a reference line. Keeping those meanings
consistent is the reason a reviewer can read your second figure without
re-reading the legend.

**Requirement lines are imported, never typed in.** The 2,500 ft circle, the
4,000–6,000 ft band and the 2.0 caliber line come from `slisim/requirements.py`
as `rq.MAX_DRIFT_FT`, `rq.APOGEE_MIN_FT` / `rq.APOGEE_MAX_FT` and
`rq.MIN_STABILITY_CAL`. If the handbook changes a limit, you edit one constant
and every figure, table and pass/fail check moves together. Do not paste the
number into a plot.

**Units convert at the plot boundary — and the two data sources differ.** This
is the most common mistake when editing these functions:

| Source | Units | What the plot must do |
|---|---|---|
| `res.series[...]`, the time histories from a nominal run | **SI** (`altitude_m`, `velocity_total_mps`) | Convert: `U.m_to_ft(s["altitude_m"])` |
| The Monte Carlo `DataFrame` | **already imperial** (`apogee_ft`, `drift_ft`, `landing_x_ft`) | Plot as-is |

That is why `plot_flight_profile` is full of `U.` calls and
`plot_apogee_distribution` has none. If a new figure comes out about 3.3 times
too large, you converted something that was already in feet.

**The `ok` mask.** Every Monte Carlo figure starts with

```python
ok = df[df.get("ok", True) == True]  # noqa: E712
```

A case that failed to simulate still gets a row, with `ok = False` and no
outputs, so that a crash in case 273 does not throw away the other 999. Plot
without the mask and those rows quietly distort the histogram. The `== True` is
deliberate — `is True` does not vectorize over a pandas Series — and the `noqa`
comment stops the linter objecting to it.

**Leave `matplotlib.use("Agg")` alone.** Near the top of `report.py` it selects
a non-interactive backend *before* `pyplot` is imported, which is the only order
that works. It is what lets the framework draw figures with no display attached:
over SSH, in CI, and inside the Monte Carlo worker processes. Remove it and the
scripts start trying to open windows. If you want to poke at a figure
interactively, do it in a separate session — see below — not by editing that
line.

## 5.5 Changing a figure

| What you want | What to edit |
|---|---|
| Fonts, grid, spines, tick sizes — everywhere | `_style()` |
| Resolution or file format — everywhere | `_save()` (`dpi=160`, and the extension in the `name` the script passes) |
| The color scheme — everywhere | The `PASS_C, FAIL_C, NEUTRAL, ACCENT` line |
| One figure's size, bins, limits, legend | That figure's own function |
| Which figures a run produces | The `report.plot_*` calls near the bottom of the script, plus the `Figures` section of its `write_markdown` call |

**Iterate on the CSV, not on the simulation.** Re-running 1,000 cases to find
out whether you like a bin count is a waste of an afternoon. Every Monte Carlo
run already wrote `montecarlo_*.csv` with every input and output in it, so
reload that and call the plotting functions directly:

```python
# scratch.py, run from the sim/ directory
from pathlib import Path
import pandas as pd
from slisim import analysis, report

out = Path("output")
df = pd.read_csv(out / "montecarlo_rocketpy_n1000_min.csv")

report.plot_apogee_distribution(df, out, 4500.0, "apogee_test.png")
report.plot_landing_scatter(df, out, analysis.landing_ellipse(df), "landing_test.png")
report.plot_sensitivity(analysis.sensitivity(df, "apogee_ft").head(12),
                        out, "apogee", "sensitivity_test.png")
```

That turns a two-minute edit-run-look cycle into a two-second one. Give the test
figures their own names so you do not overwrite the ones a real run produced.

**Adding a figure takes three steps.** Say you want max Mach dispersion against
the requirement 2.20.6 limit. First, write the function in `report.py` — copy
the nearest existing one and change step 2:

```python
def plot_mach_distribution(df: pd.DataFrame, out_dir: Path,
                           name: str = "mach_distribution.png") -> Path:
    """Max Mach against the req 2.20.6 limit."""
    ok = df[df.get("ok", True) == True]  # noqa: E712

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.hist(ok["max_mach"], bins=30, color=ACCENT, alpha=0.75,
            edgecolor="white", linewidth=0.5)
    ax.axvline(rq.MAX_MACH, color=FAIL_C, lw=1.6, ls="--",
               label=f"req 2.20.6 limit (Mach {rq.MAX_MACH:g})")

    _style(ax, f"Max Mach dispersion, N={len(ok)}", "Mach number (-)", "Cases")
    ax.legend(fontsize=8, frameon=False)
    return _save(fig, out_dir, name)
```

Second, call it from `scripts/run_montecarlo.py` alongside the other three:

```python
report.plot_mach_distribution(df, out_dir, f"mach_{tag}.png")
```

Third — the step people forget — add it to the `Figures` section of the
`write_markdown` call in the same script, or it will exist on disk and appear in
no report:

```python
f"![mach](mach_{tag}.png)"
```

**What to preserve when you change things.** These figures go in front of a
review panel, so some of the existing choices are not decoration:

- **Label the axes, with units.** "Apogee (ft AGL)", not "apogee". AGL versus
  MSL has cost teams real points.
- **Do not let color carry meaning on its own.** Reviewers print in greyscale,
  and some are colorblind. The existing figures always pair color with a line
  style, a marker, or a legend entry. Keep that.
- **Keep the requirement line on the plot.** A histogram of apogee without the
  4,000–6,000 ft band is a picture. With the band, it is evidence.
- **Say what N is.** The Monte Carlo titles carry `N=` and the pass fraction for
  a reason: a beautiful distribution built from 25 cases is not a result.
- **Commit the code, not the PNG.** `output/` is in `.gitignore` by
  design — figures are regenerable, and binary diffs tell a reviewer nothing.
  What belongs in git is the `report.py` change that makes the figure, so anyone
  on the team can reproduce it from the same seed months later.

---

# Part 6 — Troubleshooting

§6.0 covers errors that stop a script before any simulation starts — almost
always the terminal, the folder, or the environment rather than the
framework. §6.1 onward covers problems once it is running.

## 6.0 Environment errors

Before anything else, run the two checks from Part 0. Both are identical in
every shell:

```bash
ls scripts
python -c "import sys; print(sys.executable)"
```

The first should list the scripts (you are in the project folder); the second
should print a path inside `.venv` (the environment is active). Most errors
below are one of those two failing.

### `ModuleNotFoundError: No module named 'yaml'`

The same goes for `'rocketpy'`, `'numpy'`, `'jpype'`, or any other package.
`python` is your computer's own Python, not the project's, because the
environment is not active in this terminal. Activate it (§0.3) and run again:

PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Git Bash:

```bash
source .venv/Scripts/activate
```

If the prompt already shows `(.venv)` and the error persists, the environment's
packages are incomplete. Reinstall them (this is safe to repeat):

```bash
python -m pip install -r requirements.txt
```

In VS Code, check that `Python: Select Interpreter` points at `.venv`, then open
a *new* terminal with **+**. Terminals opened before the selection keep the old
Python.

### `ModuleNotFoundError: No module named 'slisim'`

The script cannot find the framework's own code. You are running a copy of the
script from somewhere else, or a script you wrote is outside `scripts/`. Run
the scripts in place, from the project folder: `python scripts/run_nominal.py`.

### `can't open file '...\scripts\run_nominal.py': [Errno 2] No such file or directory`

Wrong folder. Look at the path in the message: it shows where the terminal is,
and `scripts\` is not there. `cd` into the project folder (§0.2) and check with
`ls scripts`.

### `Activate.ps1 cannot be loaded because running scripts is disabled on this system`

PowerShell only: Windows blocks scripts by default. Allow ones you run yourself,
once per computer:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Or skip activation and type the full path, `.venv\Scripts\python`, in place of
`python`.

### `.venv\Scripts\Activate.ps1 is not recognized` / `.venv/Scripts/activate: No such file or directory`

Either you are not in the project folder (§0.2), or the command came from the
other shell's block. PowerShell activates with `Activate.ps1` and backslashes;
Git Bash uses `source` and `activate` with forward slashes. If you are in the
right folder and `.venv` is missing entirely, the environment was never created
on this computer — that is an installation step, in Setup Guide §2.4–2.6.

### `Python was not found; run without arguments to install from the Microsoft Store`

Windows' placeholder `python` answered because the environment is not active and
no system Python is on the PATH. Activate the environment (§0.3). Do **not**
install Python from the Store to make this go away — the framework needs the
environment's Python either way.

### Java not found, or `UnsupportedClassVersionError`

```
RuntimeError: No Java 17+ runtime found. OpenRocket 24.12 needs one.
```

The OpenRocket engine runs on Java 17 or newer. Check what the terminal finds
(identical in both shells):

```bash
java -version
```

If that fails or reports a version below 17, Java 17 is not installed or not on
the PATH. Install it (Setup Guide §2.4) and open a new terminal. If it reports
17 or newer but the framework still complains, an older Java is overriding it
through `JAVA_HOME`. Point `JAVA_HOME` at the Java that works, for this terminal:

PowerShell:

```powershell
$env:JAVA_HOME = (Get-Item (Get-Command java).Source).Directory.Parent.FullName
```

Git Bash:

```bash
export JAVA_HOME="$(cygpath -m "$(dirname "$(dirname "$(which java)")")")"
```

macOS / Linux:

```bash
export JAVA_HOME="$(dirname "$(dirname "$(which java)")")"
```

In Git Bash, the `cygpath -m` matters. It turns Git Bash's `/c/Program Files/...`
into `C:/Program Files/...`, the only form Windows programs like Python and Java
understand. Without it, `JAVA_HOME` looks right and silently does nothing. To
check what is set: `echo $env:JAVA_HOME` in PowerShell, `echo "$JAVA_HOME"` in
Git Bash.

Those last only for the current terminal. To make the setting permanent on
Windows:

```powershell
[Environment]::SetEnvironmentVariable("JAVA_HOME", $env:JAVA_HOME, "User")
```

On macOS or Linux, add the `export` line to `~/.zshrc` or `~/.bashrc`.

### `FileNotFoundError: OpenRocket jar not found`

The 80 MB OpenRocket engine in `vendor/` is not under git, so it is missing
from every fresh clone and every new computer. Downloading it is installation
step 5 in Setup Guide §2.4–2.6.

### The first run takes about 30 seconds

That is normal. Java starts, and OpenRocket loads its motor database and
component presets. Later flights in the same run take under a second, and a
Monte Carlo run pays the start-up once per worker process, not once per
flight.

### Still stuck

Problems with the installation itself — a broken environment, Python 3.14 build
errors, a download blocked by a corporate network — are in Setup Guide Part 3.
That includes how to rebuild the environment from scratch, which fixes most
things.

## 6.1 Monte Carlo cases fail

The script reports failures and the most common errors rather than crashing:

```
  WARNING: 7 of 500 cases failed to simulate
```

A handful of failures out of hundreds is usually a physically extreme sample
(near-zero wind combined with an extreme rail angle, for example). Many
failures means a dispersion is too wide or a configuration is wrong. Inspect
`montecarlo_*.csv` — failed rows carry an `error` column.

## 6.2 The simulation aborts immediately

Symptoms: apogee of 0, `Simulation abort` in the events list. Almost always the
motor is not attached to the flight configuration — check that `motor.search`
matches a real designation with `list_motors.py`, and that
`mount_inner_diameter_in` is large enough for the motor's actual diameter.

## 6.3 Parachutes deploy at apogee in RocketPy

If the main deploys immediately at apogee instead of at its set altitude, the
atmosphere model is degenerate. This is fixed in the framework
(`_isa_profiles()`), but if you modify `build_environment`, never pass a
*scalar* pressure to `custom_atmosphere` — it creates a constant-pressure
atmosphere, which makes barometric height meaningless and fires every
altitude-triggered parachute the moment the rocket noses over.

## 6.4 Descent rates from real altimeter data look absurd

If measured descent rates come out at 60+ fps under a large main, you are
differentiating noisy barometric data point-by-point. A few feet of baro noise
at 20 Hz is roughly 100 fps of noise in every finite difference. The framework
fits a straight line over each descent phase instead. Keep it that way.

---

# Part 7 — Command reference

Every script takes `--vehicle PATH` (default `config/vehicles/full_scale.yaml`)
and `--out DIR` (default `output/`). Output always lands under
`<out>/<vehicle>/`, so two vehicles never overwrite each other — see
[§5.0](#50-where-things-land).

### `run_nominal.py`

Nominal flight in both engines with full requirement checking.

| Flag | Default | Meaning |
|---|---|---|
| `--vehicle PATH` | `config/vehicles/full_scale.yaml` | Which vehicle to run |
| `--site KEY` | site file default | Launch site |
| `--ballast {min,max,both}` | `min` | Ballast configuration |
| `--skip-rocketpy` | off | OpenRocket only (faster) |
| `--out DIR` | `output/` | Output directory |

Exit code 0 if no requirement FAILs, 1 otherwise — usable in CI.

Besides the figures and the `.ork`, it writes `flight_states_<ballast>lb.csv`:
every simulated state at 100 Hz, from ignition to landing ([§1.7](#17-comparing-telemetry-to-the-model)).

### `compare_flight.py`

Overlays a flight computer's log on the simulation of that flight. See
[§1.7](#17-comparing-telemetry-to-the-model).

| Flag | Default | Meaning |
|---|---|---|
| `CSV` (positional) | required | The flight computer's CSV export |
| `--map FIELD=COLUMN` | auto-detected | Name the log column for a field; repeat as needed |
| `--ballast-lb X` | 0 | Ballast actually flown |
| `--wind`, `--wind-dir`, `--temp-f`, `--pressure-inhg`, `--rail-angle` | site nominal | Launch-day conditions, as for `fit_cd.py` |
| `--altitude-units {auto,ft,m}` | `auto` | Units of the log's altitude column |
| `--vehicle PATH`, `--site KEY`, `--out DIR` | | As above |

### `run_montecarlo.py`

| Flag | Default | Meaning |
|---|---|---|
| `-n, --samples N` | 500 | Number of cases |
| `--engine {rocketpy,openrocket}` | `rocketpy` | Which solver |
| `--ballast {min,max}` | `min` | Ballast configuration |
| `--seed N` | 12345 | Random seed — record this |
| `--workers N` | CPU count (max 8) | Parallel processes |
| `--only P1,P2` | all | Disperse only these parameters (§4.4) |
| `--freeze P1,P2` | none | Hold these parameters nominal (§4.4) |
| `--list-parameters` | off | Print the dispersible parameter names and exit |
| `--site KEY`, `--vehicle PATH`, `--out DIR` | | As above |

### `run_crossvalidate.py`

| Flag | Default | Meaning |
|---|---|---|
| `--mc N` | 0 | Also disperse N cases through *both* engines |
| `--ballast {min,max}`, `--seed`, `--workers` | | As above |

### `plot_inputs.py`

Draws `input_model.png`: every parameter the framework can disperse, in absolute
units. Runs no flights — a campaign draws all of its samples up front, so the
same seed regenerates them exactly. Seconds, plus a one-time JVM start to read
nominal mass, CG, and motor data from OpenRocket.

| Flag | Default | Meaning |
|---|---|---|
| `-n, --samples N` | 1000 | Draws per parameter |
| `--seed N` | 12345 | Pass a campaign's seed to plot the values it flew |
| `--engine {rocketpy,openrocket}` | `rocketpy` | `openrocket` shows only its six launch conditions |
| `--name FILE` | `input_model.png` | Output filename |
| `--ballast {min,max}`, `--site KEY`, `--vehicle PATH`, `--out DIR` | | As above |

### `check_plot_inputs.py`

No flags. Flies 20 cases and asserts `plot_inputs.py` regenerates their inputs
bit-for-bit. Both draw through `montecarlo.draw_samples`, so this checks that a
campaign flies exactly what that function returns. Run it after changing
`draw_sample`, `draw_samples`, or how `run_montecarlo` hands samples to its
workers. Exits non-zero if they diverge.

### `check_mass_csv.py`

No flags. Recomputes every derived cell of every worksheet in `config/mass/`,
checks the mass model the simulation flies against each sheet's totals, and
checks that per-part draws scatter by the sigmas asked for. Run it after any
worksheet edit (§2.10). Exits non-zero on any problem.

### `check_landing_partition.py`

No flags. For every vehicle file: the landing sections must account for the
whole structure exactly once, no piece may weigh zero or less, and the spent
motor case must land in exactly one piece.

### `check_against_ork.py`

| Flag | Default | Meaning |
|---|---|---|
| `--vehicle PATH` | required | The vehicle yaml to check |
| `--ork PATH` | required | The OpenRocket file it was transcribed from |
| `--ballast {min,max}` | `min` | Ballast configuration |
| `--mach X` | 0.3 | Evaluation Mach, matching the GUI convention |

Compares overall length, launch mass, CP and CG. Exit code 0 if every delta is
inside tolerance, 1 otherwise. See [§2.9](#29-from-an-openrocket-design-to-a-vehicle-file).

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
| `--out PATH` | `data/flights/synthetic_vdf.csv` | The altimeter file; `synthetic_telemetry.csv` is written beside it |

Writes two files: an altimeter-only CSV for `fit_cd.py`, and a full telemetry
log (barometric altitude, IMU, GPS) for `compare_flight.py`.

---

# Appendix A — Cheat sheet

Start every session (Part 0). In VS Code with `.venv` selected, the first two
lines happen on their own; just look for `(.venv)` in the prompt.

PowerShell:

```powershell
cd C:\Users\you\nasa-sli-sim                      # the project folder
.venv\Scripts\Activate.ps1                        # prompt shows (.venv)
```

Git Bash (macOS/Linux: `source .venv/bin/activate`):

```bash
cd /c/Users/you/nasa-sli-sim                      # the project folder
source .venv/Scripts/activate                     # prompt shows (.venv)
```

Everything below is identical in both shells once `(.venv)` shows:

```bash
# Check the session (§6.0 if either looks wrong)
ls scripts                                        # in the project folder?
python -c "import sys; print(sys.executable)"     # path inside .venv?

# Git (§0.4)
git pull                                          # before you start
git status                                        # what have I changed
git add config/vehicles/full_scale.yaml           # choose what to save
git commit -m "why this change"
git push                                          # when you stop

# Daily use
python scripts/run_nominal.py --ballast both      # design check
python scripts/list_motors.py --nasa              # pick a motor
python scripts/run_montecarlo.py -n 1000          # dispersion
python scripts/plot_inputs.py                     # the uncertainty model
python scripts/run_crossvalidate.py               # report table
python scripts/fit_cd.py data/flights/vdf.csv --wind 11 --temp-f 64
python scripts/compare_flight.py data/flights/vdf.csv --wind 11 --temp-f 64

# Pick a vehicle (default: full_scale.yaml)
python scripts/run_nominal.py --vehicle config/vehicles/subscale.yaml

# Files you edit
config/vehicles/*.yaml    the rockets, one file each
config/sites.yaml         where you fly
config/uncertainty.yaml   what you don't know

# Files you read
output/<vehicle>/nominal/            design check
output/<vehicle>/mc/latest/          newest Monte Carlo
output/<vehicle>/crossvalidation/    engine comparison
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
| **Commit** | One snapshot in the project's history, with a message saying why. |
| **Staging** | The set of changes you have chosen to put in the next commit (`git add`). |
| **Branch** | A separate line of work. `main` is the shared one and should always run. |
| **Remote / origin** | The shared copy on GitHub. `origin` is its default name. |
| **Pull / push** | Bring the remote's commits down; send yours up. |
| **JVM / JDK** | Java Virtual Machine / Java Development Kit. OpenRocket is a Java program. |
| **VDF / PDF** | Vehicle / Payload Demonstration Flight. |

---

*Framework verified on Python 3.13.15, RocketPy 1.13.0, OpenRocket 24.12,
Microsoft OpenJDK 17.0.20. Physics background: [`FLIGHT_DYNAMICS.md`](FLIGHT_DYNAMICS.md).*
