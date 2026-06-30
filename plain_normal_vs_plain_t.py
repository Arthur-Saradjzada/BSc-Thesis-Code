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


def gas_filter_t(a, b, sigma2, beta_bar, nu, day_list, beta_start):
    A = a * np.eye(5)
    B = b * np.eye(5)

    H = sigma2 * np.eye(24)
    H_inv = (1.0 / sigma2) * np.eye(24)
    N = 24

    beta = beta_start.copy()
    loglik = 0.0
    loglik_list = []
    forecast_list = []
    realized_list = []

    for (M_t, y_t) in day_list:
        forecast = M_t @ beta
        eps = y_t - forecast
        quad = eps @ (H_inv @ eps)

        ll = (
            gammaln((nu + N) / 2.0)
            - gammaln(nu / 2.0)
            - 0.5 * np.log(np.linalg.det((nu - 2) * np.pi * H))
            - (nu + N) / 2.0 * np.log(1.0 + quad / (nu - 2))
        )

        loglik += ll
        loglik_list.append(ll)
        forecast_list.append(forecast)
        realized_list.append(y_t)

        weight = (1.0 + (N + 2.0) / nu) / (1.0 + quad / (nu - 2))
        xi = weight * A @ np.linalg.inv(M_t.T @ H_inv @ M_t) @ M_t.T @ H_inv @ eps

        beta = (np.eye(5) - B) @ beta_bar + B @ beta + xi

    return loglik, loglik_list, forecast_list, realized_list, beta


def neg_loglik_t(params):
    a, b, sigma2 = params[0], params[1], params[2]
    beta_bar = params[3:8]
    nu = params[8]

    loglik, _, _, _, _ = gas_filter_t(
        a, b, sigma2, beta_bar, nu, EST_DAYS, beta_bar
    )

    return -loglik


bounds_t = (
    [(1e-4, 1.0), (1e-4, 0.9999), (1e-6, None)]
    + [(None, None)] * 5
    + [(2.1, 100.0)]
)


def add_var_records(var_records, model_name, forecasts, realized_values, sigma2, nu=None):
    for forecast, realized in zip(forecasts, realized_values):
        N = len(realized)

        p_hat = np.mean(forecast)
        p_real = np.mean(realized)

        var_p = sigma2 / N

        if nu is None:
            q = norm.ppf(VAR_ALPHA)
        else:
            q = np.sqrt((nu - 2.0) / nu) * student_t.ppf(VAR_ALPHA, df=nu)

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
daily_loglik_t = []

oos_loglik_normal = 0.0
oos_loglik_t = 0.0

oos_realized = []
oos_forecasts_normal = []
oos_forecasts_t = []

var_records = []

print("\nRolling estimation (plain normal vs plain t)...")

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

    start_t = [
        0.8,
        0.95,
        0.01,
        mean_logiv,
        0.0,
        0.0,
        0.0,
        0.0,
        8.0
    ]

    res_t = minimize(
        neg_loglik_t,
        start_t,
        method="L-BFGS-B",
        bounds=bounds_t
    )

    a_t, b_t, s2_t = res_t.x[0], res_t.x[1], res_t.x[2]
    bb_t = res_t.x[3:8]
    nu_t = res_t.x[8]

    _, _, _, _, warm_t = gas_filter_t(
        a_t, b_t, s2_t, bb_t, nu_t, est_days, bb_t
    )

    ll_t, lllist_t, fc_t, rl_t, _ = gas_filter_t(
        a_t, b_t, s2_t, bb_t, nu_t, forecast_days, warm_t
    )

    add_var_records(
        var_records=var_records,
        model_name="plain-normal",
        forecasts=fc_n,
        realized_values=rl_n,
        sigma2=s2_n,
        nu=None
    )

    add_var_records(
        var_records=var_records,
        model_name="plain-t",
        forecasts=fc_t,
        realized_values=rl_t,
        sigma2=s2_t,
        nu=nu_t
    )

    oos_loglik_normal += ll_n
    oos_loglik_t += ll_t

    daily_loglik_normal.extend(lllist_n)
    daily_loglik_t.extend(lllist_t)

    oos_realized.extend(rl_n)
    oos_forecasts_normal.extend(fc_n)
    oos_forecasts_t.extend(fc_t)

    print(
        f"block {block}: "
        f"normal a={a_n:.3f}  "
        f"t a={a_t:.3f}  "
        f"nu={nu_t:.2f}  "
        f"normal ll={ll_n:.1f}  "
        f"t ll={ll_t:.1f}  "
        f"conv {res_n.success}/{res_t.success}"
    )

    start += FORECAST


realized = np.array(oos_realized)

err_n = realized - np.array(oos_forecasts_normal)
err_t = realized - np.array(oos_forecasts_t)

mse_n = np.mean(err_n ** 2)
mae_n = np.mean(np.abs(err_n))

mse_t = np.mean(err_t ** 2)
mae_t = np.mean(np.abs(err_t))

aic_n = 2 * 8 - 2 * oos_loglik_normal
aic_t = 2 * 9 - 2 * oos_loglik_t


ll_normal_arr = np.array(daily_loglik_normal)
ll_t_arr = np.array(daily_loglik_t)

d = ll_t_arr - ll_normal_arr
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
print("OUT-OF-SAMPLE PERFORMANCE: plain normal vs plain t")
print("=" * 60)
print(f"Out-of-sample days   : {n:,}")
print(f"{'':20}{'normal':>14}{'t':>14}")
print(f"{'MSE':20}{mse_n:>14.6f}{mse_t:>14.6f}")
print(f"{'MAE':20}{mae_n:>14.6f}{mae_t:>14.6f}")
print(f"{'log-likelihood':20}{oos_loglik_normal:>14.2f}{oos_loglik_t:>14.2f}")
print(f"{'AIC':20}{aic_n:>14.2f}{aic_t:>14.2f}")

print("\n" + "=" * 60)
print("DIEBOLD-MARIANO TEST (t vs normal benchmark)")
print("=" * 60)
print(f"Mean daily loglik gain (t - normal): {d_bar:.4f}")
print(f"HAC lag length                     : {lag}")
print(f"DM statistic                       : {dm_stat:.3f} {stars}")
print("(positive DM => t forecasts are more accurate; "
      "*** / ** / * = 1% / 5% / 10%)")

print("\n" + "=" * 60)
print("99% VaR VIOLATION TEST: CROSS-SECTIONAL AVERAGE LOG-IV")
print("=" * 60)
print(var_summary.to_string(index=False))
