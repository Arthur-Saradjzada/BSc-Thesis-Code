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

#np.random.seed(42) 

T    = 2000

#############ESTIMATION################
def gas_filter(a, b, sigma2, beta_bar, Y):   
    A = a * np.eye(5)
    B = b * np.eye(5)

    H     = sigma2 * np.eye(24)              
    H_inv = (1.0 / sigma2) * np.eye(24)      

    beta   = np.zeros(5)
    loglik = 0.0
    beta_hat = []

    for t in range(len(Y)):
        eps = Y[t] - M @ beta
        loglik += -0.5 * (np.log(np.linalg.det(2 * np.pi * H)) + eps @ (H_inv @ eps))
        beta_hat.append(beta)
        xi = A @ np.linalg.inv(M.T @ H_inv @ M) @ M.T @ H_inv @ eps
        beta = (np.eye(5) - B) @ beta_bar + B @ beta + xi  
    return loglik, np.array(beta_hat)

def neg_loglik(params):
    a, b, sigma2 = params[0], params[1], params[2]   
    beta_bar = params[3:8]                            
    loglik, _ = gas_filter(a, b, sigma2, beta_bar, Y)
    return -loglik

start  = [0.10, 0.90, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]   
bounds = [(1e-4, 1.0), (1e-4, 0.9999), (1e-6, None)] + [(None, None)] * 5

#############MONTE CARLO################
S = 100                              
estimates = []                                          

for s in range(S):                                      
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
    Y = np.array(Y_history)                              

    result = minimize(neg_loglik, start,
                      method="L-BFGS-B", bounds=bounds)
    estimates.append(result.x)                           
    print("replication", s + 1, "/", S, "converged:", result.success) 

estimates = np.array(estimates)                         

###############OUTPUT################
names = ["a", "b", "sigma2",                            
         "beta_bar_1", "beta_bar_2", "beta_bar_3", "beta_bar_4", "beta_bar_5"]
truth = [true_a, true_b, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]  

bias = []
rmse = []
for k in range(8):
    column = estimates[:, k]                             
    bias_k = column.mean() - truth[k]                   
    rmse_k = np.sqrt(np.mean((column - truth[k]) ** 2))  
    bias.append(bias_k)
    rmse.append(rmse_k)

print("")
print("param        true      mean      bias      std       rmse")
for k in range(8):
    print(f"{names[k]:<11}"
          f"{truth[k]:>8.4f}"
          f"{estimates[:, k].mean():>10.4f}"
          f"{bias[k]:>10.4f}"
          f"{estimates[:, k].std():>10.4f}"
          f"{rmse[k]:>10.4f}")

for k in range(8):
    plt.figure()
    plt.hist(estimates[:, k], bins=30, color="steelblue", edgecolor="black")
    plt.axvline(truth[k], color="red", lw=2, label="true value")
    plt.title(names[k])
    plt.legend()
    plt.show()


