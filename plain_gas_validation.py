import numpy as np
from scipy.optimize import minimize
import matplotlib.pyplot as plt

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

A        = true_a * np.eye(5)
B        = true_b * np.eye(5)
beta_bar = np.zeros(5)
H        = np.eye(24)
H_inv    = np.linalg.inv(H)

np.random.seed(42)

T    = 2000
beta = np.zeros(5)

Y_history    = []
beta_history = []

for t in range(T): 

    eps = np.random.standard_normal(24)

    y = M @ beta + eps 
    Y_history.append(y)
    beta_history.append(beta)

    xi = A @ np.linalg.inv(M.T @ H_inv @ M) @ M.T @ H_inv @ eps

    beta = (np.eye(5) - B) @ beta_bar + B @ beta + xi
    
Y         = np.array(Y_history)
beta_true = np.array(beta_history)

#############ESTIMATION################
def gas_filter(a, b, Y):
    A = a * np.eye(5)
    B = b * np.eye(5)

    beta   = np.zeros(5)   
    loglik = 0.0
    beta_filtered = []      

    for t in range(len(Y)):
        eps = Y[t] - M @ beta

        loglik += -0.5 * (np.log(np.linalg.det(2 * np.pi * H)) + eps @ (H_inv @ eps))

        beta_filtered.append(beta)
        
        xi = A @ np.linalg.inv(M.T @ H_inv @ M) @ M.T @ H_inv @ eps

        beta = (np.eye(5) - B) @ beta_bar + B @ beta + xi

    return loglik, np.array(beta_filtered)

def neg_loglik(params):
    a, b = params
    loglik, _ = gas_filter(a, b, Y)
    return -loglik

start  = [0.10, 0.90]
result = minimize(neg_loglik, start,
                  method="L-BFGS-B",
                  bounds=[(1e-4, 1.0), (1e-4, 0.9999)])

a_hat, b_hat = result.x

_, beta_filtered = gas_filter(a_hat, b_hat, Y)
for j in range(5):
    c = np.corrcoef(beta_true[:, j], beta_filtered[:, j])[0, 1]
    print(f"beta_{j+1} correlation (true vs filtered): {round(c, 4)}")

###############OUTPUT################
for j in range(5):
    plt.figure()
    plt.plot(beta_true[:, j], color="black", lw=1.5, label="true beta")
    plt.plot(beta_filtered[:, j], color="red", ls=":", lw=1.5, label="filtered beta")
    plt.title("beta " + str(j + 1))
    plt.legend()
    plt.show()

print(M)
print(M.shape)

print("Y shape:", Y.shape)
print("beta_true shape:", beta_true.shape)
print("day 1 surface (first 5 buckets):", Y[0][:5])

print("true a =", true_a, "  estimated a =", round(a_hat, 4))
print("true b =", true_b, "  estimated b =", round(b_hat, 4))
print("converged:", result.success)

