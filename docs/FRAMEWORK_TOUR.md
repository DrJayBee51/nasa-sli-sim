# Framework Tour

**NASA Student Launch — Dual-Engine Simulation Framework**
A guided tour of how the code is put together, for the people who will use it.

This is not a reading assignment. Each stop follows the same pattern:

> **Read** a small piece of the code · **Run** something · **Predict** what a
> change will do · **Change** it and find out · **Answer** the question.

Every question has an answer you can check by running the framework, and the
last stop ends with a real contribution committed to the repository.

Budget about two sessions. Work in pairs if you can — predicting out loud
before you run something is most of the value.

**Before you start:** finish the [Setup Guide](SETUP_GUIDE.md) and confirm that
`run_nominal.py` prints `15 pass, 1 warn, 0 FAIL`. Several stops have you break
the code on purpose; `git restore <file>` puts it back. Never commit a
deliberate breakage.

The [User Guide](USER_GUIDE.md) explains how to *operate* the framework, and
[`FLIGHT_DYNAMICS.md`](FLIGHT_DYNAMICS.md) explains the *physics* it implements.
This document explains the *structure*.

---

## Stop 0 — The map

Everything flows from one file:

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

| File | Its one job |
|---|---|
| `config.py` | Read the YAML, convert to SI once, do the mass bookkeeping |
| `units.py` | Imperial ↔ SI, in exactly one place |
| `or_bridge.py` | Build and fly the rocket inside OpenRocket's real Java engine |
| `rocketpy_model.py` | Build and fly the same rocket in RocketPy |
| `requirements.py` | Every USLI check, each citing its handbook paragraph |
| `montecarlo.py` | Sample the uncertainties, run the cases in parallel |
| `analysis.py` | Statistics, compliance probabilities, sensitivity |
| `postflight.py` | Fit drag to real altimeter data after a flight |
| `report.py` | Figures and tables sized for a design review |

Scripts in `scripts/` are thin: they parse arguments, call the library, and
print. Read `scripts/run_nominal.py` end to end right now — it is about 100
lines and it names every stage of the pipeline you are about to walk through.

**Answer this:** which of the files above would you have to change to add a new
requirement check? Which would you *not*?

---

## Stop 1 — One file, two models

**Read:** `config/vehicle.yaml`, then in `config.py` the methods
`landing_section_masses_kg`, `recovery_mass_kg`, and `unassigned_members`.
Then read `check_mass_closure` in `requirements.py`.

The framework insists that section masses, parachutes, shock cord, propellant,
and the motor case add up *exactly* to the simulated lift-off mass. The FRR
requires that bookkeeping, so the framework fails the run rather than let it
drift.

**Run:**

```bash
python scripts/run_nominal.py
```

Find the `FRR-V  Mass budget closure` line. It should read `0.00 lb`.

**Predict, then change:** in `vehicle.yaml`, remove `"fins"` from the members
of the second landing section. Does anything fail? What is reported, and by
which check?

Put it back, then try instead adding 0.5 lb to the Payload Bay section mass and
re-run. Which numbers moved, and why did the mass budget still close?

**Answer this:** the `landing_sections` block does not describe any physical
part of the rocket. Why does the framework need it, and which requirement is
unsatisfiable without it?

---

## Stop 2 — Crossing into Java

OpenRocket is a Java program. `or_bridge.py` starts a JVM inside Python and
builds the rocket by calling OpenRocket's own classes, so the numbers come from
the same engine you use in the GUI rather than a re-implementation of it.

**Read:** `build_document` in `or_bridge.py`. Skip the JPype mechanics on a
first pass and just follow the order: nose cone, body tubes, fins, rail
buttons, motor mount, parachutes, shock cord, flight configuration, motor.

**Run** `run_nominal.py`, then open the `.ork` it wrote in `output/` with the
OpenRocket GUI.

**Answer this:** find each component from `build_document` in the GUI's
component tree. Two of them have their mass overridden to zero. Which two, and
what would happen to the mass budget from Stop 1 if they were not?

---

## Stop 3 — The same rocket, twice

