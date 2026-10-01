# Handoff notes — mass properties worksheet, Model A, tethered landing bodies

Working notes for picking this up on another machine. **Delete this file when the
work lands on `main`** — it is a session note, not documentation. Anything here
that turns out to be permanent belongs in `docs/USER_GUIDE.md` instead.

Branch: `mass-properties-model-a`

---

## First, on the new machine

`.venv/` and `vendor/*.jar` are **gitignored**, so cloning this branch does not
give you a runnable project. Redo [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md) —
Python 3.12/3.13 venv, `pip install -r requirements.txt`, a Java 17+ JDK, and the
OpenRocket jar into `vendor/`. Then confirm all four checks pass:

```bash
python scripts/check_mass_csv.py
python scripts/check_landing_partition.py
python scripts/check_against_ork.py \
    --vehicle config/vehicles/fullscale_model_a.yaml \
    --ork data/designs/Fullscale_Model_A.ork
python scripts/run_nominal.py --vehicle config/vehicles/fullscale_model_a.yaml
```

Expected: worksheets pass; partition passes (2 and 4 landing sections);
transcription within tolerance (length/mass/CP exact, CG +0.09 in, margin 2.23 vs
2.25); nominal **18 pass, 0 warn, 0 FAIL** at 4,666 ft.

`run_nominal.py` takes over two minutes — JVM start plus both engines.

---

## What landed

| File | What it is |
|---|---|
| `config/mass/full_scale.csv` | Worksheet for the shipped placeholder template. Hand-authored worked example. |
| `config/mass/fullscale_model_a.csv` | Worksheet for Model A, 22 parts. **Generated** — do not hand-edit. |
| `config/vehicles/fullscale_model_a.yaml` | Model A, transcribed from the `.ork`, `K1800ST-P` config. |
| `data/designs/Fullscale_Model_A.ork` | The design itself, now in-repo (see below). |
| `scripts/ork_to_mass_csv.py` | Generates a worksheet from any `.ork`; prints the yaml values to paste. |
| `scripts/check_mass_csv.py` | Recomputes every derived cell in every worksheet. |
| `scripts/check_landing_partition.py` | Guards the `internal_bodies` mass subtraction. |
| `slisim/config.py` | **Only changed source file.** Adds the `internal_bodies` block. |

### The `.ork` moved into the repo

It was at `A:\ModelRocketry\Fullscale_Model_A.ork`, outside the repo, referenced
as `../Fullscale_Model_A.ork`. That would not have survived the machine switch.
It is now `data/designs/Fullscale_Model_A.ork` and the original is untouched.

**Edit the in-repo copy from now on.** Two copies is the failure mode
`data/designs/README.md` warns about: fix a mass in one, regenerate the worksheet
from the other, and nothing reports a problem because each file is internally
consistent on its own.

---

## Design decisions worth not re-litigating

**Worksheet layout.** Per-section part rows, a `SUBTOTAL` row closing each
section, then an `AGGREGATE` block combining the subtotals. A `SUBTOTAL` row's
station column holds that section's **CG**, which makes the aggregate table the
identical Σm / Σ(m·x) arithmetic one level up.

**Derived columns are stored, not computed on read.** `moment_lb_in` and the
totals are in the file so the arithmetic is readable. That is only safe because
`check_mass_csv.py` recomputes all of it — run it after any hand edit.

**Rounding is half-up, and totals sum the printed values.** The column adds up
exactly as it reads. Mass and moment carry 3 decimals because a rail button is
0.002 lb. Python's `round` is banker's rounding and gives 26.32 where a
spreadsheet gives 26.33, hence `Decimal(ROUND_HALF_UP)`.

**`station_in` is from the nose tip, one datum for the whole vehicle** — not
per-bay. Reads straight off OpenRocket's component analysis. The loader derives
each bay's front station from the yaml lengths.

**`source` is read from the `.ork`, not hand-maintained:** `override` (a human
typed it — a mass override, or a `MassComponent` whose mass *is* its definition),
`ork` (computed from material density), `CONFIRM` (the component's GUI comment
contains placeholder/CONFIRM/TBD/guess/estimate). Currently 4 `override`, 18
`ork`.

Marking a placeholder goes in the **OpenRocket comment field**, not the CSV — a
hand edit to the CSV gets overwritten on regeneration, a GUI comment does not.
**The 6 lb Payload is a placeholder and is not yet marked;** add "placeholder" to
that component's comment in the GUI and it will come through as `CONFIRM`.

**`internal_bodies` does not touch the flight model.** A tethered body's mass is
already inside its parent section's as-built `mass_lb`, so declaring it moves mass
between landing pieces — same launch mass, same CG, same trajectory. Only req 3.2
sees it.

**`overhang_in: 1.0` on the motor is physical, not a fudge.** The `.ork`'s motor
tube runs 54.0–70.0 in, protruding 1.0 in past the airframe aft end at 69.0. The
framework always seats the mount flush, but the mount's mass is overridden to
zero, so only the motor's station moves CG. At 0.0 the model reads 2.27 cal
against the true 2.25 — *overstating* margin on a scored requirement. At 1.0 it
reads 2.23: still 0.02 off, but low. **Do not tune this to zero the error** — the
residual is the boattail mass sitting at its midpoint (the schema carries no CG
for a transition) plus rounding.

