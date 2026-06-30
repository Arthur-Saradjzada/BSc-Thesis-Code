import numpy as np
import pandas as pd

from scipy.optimize import minimize
from scipy.stats import norm, chi2


SURFACE_FILE = r"C:\Users\vcsa0\Downloads\surface_points.xlsx"

WINDOW = 500
FORECAST = 250
VAR_ALPHA = 0.01       

moneyness = ["DOTM call", "OTM call", "ATM call", "ATM put", "OTM put", "DOTM put"]
maturities = ["7-45d", "45-90d", "90-180d", "180-360d"]


df = pd.read_excel(SURFACE_FILE)
df["QUOTE_DATE"] = pd.to_datetime(df["QUOTE_DATE"])
df["LOG_IV"] = df["LOG_IV"].astype(float)
df["M"] = df["KS"].astype(float)
df["TAU"] = df["DTE"].astype(float) / 365.0

df["MON_LABEL"] = pd.Categorical(df["MON_LABEL"], categories=moneyness, ordered=True)
df["MAT_LABEL"] = pd.Categorical(df["MAT_LABEL"], categories=maturities, ordered=True)
df = df.sort_values(["QUOTE_DATE", "MON_LABEL", "MAT_LABEL"])

days = []

for date, day_data in df.groupby("QUOTE_DATE", sort=True):
    m = day_data["M"].values
    tau = day_data["TAU"].values

    M_t = np.column_stack([
        np.ones(len(m)),
        m,
        m * m,
        tau,
        m * tau
    ])

    y_t = day_data["LOG_IV"].values
    days.append((M_t, y_t))

print(f"Days loaded: {len(days):,}")


def gas_filter_plain(a, b, sigma2, beta_bar, day_list, beta_start):
    A = a * np.eye(5)
    B = b * np.eye(5)

    H = sigma2 * np.eye(24)
    H_inv = (1.0 / sigma2) * np.eye(24)

    beta = beta_start.copy()
    loglik = 0.0
    loglik_list = []
    forecast_list = []
    realized_list = []

    for (M_t, y_t) in day_list:
        forecast = M_t @ beta
        eps = y_t - forecast

        ll = -0.5 * (
            np.log(np.linalg.det(2 * np.pi * H))
            + eps @ (H_inv @ eps)
        )

        loglik += ll
        loglik_list.append(ll)
        forecast_list.append(forecast)
        realized_list.append(y_t)

        xi = A @ np.linalg.inv(M_t.T @ H_inv @ M_t) @ M_t.T @ H_inv @ eps
        beta = (np.eye(5) - B) @ beta_bar + B @ beta + xi

    return loglik, loglik_list, forecast_list, realized_list, beta


def neg_loglik_plain(params):
    a, b, sigma2 = params[0], params[1], params[2]
    beta_bar = params[3:]

    loglik, _, _, _, _ = gas_filter_plain(
        a, b, sigma2, beta_bar, EST_DAYS, beta_bar
    )

    return -loglik


bounds_plain = (
    [(1e-4, 1.0), (1e-4, 0.9999), (1e-6, None)]
    + [(None, None)] * 5
)


def gas_filter_adjusted(a, b, sigma2, beta_bar, c, day_list, beta_start):
    A = a * np.eye(5)
    B = b * np.eye(5)
    C = np.diag(c)

    beta = beta_start.copy()
    loglik = 0.0
    loglik_list = []
    forecast_list = []
    realized_list = []

    for (M_t, y_t) in day_list:
        Sigma = sigma2 * np.eye(24) + M_t @ C @ M_t.T
        Sigma_inv = np.linalg.inv(Sigma)

        forecast = M_t @ beta
        eps = y_t - forecast

        ll = -0.5 * (
            np.log(np.linalg.det(2 * np.pi * Sigma))
            + eps @ (Sigma_inv @ eps)
        )

        loglik += ll
        loglik_list.append(ll)
        forecast_list.append(forecast)
        realized_list.append(y_t)

        xi = A @ np.linalg.inv(M_t.T @ Sigma_inv @ M_t) @ M_t.T @ Sigma_inv @ eps
        beta = (np.eye(5) - B) @ beta_bar + B @ beta + xi

    return loglik, loglik_list, forecast_list, realized_list, beta


