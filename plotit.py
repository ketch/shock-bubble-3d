import matplotlib.pyplot as plt

q=np.loadtxt('fort.q0000',skiprows=12)
q=q.T
q=q.reshape(6,160,40,40,order='F')
plt.pcolormesh(q[0,:,:,20])
