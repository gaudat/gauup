import numpy as np
import matplotlib.pyplot as plt

# 1 Pixel = 0.25mm
canvas = np.zeros((128, 128), dtype=int)

fig, ax = plt.subplots()
# ICDF: Transfer uniform between 0 and 1 to needed distribution

for particle_i in range(32):
    # Generate a bunch of pixel coordinates
    velocity = 0 # Pixels per count
    start = (0, 0)
    vdir = np.random.uniform(-np.pi, np.pi)
    max_points = 256
    deltadir = 0.1
    biasdir = -0.1
    deltadirs = np.random.uniform(-deltadir+biasdir, deltadir+biasdir, (max_points,))
    absdirs = deltadir + np.cumsum(deltadirs)
    # Add some velocity when it is in the direction we wanted
    vaddterm = np.abs(np.cos(absdirs- np.pi/4)) * 1
    vaddterm[vaddterm < 0] = 0
    deltax = (velocity + vaddterm) * np.cos(absdirs) + 0.1
    deltay = (velocity + vaddterm) * np.sin(absdirs)
    deltaxy = np.stack((deltax, deltay))
    absxy = np.expand_dims(np.array(start),-1) + np.cumsum(deltaxy, axis=1)
    lifetime = np.random.uniform(max_points/2, max_points)
    absxy[:,int(lifetime):] = np.nan
    ax.plot(absxy[0], absxy[1], c=(0,0,0))

# Master curves, instance, random cut to make different angles and lengths
    
fig.set_figwidth(5)
fig.set_figheight(5)
#ax.set_xlim(0, 128)
#ax.set_ylim(0, 128)
fig.show()
plt.show()