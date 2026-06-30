import numpy as np
import pandas as pd

from scipy.special import gammaln
from scipy.optimize import minimize
from scipy.stats import norm, t as student_t, chi2


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


def gas_filter_normal(a, b, sigma2, beta_bar, day_list, beta_start):
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


def neg_loglik_normal(params):
    a, b, sigma2 = params[0], params[1], params[2]
    beta_bar = params[3:]

    loglik, _, _, _, _ = gas_filter_normal(
        a, b, sigma2, beta_bar, EST_DAYS, beta_bar
    )

    return -loglik


bounds_normal = (
    [(1e-4, 1.0), (1e-4, 0.9999), (1e-6, None)]
    + [(None, None)] * 5
)


def gas_filter_adjusted_t(a, b, sigma2, beta_bar, c, nu, day_list, beta_start):
    A = a * np.eye(5)
    B = b * np.eye(5)
    C = np.diag(c)
    N = 24

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
        quad = eps @ (Sigma_inv @ eps)

        ll = (
            gammaln((nu + N) / 2.0)
            - gammaln(nu / 2.0)
            - 0.5 * np.log(np.linalg.det((nu - 2) * np.pi * Sigma))
            - (nu + N) / 2.0 * np.log(1.0 + quad / (nu - 2))
        )

        loglik += ll
        loglik_list.append(ll)
        forecast_list.append(forecast)
        realized_list.append(y_t)

        weight = (1.0 + (N + 2.0) / nu) / (1.0 + quad / (nu - 2))
        xi = weight * A @ np.linalg.inv(M_t.T @ Sigma_inv @ M_t) @ M_t.T @ Sigma_inv @ eps

        beta = (np.eye(5) - B) @ beta_bar + B @ beta + xi

    return loglik, loglik_list, forecast_list, realized_list, beta


def neg_loglik_adjusted_t(params):
    a, b, sigma2 = params[0], params[1], params[2]
    beta_bar = params[3:8]
    c = params[8:13]
    nu = params[13]

    loglik, _, _, _, _ = gas_filter_adjusted_t(
        a, b, sigma2, beta_bar, c, nu, EST_DAYS, beta_bar
    )

    return -loglik


bounds_adjusted_t = (
    [(1e-4, 1.0), (1e-4, 0.9999), (1e-6, None)]
    + [(None, None)] * 5
    + [(0.0, None)] * 5
    + [(2.1, 100.0)]
)


def add_var_normal_records(var_records, model_name, forecasts, realized_values, sigma2):
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


def add_var_adjusted_t_records(var_records, model_name, forecasts, realized_values, day_list,
                               sigma2, c, nu):
    C = np.diag(c)
    q = np.sqrt((nu - 2.0) / nu) * student_t.ppf(VAR_ALPHA, df=nu)

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

daily_loglik_normal = []
daily_loglik_adjt = []

oos_loglik_normal = 0.0
oos_loglik_adjt = 0.0

oos_realized = []
oos_forecasts_normal = []
oos_forecasts_adjt = []

var_records = []

print("\nRolling estimation (plain normal vs adjusted t)...")

start = 0
block = 0

