"""Bound the emissions and the discharge stress that the layout and the parts decide.

Usage: check_emc.py board.kicad_pcb model.json

Design-time bounds taken from the board's own geometry. They rule out what can
be calculated: field from the converter's switching loops, a static discharge
to the plug's shell overstressing the capacitor behind it, and the ring on the
USB input, when it is plugged into a supply that is already on, reaching a
part that does not allow it. They cannot rule out common-mode current on the
cables, which decides most radiated emission results and has to be measured.
The check prints the current that reaches the limit, so a clamp-on probe can
be read against it.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hot_plug
import parts as parts_module
import pcbnew
import usb_input
from kiboard import xy
from copper_grid import collect
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from values import farads, names, rated_volts, span

# TPS631000 datasheet: its power ground pin, largest switch current limit and fastest switching frequency.
CONVERTER = {"ref": "U5", "ground": "7", "amps": 3.35, "hertz": 2.2e6}
# The loops that carry the switched current: (name, capacitor, converter pin). Each closes through the ground pin.
LOOPS = [("input", "C1", "4"), ("output", "C26", "1")]
SWITCH_NODES = ("LX1", "LX2")
# EN 55032 class B at 3 m, quasi-peak: (from Hz, to Hz, dBuV/m).
CLASS_B = [(30e6, 230e6, 40.0), (230e6, 1000e6, 47.0)]
DISTANCE = 3.0
# Far field at 1 m of a small loop (per Hz^2 m^2 A) and of a resonant wire (per A),
# each doubled for the reflection off the chamber floor.
LOOP_FIELD = 2 * 1.316e-14
WIRE_FIELD = 2 * 60.0
# IEC 61000-4-2: the discharge network's capacitor and its test levels in volts.
# EN 301 489-1 asks for 4 kV by contact and 8 kV through air; 15 kV is the standard's hardest level.
DISCHARGE_FARADS = 150e-12
DISCHARGE_VOLTS = (4000, 8000, 15000)
SHELL_NET = "CHS"
# TPS2595 datasheet: the most its input and its enable pin allow, its resistance when on, and how long it
# waits after power arrives before it raises its output. The wait is a typical figure, for nothing on its
# slew pin; a capacitor there makes it longer.
SWITCH_INPUT_VOLTS = 20.0
SWITCH_ENABLE_VOLTS = 6.0
SWITCH_OHMS = 0.034
SWITCH_WAIT = 149e-6
# The parts whose supply pins allow 6 V, from their datasheets: the mux, the converter and the timer.
SIX_VOLT_PARTS = ("TPS2116DRLR", "TPS631000DRLR", "TPL5111DDCR")
SIX_VOLTS = 6.0
MUX_OHMS = 0.037           # TPS2116 datasheet: its resistance when on, at 5 V
# USB 2.0, section 7.2.4.1: the most a device may put straight across VBUS unless it limits its inrush,
# and section 7.2.1: the current a device may take before the host has agreed to more.
USB_BULK_FARADS = 10e-6
USB_UNIT_LOAD = 0.1
RING_LEFT = 0.05           # volts of the ring that may be left when the switch turns on
# Share of its marked value that a capacitor behind the switch keeps at 5 V, at the bottom of its
# tolerance, hot or cold, less what 5 V across it takes: a part rated for 25 V or more, and one rated
# for 6.3 V, which loses far more to the voltage.
BEHIND_KEEPS = 0.45
LOW_RATED_KEEPS = 0.24
LOW_RATED_VOLTS = 10.0
# The ring behind the switch when a plug makes contact again has to stay this far under what the parts
# there allow, at the worst case of the model's ranges.
RING_MARGIN = 0.05
# The same ring with less to damp it than those ranges have: the capacitors keeping a smaller share of
# their marked value, which their maker does not publish for these parts, and the two switches at three
# quarters of their typical resistance, since neither datasheet gives a least. It has to stay under what
# the parts allow.
HARSH_KEEPS = 0.35
HARSH_LOW_RATED_KEEPS = 0.19
HARSH_SWITCHES = 0.75
# The diode from VBUS to the mux's output, from the ES1DL datasheet: what it drops over the currents the
# ring puts through it (its typical curve has 0.55 V at 10 mA and 1.0 V at 3 A), the least of those once
# it carries an amp or more, and the surge it is rated for, once.
CLAMP = {"part": "ES1D", "volts": (0.55, 0.8, 1.0), "least_volts": 0.6, "surge_amps": 30.0}


def pad_centres(board, ref):
    """{pad number: (net, (x, y))} for one part, in board millimetres."""
    footprint = board.FindFootprintByReference(ref)
    if footprint is None:
        raise SystemExit(f"{ref} is not on the board, so this check needs updating")
    return {pad.GetNumber(): (pad.GetNetname(), xy(pad.GetPosition())) for pad in footprint.Pads()}


def switching_loop(board, capacitor, pin):
    """Corners of the loop from a capacitor, through a converter pin, back by the converter's ground pin."""
    converter = pad_centres(board, CONVERTER["ref"])
    net, at_pin = converter[pin]
    ground_net, at_ground = converter[CONVERTER["ground"]]
    on_net = {pad_net: at for pad_net, at in pad_centres(board, capacitor).values()}
    if ground_net != "GND" or net == "GND" or net not in on_net or "GND" not in on_net:
        raise SystemExit(f"{capacitor} does not sit between {CONVERTER['ref']} pin {pin} and ground, so this check needs updating")
    return [on_net[net], at_pin, at_ground, on_net["GND"]]


