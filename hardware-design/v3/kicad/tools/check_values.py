"""Check the values that set the board's voltages, thresholds and timing against the datasheet formulas.

Usage: check_values.py model.json

Resistor and capacitor values alone set the 3.3 V rail, the interval between
wake-ups, the voltage at which the USB input's switch passes power, its
current limit and how fast it raises its output. Each is worked out here at
the worst case of the parts' tolerances and of the chip's own reference, and
compared with what the rest of the board needs. The power mux is checked for
the mode its pins put it in and for how far its output falls while it changes
supply, and the reset supervisor's fixed threshold is compared with the rail.

Every order that is powered is checked with the parts it fits and held to the
same marks. The default order's figures are printed in full and another
order's only where they differ. An order that leaves the rail to the wake
timer also gets the sum of what the battery feeds while the rail is off.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parts as parts_module
import supply_change
import usb_input
from values import between, divided, farads, names, one, rated_volts, resistor_between, span

# TPS631000 datasheet: feedback reference in volts (least, typical, most), and the input voltage at
# which the converter stops, at the most.
FEEDBACK = (0.495, 0.500, 0.505)
CONVERTER_STOPS = 1.499
# ESP32-S3-WROOM-1 datasheet: supply range in volts.
RAIL = (3.0, 3.6)
# TPL5111 datasheet, equation 1 with the coefficients for 100 to 1000 seconds, the timer's own accuracy
# and the least supply it is specified for.
TIMER = {"a": 0.2617, "b": -56.2407, "c": 5957.7934, "accuracy": 0.006, "least_volts": 1.8}
INTERVAL = 900.0           # seconds: the brief's nominal wake-up interval
INTERVAL_TOLERANCE = 0.05
USB_LOWEST = 4.40          # volts: the least a USB 2.0 low-power port may give a device
USB_HIGHEST = 5.5          # volts: the most a USB Type-C source may give
SIX_VOLT_LIMIT = 6.0       # volts: the most the mux, the converter and the timer allow on their supply pins
# What the board takes from its 3.3 V rail, in amps, from the ESP32-S3 and Wio-SX1262 datasheets:
# Bluetooth LE receiving 93 mA and transmitting at 21 dBm 335 mA; LoRa receiving 7.6 mA and transmitting
# at 22 dBm 125 mA.
LOADS = [("both radios listening", 0.093 + 0.0076), ("LoRa transmitting", 0.093 + 0.125), ("both radios transmitting", 0.335 + 0.125)]
PEAK_WATTS = supply_change.watts(LOADS[-1][1])
LIMIT_MARGIN = 1.5         # the current limit is at least this many times what the board takes in steady use
HANDOVER_MARGIN = 1.2      # and this many times what it takes at the moment the mux hands the load to USB
BATTERY_FLAT = 2.0         # volts at the battery connector: two AA cells at the end of their life, the least the brief runs the board from
BATTERY_LOW = 2.4          # volts: the same cells at 1.2 V each, well into their discharge
BATTERY_FRESH = 3.6        # volts: two fresh lithium AA cells, the most the brief runs the board from
# One worst-case break as USB arrives has to leave this much over the voltage at which the converter stops.
# As USB leaves it only has to leave the converter running: that figure already has the mux's output an
# assumed 0.2 V under the battery before the break starts.
RIDE_MARGIN = 0.10
LOADS_TO_HOLD = 2          # how many of LOADS, from the first, have to ride through a break from a flat battery
REACTION = 10e-6           # seconds of the mux's unstated reaction time that the log prices
# What the battery feeds while the wake timer holds the rail off: each chip's (typical, most) current in
# amps. TPS2116 datasheet, quiescent current of the input that feeds its output: typical at 25 C, most from
# -40 to 85 C. TPS631000 datasheet, shutdown current at 25 C. TPL5111 datasheet, supply current at 25 C.
CONVERTER = {"part": "TPS631000DRLR", "enable": "5"}
OFF_STATE = {"TPS2116DRLR": (1.35e-6, 3.7e-6), CONVERTER["part"]: (0.5e-6, 0.9e-6), "TPL5111DDCR": (35e-9, 50e-9)}
# ES1DL datasheet: reverse current in amps. Typical at 25 C with a tenth of its rated voltage across it, the
# least its figure 4 shows, and the most at 25 C with all of it. Nothing is given for the few volts here.
CLAMP_LEAKS = (0.25e-6, 5e-6)
# Samsung's catalogue: the least insulation resistance of a capacitor, in ohm farads, for a part rated for
# more than 16 V and for any other. It holds some parts of the first kind to the second figure and does
# not say which. It gives no typical figure.
INSULATION = (500.0, 100.0)
INSULATION_VOLTS = 16.0
OFF_TARGET = 5e-6          # amps: the brief's target for the battery current with the power off, at 25 C
# TPS2116 datasheet: the mux passes the higher of its inputs with these two pins low, and takes this as low.
MUX_LOW = 0.35
# TLV803S datasheet: falling threshold in volts (least, typical, most), the hysteresis above it, the
# most its output may sink in amps, and that output's resistance (0.4 V at 2 mA with 3.3 V on VDD).
SUPERVISOR = {"part": "TLV803S", "threshold": (2.87, 2.93, 2.99), "hysteresis": 0.04, "sink": 0.005, "ohms": 200.0}
RESET_LOW = 0.25           # Espressif's guidelines: EN resets the chip below this fraction of the rail


def interval(resistance):
    """Seconds between wake-ups for a resistance on the timer's DELAY pin."""
    x = resistance / 100
    return (TIMER["a"] * x * x + TIMER["b"] * x + TIMER["c"]) / 100