while start + WINDOW < len(days):
    block += 1

    est_days = days[start:start + WINDOW]
    forecast_days = days[start + WINDOW:start + WINDOW + FORECAST]

    mean_logiv = np.mean([y.mean() for (M_t, y) in est_days])

    EST_DAYS = est_days

    start_n = [
        0.8,
        0.95,
        0.01,
        mean_logiv,
        0.0,
        0.0,
        0.0,
        0.0
    ]

    res_n = minimize(
        neg_loglik_normal,
        start_n,
        method="L-BFGS-B",
        bounds=bounds_normal
    )

    a_n, b_n, s2_n = res_n.x[0], res_n.x[1], res_n.x[2]
    bb_n = res_n.x[3:8]

    _, _, _, _, warm_n = gas_filter_normal(
        a_n, b_n, s2_n, bb_n, est_days, bb_n
    )

    ll_n, lllist_n, fc_n, rl_n, _ = gas_filter_normal(
        a_n, b_n, s2_n, bb_n, forecast_days, warm_n
    )

    start_at = [
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
        0.01,
        8.0
    ]

    res_at = minimize(
        neg_loglik_adjusted_t,
        start_at,
        method="L-BFGS-B",
        bounds=bounds_adjusted_t
    )

    a_at, b_at, s2_at = res_at.x[0], res_at.x[1], res_at.x[2]
    bb_at = res_at.x[3:8]
    c_at = res_at.x[8:13]
    nu_at = res_at.x[13]

    _, _, _, _, warm_at = gas_filter_adjusted_t(
        a_at, b_at, s2_at, bb_at, c_at, nu_at, est_days, bb_at
    )

    ll_at, lllist_at, fc_at, rl_at, _ = gas_filter_adjusted_t(
        a_at, b_at, s2_at, bb_at, c_at, nu_at, forecast_days, warm_at
    )

    add_var_normal_records(
        var_records=var_records,
        model_name="plain-normal",
        forecasts=fc_n,
        realized_values=rl_n,
        sigma2=s2_n
    )

    add_var_adjusted_t_records(
        var_records=var_records,
        model_name="adjusted-t",
        forecasts=fc_at,
        realized_values=rl_at,
        day_list=forecast_days,
        sigma2=s2_at,
        c=c_at,
        nu=nu_at
    )

    oos_loglik_normal += ll_n
    oos_loglik_adjt += ll_at

    daily_loglik_normal.extend(lllist_n)
    daily_loglik_adjt.extend(lllist_at)

    oos_realized.extend(rl_n)
    oos_forecasts_normal.extend(fc_n)
    oos_forecasts_adjt.extend(fc_at)

    print(
        f"block {block}: "
        f"normal a={a_n:.3f}  "
        f"adj-t a={a_at:.3f}  "
        f"nu={nu_at:.2f}  "
        f"mean_c={np.mean(c_at):.5f}  "
        f"normal ll={ll_n:.1f}  "
        f"adj-t ll={ll_at:.1f}  "
        f"conv {res_n.success}/{res_at.success}"
    )

    start += FORECAST


realized = np.array(oos_realized)

err_n = realized - np.array(oos_forecasts_normal)
err_at = realized - np.array(oos_forecasts_adjt)

mse_n = np.mean(err_n ** 2)
mae_n = np.mean(np.abs(err_n))

mse_at = np.mean(err_at ** 2)
mae_at = np.mean(np.abs(err_at))

aic_n = 2 * 8 - 2 * oos_loglik_normal
aic_at = 2 * 14 - 2 * oos_loglik_adjt


ll_n_arr = np.array(daily_loglik_normal)
ll_at_arr = np.array(daily_loglik_adjt)

d = ll_at_arr - ll_n_arr
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


print("\n" + "=" * 70)
print("OUT-OF-SAMPLE PERFORMANCE: plain normal vs adjusted t")
print("=" * 70)
print(f"Out-of-sample days   : {n:,}")
print(f"{'':20}{'normal':>16}{'adjusted-t':>16}")
print(f"{'MSE':20}{mse_n:>16.6f}{mse_at:>16.6f}")
print(f"{'MAE':20}{mae_n:>16.6f}{mae_at:>16.6f}")
print(f"{'log-likelihood':20}{oos_loglik_normal:>16.2f}{oos_loglik_adjt:>16.2f}")
print(f"{'AIC':20}{aic_n:>16.2f}{aic_at:>16.2f}")

print("\n" + "=" * 70)
print("DIEBOLD-MARIANO TEST (adjusted-t vs plain-normal benchmark)")
print("=" * 70)
print(f"Mean daily loglik gain (adj-t - normal): {d_bar:.4f}")
print(f"HAC lag length                         : {lag}")
print(f"DM statistic                           : {dm_stat:.3f} {stars}")
print("(positive DM => adjusted-t forecasts are more accurate; "
      "*** / ** / * = 1% / 5% / 10%)")

print("\n" + "=" * 70)
print("99% VaR VIOLATION TEST: CROSS-SECTIONAL AVERAGE LOG-IV")
print("=" * 70)
print(var_summary.to_string(index=False))