def neg_loglik_adjusted(params):
    a, b, sigma2 = params[0], params[1], params[2]
    beta_bar = params[3:8]
    c = params[8:13]

    loglik, _, _, _, _ = gas_filter_adjusted(
        a, b, sigma2, beta_bar, c, EST_DAYS, beta_bar
    )

    return -loglik


bounds_adjusted = (
    [(1e-4, 1.0), (1e-4, 0.9999), (1e-6, None)]
    + [(None, None)] * 5
    + [(0.0, None)] * 5
)


def add_var_plain_records(var_records, model_name, forecasts, realized_values, sigma2):
    q = norm.ppf(VAR_ALPHA)

    for forecast, realized in zip(forecasts, realized_values):
        N = len(realized)

        p_hat = np.mean(forecast)
        p_real = np.mean(realized)

        var_p = sigma2 / N
        var_99 = p_hat + q * np.sqrt(var_p)

        violation = int(p_real < var_99)

        var_records.append({
            "MODEL": model_name,
            "P_REALIZED": p_real,
            "P_FORECAST": p_hat,
            "VAR_99": var_99,
            "VIOLATION": violation
        })


def add_var_adjusted_records(var_records, model_name, forecasts, realized_values, day_list, sigma2, c):
    q = norm.ppf(VAR_ALPHA)
    C = np.diag(c)

    for forecast, realized, (M_t, y_t) in zip(forecasts, realized_values, day_list):
        N = len(realized)

        Sigma = sigma2 * np.eye(N) + M_t @ C @ M_t.T
        one = np.ones(N)

        p_hat = np.mean(forecast)
        p_real = np.mean(realized)

        var_p = (one @ Sigma @ one) / (N ** 2)
        var_99 = p_hat + q * np.sqrt(var_p)

        violation = int(p_real < var_99)

        var_records.append({
            "MODEL": model_name,
            "P_REALIZED": p_real,
            "P_FORECAST": p_hat,
            "VAR_99": var_99,
            "VIOLATION": violation
        })


EST_DAYS = []

daily_loglik_plain = []
daily_loglik_adjusted = []

oos_loglik_plain = 0.0
oos_loglik_adjusted = 0.0

oos_realized = []
oos_forecasts_plain = []
oos_forecasts_adjusted = []

var_records = []

print("\nRolling estimation (plain normal vs adjusted normal)...")

start = 0
block = 0

while start + WINDOW < len(days):
    block += 1

    est_days = days[start:start + WINDOW]
    forecast_days = days[start + WINDOW:start + WINDOW + FORECAST]

    mean_logiv = np.mean([y.mean() for (M_t, y) in est_days])

    EST_DAYS = est_days

    start_plain = [
        0.8,
        0.95,
        0.01,
        mean_logiv,
        0.0,
        0.0,
        0.0,
        0.0
    ]

    res_p = minimize(
        neg_loglik_plain,
        start_plain,
        method="L-BFGS-B",
        bounds=bounds_plain
    )

    a_p, b_p, s2_p = res_p.x[0], res_p.x[1], res_p.x[2]
    bb_p = res_p.x[3:8]

    _, _, _, _, warm_p = gas_filter_plain(
        a_p, b_p, s2_p, bb_p, est_days, bb_p
    )

    ll_p, lllist_p, fc_p, rl_p, _ = gas_filter_plain(
        a_p, b_p, s2_p, bb_p, forecast_days, warm_p
    )

    start_adj = [
        0.8,
        0.95,
        0.01,
        mean_logiv,
        0.0,
        0.0,
        0.0,
        0.0,
        0.01,
        0.01,
        0.01,
        0.01,
        0.01
    ]

    res_a = minimize(
        neg_loglik_adjusted,
        start_adj,
        method="L-BFGS-B",
        bounds=bounds_adjusted
    )

    a_a, b_a, s2_a = res_a.x[0], res_a.x[1], res_a.x[2]
    bb_a = res_a.x[3:8]
    c_a = res_a.x[8:13]

    _, _, _, _, warm_a = gas_filter_adjusted(
        a_a, b_a, s2_a, bb_a, c_a, est_days, bb_a
    )

    ll_a, lllist_a, fc_a, rl_a, _ = gas_filter_adjusted(
        a_a, b_a, s2_a, bb_a, c_a, forecast_days, warm_a
    )

    add_var_plain_records(
        var_records=var_records,
        model_name="plain-normal",
        forecasts=fc_p,
        realized_values=rl_p,
        sigma2=s2_p
    )

    add_var_adjusted_records(
        var_records=var_records,
        model_name="adjusted-normal",
        forecasts=fc_a,
        realized_values=rl_a,
        day_list=forecast_days,
        sigma2=s2_a,
        c=c_a
    )

    oos_loglik_plain += ll_p
    oos_loglik_adjusted += ll_a

    daily_loglik_plain.extend(lllist_p)
    daily_loglik_adjusted.extend(lllist_a)

    oos_realized.extend(rl_p)
    oos_forecasts_plain.extend(fc_p)
    oos_forecasts_adjusted.extend(fc_a)

    print(
        f"block {block}: "
        f"plain a={a_p:.3f}  "
        f"adj a={a_a:.3f}  "
        f"mean_c={np.mean(c_a):.5f}  "
        f"plain ll={ll_p:.1f}  "
        f"adj ll={ll_a:.1f}  "
        f"conv {res_p.success}/{res_a.success}"
    )

    start += FORECAST


