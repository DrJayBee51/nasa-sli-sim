# Setup Guide

**NASA Student Launch — Dual-Engine Simulation Framework**
Season 2026–2027 · College/University (USLI) ruleset

This guide takes you from a laptop with nothing installed to a working,
verified installation of the simulation framework. It assumes no prior
experience with Python virtual environments, Java, or either simulation tool.
Every command is written out in full for Windows, macOS, and Linux.

Read Part 1 once — it explains what the framework does and why. Part 2 installs
everything and ends with a check that confirms it works. If anything goes wrong
along the way, Part 3 covers the common problems.

Running analyses — defining your vehicle, Monte Carlo dispersion, and reading
the output — is covered in a separate User Guide. The companion document,
[`FLIGHT_DYNAMICS.md`](FLIGHT_DYNAMICS.md), explains the physics behind
everything here.

---

## Before you start: this is a command-line tool

The framework has no app window or buttons. You run it by typing commands into
a **terminal**: a text window where you type a command, press Enter, and read
the text it prints back. Every command in these guides is written out in full,
so you can copy and paste them.

- **Which terminal:** the one built into VS Code is the easiest, because the
  file tree, the code, and the commands then share a single window
  ([§2.6](#26-visual-studio-code-recommended)). Outside VS Code, use PowerShell
  on Windows (Git Bash also works; see [§2.3](#23-windows)), or Terminal on
  macOS and Linux. The commands are identical either way.
- **Run everything from the project folder**, the one you clone in
  [§2.2](#22-get-the-project-files). Commands like `scripts/run_nominal.py`
  only work when the terminal is in that folder. Move there with `cd` at the
  start of each session. The prompt shows which folder you are in.
- **Results are files.** Besides the text in the terminal, each run saves
  figures (`.png`), report-ready tables (`.md`), raw data (`.csv`), and
  OpenRocket files (`.ork`) in `output/`. Open them like any other file. No
  plot windows pop up.
- **You still design in OpenRocket.** The framework runs OpenRocket's engine in
  the background. The OpenRocket app is where you do design work and where you
  open the `.ork` files the framework writes.

---

## Table of contents

- [Part 1 — What this is and why](#part-1--what-this-is-and-why)
- [Part 2 — Installation](#part-2--installation)
- [Part 3 — Troubleshooting the installation](#part-3--troubleshooting-the-installation)
- [Appendix — Glossary](#appendix--glossary)

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

## 1.3 How the framework is organized

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
about the rocket's mass, that would be a bug in the framework, not a modeling
choice.

## 1.4 What is genuinely independent — read this before writing a report

This matters more than it sounds. Claiming your two tools independently
validate each other, when they share inputs, is a claim a sharp reviewer can
dismantle.

| Quantity | Independent? | Why |
|---|---|---|
| Flight dynamics integration | **Yes** | RocketPy: 6-DOF, LSODA. OpenRocket: 6-DOF, RK4 |
| Center of pressure / normal force | **Yes** | Each runs its own Barrowman-family model over its own geometry |
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
Vehicle Demonstration Flight." Then do exactly that with `fit_cd.py`, which the
User Guide covers in its season workflow.

This is not a limitation to hide. It is the correct scope of the claim, and
stating it precisely is worth more in a review than overstating it.

---

# Part 2 — Installation

## 2.1 What you are installing, and why

| Component | Why it is needed |
|---|---|
| **Git** | Gets the project onto your machine, and is how you pull the team's changes and share your own. |
| **Python 3.12 or 3.13** | Runs the framework. **Not 3.14** — RocketPy's dependency stack does not yet have complete wheels for it. |
| **A virtual environment** (venv) | An isolated folder of Python packages, so this project's pinned versions cannot break other Python work on your machine, and so everyone on the team has identical versions. |
| **Java JDK 17 or newer** | OpenRocket is a Java program. The framework runs its real solver headlessly, so a Java runtime must be present. You do not write any Java. |
| **`OpenRocket-24.12.jar`** | The OpenRocket engine itself, ~80 MB. Not committed to the repository because of its size. |
| **Visual Studio Code** (recommended) | An editor with a built-in terminal, so the file tree, the code, and the commands share one window. Also gives you a debugger and YAML validation. |
| **OpenRocket GUI** (optional but recommended) | For opening the `.ork` files the framework generates, and for ordinary design work. |

A note on why a *JDK* rather than just a JRE: modern OpenRocket distributions
bundle a private runtime that the framework cannot reliably locate, so
installing a JDK is the dependable route.

## 2.2 Get the project files

The project lives in a Git repository. Cloning it, rather than copying a
folder, means you can pull the team's changes and share your own.

**Install Git** if you do not have it:

```powershell
winget install --id Git.Git                  # Windows
```
```bash
brew install git                             # macOS
sudo apt install git                         # Debian / Ubuntu
```

Check it with `git --version`.

**Clone the repository** into wherever you keep projects:

```bash
git clone https://github.com/DrJayBee51/nasa-sli-sim.git
cd nasa-sli-sim
```

Everything from here on happens inside that folder. `ls` (or `dir`) should show
`config/`, `slisim/`, `scripts/`, `docs/`, and `requirements.txt`.

> **Never copy a `.venv` folder from another computer.** It records the exact
> path of the Python that created it, so a copied one fails in confusing ways.
> Each machine builds its own in the steps below — that is why `.venv/` is in
> `.gitignore`.

Two folders are deliberately absent from a fresh clone, because Git cannot
track empty directories and their contents are too large or are generated:
`vendor/` (the 80 MB OpenRocket engine, created in the step below) and
`output/` (created on the first run).

## 2.3 Windows

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

Expect `openjdk version "17..."` or higher. If `java` is not recognized after
reopening the terminal, see [§3.2](#32-java-not-found).

**Step 3 — Create the virtual environment**

```powershell
cd C:\path\to\nasa-sli-sim
py -3.13 -m venv .venv
```

Use wherever you cloned the repository — the path above is a placeholder. If
you are not sure, open the folder in File Explorer and copy the path from its
address bar. Every later command assumes the terminal is still in this folder.

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
>
> **Using Git Bash instead of PowerShell?** Use forward slashes —
> `.venv/Scripts/python` — or activate with `source .venv/Scripts/activate`.

**Step 5 — Download the OpenRocket engine**

```powershell
New-Item -ItemType Directory -Force vendor | Out-Null
curl.exe -L -o vendor\OpenRocket-24.12.jar `
  https://github.com/openrocket/openrocket/releases/download/release-24.12/OpenRocket-24.12.jar
```

The `vendor` folder does not exist in a fresh clone, hence the first line.

Note `curl.exe`, not `curl` — in PowerShell the bare word is an alias for
`Invoke-WebRequest`, which will not work here.

If this fails with `curl: (35) schannel: ... CRYPT_E_NO_REVOCATION_CHECK`, you
are likely on a managed or corporate network; see
[§3.4](#34-curl-35-schannel--crypt_e_no_revocation_check) for the fix.

Verify the size is about 80 MB:

```powershell
(Get-Item vendor\OpenRocket-24.12.jar).Length / 1MB
```

## 2.4 macOS

Open **Terminal**. These instructions use [Homebrew](https://brew.sh); install
it first if you do not have it.

```bash
# Step 1 - Python 3.13
brew install python@3.13

# Step 2 - Java JDK 17
brew install --cask temurin@17
java -version          # expect 17 or higher

# Step 3 - virtual environment
cd /path/to/nasa-sli-sim
python3.13 -m venv .venv

# Step 4 - packages
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

# Step 5 - OpenRocket engine (mkdir: vendor/ is absent in a fresh clone)
mkdir -p vendor
curl -L -o vendor/OpenRocket-24.12.jar \
  https://github.com/openrocket/openrocket/releases/download/release-24.12/OpenRocket-24.12.jar
```

On Apple Silicon, if Java fails to start, confirm you installed the ARM build:
`java -XshowSettings:properties -version 2>&1 | grep os.arch` should report
`aarch64`.

## 2.5 Linux

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
cd /path/to/nasa-sli-sim
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
mkdir -p vendor
curl -L -o vendor/OpenRocket-24.12.jar \
  https://github.com/openrocket/openrocket/releases/download/release-24.12/OpenRocket-24.12.jar
```

## 2.6 Visual Studio Code (recommended)

You can run everything from a plain terminal, but VS Code puts the file tree,
the editor, and a terminal in one window — which matters on a laptop, where
alt-tabbing between a file browser and a terminal gets old fast.

**Install it:**

```powershell
winget install --id Microsoft.VisualStudioCode          # Windows
```
```bash
brew install --cask visual-studio-code                  # macOS
```

On Linux, use your distribution's package or the download at
<https://code.visualstudio.com/>.

**Open the project:** File → Open Folder → the `nasa-sli-sim` folder you
cloned. Open the *folder*, not a single file, or nothing below will work.

**Install these extensions** (Ctrl+Shift+X, then search by name):

| Extension | Why |
|---|---|
| **Python** (Microsoft) | Interpreter selection and the debugger. Nothing works without it |
| **Pylance** (Microsoft) | Autocomplete and type hints. Usually installs with Python |
| **YAML** (Red Hat) | Validates `vehicle.yaml`, `sites.yaml`, and `uncertainty.yaml` as you type, so an indentation slip surfaces immediately instead of as a confusing Python error |
| **Rainbow CSV** | Colors the Monte Carlo output columns, so a 1,000-row CSV is readable without Excel |
| **GitLens** | Shows who changed each line and when — useful on a team where several people edit the same config |

**Point it at the project's Python.** Press Ctrl+Shift+P, type
`Python: Select Interpreter`, and choose the entry containing `.venv`. It is
normally marked "Recommended". This is the single most important step: without
it, VS Code uses the system Python and every run fails with
`ModuleNotFoundError`.

**Open the built-in terminal** with Ctrl+` (the backtick key, above Tab). It
opens already in the project folder, and it activates `.venv` for you once the
interpreter is selected — the prompt shows `(.venv)`. Confirm with:

```bash
python -c "import sys; print(sys.executable)"
```

The path it prints should be inside `.venv`. If it is not, the interpreter is
not selected, or the terminal predates the selection — open a new one with the
`+` in the terminal panel. Every command in these guides can be typed here.

> **Running a script with the ▶ button or F5** works too, and the debugger is
> worth learning: set a breakpoint, then step through a real flight. The button
> passes no command-line arguments, though, so anything needing a flag (for
> example `--ballast both`) is easier in the terminal.

## 2.7 The OpenRocket GUI (optional)

Download the installer for your platform from
<https://openrocket.info/downloads.html>. **Use version 24.12** so the GUI
matches the engine the framework drives — otherwise a file the framework writes
may open with subtly different results.

## 2.8 Verifying the installation

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

If you got that, you are done. If not, go to
[Part 3](#part-3--troubleshooting-the-installation).

> **Shorthand in other documents.** The User Guide and the README write
> `python` for whichever of `.venv\Scripts\python` or `.venv/bin/python`
> applies to your machine. Always use the one inside `.venv` — a bare `python`
> will use your system Python and fail with `ModuleNotFoundError`
> ([§3.1](#31-modulenotfounderror-no-module-named-rocketpy)).

---

# Part 3 — Troubleshooting the installation

## 3.1 `ModuleNotFoundError: No module named 'rocketpy'`

The same applies to `No module named 'yaml'` or any other package. You are
using the system Python instead of the venv. Use `.venv\Scripts\python`
(Windows PowerShell), `.venv/Scripts/python` (Git Bash on Windows), or
`.venv/bin/python` (macOS/Linux) — not a bare `python`.

**In VS Code**, this means the interpreter is not the project's. Press
Ctrl+Shift+P → `Python: Select Interpreter` → the entry containing `.venv`
([§2.6](#26-visual-studio-code-recommended)), then open a *new* terminal with
the `+` button; terminals opened earlier keep the old environment. Check which
one you have with `python -c "import sys; print(sys.executable)"`.

If it persists, the venv may not have installed correctly:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

## 3.2 Java not found

```
RuntimeError: No Java 17+ runtime found. OpenRocket 24.12 needs one.
```

The framework searches the standard install locations automatically. If it
still fails, either Java is not installed or it is somewhere unusual. Check:

```bash
java -version
```

If that fails, install a JDK (§2.3–2.5). If it works but the framework does not
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

## 3.3 `FileNotFoundError: OpenRocket jar not found`

You skipped step 5, or the download failed. Check the size — a failed download
often leaves a small HTML error page:

```bash
ls -l vendor/OpenRocket-24.12.jar     # should be ~80 MB
```

Re-download with the command in §2.3–2.5. On Windows remember `curl.exe`, not
`curl`. A fresh clone has no `vendor/` folder at all, so create it first
(`mkdir -p vendor`, or `New-Item -ItemType Directory -Force vendor` in
PowerShell).

If the download itself fails with a certificate error, see
[§3.4](#34-curl-35-schannel--crypt_e_no_revocation_check).

## 3.4 `curl: (35) schannel: ... CRYPT_E_NO_REVOCATION_CHECK`

Windows only, and it is a network problem rather than a project one. The full
error from step 5 reads:

```
curl: (35) schannel: next InitializeSecurityContext failed:
CRYPT_E_NO_REVOCATION_CHECK (0x80092012) - The revocation function was
unable to check revocation for the certificate.
```

`curl.exe` uses Windows' own TLS stack (schannel), which tries to confirm that
GitHub's certificate has not been revoked. On a managed or corporate network
that check often cannot complete — the connection is inspected by a proxy, or
outbound access to the revocation endpoints (CRL/OCSP) is blocked — and
schannel treats "could not check" as fatal.

Download with `Invoke-WebRequest` instead. It uses .NET's TLS stack, which does
not fail the connection when the revocation endpoint is unreachable:

```powershell
New-Item -ItemType Directory -Force vendor | Out-Null
$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest `
  -Uri "https://github.com/openrocket/openrocket/releases/download/release-24.12/OpenRocket-24.12.jar" `
  -OutFile "vendor\OpenRocket-24.12.jar"
```

The `$ProgressPreference` line is not cosmetic — the progress bar slows large
downloads substantially. Downloading the jar in a browser and moving it into
`vendor/` by hand works equally well.

Then confirm you received an archive rather than a proxy error page saved under
a `.jar` name:

```powershell
(Get-Item vendor\OpenRocket-24.12.jar).Length              # 83149098
Get-Content vendor\OpenRocket-24.12.jar -Encoding Byte -TotalCount 4
```

Those four bytes should be `80 75 3 4` — decimal for `PK\x03\x04`, the ZIP
header every jar begins with. An HTML error page would start `60 33 100 111`
(`<!do`). On PowerShell 7 the flag is `-AsByteStream -TotalCount 4` instead of
`-Encoding Byte`.

> **What this works around.** Revocation checking is a genuine security
> control: it is how your machine learns a certificate was compromised and
> withdrawn ahead of its expiry date. Bypassing it is usually reasonable on a
> network where interception is expected and the failure is an artifact of the
> proxy, but it does mean trusting the network instead of verifying the
> certificate. If you are *not* on a managed network, find out why the check
> fails before routing around it.
>
> The size and header check above confirms the file is a well-formed archive.
> It does not confirm the file is the authentic upstream release. If the
> OpenRocket release page publishes a checksum for this jar, compare it with
> `(Get-FileHash vendor\OpenRocket-24.12.jar -Algorithm SHA256).Hash`.

## 3.5 `UnsupportedClassVersionError`

```
info/openrocket/core/startup/OpenRocketCore has been compiled by a more recent
version of the Java Runtime (class file version 61.0), this version of the Java
Runtime only recognizes class file versions up to 55.0
```

Java 17 compiles to class file version 61; 55 is Java 11. So the JVM that
actually loaded is too old, whatever `java -version` says.

```powershell
java -version            # the Java on PATH
echo $env:JAVA_HOME      # the Java the JVM launcher prefers
```

**If `java -version` is under 17**, install a newer JDK (§2.3–2.5) and reopen
the terminal.

**If `java -version` says 17 but the error persists**, `JAVA_HOME` points at an
older install — often left behind by some unrelated tool — and it wins over
PATH. Point it at the Java that works:

```powershell
$env:JAVA_HOME = (Get-Item (Get-Command java).Source).Directory.Parent.FullName
```

That lasts for the current terminal. To keep it:

```powershell
[Environment]::SetEnvironmentVariable("JAVA_HOME", $env:JAVA_HOME, "User")
```

The framework checks `JAVA_HOME`'s version and steps around it when it is too
old, so this error means no newer JDK was found either. It should now report
that in plain language rather than as a Java stack trace; if you see the raw
`UnsupportedClassVersionError` above, you are on an older version of the
framework — `git pull`.

## 3.6 Python 3.14 problems

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

## 3.7 The first run is slow

Roughly 30 seconds is normal — the JVM starts and OpenRocket loads its motor
database and 5,231 component presets. Subsequent simulations in the same
process take about 0.7 s. Monte Carlo pays this cost once per worker process,
not once per sample.

## 3.8 Getting a clean slate

```bash
rm -rf .venv output/*
py -3.13 -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python scripts/run_nominal.py
```

The `vendor/*.jar` and your `config/` files are untouched by this.

---

# Appendix — Glossary

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