**Read:** the header comment of `rocketpy_model.py`, especially the list of
what is shared between the two tools and what is not. Then read §1.4 of the
[Setup Guide](SETUP_GUIDE.md#14-what-is-genuinely-independent--read-this-before-writing-a-report).

**Run:**

```bash
python scripts/run_crossvalidate.py
```

Read `output/crossvalidation.md`, including the discussion of every difference
over 5%.

**Answer these:**

1. Apogee agrees between the two tools to about 0.1%. Explain why that is *not*
   evidence that the drag estimate is correct.
2. Rail exit velocity differs by about 10%. Which tool would you quote for
   requirement 2.14, and why is that the conservative choice?
3. A reviewer asks: "What did your second calculation method actually verify?"
   Write a two-sentence answer you would be willing to defend.

---

## Stop 4 — Four ways to be confidently wrong

This is the most important hour in the tour. Each change below is one line, and
each produces a result that *looks* fine and is not. Predict the effect before
you run. Revert with `git restore` afterward.

| # | The change | Where |
|---|---|---|
| 1 | Give the motor a numeric ejection delay instead of `PLUGGED_DELAY` (try `2.0`) | `or_bridge.build_document` |
| 2 | Pass a scalar pressure to RocketPy: replace `pressure=pressure` with `pressure=101325.0` | `rocketpy_model.build_environment` |
| 3 | Set the wind turbulence default to `0.1` instead of `0.0`, then run twice | `or_bridge.make_simulation` |
| 4 | Stop overriding the rail buttons and motor mount to zero mass | `or_bridge.build_document` |

For each one, record: what changed in the output, whether any requirement check
caught it, and how you would have noticed if nobody had told you.

**Answer this:** rank the four by how dangerous they are, where "dangerous"
means *how far a report could get before anyone noticed*. Which one would
survive all the way into an FRR?

---

## Stop 5 — From one flight to a probability

A single simulation answers "what happens if everything is nominal", which is
the one case that never occurs.

**Read:** `draw_sample` and `_draw_one` in `montecarlo.py`, then `compliance`
and `sensitivity` in `analysis.py`. Note that sampled *inputs* are stored in
each row with an `in_` prefix, which is how `sensitivity` finds them.

**Run:**

```bash
python scripts/run_montecarlo.py -n 200
python scripts/run_montecarlo.py -n 1000
```

**Answer these:**

1. Compare the two sensitivity rankings. Which entries are stable and which
   move? What does that imply about quoting a sensitivity from a 200-case run?
2. `_draw_one` *resamples* out-of-bounds draws instead of clipping them. What
   would clipping do to the tails, and why does that matter for a requirement
   margin?
3. Set `drag_coefficient.sigma` in `uncertainty.yaml` from `0.070` to `0.030`,
   which is roughly what a post-flight drag fit buys you. Predict what happens
   to P(apogee in window) and to the 5th–95th band, then run 1,000 cases and
   check. Put the sigma back afterward.

---

## Stop 6 — Write a real check

The Monte Carlo reports a probability of compliance for nine requirements. One
that it does *not* report is **3.1.1, the 500 ft main-deployment floor** — even
though `uncertainty.yaml` disperses the deploy altitude by 25 ft, so the
framework has the data and just never uses it. This is a genuine gap, and you
are going to close it.

**Where:** `compliance()` in `analysis.py`, alongside the existing `add(...)`
calls.

**What you need:**

- The nominal deploy altitude, from `vehicle.main["deploy_altitude_m"]`,
  converted with `U.m_to_ft`.
- The per-case shift, in the `in_main_deploy_altitude_ft` column. It is a
  *shift* about the nominal, not the altitude itself.
- The limit, `rq.MIN_MAIN_DEPLOY_FT` — never a bare `500.0`.

**Verify it:** with the template's 600 ft nominal and a 25 ft sigma, you should
get `P(pass) = 1.000`. That is the correct answer, and it is worth having:
"stated and shown to be safe" beats "assumed". To prove your check actually
bites, temporarily set `deploy_altitude_ft` to `520.0` and re-run. Roughly what
fraction should fail? Work it out from the sigma before you look.

Put the deploy altitude back to 600 ft, and commit the check.

**Then answer:** the same argument applies to requirement 3.1.2, the 2-second
apogee-event delay, which is also dispersed and also unreported. Should it be
added? Make the case either way.

---

## Where to go next

Each of these is a real season deliverable, owned end to end by one person:

| Piece | What it involves |
|---|---|
| **Launch sites** | Add your home field to `sites.yaml` with wind statistics from historical weather data, not guesses |
| **The sigmas** | Replace each placeholder in `uncertainty.yaml` with a justified number, and write down the justification |
| **The verification matrix** | Check all 15 coded limits against the handbook independently. If the code and the handbook disagree, the code is wrong |
| **Post-flight rehearsal** | Run the whole `make_synthetic_flight.py` → `fit_cd.py` pipeline before the subscale flight, so the FRR analysis is not the first attempt |

---

## Mentor notes — expected observations

Brief answers for checking work. Students get more out of predicting first.

- **Stop 1.** Dropping `"fins"` leaves the fin mass unassigned: the mass budget
  no longer closes, `FRR-V` FAILs, and the note names the unassigned member.
  Adding 0.5 lb to a section moves apogee, kinetic energy, and lift-off mass,
  but the budget still closes because the same section total feeds both the
  model and the bookkeeping.
- **Stop 2.** The rail buttons and the motor mount are zeroed, because section
  masses in the YAML are as-built and already include them. Leaving them
  material-derived double-counts and breaks closure.
- **Stop 4.** Trap 1 fires an ejection charge at burnout and invalidates the
  descent, while apogee still looks plausible — this is the one that reaches an
  FRR. Trap 2 makes barometric height degenerate, so the main fires at apogee;
  descent time and drift change enough to notice. Trap 3 makes drift wander by
  several percent between identical runs, and no check catches it. Trap 4 is
  caught immediately by `FRR-V`.
- **Stop 5.** Motor impulse and drag stay at the top; the smaller terms
  reshuffle, and `temperature_k` in particular is unstable at 200 cases.
  Halving the drag sigma noticeably narrows the 5th–95th band.
- **Stop 6.** At 520 ft nominal with a 25 ft sigma, 500 ft is 0.8σ below the
  mean, so roughly 20% of cases should fail.
