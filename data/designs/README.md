# OpenRocket design files

The `.ork` files a vehicle in `config/vehicles/` was transcribed from.

These are **version-controlled on purpose.** The framework runs
`vehicle.yaml` → `.ork`, but a real design starts in the OpenRocket GUI and gets
transcribed the other way (USER_GUIDE §2.9), so the GUI file is the upstream
source for every mass and dimension in the yaml. Keeping it here means:

- `scripts/check_against_ork.py` can verify the transcription on any machine,
  rather than only on the laptop that happens to hold the file.
- `scripts/ork_to_mass_csv.py` can regenerate the mass worksheet.
- `git log data/designs/` answers "what did this rocket look like at CDR".

An `.ork` is a zip of one XML file, a few KB, and it diffs about as well as any
other binary — which is to say not at all, so the commit message has to say what
changed and why.

## Keep one copy

Edit the file **here**, in the repo. A second copy outside it is the failure this
directory exists to prevent: you fix a mass in one, regenerate the worksheet from
the other, and nothing reports a problem because each file is internally
consistent.

## Current designs

| File | Vehicle | Notes |
|---|---|---|
| `Fullscale_Model_A.ork` | `config/vehicles/fullscale_model_a.yaml` | 4 motor configs; `K1800ST-P` is the default and the one the yaml uses |

After editing one, re-run both:

```bash
python scripts/ork_to_mass_csv.py \
    --ork data/designs/Fullscale_Model_A.ork \
    --out config/mass/fullscale_model_a.csv
python scripts/check_against_ork.py \
    --vehicle config/vehicles/fullscale_model_a.yaml \
    --ork data/designs/Fullscale_Model_A.ork
```

The first prints the `mass_lb` / `cg_*_in` values to paste into the yaml. The
second is what tells you the transcription still holds.
