import numpy as np
import random
import matplotlib.pyplot as plt

FAKE_ADC_MEAN = 1234567
FAKE_ADC_SD = 100

def fake_adc(n: int):
    return [int(random.normalvariate(FAKE_ADC_MEAN, FAKE_ADC_SD)) for _ in range(n)]


HIST_BIN_BITS = 6
HIST_BINS = 1 << HIST_BIN_BITS
def hist(n, shift):
    smps = fake_adc(n)
    out = [0] * HIST_BINS
    for smp in smps:
        out[(smp >> shift) & (HIST_BINS-1)] += 1
    return out

def hist_anal(h):
    if np.sum(h) == np.max(h):
        return 'SINGLE', np.argmax(h)
    if h[0] == 0 and h[-1] == 0:
        return 'MULTI', np.argmax(h)
    return 'WRAPPED', None

def bin_start(shift):
    return [x << shift for x in range(HIST_BINS)]

def zoh_plot(h, start, shift, end):
    # x: 0 1 1 2 2 ... x-1 x
    # y: 0 0 1 1 2 ... x-1 x-1
    xout = np.zeros(HIST_BINS*2, dtype=int)
    yout = np.zeros(HIST_BINS*2, dtype=float)
    xout[::2] = range(HIST_BINS)
    xout[1::2] = xout[::2]+1
    xout <<= shift
    xout += start
    yout[::2] = h
    yout[1::2] = yout[::2]
    if end is not None:
        while xout[-1] < end:
            xout = np.concatenate((xout, xout + xout[-1] - xout[0]), axis=0)
            yout = np.concatenate((yout, yout), axis=0)
    return xout, yout

def main():
    endshift = 3
    
    fig, ax = plt.subplots()

    shift = 18
    measstart = 0
    rmstart = 0
    rmend = 0
    wrapped = False
    while shift >= endshift:
        n = 400
        if shift <= HIST_BIN_BITS:
            # Fine
            n = 4000
        h = hist(n, shift)
        bins = bin_start(shift)
        has, hv = hist_anal(h)
        if has == 'SINGLE':
            rmstart = measstart
            rmend = measstart + HIST_BINS * (1 << shift)
            xo, yo = zoh_plot(h, rmstart, shift, None)
            ax.plot(xo, yo, label=f'{shift}')
            bv = bins[hv]
            assert measstart & bv == 0
            # measstart valid before this
            measstart |= bv
            shift -= HIST_BIN_BITS
        elif has == 'MULTI' and not wrapped:
            rmstart = measstart
            rmend = measstart + HIST_BINS * (1 << shift)
            xo, yo = zoh_plot(h, rmstart, shift, None)
            ax.plot(xo, yo, label=f'{shift}')
            assert (measstart & (1 << (HIST_BIN_BITS+shift-1))) == 0
            # measstart valid before this
            # Add MSb
            measstart |= (hv & (1 << (HIST_BIN_BITS-1))) << shift
            shift -= 1
        else:
            wrapped = True
            xo, yo = zoh_plot(h, rmstart, shift, rmend)
            ax.plot(xo, yo, label=f'{shift}')
            shift -= 1
    ax.legend()
    fig.show()
    plt.show()


if __name__ == "__main__":
    main()