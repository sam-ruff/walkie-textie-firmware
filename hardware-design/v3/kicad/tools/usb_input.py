"""The USB input as the design has it: the protection switch, the power mux and the parts that set what they do.

check_values.py compares the thresholds and the limit these parts set with
what the board needs, and check_emc.py works out what plugging in does to
them. Both read the circuit from the netlist, so a part that is moved or
renamed is followed and one that is missing stops the check.
"""
from values import between, divided, farads, one, span

# Pads of the TPS259531 and of the TPS2116, from their datasheets.
SWITCH = {"part": "TPS259531", "slew": "1", "enable": "2", "in": "3", "out": "5", "limit": "7"}
MUX = {"part": "TPS2116DRLR", "out": "2", "usb": "3", "select": "4", "mode": "5", "battery": "6"}
PLUG = ("J1", "A4")          # one of the plug's VBUS contacts
# TPS2595 datasheet: the enable pin's thresholds in volts (least, typical, most), the resistance its
# limit pin takes, how closely it holds the limit that sets, and the least capacitor its slew pin takes.
SWITCH_ON = (1.13, 1.20, 1.27)
SWITCH_OFF = (1.03, 1.10, 1.17)
LIMIT_OHMS = (487.0, 5000.0)
LIMIT_ACCURACY = 0.075
SLEW_FARADS = 3300e-12
# The TPS259531's clamp: the input voltage from which it holds its output down, the voltage it holds it
# at (each least, typical, most), and how long it takes to start, at 0.1 A.
CLAMP_FROM = (5.5, 5.7, 5.9)
CLAMP_TO = (5.2, 5.45, 5.7)
CLAMP_SECONDS = 10e-6


def describe(all_parts):
    """The parts and nets of the USB input, by what they do."""
    switch = one([part for part in all_parts.values() if part["value"] == SWITCH["part"]], f"{SWITCH['part']} on the USB input")
    mux = one([part for part in all_parts.values() if part["value"] == MUX["part"]], f"{MUX['part']} power mux")
    pin = {name: switch["nets"][pad] for name, pad in SWITCH.items() if name != "part"}
    plug = all_parts[PLUG[0]]["nets"][PLUG[1]]
    system = mux["nets"][MUX["out"]]
    return {
        "switch": switch,
        "mux": mux,
        "plug_net": plug,
        "input_net": pin["in"],
        "output_net": pin["out"],
        "system_net": system,
        "bead": one(between(all_parts, "L", plug, pin["in"]), "bead between the plug and the switch"),
        "input_caps": between(all_parts, "C", plug, "GND") + between(all_parts, "C", pin["in"], "GND"),
        "enable_top": one(between(all_parts, "R", pin["in"], pin["enable"]), "resistor from the switch's input to its enable pin"),
        "enable_bottom": one(between(all_parts, "R", pin["enable"], "GND"), "resistor from the switch's enable pin to ground"),
        "slew_cap": one(between(all_parts, "C", pin["slew"], "GND"), "capacitor on the switch's slew pin"),
        "limit": one(between(all_parts, "R", pin["limit"], "GND"), "resistor on the switch's limit pin"),
        "output_caps": between(all_parts, "C", pin["out"], "GND"),
        "system_caps": between(all_parts, "C", system, "GND"),
        "bleed": one(between(all_parts, "R", pin["out"], "GND"), "resistor from the switch's output to ground"),
    }


def on_net(all_parts, net):
    """[(designator, pad)] of every pad on a net."""
    return sorted((part["ref"], pad) for part in all_parts.values() for pad, pad_net in part["nets"].items() if pad_net == net)


def switch_thresholds(usb):
    """((least, nominal, most) input volts at which the switch turns on, the same for turning off)."""
    ratio = divided(span(usb["enable_top"]), span(usb["enable_bottom"]))
    return tuple(tuple(volts * part for volts, part in zip(edge, ratio)) for edge in (SWITCH_ON, SWITCH_OFF))


def limit_amps(usb):
    """(least, nominal, most) amps the switch limits its output to: equation 4 of its datasheet."""
    low, nominal, high = span(usb["limit"])
    return (2000 / high + 0.04) * (1 - LIMIT_ACCURACY), 2000 / nominal + 0.04, (2000 / low + 0.04) * (1 + LIMIT_ACCURACY)


def slew_rate(usb):
    """Volts per millisecond at which the switch raises its output: equation 3 of its datasheet."""
    return 42000 / (farads(usb["slew_cap"]["value"]) / 1e-12)


def marked_farads(capacitors):
    return sum(farads(part["value"]) for part in capacitors)
