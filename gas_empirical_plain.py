"""
gas_empirical_plain.py

Plain Gaussian score-driven (GAS) model fitted to the EMPIRICAL implied
volatility surface. Same model and recursion as the sanity check, now with
the real time-varying loadings M_t and observed log IV.

    (1)  log IV_t   = M_t beta_t + eps_t,        eps_t ~ N(0, H_t)
    (2)  beta_{t+1} = (I_p - B) beta_bar + B beta_t + xi_t
    (4)  xi_t       = A (M_t' H_t^{-1} M_t)^{-1} M_t' H_t^{-1} eps_t
    (5)  L(psi)     = -1/2 sum_t [ log|2 pi H_t| + eps_t' H_t^{-1} eps_t ]

Differences from the sanity check:
  - M is now time-varying M_t, read per day from factor_loadings_panel.csv
  - log IV_t is the real observed surface (raw IV transformed by log)
  - H_t = diag(h) is ESTIMATED (one variance per bucket), not assumed I
  - we estimate A, B, beta_bar, and h by maximum likelihood
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
import matplotlib.pyplot as plt
from pathlib import Path

LOADINGS_FILE = Path(r"C:\Users\vcsa0\Downloads\volatility_surface_panel.csv")

START_DATE = "2010-01-01"
END_DATE   = "2022-01-01"

LOADING_COLS = ["CONST", "KS", "KS_SQ", "TAU", "KS_TAU"]   # the 5 regressors


# Load the panel and build per-day arrays
df = pd.read_csv(LOADINGS_FILE)
df["QUOTE_DATE"] = pd.to_datetime(df["QUOTE_DATE"])
df = df[(df["QUOTE_DATE"] >= START_DATE) & (df["QUOTE_DATE"] < END_DATE)].copy()

# raw IV -> log IV (explicit transformation)
df["IV"]     = df["IV"].astype(float)
df["LOG_IV"] = np.log(df["IV"])

# the constant column of M_t
df["CONST"] = 1.0

# Stack into per-day matrices: M_list[t] is 24x5, Y_list[t] is 24x1
dates  = sorted(df["QUOTE_DATE"].unique())
M_list = []
Y_list = []
for d in dates:
    day = df[df["QUOTE_DATE"] == d]
    M_list.append(day[LOADING_COLS].values.astype(float))   # (24 x 5)
    Y_list.append(day["LOG_IV"].values.astype(float))        # (24,)

T = len(dates)
N, p = M_list[0].shape
print(f"Days T = {T},  buckets N = {N},  factors p = {p}")


def scaled_score(eps, M, H_inv, A):
    # xi_t = A (M' H^{-1} M)^{-1} M' H^{-1} eps_t
    S = M.T @ H_inv @ M
    g = M.T @ H_inv @ eps
    return A @ np.linalg.solve(S, g)


# Filter + exact Gaussian log-likelihood (5)
# params packs: a, b, beta_bar (p), log h (N)   -> estimated by ML
def unpack(params):
    a        = params[0]
    b        = params[1]
    beta_bar = params[2:2 + p]
    log_h    = params[2 + p:2 + p + N]
    h        = np.exp(log_h)               # ensure positive variances
    return a, b, beta_bar, h


def gas_filter_loglik(params, M_list, Y_list, return_filter=False):
    a, b, beta_bar, h = unpack(params)
    A  = a * np.eye(p)
    B  = b * np.eye(p)
    Ip = np.eye(p)

    H_inv   = np.diag(1.0 / h)              # H_t = diag(h), time-invariant here
    logdetH = np.sum(np.log(2.0 * np.pi * h))

    beta   = beta_bar.copy()               # start at long-run mean
    loglik = 0.0
    BETA_F = np.zeros((T, p))

    for t in range(T):
        M   = M_list[t]
        eps = Y_list[t] - M @ beta                                # (1)
        loglik    += -0.5 * (logdetH + eps @ (H_inv @ eps))       # (5)
        BETA_F[t]  = beta
        xi         = scaled_score(eps, M, H_inv, A)               # (4)
        beta       = (Ip - B) @ beta_bar + B @ beta + xi          # (2)

    if return_filter:
        return loglik, BETA_F
    return loglik


def neg_loglik(params, *args):
    return -gas_filter_loglik(params, *args)


# Starting values: OLS-style initials
beta0 = np.linalg.solve(M_list[0].T @ M_list[0], M_list[0].T @ Y_list[0])
x0    = np.concatenate([[0.05, 0.97], beta0, np.full(N, np.log(0.01))])

bounds = (
    [(1e-4, 1.0), (1e-4, 0.9999)]          # a, b
    + [(-50, 50)] * p                       # beta_bar
    + [(np.log(1e-8), np.log(10))] * N      # log h
)

res = minimize(
    neg_loglik, x0, args=(M_list, Y_list),
    method="L-BFGS-B", bounds=bounds,
)

a_hat, b_hat, beta_bar_hat, h_hat = unpack(res.x)
print("\nMaximum likelihood results")
print(f"  A  estimated = {a_hat:.4f}")
print(f"  B  estimated = {b_hat:.4f}")
print(f"  beta_bar     = {np.round(beta_bar_hat, 3)}")
print(f"  loglik       = {-res.fun:,.2f}")
print(f"  converged    = {res.success}")

# Filtered factors
_, BETA_FILT = gas_filter_loglik(res.x, M_list, Y_list, return_filter=True)

# Plot the 5 filtered factors over time
fig, axes = plt.subplots(p, 1, figsize=(11, 12), sharex=True)
for j in range(p):
    axes[j].plot(dates, BETA_FILT[:, j], lw=0.7)
    axes[j].set_title(f"beta_{j+1}", fontsize=9)
axes[-1].set_xlabel("Date")
plt.tight_layout()
plt.savefig(r"C:\Users\vcsa0\Downloads\gas_empirical_factors.png",
            dpi=300, bbox_inches="tight")
plt.show()

print("\nDone. Saved: gas_empirical_factors.png")
