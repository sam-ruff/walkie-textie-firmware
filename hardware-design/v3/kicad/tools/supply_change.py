"""How far the mux's output falls while it changes from one supply to the other.

The TPS2116 disconnects both supplies before it connects the new one. For
that time the capacitors on its output feed the converter alone, and the
converter takes the same power whatever its input voltage. The mux passes the
higher of its inputs, so the change comes where the USB voltage crosses the
battery's. When USB arrives, the output starts the break at what the battery
gives it under load: the voltage at the battery connector less the drop in
the MOSFET, the mux's own switch and the tracks between the connector and
the capacitors. When USB leaves, the output follows VBUS down until the mux
lets go of it, which may be some way under the battery's voltage: the
datasheet states no hysteresis, but it specifies its supply currents with the
battery input 0.2 V above the other, and that is taken as the figure.

Nothing here is measured. The datasheet gives the break as a typical figure
only, at three voltages, so the worst case takes it twice as long as the
longest of the three. The capacitors are taken to keep as little of their
marked value as their tolerance, the temperature and the voltage across them
allow. The converter's efficiency and the tracks' resistance are assumptions
too.

The figures are for one break. The mux can change over more than once at one
crossing, when loading and unloading the battery moves its voltage by more
than the mux's hysteresis, which its datasheet does not give. Nothing says
the capacitors are topped up between two such breaks, so `breaks` lets the
caller ask what several in a row would leave.
"""
import math

BREAK_SECONDS = 17.7e-6         # TPS2116 datasheet: typical switchover time at 1.8 V, the longest it gives
BREAK_ALLOWANCE = 2.0           # the worst case takes the break this many times as long
# Share of its marked value that a capacitor on the mux's output keeps at 2 to 2.5 V, where the break
# matters: at the bottom of its 20% tolerance, hot or cold, less what the voltage across it takes. A
# part rated for 6.3 V loses more to that voltage than one rated for 25 V.
OUTPUT_KEEPS = 0.6
LOW_RATED_KEEPS = 0.5
LOW_RATED_VOLTS = 10.0
EFFICIENCY = 0.85               # taken for the TPS631000 boosting from 2 V at these loads
RAIL_VOLTS = 3.3
# Between the battery connector and those capacitors, in ohms: the MOSFET at 1.8 V of gate drive and the
# mux's switch at 1.8 V, each at its datasheet's most, and about 14 mm of track taken as 20 milliohms.
SERIES_OHMS = 0.059 + 0.066 + 0.020
# How far under the battery's voltage the mux may let its output fall before it leaves USB for the
# battery: the margin at which the TPS2116 datasheet specifies the battery input's supply current.
UNPLUG_SAG = 0.2


def watts(amps):
    """Power the converter takes from the mux for a load on the 3.3 V rail."""
    return RAIL_VOLTS * amps / EFFICIENCY


def under_load(connector_volts, load_watts):
    """Voltage on the mux's output while the battery feeds a constant power through the parts in its way."""
    left = connector_volts ** 2 - 4 * load_watts * SERIES_OHMS
    return (connector_volts + math.sqrt(left)) / 2 if left > 0 else 0.0


def after_break(volts, load_watts, farads, seconds):
    """Voltage left on the output's capacitors after they feed a constant power for a time: nothing once they are empty."""
    left = volts ** 2 - 2 * load_watts * seconds / farads
    return math.sqrt(left) if left > 0 else 0.0


def kept(marked):
    """Farads left of [(marked farads, rated volts)] at the worst case."""
    return sum(farads * (LOW_RATED_KEEPS if volts < LOW_RATED_VOLTS else OUTPUT_KEEPS) for farads, volts in marked)


def typical(connector_volts, load_watts, marked):
    """Output voltage after one break of the datasheet's typical length, with the capacitors at their marked value."""
    return after_break(under_load(connector_volts, load_watts), load_watts, sum(farads for farads, _ in marked), BREAK_SECONDS)


def worst(connector_volts, load_watts, marked, breaks=1):
    """Output voltage after `breaks` worst-case breaks in a row with nothing put back between them, as USB arrives."""
    return after_break(under_load(connector_volts, load_watts), load_watts, kept(marked), BREAK_SECONDS * BREAK_ALLOWANCE * breaks)


def worst_leaving(connector_volts, load_watts, marked):
    """Output voltage after one worst-case break as USB leaves, from a battery whose voltage does not move under load."""
    return after_break(connector_volts - UNPLUG_SAG, load_watts, kept(marked), BREAK_SECONDS * BREAK_ALLOWANCE)


def least_battery(load_watts, marked, floor):
    """Lowest voltage at the battery connector from which one worst-case break still leaves `floor` volts."""
    start = math.sqrt(floor ** 2 + 2 * load_watts * BREAK_SECONDS * BREAK_ALLOWANCE / kept(marked))
    return start + load_watts / start * SERIES_OHMS
