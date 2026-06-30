import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize

SURFACE_FILE = r"C:\Users\vcsa0\Downloads\surface_points.xlsx"

WINDOW = 500
FORECAST = 250

moneyness = ["DOTM call", "OTM call", "ATM call", "ATM put", "OTM put", "DOTM put"]
maturities = ["7-45d", "45-90d", "90-180d", "180-360d"]

##############DATA#################
df = pd.read_excel(SURFACE_FILE)
df["QUOTE_DATE"] = pd.to_datetime(df["QUOTE_DATE"])
df["LOG_IV"] = df["LOG_IV"].astype(float)
df["M"] = df["KS"].astype(float)
df["TAU"] = df["DTE"].astype(float) / 365.0

df["MON_LABEL"] = pd.Categorical(df["MON_LABEL"], categories=moneyness, ordered=True)
df["MAT_LABEL"] = pd.Categorical(df["MAT_LABEL"], categories=maturities, ordered=True)
df = df.sort_values(["QUOTE_DATE", "MON_LABEL", "MAT_LABEL"])

days = []
bucket_labels = []   
for date, day_data in df.groupby("QUOTE_DATE", sort=True):
    m = day_data["M"].values
    tau = day_data["TAU"].values
    M_t = np.column_stack([np.ones(len(m)), m, m * m, tau, m * tau])
    y_t = day_data["LOG_IV"].values
    days.append((M_t, y_t))
    if not bucket_labels:  
        bucket_labels = [f"{mon[:4]} {mat}"
                         for mon, mat in zip(day_data["MON_LABEL"], day_data["MAT_LABEL"])]

print(f"Days loaded: {len(days):,}")

def gas_filter(a, b, sigma2, beta_bar, day_list, beta_start):
    A = a * np.eye(5)
    B = b * np.eye(5)

    H     = sigma2 * np.eye(24)
    H_inv = (1.0 / sigma2) * np.eye(24)

    beta   = beta_start.copy()
    loglik = 0.0
    forecast_list = []
    realized_list = []

    for (M_t, y_t) in day_list:
        forecast = M_t @ beta
        eps = y_t - forecast
        loglik += -0.5 * (np.log(np.linalg.det(2 * np.pi * H)) + eps @ (H_inv @ eps))
        forecast_list.append(forecast)
        realized_list.append(y_t)
        xi = A @ np.linalg.inv(M_t.T @ H_inv @ M_t) @ M_t.T @ H_inv @ eps
        beta = (np.eye(5) - B) @ beta_bar + B @ beta + xi

    return loglik, forecast_list, realized_list, beta


def neg_loglik(params):
    a, b, sigma2 = params[0], params[1], params[2]
    beta_bar = params[3:]
    loglik, _, _, _ = gas_filter(a, b, sigma2, beta_bar, EST_DAYS, beta_bar)
    return -loglik


bounds = [(1e-4, 1.0), (1e-4, 0.9999), (1e-6, None)] + [(None, None)] * 5

#############ROLLING WINDOW################
EST_DAYS = []        

oos_forecasts = []
oos_realized = []
oos_loglik = 0.0
block_estimates = []

print("\nRolling estimation...")
start = 0
block = 0
while start + WINDOW < len(days):
    block += 1

    est_days      = days[start:start + WINDOW]
    forecast_days = days[start + WINDOW:start + WINDOW + FORECAST]

    mean_logiv = np.mean([y.mean() for (M_t, y) in est_days])
    start_params = [0.8, 0.95, 0.01, mean_logiv, 0.0, 0.0, 0.0, 0.0]

    EST_DAYS = est_days
    result = minimize(neg_loglik, start_params, method="L-BFGS-B", bounds=bounds)

    a, b, sigma2 = result.x[0], result.x[1], result.x[2]
    beta_bar = result.x[3:8]

    _, _, _, beta_warm = gas_filter(a, b, sigma2, beta_bar, est_days, beta_bar)
    block_loglik, block_forecasts, block_realized, _ = gas_filter(
        a, b, sigma2, beta_bar, forecast_days, beta_warm)

    oos_loglik += block_loglik
    oos_forecasts.extend(block_forecasts)
    oos_realized.extend(block_realized)

    block_estimates.append([block, a, b, sigma2, result.success])
    print(f"block {block}: a = {a:.3f}  b = {b:.3f}  sigma2 = {sigma2:.5f}  "
          f"converged = {result.success}")

    start += FORECAST

#############OUTPUT################
forecasts = np.array(oos_forecasts)  
realized = np.array(oos_realized)
errors = realized - forecasts

mse = np.mean(errors ** 2)
mae = np.mean(np.abs(errors))

k = 8
aic = 2 * k - 2 * oos_loglik

print("\n" + "=" * 50)
print("OUT-OF-SAMPLE PERFORMANCE (plain GAS)")
print("=" * 50)
print(f"Out-of-sample days  : {forecasts.shape[0]:,}")
print(f"MSE                 : {mse:.6f}")
print(f"MAE                 : {mae:.6f}")
print(f"Total log-likelihood: {oos_loglik:.2f}")
print(f"AIC                 : {aic:.2f}")

print("\nPer-block estimates:")
print("block      a         b        sigma2     converged")
for row in block_estimates:
    print(f"{row[0]:<7}{row[1]:>8.3f}{row[2]:>10.3f}{row[3]:>11.5f}     {row[4]}")

corr = np.corrcoef(errors.T)

off_diag = corr[~np.eye(24, dtype=bool)] 
print(f"\nAverage off-diagonal residual correlation: {off_diag.mean():.3f}")

plt.figure(figsize=(9, 8))
im = plt.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
plt.colorbar(im, label="Correlation")
plt.xticks(range(24), bucket_labels, rotation=90, fontsize=6)
plt.yticks(range(24), bucket_labels, fontsize=6)
plt.title("Correlation of out-of-sample residuals across the 24 buckets")
plt.tight_layout()
plt.savefig("residual_correlation_heatmap.png", dpi=300, bbox_inches="tight")
plt.show()
