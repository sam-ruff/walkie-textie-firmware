"""How far the mux's output falls while it changes from one supply to the other.

The TPS2116 disconnects both supplies before it connects the new one. For
that time the capacitors on its output feed the converter alone, and the
converter takes the same power whatever its input voltage. The mux passes the
higher of its inputs, so the change comes where the USB voltage crosses the
battery's, and the output starts the break at the battery's voltage.

Nothing here is measured. The datasheet gives the break as a typical figure
only, at three voltages, so the worst case takes it twice as long as the
longest of the three. The capacitors are taken to keep as little of their
marked value as their tolerance, the temperature and the voltage across them
allow. The converter's efficiency is an assumption too.

The mux can change over more than once at one crossing, if loading and
unloading the battery moves its voltage by more than the mux's hysteresis.
The datasheet does not give that hysteresis. Each change is one such break,
and the capacitors recover in between, so the figures here are for one.
"""
import math

BREAK_SECONDS = 17.7e-6         # TPS2116 datasheet: typical switchover time at 1.8 V, the longest it gives
BREAK_ALLOWANCE = 2.0           # the worst case takes the break this many times as long
# Share of its marked value that a capacitor on the mux's output keeps at 2 to 3.6 V: a 22 uF, 25 V, X5R
# 0805 at the bottom of its 20% tolerance, hot or cold, less what the voltage across it takes.
OUTPUT_KEEPS = 0.6
EFFICIENCY = 0.85               # taken for the TPS631000 boosting from 2 V at these loads
RAIL_VOLTS = 3.3


def watts(amps):
    """Power the converter takes from the mux for a load on the 3.3 V rail."""
    return RAIL_VOLTS * amps / EFFICIENCY


def after_break(volts, load_watts, farads, seconds):
    """Voltage left on the output's capacitors after they feed a constant power for a time: nothing once they are empty."""
    left = volts ** 2 - 2 * load_watts * seconds / farads
    return math.sqrt(left) if left > 0 else 0.0


def typical(volts, load_watts, marked_farads):
    """Output voltage after one break of the datasheet's typical length, with the capacitors at their marked value."""
    return after_break(volts, load_watts, marked_farads, BREAK_SECONDS)


def worst(volts, load_watts, marked_farads):
    return after_break(volts, load_watts, marked_farads * OUTPUT_KEEPS, BREAK_SECONDS * BREAK_ALLOWANCE)


def least_battery(load_watts, marked_farads, floor):
    """Lowest battery voltage from which the worst-case break still leaves `floor` volts on the output."""
    return math.sqrt(floor ** 2 + 2 * load_watts * BREAK_SECONDS * BREAK_ALLOWANCE / (marked_farads * OUTPUT_KEEPS))