def loop_field(square_mm, hertz):
    """Most field, in dBuV/m at the test distance, that a loop of this area could radiate at one frequency.

    The loop is taken to switch the converter's whole current limit with edges of no
    duration, in free space. The ground plane a tenth of a millimetre under it, which
    cancels most of the field, is left out, so the real figure is far lower.
    """
    harmonic_amps = 2 * CONVERTER["amps"] * CONVERTER["hertz"] / (math.pi * hertz)
    volts_per_metre = LOOP_FIELD * hertz ** 2 * square_mm * 1e-6 * harmonic_amps / DISTANCE
    return 20 * math.log10(volts_per_metre / 1e-6)


def copper_shape(kind, geometry):
    if kind == "box":
        return box(*geometry)
    if kind == "seg":
        start, end, half_width = geometry
        return LineString([start, end]).buffer(half_width)
    if kind == "dot":
        centre, radius = geometry
        return Point(centre).buffer(radius)
    return Polygon(geometry)


def copper_on(items, net):
    """(area in mm2, layers, number of vias) of everything copper on one net."""
    mine = [item for item in items if item[1] == net]
    if not mine:
        raise SystemExit(f"no copper on {net}, so this check needs updating")
    layers = set().union(*(item[0] for item in mine))
    area = unary_union([copper_shape(kind, geometry) for _, _, kind, geometry in mine]).area
    return area, layers, sum(1 for item in mine if item[2] == "dot")


def polygon_area(points):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1]))) / 2


def check_converter(board):
    problems = []
    areas = {name: polygon_area(switching_loop(board, capacitor, pin)) for name, capacitor, pin in LOOPS}
    print(f"converter {CONVERTER['ref']}: " + ", ".join(f"{name} loop through {capacitor} {areas[name]:.1f} mm2" for name, capacitor, _ in LOOPS))
    largest = max(areas.values())
    print(f"field from a {largest:.1f} mm2 loop switching {CONVERTER['amps']} A at {CONVERTER['hertz'] / 1e6:.1f} MHz, "
          f"with edges of no duration and no ground plane under it, at {DISTANCE:.0f} m:")
    for _, top, limit in CLASS_B:
        field = loop_field(largest, top)
        print(f"  {field:5.1f} dBuV/m at {top / 1e6:.0f} MHz, {limit - field:.1f} dB under the {limit:.0f} dBuV/m limit")
        if field > limit:
            problems.append(f"a converter loop of {largest:.1f} mm2 could reach the class B limit at {top / 1e6:.0f} MHz: move its capacitor closer")

    items = collect(board)
    for net in SWITCH_NODES:
        area, layers, vias = copper_on(items, net)
        print(f"switch node {net}: {area:.1f} mm2 of copper on {', '.join(sorted(layers)) or 'no layer'}, {vias} vias")
        if layers != {"top"} or vias:
            problems.append(f"switch node {net} leaves the top layer, where the ground plane is right under it")
    return problems


