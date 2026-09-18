# Flight Dynamics Background

**NASA Student Launch — Dual-Engine Simulation Framework**
The physics implemented by OpenRocket and RocketPy, and the design theory
behind the USLI requirements.

---

## How to read this document

Each section states the **working equations** — the ones the code actually
evaluates — and explains every term. Where a result is not obvious, a
**Derivation** subsection carries it through from first principles. You can
read the working equations alone as a reference during a report crunch, or read
the derivations to understand where they come from.

Numbers labeled *"template vehicle"* are real outputs from the framework for
the placeholder design in `config/vehicles/full_scale.yaml` (6.00 in diameter,
103 in long,
39.58 lb on the pad, AeroTech L1520T). They are there so you can check your own
understanding against something concrete, and so you can reproduce them.

Statements about OpenRocket's internals were verified directly against
`OpenRocket-24.12.jar` — class structure by decompiling signatures, numerical
correlations by evaluating them. Where a claim rests on OpenRocket's published
technical documentation rather than direct verification, it says so. RocketPy's
behavior was read from the installed 1.13.0 source.

The companion documents, [`SETUP_GUIDE.md`](SETUP_GUIDE.md) and
[`USER_GUIDE.md`](USER_GUIDE.md), cover installation and operation.

---

## Contents

1. [Notation and coordinate systems](#1-notation-and-coordinate-systems)
2. [The atmosphere](#2-the-atmosphere)
3. [Forces on the vehicle](#3-forces-on-the-vehicle)
4. [Normal force and center of pressure](#4-normal-force-and-center-of-pressure)
5. [Drag](#5-drag)
6. [Mass properties](#6-mass-properties)
7. [Static stability](#7-static-stability)
8. [Dynamic stability](#8-dynamic-stability)
9. [Equations of motion](#9-equations-of-motion)
10. [Wind and weathercocking](#10-wind-and-weathercocking)
11. [Descent dynamics](#11-descent-dynamics)
12. [Numerical methods](#12-numerical-methods)
13. [Uncertainty and Monte Carlo](#13-uncertainty-and-monte-carlo)
14. [Why the two engines differ](#14-why-the-two-engines-differ)
15. [Appendices](#15-appendices)

---

# 1. Notation and coordinate systems

## 1.1 Symbols

| Symbol | Meaning | Units |
|---|---|---|
| $\rho$ | air density | kg/m³ |
| $V$, $\vec{V}$ | freestream speed / velocity | m/s |
| $M$ | Mach number | — |
| $\alpha$ | angle of attack | rad |
| $q = \tfrac12\rho V^2$ | dynamic pressure | Pa |
| $A_\text{ref}$ | reference area, $\pi d^2/4$ | m² |
| $d$ | body reference diameter (one caliber) | m |
| $C_N$, $C_{N\alpha}$ | normal force coefficient and its slope | —, 1/rad |
| $C_D$ | drag coefficient | — |
| $X_\text{cp}$, $X_\text{cg}$ | center of pressure / gravity, from nose tip | m |
| $\mathcal{S}$ | static margin, in calibers | cal |
| $I_L$, $I_R$ | longitudinal (pitch/yaw) and rotational (roll) inertia | kg·m² |
| $\dot m$ | propellant mass flow rate | kg/s |
| $C_d S$ | parachute drag coefficient × area | m² |

Positions are measured **from the nose tip, positive aft**. Both tools are
configured to this convention in the framework (RocketPy is explicitly set to
`nose_to_tail`), which eliminates an entire class of sign errors when comparing
CG and CP between them.

## 1.2 Frames

Three frames matter:

- **Body frame** — fixed to the rocket. $x$ along the axis (nose to tail),
  $y$ and $z$ transverse. Aerodynamic forces are naturally computed here.
- **Ground / launch frame** — fixed to the earth at the pad. $z$ up. Trajectory
  and drift are reported here.
- **Wind frame** — aligned with the relative wind. Lift and drag are defined
  relative to this.

The rotation from body to ground is carried as a **quaternion** in both tools,
not Euler angles. Euler angles have a singularity (gimbal lock) at 90° pitch,
which a rocket passes through if it goes over the top; quaternions do not.
See [Appendix C](#appendix-c--quaternion-kinematics).

## 1.3 Angle of attack

$$\alpha = \arccos\!\left(\frac{\vec{V}_\infty \cdot \hat{x}_\text{body}}{|\vec{V}_\infty|}\right)$$

where $\vec{V}_\infty$ is the velocity of the rocket **relative to the air**,
i.e. ground velocity minus wind velocity. This distinction is the entire origin
of weathercocking (§10).

---

# 2. The atmosphere

## 2.1 Why it matters more than you'd think

Every aerodynamic force scales with $\rho$. Apogee is roughly set by how much
kinetic energy survives the drag integral $\int C_D \tfrac12 \rho V^2 A\,dx$, so
a 5% density error is roughly a 5% drag error. The framework's sensitivity
analysis picks this up directly: launch-day **temperature** registers a
measurable pull on apogee (Spearman ρ ≈ +0.10 over 1,000 cases) purely
through its effect on density, with no other path to the trajectory.

## 2.2 Working equations — the ISA troposphere

Below 11 km, temperature falls linearly:

$$T(h) = T_0 - L\,(h - h_0), \qquad L = 0.0065~\text{K/m}$$

Pressure follows from hydrostatic equilibrium plus the ideal gas law:

$$p(h) = p_0\left(1 - \frac{L\,(h-h_0)}{T_0}\right)^{\frac{g}{R L}},
\qquad \frac{g}{RL} = \frac{9.80665}{287.053 \times 0.0065} = 5.2559$$

Density and speed of sound then follow:

$$\rho = \frac{p}{R T}, \qquad a = \sqrt{\gamma R T}, \qquad \gamma = 1.4$$

$h_0$, $T_0$, $p_0$ are the **launch site** elevation, temperature and pressure —
not sea-level standard values. Anchoring at the site is what makes the model
match launch day.

### Derivation — the barometric equation

Hydrostatic balance for a fluid column:

$$\frac{dp}{dh} = -\rho g$$

Substitute the ideal gas law $\rho = p/(RT)$:

$$\frac{dp}{p} = -\frac{g}{R\,T(h)}\,dh$$

Insert the linear lapse $T = T_0 - L(h-h_0)$ and let $u = T_0 - L(h-h_0)$, so
$du = -L\,dh$:

$$\frac{dp}{p} = -\frac{g}{R}\cdot\frac{1}{u}\cdot\left(-\frac{du}{L}\right)
= \frac{g}{RL}\frac{du}{u}$$

Integrating from $(p_0, T_0)$ to $(p, T)$:

$$\ln\frac{p}{p_0} = \frac{g}{RL}\ln\frac{T}{T_0}
\quad\Longrightarrow\quad
\frac{p}{p_0} = \left(\frac{T}{T_0}\right)^{g/(RL)}$$

which is the working equation above. The exponent 5.2559 is not a fitted
constant — it is $g/(RL)$ for air. ∎

## 2.3 What each tool implements

**OpenRocket** uses `ExtendedISAModel`, an interpolating layered ISA extended
from the launch conditions you set (`setLaunchTemperature`,
`setLaunchPressure`), with `setISAAtmosphere(false)` to use them.

**RocketPy** accepts an arbitrary atmosphere. The framework supplies a computed
ISA profile anchored at the site (`_isa_profiles()` in `rocketpy_model.py`),
sampled at 120 levels from site elevation to 9 km.

### The constant-pressure trap

RocketPy's `custom_atmosphere` accepts either a profile *or a scalar*. Passing a
scalar makes pressure **constant at every altitude**. This is not merely
inaccurate — it makes RocketPy's `barometric_height` inversion degenerate, so
every altitude-triggered parachute fires the instant the rocket noses over.

The failure is silent: the flight completes, the numbers look plausible, and the
main deploys at apogee instead of 600 ft. This bit the framework during
development and is the reason `_isa_profiles()` exists. If you modify the
environment code, do not reintroduce it.

---

# 3. Forces on the vehicle

Four forces act during powered ascent:

$$m\frac{d\vec V}{dt} = \vec T + \vec F_A + m\vec g + \vec N_\text{rail}$$

## 3.1 Thrust

$$\vec T = F(t)\,\hat x_\text{body}$$

$F(t)$ comes from the motor's measured thrust curve. Both tools use the **same
curve**, exported from OpenRocket's bundled database (1,088 motor sets inside
the jar), so propulsion is identical by construction.

Total impulse is the integral, and this is what requirement 2.9 caps:

$$I_t = \int_0^{t_b} F(t)\,dt \le 5{,}120~\text{N·s}$$

Template vehicle: L1520T, $I_t = 3{,}769$ N·s, $t_b = 2.49$ s, average thrust
1,511 N, peak 1,697 N, propellant 1.773 kg.

**Thrust-to-weight** (requirement 2.12, ≥ 5.0):

$$\text{TWR} = \frac{\bar F}{m_0 g}$$

The framework uses **average** thrust, which is the stricter reading — peak
thrust would flatter the design.

Template vehicle, two ways:

- Using the motor's *rated* average thrust, 1,511 N:
  $1511/(17.95\times 9.807) = \mathbf{8.6}$
- Using the mean of the *actual thrust curve* over the burn, which is what the
  framework computes: $\mathbf{8.1}$

The framework's number is lower because averaging the digitized curve includes
the tail-off, where thrust decays but is still above the 1 N threshold. Both are
far above the 5.0 floor, but if you compare a hand calculation against the
framework and get a ~6% difference, this is why.

## 3.2 Gravity

OpenRocket uses a WGS-84 model where $g$ varies with latitude and altitude.
RocketPy does likewise. At SLI altitudes the variation is under 0.1% and
irrelevant; it is included because it costs nothing.

## 3.3 Aerodynamic force

Decomposed into axial and normal components in the body frame:

$$F_A = q A_\text{ref} C_A, \qquad F_N = q A_\text{ref} C_N$$

At the small angles of attack a stable rocket flies (a few degrees), $C_A
\approx C_D$ and $C_N \approx C_{N\alpha}\,\alpha$. Sections 4 and 5 develop
these two coefficients — they are the heart of the whole model.

## 3.4 The rail constraint

While on the rail, the vehicle is constrained to one translational degree of
freedom. Rotation is suppressed, and the normal force is reacted by the rail
rather than accelerating the rocket sideways.

This matters because **the rail exit is the most dangerous moment of the
flight**. Aerodynamic restoring moment scales with $V^2$; at rail exit $V$ is at
its minimum for the rest of powered flight, so the rocket's ability to correct a
disturbance is at its weakest. Hence requirement 2.14: at least 52 fps at rail
exit. Below that, a gust can tip the vehicle before the fins can authoritatively
correct it.

Template vehicle: 78.8 fps (OpenRocket) / 70.4 fps (RocketPy) on a 12 ft rail.
The two differ because they define rail departure differently — see §14.

---

# 4. Normal force and center of pressure

## 4.1 Barrowman's method

The classical method (James Barrowman, 1966) computes each component's normal
force slope $C_{N\alpha,i}$ and its individual center of pressure $X_i$, then
combines:

$$C_{N\alpha,\text{total}} = \sum_i C_{N\alpha,i},
\qquad
X_\text{cp} = \frac{\sum_i C_{N\alpha,i} X_i}{\sum_i C_{N\alpha,i}}$$

The CP is the **normal-force-weighted centroid** of the component CPs.

Assumptions: small angle of attack, subsonic attached flow, slender body,
symmetric vehicle. All hold for a well-designed SLI rocket at $M < 0.6$ — the
template peaks at $M = 0.54$.

## 4.2 Nose cone and transitions

$$C_{N\alpha} = 2\,\frac{A_\text{base} - A_\text{fore}}{A_\text{ref}}$$

For a nose cone starting at a point, $A_\text{fore}=0$, so with
$A_\text{ref}=A_\text{base}$:

$$\boxed{C_{N\alpha,\text{nose}} = 2}$$

independent of nose shape. Shape affects only *where* the force acts:

| Shape | $X_\text{cp}$ |
|---|---|
| Conical | $\tfrac23 L$ |
| Ogive | $0.466\,L$ |
| Parabolic | $0.500\,L$ |
| Von Kármán / Haack | $\approx 0.500\,L$ |

### Derivation — why exactly 2

From slender-body theory, the normal force per unit length on a body of
revolution at small $\alpha$ is proportional to the streamwise rate of change of
cross-sectional area:

$$\frac{dN}{dx} = \rho U^2 \alpha \frac{dA}{dx}$$

Physically: the body pushes fluid aside at a rate set by how fast its
cross-section grows, and at incidence that displacement has a transverse
component. Integrating from the tip to the base:

$$N = \rho U^2 \alpha \int_0^L \frac{dA}{dx}dx = \rho U^2 \alpha A_\text{base}$$

Non-dimensionalizing by $q A_\text{ref} = \tfrac12\rho U^2 A_\text{ref}$:

$$C_N = \frac{\rho U^2 \alpha A_\text{base}}{\tfrac12 \rho U^2 A_\text{ref}}
= 2\alpha\frac{A_\text{base}}{A_\text{ref}}
\quad\Longrightarrow\quad
C_{N\alpha} = 2\frac{A_\text{base}}{A_\text{ref}}$$

With $A_\text{ref} = A_\text{base}$, $C_{N\alpha}=2$. ∎

*This is directly verifiable in RocketPy's source: `nose_cone.py` sets
`clalpha = 2 * radius_ratio**2`, and $\text{radius\_ratio}^2 = A_\text{base}/A_\text{ref}$.*

A consequence worth internalizing: **a straight body tube contributes no normal
force** in classical Barrowman, because $dA/dx = 0$. Only area *changes* and
fins generate normal force. OpenRocket adds a body-lift correction at higher
$\alpha$ where this breaks down.

## 4.3 Fins — where the two tools genuinely diverge

**Classical Barrowman**, for $N$ fins on a body of radius $r$:

$$C_{N\alpha,\text{fins}} =
\frac{4N\,(s/d)^2}{1 + \sqrt{1 + \left(\dfrac{2 \ell_m}{c_r + c_t}\right)^2}}$$

where $s$ is semi-span, $\ell_m$ the mid-chord line length, $c_r$, $c_t$ the
root and tip chords. Fin–body interference multiplies this by

$$K_{fb} = 1 + \frac{r}{s + r}$$

The fin set's CP, measured from the fin root leading edge:

$$X_f = \frac{m(c_r + 2c_t)}{3(c_r + c_t)}
+ \frac{1}{6}\left[(c_r + c_t) - \frac{c_r c_t}{c_r + c_t}\right]$$

with $m$ the leading-edge sweep distance.

**OpenRocket** implements an extended form of this in `BarrowmanCalculator`,
with corrections for body lift, fin cant, and compressibility.

**RocketPy** does something different. Reading
`rocketpy/rocket/aero_surface/fins/_base_fin.py`, it starts from a 2-D lift
slope $c_{l\alpha,2D} = 2\pi$ (thin-airfoil theory), applies a
**Prandtl–Glauert** compressibility correction

$$c_{l\alpha,2D}(M) = \frac{2\pi}{\beta}, \qquad \beta = \sqrt{1-M^2}$$

and then converts 2-D to 3-D using **Diederich's planform correlation**:

$$C_{N\alpha,\text{fin}} =
c_{l\alpha,2D}\cdot
\frac{2\pi\, AR}{c_{l\alpha,2D}\cos\Gamma_c}\cdot
\frac{A_f}{A_\text{ref}} \cdot (\ldots)$$

where $AR$ is aspect ratio, $\Gamma_c$ the mid-chord sweep angle, and $A_f$ the
fin planform area.

**This is a genuinely independent aerodynamic model, not a re-implementation of
Barrowman.** It is the strongest part of the cross-validation claim: two
different fin theories, applied to the same geometry, agreeing on static margin
to 0.01 caliber (2.18 vs 2.19 for the template) is real evidence.

## 4.4 CP moves with Mach

CP is not a constant. From the framework, for the template vehicle:

| Mach | $X_\text{cp}$ (in) | $X_\text{cg}$ (in) | Margin (cal) |
|---:|---:|---:|---:|
| 0.05 | 80.20 | 67.20 | 2.168 |
| 0.10 | 80.21 | 67.20 | 2.169 |
| 0.20 | 80.24 | 67.20 | 2.174 |
| 0.30 | 80.30 | 67.20 | **2.183** |
| 0.50 | 80.46 | 67.20 | 2.211 |
| 0.80 | 81.35 | 67.20 | 2.358 |

Two things to take from this:

1. **CP moves aft as Mach rises**, so margin *increases* with speed. The
   critical point for stability is therefore the slowest part of the flight —
   rail exit — not maximum velocity.
2. The variation from $M=0.05$ to $M=0.5$ is only 0.04 caliber. Reporting
   stability at a single Mach is defensible for a subsonic vehicle. Which
   brings us to:

**Requirement 2.11 says "while sitting on the pad", but a Barrowman CP is
undefined at exactly zero airspeed** — there is no flow, so there is no center
of pressure. Some reference velocity must be chosen. The framework evaluates at
**Mach 0.3**, which is OpenRocket's own GUI convention, so the number you report
matches the number the team sees on screen. The table above is your defense if
a reviewer asks.

---

# 5. Drag

Drag sets apogee, and drag uncertainty is — alongside motor impulse — one of
the two dominant contributors to apogee scatter (Spearman ρ ≈ −0.53, against
motor impulse's +0.61). It is the one of the two a team can actually reduce,
which is why it deserves the attention.

## 5.1 Decomposition

$$C_D = \underbrace{C_{D,\text{friction}}}_{\text{viscous shear}}
+ \underbrace{C_{D,\text{pressure}}}_{\text{form}}
+ \underbrace{C_{D,\text{base}}}_{\text{wake suction}}
+ \underbrace{C_{D,\text{parasitic}}}_{\text{lugs, buttons, steps}}$$

For the template vehicle, from an actual OpenRocket run:

| $t$ (s) | Mach | $C_D$ total | friction | pressure | base | thrust (N) |
|---:|---:|---:|---:|---:|---:|---:|
| 0.30 | 0.066 | 0.5238 | 0.3065 | 0.0967 | 0.1206 | 1582 |
| 1.00 | 0.236 | 0.5309 | 0.3049 | 0.0988 | 0.1272 | 1686 |
| 2.00 | 0.478 | 0.5550 | 0.2996 | 0.1056 | 0.1497 | 1561 |
| 2.40 | 0.541 | **0.5640** | 0.2977 | 0.1082 | 0.1581 | 457 |
| 3.53 | 0.477 | 0.5549 | 0.2997 | 0.1056 | 0.1496 | 0 |
| 15.03 | 0.050 | 0.5235 | 0.3066 | 0.0966 | 0.1203 | 0 |

**Skin friction is 55–58% of total drag.** That is typical for a long slender
airframe and it is why `surface_finish` in `vehicle.yaml` is a performance
parameter, not a cosmetic one.

## 5.2 Skin friction

Friction drag comes from the turbulent boundary layer over the wetted area.
OpenRocket's published technical documentation gives the skin friction
coefficient as, for turbulent flow,

$$C_f = \frac{1}{\left(1.50 \ln Re - 5.6\right)^2}$$

with a roughness-limited floor

$$C_{f,\text{rough}} = 0.032\left(\frac{R_s}{L}\right)^{0.2}$$

where $R_s$ is the surface roughness height — set by `surface_finish` — and the
actual $C_f$ is the larger of the two. Reynolds number is

$$Re = \frac{\rho V L}{\mu}$$

Template vehicle at $M=0.5$, $L = 2.62$ m: $Re \approx 3\times10^7$, firmly
turbulent.

Converting to a drag coefficient requires the wetted area and a form factor
accounting for the fact that a body is not a flat plate:

$$C_{D,\text{friction}} = \frac{C_f\left[\left(1+\frac{1}{2f_B}\right)A_\text{wet,body}
+ \left(1 + \frac{2t}{\bar c}\right)A_\text{wet,fins}\right]}{A_\text{ref}}$$

with $f_B = L/d$ the fineness ratio and $t/\bar c$ the fin thickness ratio.

**Design implication:** friction drag scales with *wetted area*. A longer rocket
of the same diameter has more skin, more drag, and less altitude. Length costs
altitude even when it costs no mass.

## 5.3 Base drag — verified correlation

Behind the blunt aft end, flow separates into a low-pressure wake that pulls the
rocket backwards. Evaluating `BarrowmanCalculator.calculateBaseCD` directly from
the jar:

| Mach | 0.0 | 0.3 | 0.6 | 0.9 |
|---|---|---|---|---|
| $C_{D,\text{base}}$ | 0.1200 | 0.1317 | 0.1668 | 0.2253 |

These fit exactly:

$$\boxed{C_{D,\text{base}} = 0.12 + 0.13\,M^2} \qquad (M < 1)$$

Check: $M=0.9 \Rightarrow 0.12 + 0.13(0.81) = 0.2253$. ✓

Similarly, `calculateStagnationCD` (the pressure drag on a blunt forward-facing
surface) fits

$$C_{D,\text{stag}} = 0.85\left(1 + \frac{M^2}{4} + \frac{M^4}{40}\right)$$

Check: $M=0.6 \Rightarrow 0.85(1 + 0.09 + 0.00324) = 0.9293$. ✓

*(These correlations were verified numerically against the shipped jar, not
taken from documentation.)*

Base drag is ~23% of the template's total and **grows as $M^2$**. It is also the
term you can most easily reduce, with a boat tail — at the cost of complexity
and a CP shift.

## 5.4 Compressibility

Below about $M=0.8$, compressibility effects are modest — visible in the table
above as the gentle rise from $C_D = 0.524$ at $M=0.07$ to $0.564$ at $M=0.54$,
about 8%.

Requirement 2.20.6 forbids exceeding Mach 1, and there is good physics behind
that rule: transonic drag rise is steep, poorly predicted by any of these
subsonic correlations, and accompanied by large CP shifts. A vehicle that grazes
$M=0.9$ is one whose simulation you should trust considerably less. The template
peaks at $M=0.54$, comfortably inside the regime where the models are reliable.

## 5.5 The critical asymmetry between the tools

**OpenRocket computes $C_D$ from geometry.** Everything above — friction from
wetted area and roughness, pressure from nose shape and joints, base from aft
geometry — is derived from the component tree.

**RocketPy does not.** `power_off_drag` and `power_on_drag` are **required
inputs**. RocketPy has no parasitic-drag model of its own.

The framework therefore samples OpenRocket's simulated $C_D(M)$ during ascent
and hands it to RocketPy (`export_drag_curves`). Sampling the simulation rather
than doing a static Barrowman sweep captures the full model, including any
base-drag change at burnout.

For the template, the power-on and power-off curves come out nearly identical
(0.524–0.564 in both cases) because base-drag reduction from the exhaust plume
is modest for this configuration — visible in the table above, where base drag
at $t=2.00$ (thrust on, $M=0.478$) is 0.1497 and at $t=3.53$ (coasting, $M=0.477$)
is 0.1496.

**Consequence for your report:** the two tools cannot independently validate
drag. They validate everything downstream of it. To validate drag itself you
need flight data — §11.8 and the FRR requirement.

---

# 6. Mass properties

## 6.1 Center of gravity

$$X_\text{cg} = \frac{\sum_i m_i X_i}{\sum_i m_i}$$

The framework sets component masses as **overrides** from weighed values rather
than letting OpenRocket compute them from material densities. An as-built mass
from a scale beats a density estimate, and it guarantees both tools carry
identical masses.

**The mass budget must close.** The FRR requires:

> *"The sum of the propellant mass, recovery components, and individual section
> landing masses shall equal the gross lift-off mass."*

The framework enforces this (`check_mass_closure`). During development this
check caught a real 0.33 lb discrepancy: OpenRocket was adding its own
material-derived mass for the motor mount and rail buttons *on top of* as-built
section masses that already included them. Both are now overridden to zero.

## 6.2 Moments of inertia

Rotational dynamics need the inertia tensor. For an axisymmetric rocket it
reduces to two numbers: longitudinal $I_L$ (pitch and yaw, equal by symmetry)
and rotational $I_R$ (roll).

Each is assembled by the parallel-axis theorem:

$$I_L = \sum_i \left[I_{L,i} + m_i (X_i - X_\text{cg})^2\right]$$

The $m_i r_i^2$ transfer terms dominate: a mass far from the CG contributes far
more to pitch inertia than its own local inertia does.

Template vehicle, structure only: $I_L = 5.814$ kg·m², $I_R = 0.1011$ kg·m².
The ratio of ~58 is characteristic — rockets are hard to pitch and easy to roll.

## 6.3 Time-varying mass

During burn, mass, CG and inertia all change. Propellant leaves from the aft
end, so the CG typically moves **forward**, which *increases* static margin
through the burn. Combined with the CP moving aft with Mach (§4.4), a rocket
usually becomes more stable as it accelerates — which is why the pad and rail
exit are the binding cases.

RocketPy handles this through `GenericMotor`, which the framework prefers over
`SolidMotor`. `SolidMotor` requires grain geometry — grain count, inner and
outer radii, separation — that OpenRocket's database simply does not contain.
Inventing those numbers to satisfy the constructor would fabricate data the team
does not have. `GenericMotor` takes the thrust curve and mass endpoints, which
is exactly what is actually known.

---

# 7. Static stability

## 7.1 The working definition

$$\boxed{\mathcal{S} = \frac{X_\text{cp} - X_\text{cg}}{d}}$$

measured in **calibers** (body diameters). Requirement 2.11: $\mathcal{S} \ge
2.0$ on the pad.

## 7.2 Derivation — why CP behind CG means stable

Suppose the rocket is disturbed to a small angle of attack $\alpha$. The
aerodynamic normal force acts at the CP:

$$F_N = q A_\text{ref} C_{N\alpha}\,\alpha$$

The rocket rotates freely about its **center of gravity** (a body in free
flight rotates about its CG, not about any structural point). The moment about
the CG is therefore

$$\mathcal{M} = -F_N\,(X_\text{cp} - X_\text{cg})
= -q A_\text{ref} C_{N\alpha}(X_\text{cp}-X_\text{cg})\,\alpha$$

The sign convention: a positive $\alpha$ (nose pitched up relative to the
airflow) produces a normal force that, acting *behind* the CG, pitches the nose
back **down**. Restoring.

The condition for stability is that the moment opposes the disturbance:

$$\frac{\partial \mathcal{M}}{\partial \alpha} < 0
\quad\Longleftrightarrow\quad
X_\text{cp} > X_\text{cg}$$

**CP aft of CG.** If CP were ahead of CG, the same force would amplify the
disturbance and the rocket would tumble. ∎

## 7.3 Why calibers, and why 2.0

Non-dimensionalizing by diameter makes the criterion **scale-independent**: a
3-inch and a 6-inch rocket with the same margin in calibers have comparable
handling. Expressing it in inches would not transfer between vehicles.

Why 2.0 rather than 1.0? Requirement 2.11's number is a safety margin covering
what the simulation does not know:

- **CG uncertainty.** Ballast, payload placement, and build variation all move
  the CG. The framework disperses CG by ±1 cm (1σ), which on a 6-inch airframe
  is ±0.066 caliber.
- **CP uncertainty.** Barrowman is a subsonic, small-α approximation. Real CP at
  high α moves forward, reducing margin exactly when you need it.
- **Wind.** A gust creates instantaneous α of several degrees at low speed.

Note that the two error sources are asymmetric: CP errors tend to *reduce*
margin under the conditions that matter, so a nominal 2.0 is closer to a true
1.5 than to a true 2.5.

**The upper bound nobody writes down.** More stability is not simply better.
Above roughly 3 calibers a rocket becomes *overstable*: it aligns so eagerly
with the relative wind that it weathercocks hard into a crosswind, losing
altitude and flying upwind (§10). The practical window is about **1.5 to 3.0
calibers**, and the handbook's 2.0 floor sits sensibly inside it.

Template vehicle: 2.18 caliber. Enlarging the fins from 12×5×5.5 in to
15×6×7.5 in moved it from 1.40 (failing) to 2.18 (passing), at a cost of about
45 ft of apogee — a concrete instance of the stability/performance trade.

---

# 8. Dynamic stability

Static margin says the rocket *returns* to alignment. It says nothing about
*how* — quickly and smoothly, or with a long ringing oscillation. That is
dynamic stability, and neither tool reports it directly, so it is worth being
able to compute by hand.

## 8.1 The pitch oscillation equation

Linearizing about small $\alpha$, pitch obeys a damped second-order system:

$$I_L\ddot\theta + C_2\dot\theta + C_1\theta = 0$$

**Corrective moment coefficient** (the restoring spring):

$$C_1 = q A_\text{ref} C_{N\alpha}\,(X_\text{cp}-X_\text{cg})
= \tfrac12\rho V^2 A_\text{ref} C_{N\alpha}\,\mathcal{S}\,d$$

**Damping moment coefficient**, with two physically distinct parts:

$$C_2 = \underbrace{\tfrac12 \rho V A_\text{ref}\sum_i C_{N\alpha,i}(X_i-X_\text{cg})^2}_{C_{2R}\;\text{aerodynamic}}
\;+\;\underbrace{\dot m\,(X_\text{nozzle}-X_\text{cg})^2}_{C_{2P}\;\text{jet damping}}$$

*Aerodynamic damping*: when the rocket pitches at rate $\dot\theta$, each
surface at distance $r$ from the CG sees an extra local angle of attack
$r\dot\theta/V$, generating a force opposing the rotation. The $r^2$ weighting is
why aft fins damp so effectively.

*Jet damping*: exhaust leaving a rotating rocket carries away angular momentum,
which resists the rotation. It exists only while the motor burns.

## 8.2 Frequency and damping ratio

$$\omega_n = \sqrt{\frac{C_1}{I_L}}
\qquad
\zeta = \frac{C_2}{2\sqrt{C_1 I_L}}$$

Design targets:

- $\zeta \approx 0.05$–$0.3$ is typical and acceptable. Rockets are lightly
  damped; a few visible oscillations after a gust are normal.
- $\zeta < 0.05$ means a disturbance rings for many cycles — the vehicle
  "corkscrews", costing altitude to induced drag.
- $\omega_n$ should be **well separated from the natural frequency of anything
  else** — the rate at which the rocket climbs through wind-shear layers,
  and any structural mode.

**A caution about roll.** If canted fins drive the roll rate near the pitch
frequency, energy couples between roll and pitch — *roll–pitch resonance* — and
the vehicle can diverge despite adequate static margin. The template has
`cant_deg: 0.0`, avoiding this entirely. If you cant fins for roll stability,
check that the resulting roll rate stays clear of $\omega_n$.

---

# 9. Equations of motion

## 9.1 Translation

Newton's second law in the ground frame:

$$m\frac{d\vec V}{dt} = \mathbf{R}(\mathbf{q})\left(\vec T + \vec F_A\right) + m\vec g$$

$\mathbf{R}(\mathbf q)$ is the rotation matrix from the quaternion, taking
body-frame forces into the ground frame.

## 9.2 Rotation — Euler's equations

For a rigid body in the body frame:

$$\mathbf{I}\dot{\vec\omega} + \vec\omega\times(\mathbf{I}\vec\omega) = \vec{\mathcal M}$$

The $\vec\omega\times(\mathbf I\vec\omega)$ term is gyroscopic coupling. For an
axisymmetric rocket with $I_L \gg I_R$ this couples roll into pitch/yaw: a
rolling rocket resists pitching, which is why spin-stabilized vehicles work and
why a fast-rolling finned rocket behaves differently from a non-rolling one.

Expanded for $\mathbf I = \text{diag}(I_R, I_L, I_L)$:

$$
\begin{aligned}
I_R\dot\omega_x &= \mathcal M_x \\
I_L\dot\omega_y &= \mathcal M_y - (I_R - I_L)\,\omega_z\omega_x \\
I_L\dot\omega_z &= \mathcal M_z - (I_L - I_R)\,\omega_x\omega_y
\end{aligned}
$$

## 9.3 Attitude

Quaternion kinematics (derived in [Appendix C](#appendix-c--quaternion-kinematics)):

$$\dot{\mathbf q} = \tfrac12\,\mathbf q \otimes \begin{bmatrix}0\\ \vec\omega\end{bmatrix}$$

Thirteen states in total: 3 position, 3 velocity, 4 quaternion, 3 angular rate.
Both tools carry exactly this state vector. RocketPy's is literally
`u = [x, y, z, vx, vy, vz, e0, e1, e2, e3, ω1, ω2, ω3]`.

## 9.4 What each tool actually does

This was verified by inspecting the shipped code, and the answer is more
interesting than "both are 6-DOF".

**OpenRocket** dispatches to different steppers by flight phase:

| Phase | Class | Scheme |
|---|---|---|
| Powered + coasting ascent | `RK4SimulationStepper` | 6-DOF, **4th-order Runge–Kutta** |
| Descent under parachute | `BasicLandingStepper` → `AbstractEulerStepper` | 3-DOF, **first-order Euler** |
| Tumbling descent | `BasicTumbleStepper` → `AbstractEulerStepper` | 3-DOF, first-order Euler |
| On the ground | `GroundStepper` | — |

Solver constants read from the jar:

| Constant | Value |
|---|---|
| `RECOMMENDED_TIME_STEP` | 0.05 s |
| `RECOMMENDED_ANGLE_STEP` | 0.0524 rad = 3.0° |
| `PITCH_YAW_RANDOM` | 0.0005 |
| `RECOMMENDED_MAX_TIME` | 1200 s |

The angle step is an adaptive limiter: if a step would rotate the vehicle more
than 3°, the step is shortened. This keeps the rotational integration accurate
during the high-rate pitch-over near apogee without paying for small steps
throughout.

`PITCH_YAW_RANDOM` injects a tiny random perturbation, so that a perfectly
symmetric rocket at exactly zero angle of attack does not sit on an unstable
knife-edge equilibrium forever — a numerical necessity, not physics.

**RocketPy** uses SciPy's `solve_ivp` with adaptive-order, adaptive-step
methods; the framework uses the default **LSODA**. Available alternatives
include RK45, DOP853, Radau, and BDF. Its phase functions are `udot_rail1`
(rail), `u_dot` / `u_dot_generalized` (free flight, 6-DOF), and
`u_dot_parachute` (descent, 3-DOF).

## 9.5 The descent phase — the largest structural difference

Both tools drop to 3 degrees of freedom under parachute, which is physically
reasonable: a parachute-borne vehicle's attitude barely affects its trajectory.
But the implementations differ substantially.

**OpenRocket:** first-order explicit Euler, drag and gravity only.

**RocketPy** (`u_dot_parachute`, read directly from source) adds two terms
OpenRocket omits:

$$a = \frac{D - mg}{m + m_a}$$

- **Added mass** $m_a = k\,\rho\,\frac{2}{3}\pi R^2 h$. A parachute drags a
  significant volume of air along with it; the effective inertia is larger than
  the vehicle's mass. This matters most during the deployment transient, when
  accelerations are largest — it softens the opening shock.
- **Coriolis acceleration** from Earth's rotation. Negligible over a 90-second
  descent, but present.

The drag itself is the same form in both:
$D = -\tfrac12\rho\,(C_d S)\,|\vec V_\infty|\,\vec V_\infty$, quadratic in
speed and directed against the freestream.

For the template these differences are small — descent times agree to 0.8%,
descent rates to 1.3% — but they are the reason to expect *some* disagreement,
and they are worth naming in a report rather than hand-waving.

---

# 10. Wind and weathercocking

## 10.1 Wind enters through the relative velocity

Wind does not appear as a force. It appears in the freestream velocity:

$$\vec V_\infty = \vec V_\text{ground} - \vec V_\text{wind}$$

Every aerodynamic force then follows from $\vec V_\infty$. The consequence is
that a crosswind creates an **angle of attack**:

$$\alpha_\text{wind} \approx \arctan\!\left(\frac{V_\text{wind}}{V_\text{rocket}}\right)$$

At rail exit with a 15 mph wind and 78 fps rail exit speed, $\alpha \approx
\arctan(22/78) = 15.7°$. That is a very large angle of attack, and it is why
rail exit velocity is a safety requirement.

As the rocket accelerates, $\alpha_\text{wind}$ falls as $1/V$. By $M=0.5$ (560
fps) the same wind produces only 2.3°.

## 10.2 Weathercocking

The rocket is statically stable, so it turns to align with $\vec V_\infty$ —
which points partly *into* the wind. The vehicle therefore **turns upwind**.
This is weathercocking, and it is not a defect; it is static stability working
exactly as designed.

Its magnitude scales with static margin: a stiffer rocket aligns faster and
weathercocks harder. This is the practical upper bound on static margin
mentioned in §7.3.

## 10.3 Measured behavior

Framework output for the template vehicle, wind of 15 mph **from 180°** (out of
the south). Negative $y$ is upwind (south), positive $y$ downwind (north):

| Rail angle | Rail direction | $y$ at apogee (ft) | $y$ at landing (ft) | Total drift (ft) | Apogee (ft) |
|---:|---:|---:|---:|---:|---:|
| 0° (vertical) | — | **−766** | +610 | 610 | 4462 |
| 5° | downwind | −4 | +1633 | 1633 | 4521 |
| 5° | **into wind** | −1534 | −309 | **309** | 4310 |
| 10° | downwind | +794 | +2584 | 2584 | 4499 |
| 10° | into wind | −2254 | −1287 | 1287 | 4067 |

Read the first row carefully. Launched **vertically**, the rocket weathercocks
766 ft *upwind* during ascent, then drifts 1,376 ft downwind under parachute,
landing 610 ft downwind of the pad. Weathercocking already cancels almost half
the parachute drift.

## 10.4 The rail angle trade

The table shows three coupled effects:

1. **Tilting into the wind reduces net drift** — 610 ft vertical → 309 ft at 5°.
   The ascent moves further upwind, offsetting more of the descent drift.
2. **Over-correcting overshoots.** At 10° into the wind the rocket lands 1,287 ft
   *upwind*. There is an optimum near 5°, not "more is better".
3. **Tilting into the wind costs apogee** — 4,462 → 4,310 → 4,067 ft. Two
   reasons: the cosine loss of a non-vertical trajectory, and a larger sustained
   angle of attack, which raises induced drag.

So requirement 3.10 (2,500 ft recovery radius) and requirement 2.1 (apogee
window) pull against each other through the rail angle, and the RSO sets it on
the day. This is exactly the kind of trade the Monte Carlo is for: disperse rail
angle over its plausible range rather than assuming a value.

## 10.5 Turbulence models — and why the framework leaves it off

**OpenRocket** offers `PinkNoiseWindModel` and `MultiLevelPinkNoiseWindModel`.
Pink noise (a $1/f$ spectrum) reproduces the observed property that atmospheric
gusts carry more energy at long wavelengths than white noise would give.

**RocketPy**, as configured here, uses steady uniform wind. It supports imported
atmospheric soundings, which is the better path once you have launch-day data.

**The framework sets OpenRocket's turbulence intensity to 0 by default**, which
is also OpenRocket's own default. The reason is reproducibility: OpenRocket's
pink-noise generator seeds itself independently of
`SimulationOptions.setRandomSeed`, so any non-zero turbulence makes results
irreproducible. Repeated runs of an identical configuration scattered apogee by
a few tenths of a percent and drift by several percent — meaning a number quoted
in a report could not be regenerated. That is disqualifying for a document
someone will be asked to defend.

Wind variability belongs in the **Monte Carlo**, where wind speed and direction
are dispersed explicitly, the seed genuinely controls the outcome, and the
result is a distribution rather than one arbitrary realization.

Pass `wind_turbulence` explicitly if you want it for a one-off study — for
example, to check the sensitivity of rail-exit behavior to gusts.

---

# 11. Descent dynamics

## 11.1 Terminal velocity

Under a fully inflated parachute the vehicle reaches terminal velocity within a
few seconds. Setting drag equal to weight:

$$\tfrac12 \rho\,(C_d S)\,V_t^2 = mg
\qquad\Longrightarrow\qquad
\boxed{V_t = \sqrt{\frac{2mg}{\rho\,C_d S}}}$$

Note what this does **not** contain: the parachute's diameter and drag
coefficient appear only through their product $C_d S$. That is the physically
meaningful parameter, and it is why RocketPy's API takes `cd_s` directly.

## 11.2 Worked example — checking the simulation by hand

Template vehicle, descending mass 16.18 kg (burnout mass; propellant expended):

- Main: 108 in diameter, $C_d = 2.20$ → $S = 5.910$ m², $C_d S = 13.00$ m²
- Drogue: 18 in, $C_d = 1.55$ → $C_d S = 0.2545$ m²

$$V_{t,\text{main}} = \sqrt{\frac{2(16.18)(9.807)}{1.225 \times 13.00}}
= \sqrt{\frac{317.4}{15.93}} = 4.46~\text{m/s} = 14.64~\text{fps}$$

| Case | Hand calculation | Simulation | Agreement |
|---|---|---|---|
| Main, $\rho$ = 1.225 (sea level) | 14.64 fps | **14.61 fps** | 0.2% |
| Drogue, $\rho$ = 1.225 | 104.68 fps | — | |
| Drogue, $\rho$ = 1.16 (≈1,500 m) | 107.57 fps | **108.72 fps** | 1.1% |

The main matches sea-level density because the main phase happens near the
ground. The drogue matches the *reduced* density at altitude, because drogue
descent occurs high up — a good reminder that $\rho$ is not a constant, and a
satisfying confirmation that both the hand calculation and the simulation are
doing the right thing.

**Do this check.** A five-line hand calculation that agrees with a
1,000-line simulation is the cheapest validation available, and it is precisely
the kind of evidence a review panel finds convincing.

## 11.3 Kinetic energy at landing — the judgement call

Requirement 3.2 caps each independent section at **75 ft·lbf**:

$$KE = \tfrac12 m_\text{section} V^2 \le 75~\text{ft·lbf}$$

**Which $V$?** This is a real engineering decision, not a detail.

Under a parachute in wind, the vehicle's velocity has two components: it
descends at $V_t$ and it translates horizontally with the wind at
$V_\text{wind}$. The total speed is

$$V_\text{total} = \sqrt{V_t^2 + V_\text{wind}^2}$$

Since energy goes as $V^2$, and since a 10 mph wind (14.7 fps) is *comparable to
the descent rate* (14.6 fps) for a well-sized main, including drift roughly
**doubles** the computed energy.

Template vehicle:

| Section | Mass | $KE$ (vertical, 14.6 fps) | $KE$ (total, 20.7 fps) |
|---|---:|---:|---:|
| Nose + Payload Bay | 10.20 lb | 33.6 ft·lbf | 63.9 ft·lbf |
| Avionics Bay + Booster | 17.00 lb | **56.1 ft·lbf** | **106.5 ft·lbf** |

The handbook's FRR table asks for *"descent rate under both drogue and main
parachutes"* — the vertical rate — and that is what essentially every team
reports and what the framework uses as its pass/fail basis. But the heavier
section would fail on the conservative basis, so the framework prints both.

Sizing to the vertical rate is defensible and conventional. Understanding that
it leaves little true margin is the useful part, and raising it yourselves in a
review is far better than having a panelist raise it for you.

## 11.4 Sizing a parachute from the energy limit

Invert the requirement. For the heaviest section:

$$V_\text{max} = \sqrt{\frac{2\,KE_\text{max}}{m_\text{section}}}$$

With $KE_\text{max} = 75$ ft·lbf $= 101.7$ J and $m = 7.711$ kg (17.00 lb):

$$V_\text{max} = \sqrt{\frac{2 \times 101.7}{7.711}} = 5.14~\text{m/s} = 16.9~\text{fps}$$

Then size the canopy for the **whole descending mass** at that rate:

$$C_d S = \frac{2 m_\text{total}\, g}{\rho V_\text{max}^2}
= \frac{2(16.18)(9.807)}{1.225(5.14)^2} = 9.80~\text{m}^2$$

$$S = \frac{9.80}{2.20} = 4.45~\text{m}^2
\quad\Rightarrow\quad
D = \sqrt{\frac{4S}{\pi}} = 2.38~\text{m} = 93.7~\text{in}$$

So a 96-inch main is the bare minimum. The template uses **108 inches**,
deliberately, because 94 inches leaves no margin once Monte Carlo scatter in
mass, $C_d$, and density is applied. During development a 96-inch main gave 70.4
ft·lbf against a 75 limit — 6% margin, which dispersion would eat.

**Rule of thumb: size for about 75–80% of the KE limit at nominal**, so the
distribution stays clear of it.

## 11.5 Descent time and the conflict with drift

Requirement 3.11 caps descent at **100 s** apogee-to-touchdown. Requirement 3.10
caps drift at **2,500 ft**. These pull in opposite directions, and understanding
why is worth more than memorizing both numbers.

Two-phase descent from apogee $h_a$ with main deployment at $h_m$:

$$t_\text{descent} \approx \frac{h_a - h_m}{V_\text{drogue}} + \frac{h_m}{V_\text{main}}$$

Drift, to first order, is the wind speed times the time aloft:

$$x_\text{drift} \approx V_\text{wind}\, t_\text{descent} \;-\; (\text{upwind weathercocking offset})$$

Template check, with apogee 1,382 m (4,533 ft), main deployment 183 m (600 ft),
drogue rate 33.1 m/s and main rate 4.45 m/s:

$$t \approx \frac{1382 - 183}{33.1} + \frac{183}{4.45} = 36.2 + 41.1 = 77.3~\text{s}$$

against a simulated **77.2 s** — a 0.1% agreement from two lines of arithmetic.
Note that 41 of those 77 seconds are spent in the last 600 ft.

Now the tension. Reducing kinetic energy at landing requires a **slower**
descent, which means **more time aloft** and therefore **more drift**, and risks
the 100 s limit. The available moves:

| Move | KE | Descent time | Drift |
|---|---|---|---|
| Larger main | ↓ better | ↑ worse | ↑ worse |
| Lower main deployment altitude | — | ↓ better | ↓ better |
| Larger drogue | — | ↑ worse | ↑ worse |
| More independent sections | ↓ better | — | — |

**Deploying the main lower is the move that helps both** — it shortens the slow
phase without changing landing speed. This is why requirement 3.1.1 exists
(main no lower than 500 ft): it prevents teams from optimizing this trade into
a configuration with no altitude left to recover from a failed deployment. The
template deploys at 600 ft, leaving a small buffer above the floor.

Splitting into more independent sections reduces per-section mass and hence
per-section KE at no cost in time or drift — which is why so many SLI vehicles
separate into three or four tethered sections (requirement 2.5 permits up to
four).

## 11.6 Parachute inflation

Neither tool models canopy inflation in detail. OpenRocket applies the
parachute's full $C_d S$ after the specified deployment delay; RocketPy applies
it after `lag`. Real inflation takes a finite time, over which drag rises from
zero to full.

The consequence is that **neither tool predicts opening shock loads**. Peak
deployment force is a structural sizing problem for shock cords, bulkheads, and
eyebolts, and it must be computed separately. OpenRocket does at least warn when
deployment occurs at high speed — the template triggers *"Recovery device
deployment at high speed (32.8 m/s)"* for the main, which is a real design flag
worth heeding, not noise to be suppressed.

## 11.7 Drogue-phase caveat

Descent under drogue at ~108 fps involves a partially tumbling, high-drag,
unsteady configuration that neither tool resolves properly. That the two engines
agree to 0.9% on drogue descent rate is **coincidence, not validation** — they
agree because they were handed the same $C_d S$ and both integrate the same
simple drag law. Treat drogue descent as the least trustworthy part of the
prediction and validate it against flight data.

## 11.8 Fitting drag from flight data

The FRR requires:

> *"Estimate the drag coefficient of the full-scale rocket utilizing launch
> data. Use this value to run a post-flight simulation."*

The framework fits a single multiplicative scale $k$ on $C_D(M)$ by minimizing
the apogee residual (or full ascent RMSE):

$$k^\star = \arg\min_k \left| h_\text{apogee}^\text{sim}(k) - h_\text{apogee}^\text{measured} \right|$$

**Why a single scale factor rather than a full curve?** With one altimeter trace
there is not enough information to resolve $C_D$ as a function of Mach. Attempting
it would fit barometric noise and produce a curve that looks precise and means
nothing. A scale factor is what the data can actually support.

Validation of the fitter itself: run against synthetic data with a known scale
of 1.180, it recovers **1.173** — 0.6% error, 9 ft ascent RMSE. Testing an
estimator against a known answer before trusting it with real data is a habit
worth building.

**Why this matters more than anything else in the framework:** drag is the
dominant uncertainty. Replacing a 7% pre-flight guess with a 2–3% measured value
roughly halves the apogee spread, which directly improves the requirement 2.3
altitude score. You improve your score not by simulating more carefully, but by
measuring.

**A caution on extracting descent rate from altimeter data.** Do not
differentiate the altitude trace point-by-point. A few feet of barometric noise
at 20 Hz is roughly 100 fps of noise in every finite difference, which entirely
swamps a 15 fps descent under the main. Fit a straight line over each descent
phase instead — steady-parachute descent is linear in time, so the slope uses
every sample and is essentially immune to the noise. The framework does this;
during development the naive approach reported 62 fps where the truth was 14.8.

---

# 12. Numerical methods

## 12.1 Runge–Kutta 4 (OpenRocket, ascent)

For $\dot y = f(t,y)$ with step $h$:

$$
\begin{aligned}
k_1 &= f(t_n, y_n) \\
k_2 &= f(t_n + \tfrac h2,\; y_n + \tfrac h2 k_1) \\
k_3 &= f(t_n + \tfrac h2,\; y_n + \tfrac h2 k_2) \\
k_4 &= f(t_n + h,\; y_n + h k_3) \\
y_{n+1} &= y_n + \tfrac h6(k_1 + 2k_2 + 2k_3 + k_4)
\end{aligned}
$$

Local error $O(h^5)$, global $O(h^4)$. Four force evaluations per step. Fixed
step (0.05 s default), with the 3° angle limiter shortening steps during rapid
rotation.

## 12.2 LSODA (RocketPy)

LSODA automatically switches between an **Adams–Moulton** method (non-stiff) and
**BDF** (stiff), and adapts both order and step size to meet a tolerance
(default `rtol=1e-6`).

**Why stiffness matters here.** A stiff system has processes on widely separated
timescales. Rocket flight is exactly that: high-frequency pitch oscillation
(§8.2) alongside a 90-second descent. A fixed-step explicit method must use a
step small enough for the fastest mode throughout the whole flight. An adaptive
implicit method can take large steps during the smooth descent and small ones
through the transients.

This is the deepest structural difference between the two integrators, and it is
why the tools can agree closely on apogee while differing on quantities that
depend on how transients are resolved.

## 12.3 Event detection

Ignition, burnout, apogee, deployments, ground hit. Both tools detect these by
monitoring conditions between steps and refining the crossing time.

Apogee is $v_z = 0$; ground hit is $z = 0$. Parachute triggers are evaluated at
a finite sampling rate — the framework sets 105 Hz in RocketPy, mimicking a real
altimeter that polls a barometer rather than solving continuously.

## 12.4 Choosing a time step

The 0.05 s default resolves a ~2 s burn in 50 steps and the pitch oscillation
adequately. Halving it changes template apogee by well under 0.1%.

If you shorten the time step and results change materially, that is a signal
something is wrong — most likely a genuinely stiff transient being under-resolved
— not a reason to keep shrinking the step. **Run a step-size convergence check
once per season and put it in an appendix.** It is cheap and it forecloses an
entire line of reviewer questioning.

---

# 13. Uncertainty and Monte Carlo

## 13.1 Why probabilistic

A deterministic simulation answers "what happens if every input is exactly its
nominal value" — a case that will never occur. Monte Carlo answers "given what I
actually know, what is the distribution of outcomes", which is the question the
requirements pose.

Requirement 2.1 is not "will apogee be 4,500 ft" but "will apogee be between
4,000 and 6,000 ft". That is a probability.

## 13.2 The method

1. Declare each uncertain input as a distribution (`config/uncertainty.yaml`).
2. Draw $N$ independent samples.
3. Simulate each.
4. Report the output distribution and per-requirement compliance rates.

Statistical error on an estimated quantile falls as $1/\sqrt N$: 100 samples
give ~10% relative error on a tail quantile, 1,000 give ~3%, 10,000 give ~1%.
For report-quality numbers, 1,000–2,000 is the right range.

## 13.3 Choosing distributions

- **Normal** for quantities that are sums of many small independent errors —
  mass (many components), CG. The Central Limit Theorem earns this one.
- **Uniform** for genuinely unknown-within-a-range quantities. Rail azimuth
  relative to the wind is uniform on [0°, 360°) because the RSO's choice is not
  known in advance.
- **Truncated normal** where a normal would produce impossible values. Wind
  speed cannot be negative.

**On truncation:** the framework *resamples* out-of-bounds draws rather than
clipping them. Clipping piles probability mass onto the boundary — a
`truncnormal` with $\sigma=2$ clipped at 0 would put a spike of probability at
exactly zero wind — and it biases exactly the tails where requirement margins
live.

## 13.4 Sensitivity analysis

The framework ranks inputs by **Spearman rank correlation** with each output.
Spearman rather than Pearson because it detects any *monotone* relationship, not
just a linear one — wind speed's effect on drift is monotone but not linear, and
Pearson would understate it.

Template vehicle, 1,000 cases, seed 12345:

| Input | ρ vs apogee | ρ vs drift | ρ vs landing speed |
|---|---:|---:|---:|
| `motor_total_impulse` | **+0.605** | −0.007 | +0.006 |
| `drag_coefficient` | **−0.528** | −0.059 | −0.012 |
| `dry_mass` | −0.267 | −0.000 | +0.108 |
| `wind_speed_mps` | −0.226 | −0.015 | +0.011 |
| `rail_angle_deg` | −0.159 | **+0.829** | −0.009 |
| `temperature_k` | +0.098 | +0.032 | +0.179 |
| `pressure_pa` | −0.072 | −0.014 | −0.105 |
| `motor_burn_time` | −0.054 | −0.038 | +0.008 |
| `cg_shift` | +0.053 | −0.018 | −0.077 |
| `main_cd` | −0.010 | +0.019 | **−0.965** |

Read it as a priority list, and read all three columns — **the dominant driver is
different for every question you ask.** Apogee is a motor-and-drag problem.
Drift is almost entirely a rail-angle problem, and the rail angle is set by the
RSO on the day rather than chosen by the team. Landing speed — and therefore
kinetic energy at touchdown, requirement 3.2 — is a main-parachute problem and
essentially nothing else.

So there is no point agonizing over a quarter-pound of mass while carrying a 7%
drag uncertainty, and no point tuning drag at all if the question you are asking
is about landing energy.

### Sample size is not optional here

These figures come from 1,000 cases because smaller runs give *misleading*
rankings, not merely noisier ones. Development runs of 60 to 200 cases put
`temperature_k` third at ρ ≈ +0.40; at 1,000 cases it settles at +0.10. The
small-sample value was sampling noise wearing the costume of a physical effect,
and a team acting on it would have gone off chasing the wrong variable.

A rank correlation is an estimate like any other, with error falling as 1/√N.
Quote sensitivities from a run of at least 1,000, state the sample size and seed
beside them, and be suspicious of any ranking that reorders when you change
either.

Two sanity checks that this analysis is working correctly:

- **Signs are physical.** More drag → lower apogee (negative). More impulse →
  higher apogee (positive). Warmer air → less dense → less drag → higher apogee
  (positive).
- **`motor_burn_time` is near zero, and should be.** The framework scales thrust
  by $1/k$ when stretching the time axis by $k$, holding total impulse fixed.
  Burn time at constant impulse genuinely has little effect on apogee. During
  development, before that correction, burn time and impulse were entangled and
  the ranking was misleading — a reminder that a sensitivity analysis is also a
  test of your own model.

---

# 14. Why the two engines differ

For the template vehicle, 11 of 13 compared quantities agree within 5%, most
within 1%.

| Quantity | OpenRocket | RocketPy | Diff |
|---|---:|---:|---:|
| Apogee | 4,534.22 ft | 4,536.87 ft | **+0.06%** |
| Max velocity | 606.03 fps | 606.20 fps | +0.03% |
| Max Mach | 0.544 | 0.544 | +0.07% |
| Max acceleration | 8.83 g | 8.83 g | −0.03% |
| Time to apogee | 16.74 s | 16.77 s | +0.13% |
| Static stability | 2.18 cal | 2.19 cal | +0.47% |
| Descent time | 76.94 s | 77.83 s | +1.16% |
| Descent rate (drogue) | 108.72 fps | 109.71 fps | +0.91% |
| Descent rate (main) | 14.61 fps | 14.77 fps | +1.10% |
| **Rail exit velocity** | **78.81 fps** | **70.42 fps** | **−10.64%** |
| **Drift from pad** | **1,355.0 ft** | **1,218.7 ft** | **−10.06%** |

These are exactly reproducible: `python scripts/run_nominal.py`.

## 14.1 Rail exit velocity, −10.6%

**Definitional, not physical.** OpenRocket releases the vehicle when the forward
rail button passes the rail tip; RocketPy when the center of mass has traveled
the full rail length. The effective travel differs by roughly the button
spacing.

Neither is wrong. RocketPy reads lower, so **quote RocketPy for requirement
2.14** — it is the conservative number. Both are far above the 52 fps floor.

## 14.2 Drift, −10%

**Physical, and it originates during ascent — not descent.**

Decomposing the trajectory for a 10 mph crosswind, rail vertical:

| | Apogee position (upwind) | Descent travel (downwind) | Net landing |
|---|---:|---:|---:|
| OpenRocket | 570 ft | 893 ft | 323 ft downwind |
| RocketPy | 691 ft | 878 ft | 187 ft downwind |
| Difference | **21%** | **1.7%** | 42% |

The **descent phases agree to 1.7%**. The disagreement is entirely in ascent
weathercocking, and it traces directly to §14.1: RocketPy leaves the rail at
70.4 fps against OpenRocket's 78.8 fps, so it enters free flight at a larger
angle of attack relative to the wind —

$$\alpha_\text{RP} = \arctan\frac{4.5}{21.5} = 11.8°
\qquad
\alpha_\text{OR} = \arctan\frac{4.5}{24.0} = 10.6°$$

— weathercocks harder, and reaches apogee further upwind. A secondary
contribution comes from the different fin lift models (§4.3), which give
slightly different $C_{N\alpha}$ and hence different turn rates.

**Why the net difference is amplified.** Net drift is the *difference* between
an upwind apogee offset and a downwind descent — two numbers of similar
magnitude. A 21% difference in the first, against a 1.7% difference in the
second, leaves a 42% difference in the small remainder. This is ordinary
catastrophic cancellation, and it is why single-run drift is a fragile number.

Quote the **Monte Carlo landing ellipse**, which spans the plausible range of
wind conditions, rather than either single-run value.

> **A note on how this entry was corrected.** An earlier version of this
> document attributed the drift difference to OpenRocket's pink-noise wind
> turbulence. That was wrong: turning turbulence off in both tools left the
> difference essentially unchanged, which is how the real mechanism was found.
> If you inherit an explanation for a discrepancy, test it by removing the
> supposed cause. A plausible story is not evidence.

## 14.3 Max acceleration — a lesson in comparing like with like

Initially these differed by **216%** (8.83 g vs 27.92 g). Not a physics
disagreement: RocketPy's `max_acceleration` covers the *entire* flight and was
catching the parachute inflation transient, while OpenRocket's covers ascent.

The fix was to restrict both to the ascent phase, after which they agree to
0.03%. The handbook asks for this quantity to *"verify the vehicle is robust
enough to withstand the expected loads"* — a boost-phase structural question —
so ascent is the correct window anyway.

**The general lesson:** when two tools disagree wildly, suspect a definition
mismatch before suspecting physics. A 216% discrepancy is almost never a subtle
modeling difference.

## 14.4 What agreement does and does not prove

**Does prove:** two independent 6-DOF formulations, two integrators, two fin
aerodynamic theories, and two atmosphere implementations produce the same
trajectory from the same drag, thrust, and mass. That is a real check on the
dynamics, and on the framework's own bookkeeping.

**Does not prove:** that the drag coefficient is right. Both tools use the same
$C_D(M)$. If OpenRocket's drag estimate is 15% low, both tools are 15% low
together and agree beautifully while both being wrong.

This is not hypothetical. Teams routinely find post-flight that their pre-flight
drag was off by 10–20% — the synthetic example in §11.8 uses 18% for exactly
that reason. Only flight data closes that loop, which is precisely why the FRR
asks for it.

State the scope of the claim accurately in your reports. It is stronger to say
"the dynamics are cross-validated, and the drag is validated separately against
flight data" than to imply everything is confirmed by everything.

---

# 15. Appendices

## Appendix A — Requirements traceability

| Req | Constraint | Physics section |
|---|---|---|
| 2.1 | Apogee 4,000–6,000 ft AGL | §5 drag, §3.1 thrust, §13 dispersion |
| 2.3 | Declared target altitude | §13 (declare the distribution median) |
| 2.9 | Total impulse ≤ 5,120 N·s | §3.1 |
| 2.11 | Static stability ≥ 2.0 cal | §7 |
| 2.12 | Thrust-to-weight ≥ 5.0 | §3.1 |
| 2.14 | Rail exit ≥ 52 fps | §3.4, §10.1 |
| 2.20.6 | Mach < 1.0 | §5.4 |
| 2.20.7 | Ballast ≤ 10% | §6.1 |
| 3.1.1 | Main deploy ≥ 500 ft | §11.5 |
| 3.2 | KE ≤ 75 ft·lbf per section | §11.3, §11.4 |
| 3.10 | Drift ≤ 2,500 ft | §10, §11.5 |
| 3.11 | Descent ≤ 100 s | §11.5 |

## Appendix B — Constants

| Constant | Value |
|---|---|
| $g_0$ | 9.80665 m/s² |
| $R_\text{air}$ | 287.053 J/(kg·K) |
| $\gamma$ | 1.4 |
| ISA lapse rate $L$ | 0.0065 K/m |
| $g/(RL)$ | 5.2559 |
| $\rho_\text{ISA,SL}$ | 1.225 kg/m³ |
| $a_\text{ISA,SL}$ | 340.29 m/s |
| 1 ft·lbf | 1.3558179 J |
| 1 ft | 0.3048 m |
| 1 lb | 0.45359237 kg |

## Appendix C — Quaternion kinematics

A unit quaternion $\mathbf q = [q_0, q_1, q_2, q_3]$ with $|\mathbf q| = 1$
represents a rotation of angle $\theta$ about unit axis $\hat n$:

$$\mathbf q = \left[\cos\tfrac\theta2,\; \hat n \sin\tfrac\theta2\right]$$

**Derivation of the rate equation.** Let $\mathbf q(t)$ be the body's attitude.
Over a small interval $\Delta t$ the body rotates by angle
$|\vec\omega|\Delta t$ about $\hat\omega$, an incremental quaternion

$$\Delta\mathbf q = \left[\cos\frac{|\vec\omega|\Delta t}{2},\;
\hat\omega\sin\frac{|\vec\omega|\Delta t}{2}\right]$$

Composing rotations is quaternion multiplication, so
$\mathbf q(t+\Delta t) = \mathbf q(t)\otimes\Delta\mathbf q$. For small
$\Delta t$, $\cos(\cdot)\to 1$ and $\sin(\cdot)\to |\vec\omega|\Delta t/2$:

$$\Delta \mathbf q \approx \left[1,\; \frac{\vec\omega\,\Delta t}{2}\right]$$

Therefore

$$\mathbf q(t+\Delta t) - \mathbf q(t)
\approx \mathbf q \otimes \left[0, \tfrac{\vec\omega \Delta t}{2}\right]$$

and dividing by $\Delta t$:

$$\dot{\mathbf q} = \tfrac12\,\mathbf q\otimes[0,\vec\omega] \qquad\blacksquare$$

In matrix form:

$$
\begin{bmatrix}\dot q_0\\ \dot q_1\\ \dot q_2\\ \dot q_3\end{bmatrix}
= \frac12
\begin{bmatrix}
0 & -\omega_x & -\omega_y & -\omega_z\\
\omega_x & 0 & \omega_z & -\omega_y\\
\omega_y & -\omega_z & 0 & \omega_x\\
\omega_z & \omega_y & -\omega_x & 0
\end{bmatrix}
\begin{bmatrix}q_0\\ q_1\\ q_2\\ q_3\end{bmatrix}
$$

**Why not Euler angles.** Euler angles suffer gimbal lock: at 90° pitch two axes
align and one degree of freedom is lost, with the rate equations becoming
singular. A rocket passes through 90° pitch at apogee on any windy day, so this
is not an edge case. Quaternions have no singularity. Their cost is a redundant
fourth parameter and the need to renormalize periodically, since numerical
integration slowly drifts $|\mathbf q|$ away from 1.

## Appendix D — Descent time with a non-constant density

§11.5 assumed constant descent rate per phase. Since $V_t \propto
\rho^{-1/2}$ and $\rho$ falls with altitude, the vehicle descends faster higher
up. The exact time is

$$t = \int_{h_m}^{h_a} \frac{dh}{V_t(h)}
= \int_{h_m}^{h_a} \sqrt{\frac{\rho(h)\,C_d S}{2mg}}\;dh$$

Using the ISA profile, $\rho(h) = \rho_0(1 - Lh/T_0)^{g/(RL)-1}$, this is
analytic but unilluminating. The practical point is the *sign* of the
correction: using sea-level density overestimates drogue-phase descent time,
because the drogue phase happens where the air is thinner and the vehicle falls
faster.

This is visible in §11.2, where the drogue hand-calculation matches the
simulation only after using density at altitude (107.6 fps) rather than sea
level (104.7 fps). Both tools integrate this properly; the correction matters
only when you are checking them by hand.

## Appendix E — Further reading

**Primary sources**

- Barrowman, J. S., *The Practical Calculation of the Aerodynamic
  Characteristics of Slender Finned Vehicles*, M.S. thesis, Catholic University
  of America, 1967. The original method.
- Niskanen, S., *OpenRocket Technical Documentation*. The authoritative
  reference for OpenRocket's aerodynamic and simulation models, including the
  skin-friction and base-drag correlations of §5. Distributed with OpenRocket
  and available at <https://openrocket.info/documentation.html>.
- Ceotto et al., *RocketPy: Six Degree-of-Freedom Rocket Trajectory Simulator*,
  Journal of Aerospace Engineering, 2021.

**Texts**

- Hoerner, S. F., *Fluid-Dynamic Drag*, 1965. The source of many drag
  correlations still in use.
- Box, Bishop & Hunt, *Estimating the dynamic and aerodynamic parameters of
  passively controlled high power rockets for flight simulation*, 2009. The
  clearest treatment of dynamic stability at this scale.
- Anderson, J. D., *Fundamentals of Aerodynamics*. For the compressible-flow and
  thin-airfoil background.

**Code, which is the ground truth**

- `slisim/or_bridge.py` — how OpenRocket is driven, and what is extracted
- `slisim/rocketpy_model.py` — the RocketPy model and the shared-input boundary
- `slisim/requirements.py` — every requirement check, citing its paragraph
- `.venv/Lib/site-packages/rocketpy/simulation/flight.py` — RocketPy's equations
  of motion, including `u_dot_parachute`

---

*Numerical values are from the framework's template vehicle
(`config/vehicles/full_scale.yaml`), reproducible with
`python scripts/run_nominal.py`.
Verified on OpenRocket 24.12 and RocketPy 1.13.0.*
