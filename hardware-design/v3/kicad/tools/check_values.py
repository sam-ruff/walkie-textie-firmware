"""Check the values that set the board's voltages, thresholds and timing against the datasheet formulas.

Usage: check_values.py model.json

Resistor and capacitor values alone set the 3.3 V rail, the interval between
wake-ups, the voltage at which the USB input's switch passes power, its
current limit and how fast it raises its output. Each is worked out here at
the worst case of the parts' tolerances and of the chip's own reference, and
compared with what the rest of the board needs. The power mux is checked for
the mode its pins put it in and for how far its output falls while it changes
supply, and the reset supervisor's fixed threshold is compared with the rail.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parts as parts_module
import supply_change
import usb_input
from values import divided, farads, names, resistor_between, span

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
BATTERY_FLAT = 2.0         # volts: two AA cells at the end of their life, the least the brief runs the board from
BATTERY_LOW = 2.4          # volts: the same cells at 1.2 V each, well into their discharge
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
    handover = PEAK_WATTS / BATTERY_FLAT + usb_input.marked_farads(behind) * usb_input.slew_rate(usb) * 1000
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
    print(f"USB switch: {capacitor['ref']} {capacitor['value']} has it raise its output at {usb_input.slew_rate(usb):.1f} V a millisecond")

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
    """The mode the mux's pins select, and how far its output falls while it changes supply."""
    problems = []
    mux, pads = usb["mux"], usb_input.MUX
    if mux["nets"][pads["usb"]] != usb["output_net"]:
        problems.append("the mux's first input is not on the USB switch's output")
    if {mux["nets"][pads["select"]], mux["nets"][pads["mode"]]} != {"GND"}:
        problems.append("the mux's select and mode pins are not both on ground, which is what has it pass the higher input")
    bleed = usb["bleed"]
    print(f"power mux: {mux['ref']} has its select and mode pins on ground (under {MUX_LOW} V), so it passes the higher of USB and the battery; "
          f"{bleed['ref']} {bleed['value']} empties VBUS when USB goes")

    capacitors = usb["system_caps"]
    marked = usb_input.marked_farads(capacitors)
    loads = [(label, supply_change.watts(amps)) for label, amps in LOADS]
    print(f"  at each change of supply it disconnects both for {supply_change.BREAK_SECONDS * 1e6:.1f} us, a typical figure with no maximum given, "
          f"and {names(capacitors)} feed the converter alone")
    print(f"  from a {BATTERY_FLAT:.1f} V battery that leaves " + ", ".join(
        f"{supply_change.typical(BATTERY_FLAT, power, marked):.2f} V with {label}" for label, power in loads))
    print(f"  at {supply_change.BREAK_ALLOWANCE:g} times that break, with the capacitors at {supply_change.OUTPUT_KEEPS:.0%} of their marked value: " + ", ".join(
        f"{supply_change.worst(BATTERY_FLAT, power, marked):.2f} V" for _, power in loads)
        + f"; the converter stops at {CONVERTER_STOPS:.2f} V at the most and the timer is specified from {TIMER['least_volts']} V")
    for label, power in loads:
        least = supply_change.least_battery(power, marked, CONVERTER_STOPS)
        if least > BATTERY_FLAT:
            print(f"  so with {label} a change of supply can stop the converter when the battery is under {least:.2f} V; the supervisor then resets the ESP32")
    for label, power in loads[:-1]:
        if supply_change.worst(BATTERY_FLAT, power, marked) <= CONVERTER_STOPS:
            problems.append(f"a change of supply can stop the converter with {label} from a {BATTERY_FLAT:.1f} V battery")
    label, power = loads[-1]
    if supply_change.least_battery(power, marked, CONVERTER_STOPS) > BATTERY_LOW:
        problems.append(f"a change of supply can stop the converter with {label} from a {BATTERY_LOW:.1f} V battery")
    return problems


def main():
    with open(sys.argv[1]) as fh:
        all_parts = parts_module.resolve(json.load(fh))
    usb = usb_input.describe(all_parts)
    problems = check_rail(all_parts) + check_timer(all_parts) + check_switch(usb) + check_mux(usb) + check_supervisor(all_parts)
    if problems:
        print("\n".join(problems))
        raise SystemExit(f"{len(problems)} problems with the values that set the rails, the thresholds and the timer")
    print("the values that set the rail, the timer, the USB switch and the reset are inside their limits, and the mux hands over as designed")


if __name__ == "__main__":
    main()