---

## Two bugs found, for the record

**`getMass()` on a fin set already covers every fin.** Multiplying by
`getComponentLocations()` count inflated the 4-fin set 4× (2.164 vs 0.541 lb).
The unmultiplied sum matches `MassCalculator.calculateStructure` exactly at
19.247 lb — always cross-check against that, not against hand arithmetic.

**The generator computed moments at full precision while printing rounded mass
and station,** so the column did not add up as it read. `check_mass_csv.py`
caught every affected row in both files. Round first, then multiply.

---

## Open: the subscale — THIS IS WHERE WE STOPPED

**Nothing is implemented. No `subscale.yaml` exists yet.**

The requirement stated so far: *the outer vehicle geometry and the CG location
must be scaled identically.* That is geometric **similarity**, not merely a size
bound — one scale factor k applied to every external dimension (overall length,
diameter, nose length, fin root/tip/sweep/span, boattail), plus the CG station
from the nose tip scaling by that same k.

Why the pairing matters: CP is purely geometric under Barrowman, so it scales
with k on its own. Pin CG to the same k and the **static margin in calibers comes
out identical** between the two vehicles — which is what makes the subscale flight
evidence about the full-scale's stability rather than a loosely related data
point. Equivalently, CG as a fraction of length is preserved.

Known limits to state in any such check: mass goes as k³ only if construction and
density match, which in practice they do not (subscales come out relatively
heavy), and Reynolds number does not scale at all, so Cd differs regardless of how
good the geometry match is.

This is a **materially stronger check than req 2.16**, which only bounds overall
length and diameter at ≤75% and says nothing about similarity. The 75% bound falls
out as k ≤ 0.75. Existing code to extend, not duplicate:
`requirements.check_subscale_scale()` and `config.Vehicle.scale_reference()`
(which already resolves a `scales_from:` filename).

**Next step: resume the elaboration — more detail was coming when we broke off.**

---

## Other open items

1. **Worksheet wiring is undecided.** The worksheets are not read by anything
   yet; the yaml carries the numbers, and `ork_to_mass_csv.py` prints them to
   paste. The proposal on the table was: the loader rolls up the CSV and replaces
   `mass_lb` / `cg_from_front_in`, deriving each bay's front station from the yaml
   lengths and skipping `SUBTOTAL` / `AGGREGATE` rows. Worth deciding before the
   yaml and the CSV drift.
2. **`internal_bodies` is undocumented.** USER_GUIDE §2.7 covers
   `landing_sections` but not this. Real debt in a repo this heavily documented.
3. **The main opens at ~88.5 fps** — an 18 in drogue gives an 88.6 fps descent
   rate and the main deploys at 600 ft into that. OpenRocket flags
   `HighSpeedDeployment` in the `.ork`'s own saved simulation ("86.3 ft/s", Main
   Parachute). No handbook requirement checks it. **Biggest real risk on the
   design** — an 84 in canopy opening at that speed is a zipper/shred concern.
4. **Ballast and `target_apogee_ft` are placeholders.** No ballast is modeled
   (`--ballast both` is a no-op until `max_lb` is set; the 10% ceiling is 1.92 lb
   of 19.25 lb). `target_apogee_ft: 4670.0` is the nominal at Bragg Farms, *not* a
   declaration — re-declare from a Monte Carlo median before CDR.
5. **Stability spread is 4.4%** between engines (OR 2.23, RocketPy 2.33), just
   under the 5% that forces a written explanation in the cross-validation report.
6. **`full_scale.yaml` is still the default vehicle**, so a bare
   `run_nominal.py` flies the placeholder template, not Model A.

### Closed

- **The NASA motor list is a suggestion, not a constraint.** `K1800ST-P` not
  carrying a `*` in `list_motors.py` is informational. No req 2.7 check exists or
  is needed.
- **The nose cone keeps its bulkhead** (0.215 lb), giving `nose_cone` 1.487 lb.
  Its shock cord stays in `shock_cord`, since the FRR has you subtract recovery
  components from landing mass.

---

## Model A, as simulated

4,666 ft at Bragg Farms, both engines within 0.1%. Launch 25.36 lb, structure
19.247 lb, CG 34.16 in, margin 2.23 cal. 18 pass, 0 warn, 0 FAIL.

Four independent landing bodies, all passing req 3.2 **even on the conservative
drift-inclusive basis** — worst case 44.6 against the 75 limit:

| Body | Mass | KE vertical | KE with drift |
|---|---|---|---|
| Nose Cone | 1.49 lb | 5.14 | 10.2 |
| Payload (tethered) | 6.00 lb | 20.76 | 41.1 |
| Payload Airframe | 6.51 lb | 22.53 | 44.6 |
| Booster + Boattail | 3.41 lb | 11.80 | 23.4 |

Before splitting the payload out, nose+payload was a single 14.00 lb piece at
48.4 ft·lbf vertical and **95.9 with drift — over the limit.** The four-body
tethered architecture is what buys req 3.2 its margin, which is worth raising in
a review rather than waiting to be asked.