realized = np.array(oos_realized)

err_p = realized - np.array(oos_forecasts_plain)
err_a = realized - np.array(oos_forecasts_adjusted)

mse_p = np.mean(err_p ** 2)
mae_p = np.mean(np.abs(err_p))

mse_a = np.mean(err_a ** 2)
mae_a = np.mean(np.abs(err_a))

aic_p = 2 * 8 - 2 * oos_loglik_plain
aic_a = 2 * 13 - 2 * oos_loglik_adjusted


ll_plain = np.array(daily_loglik_plain)
ll_adj = np.array(daily_loglik_adjusted)

d = ll_adj - ll_plain
n = len(d)
d_bar = d.mean()

lag = int(np.floor(n ** (1.0 / 3.0)))
d_centered = d - d_bar

gamma0 = np.mean(d_centered ** 2)
lrv = gamma0

for h in range(1, lag + 1):
    w_h = 1.0 - h / (lag + 1.0)
    gamma_h = np.mean(d_centered[h:] * d_centered[:-h])
    lrv += 2.0 * w_h * gamma_h

dm_stat = d_bar / np.sqrt(lrv / n)

abs_dm = abs(dm_stat)

if abs_dm > 2.576:
    stars = "***"
elif abs_dm > 1.960:
    stars = "**"
elif abs_dm > 1.645:
    stars = "*"
else:
    stars = ""


var_df = pd.DataFrame(var_records)

var_summary_rows = []

for model_name, g in var_df.groupby("MODEL"):
    total = len(g)
    violations = int(g["VIOLATION"].sum())
    violation_rate = violations / total
    expected_violations = VAR_ALPHA * total

    var_summary_rows.append({
        "MODEL": model_name,
        "OBSERVATIONS": total,
        "VIOLATIONS": violations,
        "EXPECTED_VIOLATIONS": expected_violations,
        "VIOLATION_RATE": violation_rate,
        "EXPECTED_RATE": VAR_ALPHA
    })

var_summary = pd.DataFrame(var_summary_rows)


print("\n" + "=" * 60)
print("OUT-OF-SAMPLE PERFORMANCE: plain normal vs adjusted normal")
print("=" * 60)
print(f"Out-of-sample days   : {n:,}")
print(f"{'':20}{'plain':>14}{'adjusted':>14}")
print(f"{'MSE':20}{mse_p:>14.6f}{mse_a:>14.6f}")
print(f"{'MAE':20}{mae_p:>14.6f}{mae_a:>14.6f}")
print(f"{'log-likelihood':20}{oos_loglik_plain:>14.2f}{oos_loglik_adjusted:>14.2f}")
print(f"{'AIC':20}{aic_p:>14.2f}{aic_a:>14.2f}")

print("\n" + "=" * 60)
print("DIEBOLD-MARIANO TEST (adjusted vs plain benchmark)")
print("=" * 60)
print(f"Mean daily loglik gain (adjusted - plain): {d_bar:.4f}")
print(f"HAC lag length                           : {lag}")
print(f"DM statistic                             : {dm_stat:.3f} {stars}")
print("(positive DM => adjusted forecasts are more accurate; "
      "*** / ** / * = 1% / 5% / 10%)")

print("\n" + "=" * 60)
print("99% VaR VIOLATION TEST: CROSS-SECTIONAL AVERAGE LOG-IV")
print("=" * 60)
print(var_summary.to_string(index=False))
