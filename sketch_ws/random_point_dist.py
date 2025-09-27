import numpy as np
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
# ICDF: Transfer uniform between 0 and 1 to needed distribution

def icdf(x):
    return x ** 0.5 * 1024

xts = np.random.uniform(0, 1, 1024)
yts = np.random.uniform(0, 128, 1024)
ax.scatter(icdf(xts), yts)
    
fig.set_figwidth(10)
fig.set_figheight(5)
#ax.set_xlim(0, 128)
#ax.set_ylim(0, 128)
fig.show()
plt.show()