def print_cable_ceiling():
    """The common-mode current at which a cable, radiating as a resonant wire, meets the limit by itself."""
    print("common-mode current that takes a cable to the limit, as a resonant wire:")
    for low, high, limit in CLASS_B:
        amps = 10 ** (limit / 20) * 1e-6 * DISTANCE / WIRE_FIELD
        print(f"  {amps * 1e6:.1f} uA ({20 * math.log10(amps / 1e-6):.0f} dBuA) from {low / 1e6:.0f} to {high / 1e6:.0f} MHz")


def check_shell(all_parts):
    fitted = [part for part in all_parts.values() if not part["dnp"] and set(part["nets"].values()) == {SHELL_NET, "GND"}]
    capacitors = [part for part in fitted if part["ref"].startswith("C")]
    if not capacitors:
        return [f"no capacitor between the plug's shell ({SHELL_NET}) and ground"]
    total = sum(farads(part["value"]) for part in capacitors)
    rating = min(rated_volts(part["mpn"]) for part in capacitors)
    reached = {volts: volts * DISCHARGE_FARADS / (DISCHARGE_FARADS + total) for volts in DISCHARGE_VOLTS}
    print(f"plug shell: {' and '.join(part['ref'] + ' ' + part['value'] for part in capacitors)}, rated {rating:.0f} V, in a static discharge reaches "
          + ", ".join(f"{reached[volts]:.0f} V at {volts / 1000:.0f} kV" for volts in DISCHARGE_VOLTS))
    worst = reached[max(DISCHARGE_VOLTS)]
    if worst > rating:
        return [f"a {max(DISCHARGE_VOLTS) / 1000:.0f} kV discharge to the plug's shell puts {worst:.0f} V on a {rating:.0f} V capacitor"]
    return []


def check_usb_input(all_parts):
    """Plugging into a supply that is already on: the ring ahead of the protection switch, and the charging behind it."""
    usb = usb_input.describe(all_parts)
    switch = usb["switch"]["ref"]
    ahead = usb["input_caps"]
    if not ahead:
        return [f"no capacitor on {switch}'s input"]
    problems = []
    marked = sum(farads(part["value"]) for part in ahead)
    rating = min(rated_volts(part["mpn"]) for part in ahead)
    peaks = [(metres, hot_plug.worst_peak(metres, marked)) for metres in hot_plug.LEAD_METRES]
    worst = max(volts for _, volts in peaks)
    top, bottom = span(usb["enable_top"]), span(usb["enable_bottom"])
    enable = worst * bottom[2] / (top[0] + bottom[2])
    left = max(hot_plug.worst_left(metres, SWITCH_WAIT) for metres in hot_plug.LEAD_METRES)
    print(f"USB input plugged into a {hot_plug.SOURCE_VOLTS} V supply that is already on: {switch} is off, and {names(ahead)} is the only capacitance ahead of it")
    print("  highest peak there, modelled: " + ", ".join(
        f"{volts:.1f} V {'straight into a socket' if not metres else f'on {metres:g} m of lead'}" for metres, volts in peaks)
        + f"; {switch} allows {SWITCH_INPUT_VOLTS:.0f} V and the capacitor {rating:.0f} V")
    print(f"  the peak puts {enable:.1f} V on {switch}'s enable pin, which allows {SWITCH_ENABLE_VOLTS:.0f} V")
    print(f"  {switch} waits {SWITCH_WAIT * 1e6:.0f} us before it raises its output, a typical figure that its slew capacitor lengthens, "
          f"by when {left * 1000:.1f} mV of the ring is left at the most")
    if worst > min(SWITCH_INPUT_VOLTS, rating):
        problems.append(f"plugged into a live supply the USB input can ring to {worst:.1f} V, over what {switch} or its capacitor allows")
    if enable > SWITCH_ENABLE_VOLTS:
        problems.append(f"the ring on the USB input can put {enable:.1f} V on {switch}'s enable pin")
    if left > RING_LEFT:
        problems.append(f"the ring on the USB input can still be there when {switch} turns on")

    pads = usb_input.on_net(all_parts, usb["plug_net"]) + usb_input.on_net(all_parts, usb["input_net"])
    there = sorted({ref for ref, _ in pads})
    print(f"  ahead of {switch}: {' '.join(there)}; none of the parts that allow 6 V")
    problems += [f"{ref} allows 6 V and is ahead of {switch}" for ref in there if all_parts[ref]["value"] in SIX_VOLT_PARTS]

    behind = usb["output_caps"] + usb["system_caps"]
    rate = usb_input.slew_rate(usb)
    amps = usb_input.marked_farads(behind) * rate * 1000
    print(f"  behind it VBUS rises at {rate:.2f} V a millisecond, so nothing there sees a step: {names(behind)} charge at {amps * 1000:.0f} mA, "
          f"where a USB port owes a device {USB_UNIT_LOAD * 1000:.0f} mA before it has asked for more")
    print(f"  {marked * 1e6:.1f} uF is straight across the plug, where USB 2.0 allows a device {USB_BULK_FARADS * 1e6:.0f} uF")
    if amps > USB_UNIT_LOAD:
        problems.append(f"{switch} would charge the board's capacitors at more than a USB port owes a device")
    if marked > USB_BULK_FARADS:
        problems.append("more capacitance sits straight across the plug than USB 2.0 allows")

    return problems + check_contact_again(usb, ahead, behind)