def rail_volts(all_parts):
    """(least, nominal, most) volts on the 3.3 V rail, and the two resistors that set it."""
    top, bottom = resistor_between(all_parts, "+3V3", "FB"), resistor_between(all_parts, "FB", "GND")
    ratio = divided(span(top), span(bottom))
    return tuple(reference * part for reference, part in zip(FEEDBACK, ratio)), top, bottom


def check_rail(all_parts):
    (least, nominal, most), top, bottom = rail_volts(all_parts)
    print(f"3.3 V rail: {top['ref']} {top['value']} and {bottom['ref']} {bottom['value']} give {nominal:.2f} V, "
          f"{least:.2f} to {most:.2f} V at the worst case; the ESP32 module takes {RAIL[0]} to {RAIL[1]} V")
    return [] if RAIL[0] <= least and most <= RAIL[1] else ["the 3.3 V rail can leave the ESP32 module's supply range"]


def check_supervisor(all_parts):
    found = [part for part in all_parts.values() if part["value"] == SUPERVISOR["part"]]
    outputs = set(found[0]["nets"].values()) - {"+3V3", "GND"} if len(found) == 1 else set()
    if len(outputs) != 1 or len(found[0]["nets"]) != 3:
        raise SystemExit(f"expected one {SUPERVISOR['part']} between +3V3 and GND with one output, found {[part['ref'] for part in found]}")
    (rail_least, _, rail_most), _, _ = rail_volts(all_parts)
    trip_least, _, trip_most = SUPERVISOR["threshold"]
    release = trip_most + SUPERVISOR["hysteresis"]
    print(f"reset supervisor: {found[0]['ref']} resets the ESP32 once the rail falls to {trip_least:.2f} to {trip_most:.2f} V "
          f"and lets go by {release:.2f} V; the rail's worst case is {rail_least:.2f} V and the module's least is {RAIL[0]:.1f} V")
    problems = []
    if release >= rail_least:
        problems.append("the reset supervisor can hold the ESP32 in reset with the rail at its worst case")
    if trip_most >= RAIL[0]:
        problems.append("the reset supervisor can trip with the rail inside the ESP32 module's supply range")

    # Its output discharges the capacitor on EN through the series resistor, and then holds EN low against the pull-up.
    series, pull = resistor_between(all_parts, outputs.pop(), "EN"), resistor_between(all_parts, "+3V3", "EN")
    peak = rail_most / span(series)[0]
    held = (span(series)[2] + SUPERVISOR["ohms"]) / (span(pull)[0] + span(series)[2] + SUPERVISOR["ohms"])
    print(f"reset supervisor: through {series['ref']} {series['value']} its output sinks {peak * 1000:.1f} mA at most, against a rating of "
          f"{SUPERVISOR['sink'] * 1000:.0f} mA, and holds EN at {held:.0%} of the rail against {pull['ref']} {pull['value']}; "
          f"the ESP32 resets below {RESET_LOW:.0%}")
    if peak > SUPERVISOR["sink"]:
        problems.append("the reset supervisor's output can sink more than its rating while it discharges the capacitor on EN")
    if held >= RESET_LOW:
        problems.append("the reset supervisor cannot pull EN low enough to reset the ESP32")
    return problems


