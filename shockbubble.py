#!/usr/bin/env python
# encoding: utf-8

import numpy as np
from scipy import integrate

gamma = 1.4
gamma1 = gamma - 1.
x0=0.5; y0=0.; z0=0.; r0=0.2
xshock = 0.2
pinf=5.

def meshgrid2(*arrs):
    arrs = tuple(reversed(arrs))  #edit
    lens = map(len, arrs)
    dim = len(arrs)

    sz = 1
    for s in lens:
        sz*=s

    ans = []    
    for i, arr in enumerate(arrs):
        slc = [1]*dim
        slc[i] = lens[i]
        arr2 = np.asarray(arr).reshape(slc)
        for j, sz in enumerate(lens):
            if j!=i:
                arr2 = arr2.repeat(sz, axis=j) 
        ans.append(arr2)

    return tuple(ans)

def zsphere(z,cmin,cmax):
    r"""Fraction of cell that lies in sphere centered at (x0,y0,z0)."""
    ymin, zmin = cmin
    ymax, zmax = cmax
    if r0**2>((z-z0)**2):
        return max(min(z0 + np.sqrt(r0**2-(x-x0)**2-(y-y0)**2),zmax) - zmin,0.)
    else:
        return 0

def qinit(state,rhoin=0.1):
    r"""
    Initialize data with a shock at x=xshock and a low-density bubble (of density rhoin)
    centersed at (x0,y0) with radius r0.
    """
    rhoout = 1.
    pout   = 1.
    pin    = 1.

    rinf = (gamma1 + pinf*(gamma+1.))/ ((gamma+1.) + gamma1*pinf)
    vinf = 1./np.sqrt(gamma) * (pinf - 1.) / np.sqrt(0.5*((gamma+1.)/gamma) * pinf+0.5*gamma1/gamma)
    einf = 0.5*rinf*vinf**2 + pinf/gamma1
    
    x =state.grid.x.centers
    y =state.grid.y.centers
    z =state.grid.z.centers
    Z,Y,X = meshgrid2(z,y,x)
    r = np.sqrt((X-x0)**2 + (Y-y0)**2 + (Z-z0)**2)

    #First set the values for the cells that don't intersect the bubble boundary
    state.q[0,:,:] = rinf*(X<xshock) + rhoin*(r<=r0) + rhoout*(r>r0)*(X>xshock)
    state.q[1,:,:] = 0.#rinf*vinf*(X<xshock)
    state.q[2,:,:] = 0.
    state.q[3,:,:] = 0.
    state.q[4,:,:] = einf*(X<xshock) + (pin*(r<=r0) + pout*(r>r0)*(X>xshock))/gamma1

    #Now average for the cells on the edges of the bubble
    d2 = np.linalg.norm(state.grid.delta)/2.
    dx = state.grid.delta[0]
    dy = state.grid.delta[1]
    dz = state.grid.delta[2]
    dx2 = state.grid.delta[0]/2.
    dy2 = state.grid.delta[1]/2.
    dz2 = state.grid.delta[2]/2.
    for i in xrange(state.q.shape[1]):
        xdown = x[i]-dz2
        xup   = x[i]+dz2
        for j in xrange(state.q.shape[2]):
            cmin = (xdown,y[j]-dy2)
            cmax = (xup,y[j]+dy2)
            for k in xrange(state.q.shape[3]):
                if abs(r[i,j,k]-r0)<d2:
                    infrac,abserr = integrate.quad(zsphere,z[k]-dz2,z[k]+dz2,args=(cmin,cmax),epsabs=1.e-8,epsrel=1.e-5)
                    infrac=infrac/(dx*dy*dz)
                    state.q[0,i,j] = rhoin*infrac + rhoout*(1.-infrac)
                    state.q[4,i,j] = (pin*infrac + pout*(1.-infrac))/gamma1


def shockbc(state,dim,t,qbc,num_ghost):
    """
    Incoming shock at left boundary.
    """
    rinf = (gamma1 + pinf*(gamma+1.))/ ((gamma+1.) + gamma1*pinf)
    vinf = 1./np.sqrt(gamma) * (pinf - 1.) / np.sqrt(0.5*((gamma+1.)/gamma) * pinf+0.5*gamma1/gamma)
    einf = 0.5*rinf*vinf**2 + pinf/gamma1

    for i in xrange(num_ghost):
        qbc[0,i,...] = rinf
        qbc[1,i,...] = rinf*vinf
        qbc[2,i,...] = 0.
        qbc[3,i,...] = 0.
        qbc[4,i,...] = einf


def shockbubble(use_petsc=False,iplot=False,htmlplot=False,outdir='./_output',solver_type='classic'):
    """
    Solve the Euler equations of compressible fluid dynamics.
    This example involves a bubble of dense gas that is impacted by a shock.
    """

    if use_petsc:
        import clawpack.petclaw as pyclaw
    else:
        from clawpack import pyclaw

    if solver_type=='sharpclaw':
        solver = pyclaw.SharpClawSolver3D()
        solver.weno_order=5
        solver.lim_type=2
    else:
        solver = pyclaw.ClawSolver3D()
        solver.dimensional_split = 1
        solver.transverse_waves = 3
        solver.limiters = 4
        solver.cfl_max = 0.2
        solver.cfl_desired = 0.15
        solver.order = 1
        solver.dt_initial = 0.000125

    from clawpack import riemann
    solver.rp = riemann.rp3_euler
    solver.num_waves = 3
    solver.bc_lower[0]=pyclaw.BC.custom
    solver.bc_upper[0]=pyclaw.BC.extrap
    solver.bc_lower[1]=pyclaw.BC.extrap
    solver.bc_upper[1]=pyclaw.BC.extrap
    solver.bc_lower[2]=pyclaw.BC.extrap
    solver.bc_upper[2]=pyclaw.BC.extrap

    # Initialize domain
    mx=160; my=40; mz = 40
    x = pyclaw.Dimension('x', 0.0,2.0,mx)
    y = pyclaw.Dimension('y',-0.5,0.5,my)
    z = pyclaw.Dimension('z',-0.5,0.5,mz)
    domain = pyclaw.Domain([x,y,z])
    num_eqn = 5
    state = pyclaw.State(domain,num_eqn)

    state.problem_data['gamma']= gamma
    state.problem_data['gamma1']= gamma1

    qinit(state)
    print np.min(state.q[0,...].reshape(-1))

    solver.user_bc_lower=shockbc

    claw = pyclaw.Controller()
    claw.tfinal = 0.3
    claw.solution = pyclaw.Solution(state,domain)
    claw.solver = solver
    claw.num_output_times = 10
    claw.outdir = outdir

    # Solve
    status = claw.run()

    if htmlplot:  pyclaw.plot.html_plot(outdir=outdir)
    if iplot:     pyclaw.plot.interactive_plot(outdir=outdir)

    return claw.solution.q

if __name__=="__main__":
    from clawpack.pyclaw.util import run_app_from_main
    output = run_app_from_main(shockbubble)
