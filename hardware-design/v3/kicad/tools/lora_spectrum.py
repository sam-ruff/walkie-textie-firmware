"""Model the spectrum of a LoRa signal, to see how a channel setting sits against EN 300 220-2.

The signal is the ideal one: constant envelope, continuous phase, the frequency
sweeping across the bandwidth and jumping back at each symbol boundary and at
the fold inside a symbol. A real transmitter's loop filter rounds those jumps
off, so its skirts are lower than the model's. The occupied bandwidth depends
mostly on the sweep itself and should be close.

Clause numbers are those of EN 300 220-2 V3.3.1 (2025-03).
"""
import math

import numpy as np

OVERSAMPLE = 16            # samples per chip
SYMBOLS = 64
BINS_PER_BANDWIDTH = 2048  # frequency resolution of the model: 122 Hz at 250 kHz


def waveform(spreading_factor, bandwidth):
    """Complex samples of SYMBOLS random symbols, at OVERSAMPLE times the bandwidth."""
    chips = 2 ** spreading_factor
    within = np.arange(chips * OVERSAMPLE) / (chips * OVERSAMPLE)       # position inside one symbol
    values = np.random.default_rng(1).integers(0, chips, SYMBOLS)
    frequency = np.concatenate([((value / chips + within) % 1.0 - 0.5) * bandwidth for value in values])
    return np.exp(2j * np.pi * np.cumsum(frequency) / (bandwidth * OVERSAMPLE))


def density(signal, bandwidth):
    """(frequencies in Hz from the carrier, share of the total power per Hz)."""
    length = BINS_PER_BANDWIDTH * OVERSAMPLE
    window = np.hanning(length)
    starts = range(0, len(signal) - length + 1, length // 2)
    power = sum(np.abs(np.fft.fft(signal[start:start + length] * window)) ** 2 for start in starts)
    step = bandwidth / BINS_PER_BANDWIDTH
    return np.fft.fftshift(np.fft.fftfreq(length, 1 / (bandwidth * OVERSAMPLE))), np.fft.fftshift(power) / (power.sum() * step)


def through_filter(frequencies, share_per_hz, resolution):
    """Share of the total power an analyser shows at each frequency through a Gaussian filter `resolution` wide."""
    step = frequencies[1] - frequencies[0]
    sigma = resolution / (2 * math.sqrt(math.log(2)))
    reach = int(4 * sigma / step)
    kernel = np.exp(-((np.arange(-reach, reach + 1) * step) / sigma) ** 2)
    return np.convolve(share_per_hz, kernel, mode="same") * step


def occupied_edges(frequencies, shown, span):
    """The frequencies below and above which 0,5 per cent of the power in `span` lies (clause 5.4.4)."""
    inside = np.abs(frequencies) <= span / 2
    running = np.cumsum(shown[inside]) / shown[inside].sum()
    return frequencies[inside][np.searchsorted(running, 0.005)], frequencies[inside][np.searchsorted(running, 0.995)]


def mask_limit(offset, channel_edge, band_edges, channel_width):
    """Limit in dBm per kHz at `offset` Hz from the carrier, or None inside the operating channel.

    The lower of the out of band mask, which hangs from the channel's edges
    (clause 4.4.6), and the mask at the band's edges (clause 4.4.8).
    """
    beyond_channel = abs(offset) - channel_edge
    if beyond_channel < 0:
        return None
    out_of_band = max(-36.0, -36.0 * beyond_channel / (2 * channel_width))
    beyond_band = offset - band_edges[1] if offset > 0 else band_edges[0] - offset
    if beyond_band < 0:
        return out_of_band
    return min(out_of_band, max(-36.0, -180.0 * beyond_band / 1e6))


def fit(carrier, spreading_factor, bandwidth, power_dbm, band):
    """How the modelled signal sits in its band. Frequencies in Hz, `band` as (low edge, high edge).

    The operating channel is taken as the widest the standard lets a carrier
    at this frequency declare (clause 4.2.3): twice the distance to the nearer
    band edge. Returns the occupied bandwidth at the two ends of the resolution
    the test method allows, the least room either occupied edge leaves inside
    the band, and the smallest margin to the emission masks with where it falls.
    """
    channel = 2 * min(carrier - band[0], band[1] - carrier)
    frequencies, share_per_hz = density(waveform(spreading_factor, bandwidth), bandwidth)
    widths, room = [], []
    for part in (0.01, 0.03):
        low, high = occupied_edges(frequencies, through_filter(frequencies, share_per_hz, channel * part), 2 * channel)
        widths.append(high - low)
        room.append(min(carrier + low - band[0], band[1] - (carrier + high)))

    per_khz = power_dbm + 10 * np.log10(np.maximum(through_filter(frequencies, share_per_hz, 1e3), 1e-30))
    band_edges = (band[0] - carrier, band[1] - carrier)
    margins = []
    for offset, level in zip(frequencies, per_khz):
        limit = mask_limit(offset, channel / 2, band_edges, channel)
        if limit is not None and abs(offset) <= channel / 2 + 500e3:
            margins.append((limit - level, offset))
    return {"occupied": (min(widths), max(widths)), "room": (min(room), max(room)), "mask": min(margins)}
