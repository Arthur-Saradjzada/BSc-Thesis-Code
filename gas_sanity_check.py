"""
gas_sanity_check.py

Sanity-check the plain Gaussian score-driven (GAS) model: simulate data from
the model with known parameters, then re-estimate them by maximum likelihood.
Recovering A = 0.05 and B = 0.99 confirms the recursion and likelihood are
correctly implemented before applying the model to the empirical surface.

    (1)  log IV_t   = M_t beta_t + eps_t,        eps_t ~ N(0, H_t)
    (2)  beta_{t+1} = (I_p - B) beta_bar + B beta_t + xi_t
    (4)  xi_t       = A (M_t' H_t^{-1} M_t)^{-1} M_t' H_t^{-1} eps_t
    (5)  L(psi)     = -1/2 sum_t [ log|2 pi H_t| + eps_t' H_t^{-1} eps_t ]

Settings: A = 0.05 I, B = 0.99 I, beta_bar = 0, beta_1 = 0, H = I, eps ~ N(0,I).
"""

import numpy as np
from scipy.optimize import minimize
import matplotlib.pyplot as plt

rng = np.random.default_rng(42)


# Loading matrix M (N x p): rows are [1, m, m^2, tau, m*tau]
m_grid   = np.array([0.90, 0.98, 1.05, 1.15, 1.30, 1.50])
tau_grid = np.array([10.0, 50.0, 100.0, 180.0]) / 255.0

rows = []
for m in m_grid:
    for tau in tau_grid:
        rows.append([1.0, m, m**2, tau, m * tau])

M = np.asarray(rows, dtype=float)
N, p = M.shape
print(f"M: {N} x {p}")


# Fixed model objects in full matrix form
H        = np.eye(N)                       # H_t = I_N
H_inv    = np.linalg.inv(H)
I_p      = np.eye(p)
beta_bar = np.zeros(p)

_, LOG_DET_2PI_H = np.linalg.slogdet(2.0 * np.pi * H)   # log|2 pi H|


def scaled_score(eps, M, H_inv, A):
    # xi_t = A (M' H^{-1} M)^{-1} M' H^{-1} eps_t
    S = M.T @ H_inv @ M
    g = M.T @ H_inv @ eps
    return A @ np.linalg.solve(S, g)


# Simulate the DGP
T_total = 2000
A_true  = 0.05 * I_p
B_true  = 0.99 * I_p
chol_H  = np.linalg.cholesky(H)

beta      = np.zeros(p)
Y         = np.zeros((T_total, N))
BETA_TRUE = np.zeros((T_total, p))

for t in range(T_total):
    eps          = chol_H @ rng.standard_normal(N)        # eps_t ~ N(0, H)
    Y[t]         = M @ beta + eps                         # (1)
    BETA_TRUE[t] = beta
    xi           = scaled_score(eps, M, H_inv, A_true)    # (4)
    beta         = (I_p - B_true) @ beta_bar + B_true @ beta + xi   # (2)

print(f"Simulated T = {T_total}, true A = 0.05, true B = 0.99")


# Filter + exact log-likelihood (5) for candidate (a, b)
def gas_filter_loglik(params, Y, M, H_inv, LOG_DET_2PI_H, beta_bar,
                      return_filter=False):
    a, b   = params
    T, N   = Y.shape
    p      = M.shape[1]
    A      = a * np.eye(p)
    B      = b * np.eye(p)
    Ip     = np.eye(p)

    beta   = np.zeros(p)
    loglik = 0.0
    BETA_F = np.zeros((T, p))

    for t in range(T):
        eps        = Y[t] - M @ beta                                  # (1)
        loglik    += -0.5 * (LOG_DET_2PI_H + eps @ (H_inv @ eps))     # (5)
        BETA_F[t]  = beta
        xi         = scaled_score(eps, M, H_inv, A)                   # (4)
        beta       = (Ip - B) @ beta_bar + B @ beta + xi              # (2)

    if return_filter:
        return loglik, BETA_F
    return loglik


def neg_loglik(params, *args):
    return -gas_filter_loglik(params, *args)


# Maximum likelihood estimation of (A, B)
x0 = np.array([0.10, 0.90])                # deliberately wrong start
res = minimize(
    neg_loglik, x0,
    args=(Y, M, H_inv, LOG_DET_2PI_H, beta_bar),
    method="L-BFGS-B",
    bounds=[(1e-4, 1.0), (1e-4, 0.9999)],
)

a_hat, b_hat = res.x
print("\nMaximum likelihood results")
print(f"  A: true = 0.0500   estimated = {a_hat:.4f}")
print(f"  B: true = 0.9900   estimated = {b_hat:.4f}")
print(f"  loglik at optimum = {-res.fun:,.2f}")
print(f"  converged = {res.success}")


# Verify filtered factors match the true factors
_, BETA_FILT = gas_filter_loglik(
    res.x, Y, M, H_inv, LOG_DET_2PI_H, beta_bar, return_filter=True
)

print("\nCorrelation true vs filtered factors:")
for j in range(p):
    c = np.corrcoef(BETA_TRUE[:, j], BETA_FILT[:, j])[0, 1]
    print(f"  beta_{j+1}: {c:.4f}")


# Plot
fig, axes = plt.subplots(p, 1, figsize=(10, 12), sharex=True)
for j in range(p):
    axes[j].plot(BETA_TRUE[:, j], lw=1.0, label="true")
    axes[j].plot(BETA_FILT[:, j], lw=0.8, ls="--", label="filtered")
    axes[j].set_title(f"beta_{j+1}", fontsize=9)
    axes[j].legend(fontsize=7, loc="upper right")
axes[-1].set_xlabel("time")
plt.tight_layout()
plt.savefig("gas_simulation_check.png", dpi=300, bbox_inches="tight")
plt.show()

print("\nDone. Saved: gas_simulation_check.png")
