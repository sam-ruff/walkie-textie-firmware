"""Peak voltage on the USB input when the board is plugged into a supply that is already on.

The lead's inductance rings with the capacitance on the input. The protection
switch is off while it does, so the ring is on the switch's input and the
capacitor there and nowhere else. The model is a step of the supply's voltage
into an inductance and a resistance in series (the supply, the lead and the
ferrite bead) charging one capacitance from nothing.

Nothing here is measured. The ranges below are assumptions about the supply,
the lead and what the capacitor keeps of its marked value. The protection
diode on the plug is left out, which can only make the answer too high. The
answer is the worst case over the ranges.
"""
import itertools
import math

SOURCE_VOLTS = 5.5              # the most a USB Type-C source may give
SOURCE_HENRIES = 0.05e-6        # the plug and socket themselves
SOURCE_OHMS = (0.05, 0.15)      # the supply's switch or fuse and two pairs of contacts
LEAD_HENRIES = (0.6e-6, 1.0e-6)     # per metre of lead, there and back
LEAD_OHMS = (0.067, 0.42)       # per metre, there and back: 20 AWG to 28 AWG
LEAD_METRES = (0.0, 0.5, 1.0, 2.0, 3.0)
# A 120 ohm ferrite bead well below the frequency it is rated at, and the same bead saturated by the
# inrush, when only its resistance is left. The answer is the worse of the two.
BEAD_HENRIES = (0.25e-6, 0.0)
BEAD_OHMS = 0.04
# Share of its marked value that the input capacitor keeps at 5 V, tolerance and temperature included:
# 100 nF, 50 V, X7R, 0402.
INPUT_KEEPS = (0.7, 1.1)


def peak(volts, henries, ohms, farads):
    """Highest voltage on the capacitor after the step."""
    damping = ohms / 2 * math.sqrt(farads / henries)
    if damping >= 1:
        return volts
    return volts * (1 + math.exp(-math.pi * damping / math.sqrt(1 - damping ** 2)))


def corners(metres):
    """(henries, ohms) in series between the supply and the capacitor, at each end of the assumed ranges."""
    for bead, per_metre_h, per_metre_ohms, source in itertools.product(BEAD_HENRIES, LEAD_HENRIES, LEAD_OHMS, SOURCE_OHMS):
        yield SOURCE_HENRIES + metres * per_metre_h + bead, source + metres * per_metre_ohms + BEAD_OHMS


def least_ohms():
    """Least resistance between the supply and the board's input: plugged straight into a socket."""
    return min(ohms for _, ohms in corners(0.0))


def worst_peak(metres, farads):
    """Highest peak over the assumed ranges for one length of lead. `farads` is the capacitor's marked value."""
    return max(peak(SOURCE_VOLTS, henries, ohms, farads * keeps) for henries, ohms in corners(metres) for keeps in INPUT_KEEPS)


def remake_peak(metres, farads, from_volts, switch_ohms):
    """Highest voltage behind the switch when the plug loses contact and makes it again with the switch on.

    The switch is then a resistance between the lead and every capacitor on the board, which the load has
    drawn down to `from_volts`. `farads` is what those capacitors keep of their marked value at 5 V. The
    ring is in the step from there to the supply's voltage, and the load is left out, which can only make
    the answer too high.
    """
    step = SOURCE_VOLTS - from_volts
    return max(from_volts + peak(step, henries, ohms + switch_ohms, farads) for henries, ohms in corners(metres))


def worst_left(metres, seconds):
    """Most that is left of the ring after a time, in volts either side of the supply's voltage.

    A ring dies at a rate of the resistance over twice the inductance, whatever the capacitance.
    """
    return max(SOURCE_VOLTS * math.exp(-ohms / (2 * henries) * seconds) for henries, ohms in corners(metres))
