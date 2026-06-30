import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"

import numpy as np
from scipy.optimize import minimize
import matplotlib.pyplot as plt
import pandas as pd
from multiprocessing import Pool
from tqdm import tqdm

##############DGP#################
moneyness = [0.9, 0.98, 1.05, 1.15, 1.30, 1.50]
maturities = [10/255, 50/255, 100/255, 180/255]

M_rows = []
for m in moneyness:
    for tau in maturities:
        row = [1, m, m*m, tau, m*tau]
        M_rows.append(row)
M = np.array(M_rows)

true_a = 0.05
true_b = 0.99
true_sigma2 = 1.0
true_c = [0.05, 0.05, 0.05, 0.05, 0.05] 

A        = true_a * np.eye(5)
B        = true_b * np.eye(5)
beta_bar = np.zeros(5)

C_true     = np.diag(true_c)
Sigma_true = true_sigma2 * np.eye(24) + M @ C_true @ M.T
Sigma_true_inv = np.linalg.inv(Sigma_true)

T = 2000

#############ESTIMATION ################
def gas_filter(a, b, sigma2, beta_bar, c, Y):
    A = a * np.eye(5)
    B = b * np.eye(5)

    C     = np.diag(c)
    Sigma = sigma2 * np.eye(24) + M @ C @ M.T
    Sigma_inv = np.linalg.inv(Sigma)

    beta   = np.zeros(5)
    loglik = 0.0
    beta_hat = []

    for t in range(len(Y)):
        eps = Y[t] - M @ beta
        loglik += -0.5 * (np.log(np.linalg.det(2 * np.pi * Sigma)) + eps @ (Sigma_inv @ eps))
        beta_hat.append(beta)
        xi = A @ np.linalg.inv(M.T @ Sigma_inv @ M) @ M.T @ Sigma_inv @ eps
        beta = (np.eye(5) - B) @ beta_bar + B @ beta + xi
    return loglik, np.array(beta_hat)

def neg_loglik(params, Y):
    a, b, sigma2 = params[0], params[1], params[2]
    beta_bar = params[3:8]
    c        = params[8:13]
    loglik, _ = gas_filter(a, b, sigma2, beta_bar, c, Y)
    return -loglik

start  = [0.10, 0.90, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.01, 0.01, 0.01, 0.01, 0.01]
bounds = ([(1e-4, 1.0), (1e-4, 0.9999), (1e-6, None)]
          + [(None, None)] * 5
          + [(0.0, None)] * 5)

names = ["a", "b", "sigma2",
         "beta_bar_1", "beta_bar_2", "beta_bar_3", "beta_bar_4", "beta_bar_5",
         "c_1", "c_2", "c_3", "c_4", "c_5"]
truth = [true_a, true_b, true_sigma2, 0.0, 0.0, 0.0, 0.0, 0.0] + true_c

PROGRESS_CSV = r"C:\Users\vcsa0\Downloads\adjusted_gas_estimates.csv"
OUTPUT_XLSX  = r"C:\Users\vcsa0\Downloads\adjusted_gas_estimates.xlsx"

#############ONE REPLICATION################
def run_one_replication(seed):
    np.random.seed(seed)
    beta = np.zeros(5)
    Y_history = []
    for t in range(T):
        eps = np.random.multivariate_normal(np.zeros(24), Sigma_true)
        y = M @ beta + eps
        Y_history.append(y)
        xi = A @ np.linalg.inv(M.T @ Sigma_true_inv @ M) @ M.T @ Sigma_true_inv @ eps
        beta = (np.eye(5) - B) @ beta_bar + B @ beta + xi
    Y = np.array(Y_history)

    result = minimize(neg_loglik, start, args=(Y,), method="L-BFGS-B", bounds=bounds)
    return [seed] + list(result.x)

#############MONTE CARLO ################
if __name__ == "__main__":
    S = 10000
    seeds = list(range(S))

    if not os.path.exists(PROGRESS_CSV):
        pd.DataFrame(columns=["seed"] + names).to_csv(PROGRESS_CSV, index=False)

    done = 0
    try:
        with Pool(processes=14) as pool:
            for row in tqdm(pool.imap_unordered(run_one_replication, seeds),
                            total=S, desc="adjusted simulations"):
                pd.DataFrame([row]).to_csv(PROGRESS_CSV, mode="a", header=False, index=False)
                done += 1
    except KeyboardInterrupt:
        print(f"\nStopped early. {done} simulations saved so far.")

    ###############BUILD THE EXCEL FILE ################
    saved = pd.read_csv(PROGRESS_CSV)
    saved.to_excel(OUTPUT_XLSX, index=False)
    estimates = saved[names].values
    n_done = len(estimates)
    print(f"\nReplications saved: {n_done}")
    print(f"Saved Excel file  : {OUTPUT_XLSX}")

    ###############OUTPUT TABLE + HISTOGRAMS################
    if n_done > 0:
        print("")
        print("param        true      mean      bias      std       rmse")
        for k in range(13):
            column = estimates[:, k]
            bias_k = column.mean() - truth[k]
            rmse_k = np.sqrt(np.mean((column - truth[k]) ** 2))
            print(f"{names[k]:<11}"
                  f"{truth[k]:>8.4f}"
                  f"{column.mean():>10.4f}"
                  f"{bias_k:>10.4f}"
                  f"{column.std():>10.4f}"
                  f"{rmse_k:>10.4f}")

        for k in range(13):
            plt.figure()
            plt.hist(estimates[:, k], bins=30, color="steelblue", edgecolor="black")
            plt.axvline(truth[k], color="red", lw=2, label="true value")
            plt.title(names[k])
            plt.legend()
            plt.show()