def check_timer(all_parts):
    resistor = resistor_between(all_parts, "DELAY", "GND")
    low, nominal, high = (interval(resistance) for resistance in span(resistor))
    least, most = low * (1 - TIMER["accuracy"]), high * (1 + TIMER["accuracy"])
    print(f"wake-up interval: {resistor['ref']} {resistor['value']} gives {nominal:.0f} s, "
          f"{least:.0f} to {most:.0f} s at the worst case; the brief asks for {INTERVAL:.0f} s")
    inside = INTERVAL * (1 - INTERVAL_TOLERANCE) <= least and most <= INTERVAL * (1 + INTERVAL_TOLERANCE)
    return [] if inside else [f"the wake-up interval can be more than {INTERVAL_TOLERANCE:.0%} from {INTERVAL:.0f} s"]


def check_switch(usb):
    problems = []
    name, top, bottom = usb["switch"]["ref"], usb["enable_top"], usb["enable_bottom"]
    on, off = usb_input.switch_thresholds(usb)
    print(f"USB switch: {top['ref']} {top['value']} and {bottom['ref']} {bottom['value']} let {name} pass power once its input is over "
          f"{on[1]:.2f} V, {on[0]:.2f} to {on[2]:.2f} V at the worst case, and stop it under {off[1]:.2f} V, {off[0]:.2f} to {off[2]:.2f} V; "
          f"a USB port may give as little as {USB_LOWEST:.2f} V")
    if on[2] > USB_LOWEST:
        problems.append("the USB switch can stay off with a USB supply that is within its limits")

    resistor = usb["limit"]
    low, _, high = span(resistor)
    if low < usb_input.LIMIT_OHMS[0] or high > usb_input.LIMIT_OHMS[1]:
        problems.append(f"{resistor['ref']} is outside the {usb_input.LIMIT_OHMS[0]:.0f} to {usb_input.LIMIT_OHMS[1]:.0f} ohms the switch's limit pin takes")
    amps = usb_input.limit_amps(usb)
    steady = PEAK_WATTS / USB_LOWEST
    # The mux hands the load to USB while the switch is still raising VBUS past the battery's voltage,
    # so for a moment the switch feeds the converter at that voltage and charges the capacitors as well.
    behind = usb["output_caps"] + usb["system_caps"]
    handover = PEAK_WATTS / supply_change.under_load(BATTERY_FLAT, PEAK_WATTS) + usb_input.marked_farads(behind) * usb_input.slew_rate(usb) * 1000
    print(f"USB switch: {resistor['ref']} {resistor['value']} limits it to {amps[1]:.2f} A, {amps[0]:.2f} to {amps[2]:.2f} A at the worst case")
    print(f"  with both radios transmitting the board takes {steady:.2f} A from a {USB_LOWEST:.1f} V supply, "
          f"and {handover:.2f} A at the moment the mux hands over the load of a {BATTERY_FLAT:.1f} V battery")
    if amps[0] < LIMIT_MARGIN * steady:
        problems.append(f"the USB switch's limit can be under {LIMIT_MARGIN} times what the board takes")
    if amps[0] < HANDOVER_MARGIN * handover:
        problems.append(f"the USB switch's limit can be under {HANDOVER_MARGIN} times what the board takes as the mux hands over")

    capacitor = usb["slew_cap"]
    if farads(capacitor["value"]) < usb_input.SLEW_FARADS:
        problems.append(f"{capacitor['ref']} is under the {usb_input.SLEW_FARADS * 1e12:.0f} pF the switch's slew pin takes")
    print(f"USB switch: {capacitor['ref']} {capacitor['value']} has it raise its output at {usb_input.slew_rate(usb):.2f} V a millisecond")

    from_volts, to_volts = usb_input.CLAMP_FROM, usb_input.CLAMP_TO
    print(f"USB switch: with {from_volts[0]} to {from_volts[2]} V or more on its input {name} holds its output at {to_volts[0]} to {to_volts[2]} V; "
          f"the mux, the converter and the timer allow {SIX_VOLT_LIMIT:.0f} V")
    print(f"  a supply at the {USB_HIGHEST} V a USB source may give can bring that on, and the board then takes its power through "
          f"{USB_HIGHEST - to_volts[0]:.1f} V across {name}: {(USB_HIGHEST - to_volts[0]) * steady:.2f} W at the most")
    if max(from_volts[2], to_volts[2]) >= SIX_VOLT_LIMIT:
        problems.append(f"{name} can let its output reach a voltage the parts behind it do not allow")
    if from_volts[0] < USB_HIGHEST:
        problems.append(f"{name} can start holding its output down with the input inside what USB allows")
    return problems


