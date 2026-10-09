# Handoff notes

Session notes for continuing on another machine. Delete this file when the
branch lands on `main`; anything permanent belongs in `docs/USER_GUIDE.md`.

Branch: `mass-properties-model-a`

## Setting up a new machine

`.venv/` and `vendor/*.jar` are gitignored. Follow
[docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md), then check:

```bash
python scripts/check_mass_csv.py          # model_a passes; full_scale.csv fails (see below)
python scripts/check_landing_partition.py # all pass
python scripts/run_nominal.py --vehicle config/vehicles/fullscale_model_a.yaml
```

The nominal run should give **18 pass, 0 warn, 0 FAIL**, apogee 4,666 ft, mass
budget 25.357 lb. It takes a few minutes.

## Where things stand

**The CSV is the source of truth for mass properties.** The Model A yaml has
`mass_properties: fullscale_model_a.csv` and holds only shapes, the motor,
recovery hardware and decisions. `slisim/config.py` (`_apply_mass_sheet`) reads
the sheet and fills in the yaml keys, so the OpenRocket and RocketPy code are
unchanged. A value present in both files is an error.

**Sheet layout** (`slisim/massprops.py`, checked by `scripts/check_mass_csv.py`):

- One row per part. Position is measured from the front of its own section;
  `from_nose_tip_in` is derived.
- `kind` is what the part counts toward: structure, tethered, fins, main, drogue,
  shock_cord. `section` is the tube it physically sits in.
- A `SECTION` row closes each section with its length and totals. An `AGGREGATE`
  block combines the sections. No comment header.
- Inertia columns: the part's own pitch and roll inertia about its own CG, in
  lb·in², from SolidWorks "taken at the center of mass" (pitch = Lyy, roll = Lxx,
  X along the rocket axis). Totals use the parallel-axis theorem.
- Sigma columns: `mass_sigma_pct`, `position_sigma_in`, `inertia_sigma_pct`.
  Required on every row; 0 means exact.
- Model A's inertia comes from OpenRocket for now (sums to its vehicle total).
  **All sigmas are 0** until the team sets them.

## Next: per-part dispersion for RocketPy Monte Carlo

Agreed design, not yet built:

1. Each case draws every part's mass, position and inertia from its sigmas.
2. Aggregate: m = Σmᵢ, x_cg = Σmᵢxᵢ/m, pitch = Σ(Iᵢ + mᵢ(xᵢ − x_cg)²),
   roll = ΣI_roll,i. Pass these to RocketPy (`mass`,
   `center_of_mass_without_motor`, `inertia`).
3. Landing-piece masses for req 3.2 come from the same draws.
4. `uncertainty.yaml`: keep `dry_mass` as a system multiplier, sigma 0 (no
   effect) by default. Remove `cg_shift`. Motor dispersions stay in the yaml.
5. Warn when every sigma is 0, so a campaign with no mass dispersion isn't
   mistaken for a real one.
6. Nominal RocketPy uses the CSV inertia. Show the CSV-vs-OpenRocket inertia
   comparison in `scripts/run_crossvalidate.py`.

OpenRocket only matters for the nominal run; it doesn't need to disperse mass.
Changing the sampling will change what old seeds produce; `plot_inputs.py` and
`check_plot_inputs.py` copy the sampling loop and need updating with it.

Work in small steps and pause for review after each.

## Other open items

- `config/mass/full_scale.csv` (the placeholder template) is still in the old
  format and fails `check_mass_csv.py`. Convert it and point `full_scale.yaml` at it.
- `scripts/ork_to_mass_csv.py` still writes the old format. Only needed until the
  subscale flies.
- User Guide section describing the CSV, including `internal_bodies` / tethered
  parts.
- Subscale similarity check: one scale factor k on all outer geometry and the CG
  station, so static margin in calibers matches. Not started; waiting on more
  detail from the user. Extend `requirements.check_subscale_scale()` and
  `Vehicle.scale_reference()`.
- Main parachute opens at about 88 fps (OpenRocket flags it in the `.ork`).
- Model A ballast and `target_apogee_ft` are placeholders.
- A second copy of the `.ork` sits at `A:\ModelRocketry\Fullscale_Model_A.ork`,
  outside the repo. The in-repo `data/designs/` copy is the one to edit.
