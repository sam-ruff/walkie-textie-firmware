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

The same lead and supply are used for a plug that loses contact and makes it
again with the switch on. Then the ring is behind the switch, on whatever
capacitance is there: all of it at once when the mux has USB selected, or a
little of it with a diode to the rest when the mux has gone back to the
battery.
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
# The stepped part of the model: time steps to a natural period, and the periods after which it gives up.
STEPS = 2000
PERIODS = 50


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


def peak_from(henries, ohms, farads, volts, amps):
    """Highest voltage a capacitance reaches when the lead goes on charging it from `volts` with `amps` already flowing.

    The series circuit's own solution, taken at the moment the current stops. With enough resistance
    the current never stops and the voltage only approaches the supply's.
    """
    decay, natural = ohms / (2 * henries), 1 / (henries * farads)
    below, slope = volts - SOURCE_VOLTS, amps / farads
    if decay ** 2 < natural:
        turns = math.sqrt(natural - decay ** 2)
        when = math.atan2(slope * turns, decay * slope + natural * below) / turns
        over = math.exp(-decay * when) * (below * math.cos(turns * when) + (slope + decay * below) / turns * math.sin(turns * when))
        return SOURCE_VOLTS + over
    root = math.sqrt(decay ** 2 - natural) or decay * 1e-9
    slow, fast = -decay + root, -decay - root
    first, second = (slope - fast * below) / (slow - fast), (slow * below - slope) / (slow - fast)
    # The voltage passes the supply's only if the two terms cancel at some later time.
    if first == 0 or -second / first <= 1:
        return SOURCE_VOLTS
    when = math.log(-second * fast / (first * slow)) / (slow - fast)
    return SOURCE_VOLTS + first * math.exp(slow * when) + second * math.exp(fast * when)


def diode_peak(henries, ohms, small, large, from_volts, diode_volts):
    """Highest voltage on a small capacitance that a diode joins to a large one, when contact comes back.

    Both start at `from_volts`. The lead charges the small one alone, stepped through time, until it
    stands `diode_volts` above the large one. From then the diode passes the current on, dropping
    `diode_volts` whatever it carries, so the two rise together as one capacitance.
    """
    amps, volts = 0.0, from_volts
    step = 2 * math.pi * math.sqrt(henries * small) / STEPS
    for _ in range(STEPS * PERIODS):
        amps += step * (SOURCE_VOLTS - amps * ohms - volts) / henries
        volts += step * amps / small
        if volts >= from_volts + diode_volts:
            return peak_from(henries, ohms, small + large, volts, amps)
    raise SystemExit("the capacitance on VBUS never reached the diode's drop in the time modelled: this model needs looking at")


def remake_peak_through_diode(metres, small, large, from_volts, switch_ohms, diode_volts):
    """Highest voltage behind the switch when contact comes back while only `small` farads are behind it.

    A diode joins that to the `large` farads on the far side of the mux. `diode_volts` is the range of
    its drop, and the answer is the worst over that range and over the lead's.
    """
    return max(diode_peak(henries, ohms + switch_ohms, small, large, from_volts, drop)
               for henries, ohms in corners(metres) for drop in diode_volts)


def worst_left(metres, seconds):
    """Most that is left of the ring after a time, in volts either side of the supply's voltage.

    A ring dies at a rate of the resistance over twice the inductance, whatever the capacitance.
    """
    return max(SOURCE_VOLTS * math.exp(-ohms / (2 * henries) * seconds) for henries, ohms in corners(metres))