def check_mux(usb):
    """The mode the mux's pins select."""
    problems = []
    mux, pads = usb["mux"], usb_input.MUX
    if mux["nets"][pads["usb"]] != usb["output_net"]:
        problems.append("the mux's first input is not on the USB switch's output")
    if {mux["nets"][pads["select"]], mux["nets"][pads["mode"]]} != {"GND"}:
        problems.append("the mux's select and mode pins are not both on ground, which is what has it pass the higher input")
    bleed = usb["bleed"]
    print(f"power mux: {mux['ref']} has its select and mode pins on ground (under {MUX_LOW} V), so it passes the higher of USB and the battery; "
          f"{bleed['ref']} {bleed['value']} empties VBUS when USB goes")
    print(f"  at each change of supply it disconnects both for {supply_change.BREAK_SECONDS * 1e6:.1f} us, a typical figure with no maximum given, "
          f"and the capacitors on its output feed the converter alone")
    return problems


def against_stop(figures):
    """How far each voltage is over or under the one at which the converter stops, as text."""
    return ", ".join(f"{volts / CONVERTER_STOPS - 1:+.0%}" for volts in figures)


def check_hold_up(usb):
    """How far the mux's output falls while it changes supply, for the capacitors fitted.

    The first LOADS_TO_HOLD of LOADS have to ride through one worst-case break from a flat battery.
    """
    problems = []
    capacitors = usb["system_caps"]
    marked = [(farads(part["value"]), rated_volts(part["mpn"])) for part in capacitors]
    loads = [(label, supply_change.watts(amps)) for label, amps in LOADS]
    arriving = [supply_change.worst(BATTERY_FLAT, power, marked) for _, power in loads]
    leaving = [supply_change.worst_leaving(BATTERY_FLAT, power, marked) for _, power in loads]
    print(f"hold-up: {names(capacitors)}, {supply_change.kept(marked) * 1e6:.0f} uF of them left at the worst case")
    print("  loads: " + ", ".join(label for label, _ in loads) + f"; the converter stops at {CONVERTER_STOPS:.2f} V at the most")
    print(f"  USB arriving, {BATTERY_FLAT:.1f} V at the battery connector: the break starts at " + ", ".join(
        f"{supply_change.under_load(BATTERY_FLAT, power):.2f} V" for _, power in loads)
        + f" after {supply_change.SERIES_OHMS * 1000:.0f} milliohms of MOSFET, mux and track")
    print("    one break of the typical length, capacitors at their marked value, leaves " + ", ".join(
        f"{supply_change.typical(BATTERY_FLAT, power, marked):.2f} V" for _, power in loads))
    print(f"    one break {supply_change.BREAK_ALLOWANCE:g} times as long at the worst case leaves " + ", ".join(f"{volts:.2f} V" for volts in arriving)
          + f": {against_stop(arriving)} against the converter's stop")
    print(f"  USB leaving, a battery that stays at {BATTERY_FLAT:.1f} V: the mux may let its output fall {supply_change.UNPLUG_SAG} V under the battery first, "
          f"and one worst-case break then leaves " + ", ".join(f"{volts:.2f} V" for volts in leaving) + f": {against_stop(leaving)}")
    print(f"    that sag stands for the mux's hysteresis alone. Its datasheet does not say how long it takes to act, and each "
          f"{REACTION * 1e6:.0f} us of that costs another " + ", ".join(
              f"{supply_change.fall_rate(BATTERY_FLAT - supply_change.UNPLUG_SAG, power, marked) * REACTION:.2f} V" for _, power in loads))
    print(f"  asked of the first {LOADS_TO_HOLD} loads: {RIDE_MARGIN:.0%} over the converter's stop as USB arrives, and the converter still running as it leaves")
    label, power = loads[1]
    print(f"  the mux may change over more than once at one crossing, how often is not known, and nothing says the capacitors are topped up "
          f"between: with {label}, " + " and ".join(
              f"{count} worst-case breaks in a row leave {supply_change.worst(BATTERY_FLAT, power, marked, count):.2f} V" for count in (2, 3)))
    for label, power in loads:
        least_in = supply_change.least_battery(power, marked, CONVERTER_STOPS)
        least_out = supply_change.least_battery_leaving(power, marked, CONVERTER_STOPS)
        if max(least_in, least_out) > BATTERY_FLAT:
            print(f"  with {label}, one worst-case break can stop the converter when the connector is under {least_in:.2f} V as USB arrives "
                  f"and under {least_out:.2f} V as it leaves; the supervisor then resets the ESP32")
    timer = TIMER["least_volts"]
    under = sum(volts < timer for volts in arriving + leaving)
    if under:
        print(f"  the wake timer is supplied from this node and is specified from {timer} V: {under} of those {len(arriving + leaving)} "
              f"worst-case figures are under that. If such a dip restarts the timer, it wakes the board and begins a new interval")
    for (label, _), into, out in list(zip(loads, arriving, leaving))[:LOADS_TO_HOLD]:
        if into < CONVERTER_STOPS * (1 + RIDE_MARGIN):
            problems.append(f"one break as USB arrives leaves under {RIDE_MARGIN:.0%} over the converter's stop with {label} from {BATTERY_FLAT:.1f} V")
        if out < CONVERTER_STOPS:
            problems.append(f"one break as USB leaves can stop the converter with {label} from {BATTERY_FLAT:.1f} V")
    label, power = loads[-1]
    if supply_change.least_battery(power, marked, CONVERTER_STOPS) > BATTERY_LOW:
        problems.append(f"a change of supply can stop the converter with {label} from {BATTERY_LOW:.1f} V at the connector")
    return problems


