"""Unit conversions.

The USLI handbook states every requirement in imperial units (feet, ft-lbf,
fps, pounds) while both simulators work in SI.  Every number that crosses the
boundary between "what the handbook says" and "what the solver computes" goes
through this module, so the conversion lives in exactly one place.

Convention: `X_to_Y(value)` converts *from* X *to* Y.
"""

from __future__ import annotations

# --- Length -----------------------------------------------------------------
FT_PER_M = 3.280839895013123
IN_PER_M = 39.37007874015748


def m_to_ft(x): return x * FT_PER_M
def ft_to_m(x): return x / FT_PER_M
def m_to_in(x): return x * IN_PER_M
def in_to_m(x): return x / IN_PER_M


# --- Mass -------------------------------------------------------------------
LB_PER_KG = 2.204622621848776
OZ_PER_KG = 35.27396194958041


def kg_to_lb(x): return x * LB_PER_KG
def lb_to_kg(x): return x / LB_PER_KG
def kg_to_oz(x): return x * OZ_PER_KG
def oz_to_kg(x): return x / OZ_PER_KG


# --- Velocity ---------------------------------------------------------------
def mps_to_fps(x): return x * FT_PER_M
def fps_to_mps(x): return x / FT_PER_M
def mps_to_mph(x): return x * 2.2369362920544
def mph_to_mps(x): return x / 2.2369362920544


# --- Energy -----------------------------------------------------------------
# 1 ft-lbf = 1.3558179483314004 J
J_PER_FTLBF = 1.3558179483314004


def j_to_ftlbf(x): return x / J_PER_FTLBF
def ftlbf_to_j(x): return x * J_PER_FTLBF


# --- Misc -------------------------------------------------------------------
def c_to_k(x): return x + 273.15
def k_to_c(x): return x - 273.15
def f_to_k(x): return (x - 32.0) * 5.0 / 9.0 + 273.15
def k_to_f(x): return (x - 273.15) * 9.0 / 5.0 + 32.0
def inhg_to_pa(x): return x * 3386.388640341
def pa_to_inhg(x): return x / 3386.388640341

G0 = 9.80665  # m/s^2, standard gravity