def kept_at_usb(capacitors, keeps=BEHIND_KEEPS, low_rated_keeps=LOW_RATED_KEEPS):
    """Farads that capacitors keep of their marked value with 5 V across them, at the worst case."""
    return sum(farads(part["value"]) * (low_rated_keeps if rated_volts(part["mpn"]) < LOW_RATED_VOLTS else keeps)
               for part in capacitors)


def check_contact_again(usb, ahead, behind):
    """The plug losing contact and making it again while the switch is on, when the ring passes through it.

    The switch turns off once its input is under its threshold, so what is behind it can be no lower than
    that when contact comes back. There are two states. With USB selected, every capacitor on the mux's
    output is behind the switch and damps the ring. With the battery selected, which the mux goes back to
    as soon as VBUS is under the battery's voltage, only the capacitors on VBUS itself are, and a diode
    has to pass the ring on to the rest.
    """
    problems = []
    switch = usb["switch"]["ref"]
    _, off = usb_input.switch_thresholds(usb)
    allowed = SIX_VOLTS * (1 - RING_MARGIN)
    everything = ahead + behind
    kept = kept_at_usb(everything)
    again = max(hot_plug.remake_peak(metres, kept, off[0], SWITCH_OHMS + MUX_OHMS) for metres in hot_plug.LEAD_METRES)
    less = kept_at_usb(everything, HARSH_KEEPS, HARSH_LOW_RATED_KEEPS)
    harsh = max(hot_plug.remake_peak(metres, less, off[0], (SWITCH_OHMS + MUX_OHMS) * HARSH_SWITCHES) for metres in hot_plug.LEAD_METRES)
    print(f"the plug losing contact and making it again with {switch} on: what is behind it is at {off[0]:.2f} V or more, "
          f"and the parts there allow {SIX_VOLTS:.0f} V")
    print(f"  with USB selected, {kept * 1e6:.0f} uF at the least is behind {switch} and the highest peak there, modelled, is {again:.2f} V, "
          f"which has to be {RING_MARGIN:.0%} under what those parts allow: {allowed:.2f} V")
    print(f"  with the capacitors keeping {HARSH_KEEPS:.0%} of their marked value, not {BEHIND_KEEPS:.0%}, and the two switches at "
          f"{HARSH_SWITCHES:.0%} of their typical resistance, it is {harsh:.2f} V")
    print(f"  {switch} also holds its output down once its input passes {usb_input.CLAMP_FROM[0]} to {usb_input.CLAMP_FROM[2]} V, but takes "
          f"{usb_input.CLAMP_SECONDS * 1e6:.0f} us, a typical figure, to start")
    if again > allowed:
        problems.append(f"a plug that makes contact again can ring the parts behind {switch} to {again:.2f} V, less than {RING_MARGIN:.0%} under what they allow")
    if harsh >= SIX_VOLTS:
        problems.append(f"with less to damp it than the model's ranges, a plug that makes contact again rings the parts behind {switch} to {harsh:.2f} V")
    if max(usb_input.CLAMP_FROM[2], usb_input.CLAMP_TO[2]) >= SIX_VOLTS:
        problems.append(f"{switch} does not hold its output under what the parts behind it allow")

    few = ahead + usb["output_caps"]
    bare = max(hot_plug.remake_peak(metres, kept_at_usb(few), off[0], SWITCH_OHMS) for metres in hot_plug.LEAD_METRES)
    print(f"  with the battery selected, which takes a battery over {off[0]:.2f} V, only {names(few)} are behind {switch}: "
          f"left to themselves they would ring to {bare:.1f} V")
    if len(usb["clamp"]) != 1:
        return problems + [f"nothing turns that ring into the mux's output: expected one diode from {usb['output_net']} to {usb['system_net']}"]
    diode = usb["clamp"][0]
    # The mux lets no current back into the battery, so the diode does not hold VBUS near the battery's
    # voltage: it passes the ring on to the capacitors on the mux's output, which start at the battery's
    # voltage, taken at its least. The few capacitors on VBUS are taken at each end of what they may keep.
    # Once VBUS is over the battery the mux changes over to USB and joins the two nodes itself, which
    # is the state worked out above, so the bound is the higher of the two figures.
    small = usb_input.marked_farads(few)

    def through_diode(large, switch_ohms):
        return max(hot_plug.remake_peak_through_diode(metres, small * share, large, off[0], switch_ohms, CLAMP["volts"])
                   for metres in hot_plug.LEAD_METRES for share in (BEHIND_KEEPS, max(hot_plug.INPUT_KEEPS)))

    through = through_diode(kept_at_usb(usb["system_caps"]), SWITCH_OHMS)
    harsh_through = through_diode(kept_at_usb(usb["system_caps"], HARSH_KEEPS, HARSH_LOW_RATED_KEEPS), SWITCH_OHMS * HARSH_SWITCHES)
    print(f"  {diode['ref']} {diode['value']} passes that ring on to the capacitors on the mux's output, {CLAMP['volts'][0]} to {CLAMP['volts'][-1]} V "
          f"below VBUS: the highest peak on VBUS, modelled, is then {through:.2f} V, and {harsh_through:.2f} V with the harsher figures, "
          f"until the mux changes over to USB and the state above applies")
    # The most the lead can push through the diode is the supply over the least resistance in the way,
    # as if nothing else limited it.
    surge = (hot_plug.SOURCE_VOLTS - off[0] - CLAMP["least_volts"]) / (hot_plug.least_ohms() + SWITCH_OHMS)
    print(f"  the most the lead can push through {diode['ref']} is {surge:.0f} A, and it is rated for {CLAMP['surge_amps']:.0f} A once")
    if through > allowed:
        problems.append(f"with the battery selected a plug that makes contact again can ring VBUS to {through:.2f} V, less than {RING_MARGIN:.0%} under what its parts allow")
    if harsh_through >= SIX_VOLTS:
        problems.append(f"with the battery selected and less to damp it than the model's ranges, a plug that makes contact again rings VBUS to {harsh_through:.2f} V")
    if diode["value"] != CLAMP["part"]:
        problems.append(f"{diode['ref']} is not the {CLAMP['part']} whose ratings this check knows")
    if diode["nets"]["1"] != usb["system_net"]:
        problems.append(f"{diode['ref']} has its cathode on {diode['nets']['1']}, not on the mux's output")
    if surge >= CLAMP["surge_amps"]:
        problems.append(f"the lead can push {surge:.0f} A through {diode['ref']}, which is rated for {CLAMP['surge_amps']:.0f} A")
    return problems


def main():
    board_path, model_path = sys.argv[1:3]
    with open(model_path) as fh:
        all_parts = parts_module.resolve(json.load(fh))
    board = pcbnew.LoadBoard(board_path)
    problems = check_converter(board)
    print_cable_ceiling()
    problems += check_shell(all_parts)
    print("the USB input, for each order that is powered:")
    problems += parts_module.for_each_order(all_parts, check_usb_input)
    if problems:
        print("\n".join(problems))
        raise SystemExit(f"{len(problems)} problems in the emissions and discharge bounds")
    print("emissions, discharge and hot-plug bounds hold; cable currents still have to be measured")


if __name__ == "__main__":
    main()