def insulation_leak(capacitors, volts, hold_all_to_least):
    """Most that capacitors may leak in amps with `volts` across them, by their maker's insulation limit."""
    over, others = INSULATION
    return sum(volts * farads(part["value"]) / (over if rated_volts(part["mpn"]) > INSULATION_VOLTS and not hold_all_to_least else others)
               for part in capacitors)


def print_off_state(all_parts, usb):
    """What the battery still feeds while the wake timer holds the rail off, beside the brief's target.

    Only an order that leaves the converter's enable to the timer has that state. The figures are the
    makers', and for the capacitors their limits alone, so this stops nothing: it says what to measure.
    """
    converter = one([part for part in all_parts.values() if part["value"] == CONVERTER["part"]], "converter")
    system, battery = usb["system_net"], usb["mux"]["nets"][usb_input.MUX["battery"]]
    if between(all_parts, "R", system, converter["nets"][CONVERTER["enable"]]):
        return
    chips = [part for part in all_parts.values() if part["value"] in OFF_STATE and not part["dnp"]]
    diodes = usb["clamp"]
    capacitors = between(all_parts, "C", system, "GND") + between(all_parts, "C", battery, "GND")
    typical = sum(OFF_STATE[part["value"]][0] for part in chips) + CLAMP_LEAKS[0] * len(diodes)
    most = sum(OFF_STATE[part["value"]][1] for part in chips) + CLAMP_LEAKS[1] * len(diodes)
    leaks = [insulation_leak(capacitors, BATTERY_FRESH, hold_all) for hold_all in (False, True)]
    print(f"power off: with the timer holding the rail off, a {BATTERY_FRESH} V battery still feeds {names(chips + diodes)}, "
          f"the diode through {usb['bleed']['ref']}, and {len(capacitors)} capacitors of {usb_input.marked_farads(capacitors) * 1e6:.0f} uF")
    print(f"  the chips and the diode: {typical * 1e6:.1f} uA typical, {most * 1e6:.1f} uA at their makers' limits, "
          f"which for the mux is over temperature and for the diode at its full rated voltage")
    print(f"  the capacitors, by their maker's insulation limit: {leaks[0] * 1e6:.1f} uA, or {leaks[1] * 1e6:.1f} uA if the maker holds "
          f"the parts rated over {INSULATION_VOLTS:.0f} V to its lower figure as well. No typical figure is given")
    total = typical + leaks[0]
    print(f"  the chips typical and the capacitors at their limit: {total * 1e6:.1f} to {(typical + leaks[1]) * 1e6:.1f} uA; "
          f"the brief's target is {OFF_TARGET * 1e6:.0f} uA at 25 C")
    if total > OFF_TARGET:
        print(f"  RISK: on the makers' figures this order can draw more than {OFF_TARGET * 1e6:.0f} uA with the power off. "
              f"The capacitors' share is a limit with no typical figure beside it: measure it on the first board")


def check_order(built):
    """Every check on the parts as one order builds them. Returns the problems."""
    usb = usb_input.describe(built)
    problems = check_rail(built) + check_timer(built) + check_switch(usb) + check_mux(usb) + check_supervisor(built) + check_hold_up(usb)
    print_off_state(built, usb)
    return problems


def main():
    with open(sys.argv[1]) as fh:
        all_parts = parts_module.resolve(json.load(fh))
    problems = parts_module.for_each_order(all_parts, check_order)
    if problems:
        print("\n".join(problems))
        raise SystemExit(f"{len(problems)} problems with the values that set the rails, the thresholds and the timer")
    print("the values that set the rail, the timer, the USB switch and the reset are inside their limits, and the mux hands over as designed")


if __name__ == "__main__":
    main()
