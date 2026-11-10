"""Work out the numbers that decide the radio performance of the layout.

Usage: check_rf.py model.json hand_drawn_footprints_dir jlc_cache_dir firmware_src_dir

These are design-time checks. They show the layout follows the antenna maker's
reference, that the feed is a 50 ohm line on the chosen stack-up, and what the
datasheets predict for the transmitter tests at the power the firmware sets.
They do not replace tuning the antenna match on a VNA, which only the built
board in its enclosure can settle.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import lora_spectrum
import parts as parts_module
from firmware_config import radio_settings, selectable_spreading_factors
from sexpr import find, find_all, parse

MHZ = 868.0
TARGET = 50.0
TOLERANCE = 5.0            # ohms: the board maker holds impedance to 10 per cent
# Pulse W3000 datasheet, 868 MHz reference layout.
PULSE = {"pad": (1.2, 1.6), "pitch": 6.6, "clearance": (20.0, 9.5)}
# Pulse W3000 datasheet, 868 MHz typical performance on its two 20 x 40 mm boards:
# the higher of the two peak gains and the lower of the two peak efficiencies.
ANTENNA = {"gain_dbi": -1.4, "efficiency_db": -5.4, "matched_mhz": (858.0, 878.0)}
# ESP32-S3-WROOM-1 datasheet: the antenna takes the last 6 mm of the module and wants no board under it.
MODULE_ANTENNA = 6.0
MODULE_LCSC = "C2913201"
# IR 2030 and EN 300 220-2: 500 mW ERP, which holds only inside this sub-band, and spurious emissions above 1 GHz.
BAND_HZ = (869_400_000, 869_650_000)
ERP_LIMIT = 27.0
HARMONIC_LIMIT = -30.0
DIPOLE = 2.15              # dBi: the half-wave dipole that ERP is measured against
GAIN_CEILING = 2.15        # dBi: the most antenna gain the compliance plan allows, so the worst case for every limit
# Wio-SX1262 datasheet: harmonics above 1 GHz at full power, and sensitivity at SF12 in 125 kHz.
RADIO = {"harmonic_dbm": -45.0, "sensitivity_dbm": -136.73, "measured_at": (12, 125)}
# SX1262 datasheet: the signal-to-noise ratio each spreading factor needs.
SNR_NEEDED = {7: -7.5, 8: -10.0, 9: -12.5, 10: -15.0, 11: -17.5, 12: -20.0}
# What to show beside a setting that fits poorly: half the sub-band's width, at the spreading factor with the
# symbol time of SF11 in 250 kHz.
NARROWER = {"bandwidth_khz": 125, "spreading_factor": 10}


def elliptic_k(k):
    """Complete elliptic integral of the first kind, by the arithmetic-geometric mean."""
    a, b = 1.0, math.sqrt(1.0 - k * k)
    while abs(a - b) > 1e-12:
        a, b = (a + b) / 2, math.sqrt(a * b)
    return math.pi / (2 * a)


def coplanar_over_ground(width, gap, height, permittivity, copper=0.0):
    """Impedance and effective permittivity of a track with ground beside it and a ground plane under it."""
    if copper:
        # the usual allowance for copper thickness: the track behaves as if it were this much wider
        grow = 1.25 * copper / math.pi * (1 + math.log(2 * height / copper))
        width, gap = width + grow, gap - grow / 2
    k = width / (width + 2 * gap)
    k1 = math.tanh(math.pi * width / (4 * height)) / math.tanh(math.pi * (width + 2 * gap) / (4 * height))
    ratio = elliptic_k(k) / elliptic_k(math.sqrt(1 - k * k))
    ratio1 = elliptic_k(k1) / elliptic_k(math.sqrt(1 - k1 * k1))
    fill = ratio1 / ratio
    effective = (1 + permittivity * fill) / (1 + fill)
    return 60 * math.pi / math.sqrt(effective) / (ratio + ratio1), effective


def reflection(line, load, degrees):
    """Size of the reflection looking into a short line of impedance `line` ended in `load`."""
    t = math.tan(math.radians(degrees))
    z_in = line * complex(load, line * t) / complex(line, load * t)
    return abs((z_in - load) / (z_in + load))


def footprint_pads(path):
    with open(path) as fh:
        tree = parse(fh.read())
    out = {}
    for pad in find_all(tree, "pad"):
        at, size = find(pad, "at"), find(pad, "size")
        out[str(pad[1])] = ((float(at[1]), float(at[2])), (float(size[1]), float(size[2])))
    return out


def module_top(cache_dir):
    """How far the ESP32 module reaches past its footprint origin at the antenna end, from JLCPCB's footprint."""
    with open(os.path.join(cache_dir, f"{MODULE_LCSC}.json")) as fh:
        data = json.load(fh)["result"]["packageDetail"]["dataStr"]
    origin_y = float(data["head"]["y"])
    top = 0.0
    for shape in data["shape"]:
        field = shape.split("~")
        if field[0] == "TRACK":
            ys = [float(v) for v in field[4].split(" ")][1::2]
            top = max(top, max(-(y - origin_y) * 0.254 for y in ys))
    return top


def milliwatts(dbm):
    return 10 ** (dbm / 10)


def sensitivity(spreading_factor, bandwidth_khz):
    """The module's sensitivity at the firmware's setting, scaled from the one setting its datasheet gives."""
    factor, khz = RADIO["measured_at"]
    return RADIO["sensitivity_dbm"] + 10 * math.log10(bandwidth_khz / khz) + SNR_NEEDED[spreading_factor] - SNR_NEEDED[factor]


def transmitter_budget(radio):
    """Print what the datasheets predict for the transmitter tests; return whatever would break a limit."""
    problems = []
    power = radio["power_dbm"]
    low, high = (radio["hertz"] + side * radio["bandwidth_khz"] * 500 for side in (-1, 1))
    spare = min(low - BAND_HZ[0], BAND_HZ[1] - high)
    print(f"channel: {radio['hertz'] / 1e6:.3f} MHz, {radio['bandwidth_khz']} kHz wide, so {low / 1e6:.3f} to {high / 1e6:.3f} MHz; "
          f"the 500 mW sub-band is {BAND_HZ[0] / 1e6:.3f} to {BAND_HZ[1] / 1e6:.3f} MHz, which leaves {spare / 1e3:.0f} kHz each side")
    if spare < 0:
        problems.append("the channel reaches outside the sub-band that allows 500 mW")

    erp = power + ANTENNA["gain_dbi"] - DIPOLE
    worst_erp = power + GAIN_CEILING - DIPOLE
    print(f"radiated power: +{power} dBm into the antenna's {ANTENNA['gain_dbi']} dBi is {erp:.1f} dBm ERP ({milliwatts(erp):.0f} mW); "
          f"an antenna at the plan's {GAIN_CEILING} dBi ceiling would give {worst_erp:.1f} dBm; the limit is {ERP_LIMIT:.0f} dBm")
    if worst_erp > ERP_LIMIT:
        problems.append(f"+{power} dBm could exceed the {ERP_LIMIT:.0f} dBm ERP limit")

    harmonic = RADIO["harmonic_dbm"] + GAIN_CEILING
    second, third = (multiple * radio["hertz"] / 1e6 for multiple in (2, 3))
    print(f"harmonics at {second:.0f} and {third:.0f} MHz: the module's {RADIO['harmonic_dbm']:.0f} dBm through a {GAIN_CEILING} dBi antenna "
          f"is {harmonic:.1f} dBm, {HARMONIC_LIMIT - harmonic:.1f} dB under the {HARMONIC_LIMIT:.0f} dBm limit")
    if harmonic > HARMONIC_LIMIT:
        problems.append("the module's harmonics could exceed the limit above 1 GHz")

    radiated = power + ANTENNA["efficiency_db"]
    floor = sensitivity(radio["spreading_factor"], radio["bandwidth_khz"])
    link = radiated + ANTENNA["efficiency_db"] - floor
    print(f"range: the antenna radiates {milliwatts(ANTENNA['efficiency_db']) * 100:.0f} per cent on the maker's board, {radiated:.1f} dBm ({milliwatts(radiated):.0f} mW); "
          f"sensitivity at SF{radio['spreading_factor']} in {radio['bandwidth_khz']} kHz is {floor:.1f} dBm, "
          f"so two boards have {link:.0f} dB between them ({power - floor:.0f} dB with lossless antennas)")
    low_mhz, high_mhz = ANTENNA["matched_mhz"]
    print(f"match: the maker's board holds 10 dB return loss from {low_mhz:.0f} to {high_mhz:.0f} MHz, "
          f"so the tuned dip may sit {min(radio['hertz'] / 1e6 - low_mhz, high_mhz - radio['hertz'] / 1e6):.0f} MHz off the channel")
    return problems


def modelled_line(radio, factor, bandwidth_khz):
    """One line on how the modelled signal sits in the sub-band, and whether it fits at every resolution the test allows."""
    result = lora_spectrum.fit(radio["hertz"], factor, bandwidth_khz * 1e3, radio["power_dbm"], BAND_HZ)
    narrow, wide = (width / 1e3 for width in result["occupied"])
    least, most = (room / 1e3 for room in result["room"])
    margin, offset = result["mask"]
    drift = f", which is {most * 1e9 / radio['hertz']:.1f} ppm of the carrier at best" if most > 0 else ""
    print(f"  SF{factor} in {bandwidth_khz} kHz: occupies {narrow:.1f} to {wide:.1f} kHz, room {least:+.1f} to {most:+.1f} kHz{drift}; "
          f"emission masks clear by {margin:.1f} dB at {offset / 1e3:+.0f} kHz")
    return least >= 0 and margin >= 0


def modelled_fit(radio, factors):
    """Print how a modelled LoRa signal sits in the sub-band at the firmware's settings.

    Nothing here fails the build. The model is a prediction, and the remedy for
    a poor fit is a radio setting in the firmware, which is the owner's to change.
    """
    print(f"modelled spectrum (EN 300 220-2 clauses 4.4.4 to 4.4.8): the sub-band allows {(BAND_HZ[1] - BAND_HZ[0]) / 1e3:.0f} kHz, "
          "and both occupied edges have to stay inside it as the oscillator drifts. Room is from an occupied edge to the "
          "sub-band's edge, negative when outside it")
    poor = [factor for factor in factors if not modelled_line(radio, factor, radio["bandwidth_khz"])]
    if not poor:
        return
    print("  for comparison:")
    for factor in sorted({NARROWER["spreading_factor"], min(factors)}, reverse=True):
        modelled_line(radio, factor, NARROWER["bandwidth_khz"])
    print(f"RISK: at {' and '.join(f'SF{factor}' for factor in poor)} the modelled signal does not stay inside the sub-band at every "
          f"resolution the test method allows. Expect the occupied bandwidth test to fail or pass by under 2 kHz at {radio['bandwidth_khz']} kHz.")


def main():
    model_path, footprints_dir, cache_dir, firmware_dir = sys.argv[1:5]
    with open(model_path) as fh:
        all_parts = parts_module.resolve(json.load(fh))
    with open(os.path.join(firmware_dir, "config.rs")) as fh:
        radio = radio_settings(fh.read())
    with open(os.path.join(firmware_dir, "dispatcher", "handler.rs")) as fh:
        lowest_factor, _ = selectable_spreading_factors(fh.read())
    problems = []

    # ---- the 50 ohm feed between the isolation link and the matching network
    height, permittivity = next((layer[2], layer[4]) for layer in design.STACKUP if layer[0] == "dielectric 1")
    copper = design.STACKUP[0][2]
    gap, width, _ = design.NET_CLASSES["RF"]
    feed = [entry for entry in design.COPPER if entry[0] == design.T and entry[1] == "RF_FEED" and abs(entry[3] - width) < 1e-6]
    length = sum(math.dist(a, b) for entry in feed for a, b in zip(entry[4][:-1], entry[4][1:]))
    bare, _ = coplanar_over_ground(width, gap, height, permittivity)
    real, effective = coplanar_over_ground(width, gap, height, permittivity, copper)
    degrees = 360 * length / (299792.458 / MHZ / math.sqrt(effective))
    # the line is so short that even a badly wrong impedance reflects almost nothing: show the bound
    off = max(reflection(TARGET * factor, TARGET, degrees) for factor in (0.75, 1.25))
    print(f"feed line: {width} mm wide, {gap} mm to ground, {height} mm above the ground plane: "
          f"{real:.1f} ohms ({bare:.1f} if copper thickness is ignored)")
    print(f"feed line: {length:.2f} mm long, {degrees:.1f} degrees at {MHZ:.0f} MHz; "
          f"a line 25 per cent off 50 ohms would still return less than {20 * math.log10(off):.0f} dB")
    if not (TARGET - TOLERANCE <= real <= TARGET + TOLERANCE):
        problems.append(f"feed line is {real:.1f} ohms")
    if degrees > 15:
        problems.append(f"feed line is {degrees:.0f} degrees long: its impedance now matters, so have it field-solved")

    # ---- the 868 MHz antenna against the Pulse reference layout
    pads = footprint_pads(os.path.join(footprints_dir, "Pulse_W3000.kicad_mod"))
    pitch = abs(pads["2"][0][0] - pads["1"][0][0])
    x1, y1, x2, y2 = design.ANT_CLEAR
    antenna = all_parts["ANT1"]
    print(f"antenna pads {pads['1'][1][0]} x {pads['1'][1][1]} mm at {pitch:.1f} mm centres; copper-free area {x2 - x1:.1f} x {y2 - y1:.1f} mm on all four layers")
    if pads["1"][1] != PULSE["pad"] or abs(pitch - PULSE["pitch"]) > 0.01:
        problems.append("antenna land pattern differs from the Pulse datasheet")
    if (x2 - x1, y2 - y1) != PULSE["clearance"]:
        problems.append("antenna clearance differs from the Pulse datasheet")
    if not (x1 < antenna["at"][0] < x2 and y1 < antenna["at"][1] < y2):
        problems.append("antenna is not inside its clearance")
    allowed = {"ANT1", "TL1"}
    inside = sorted(ref for ref, part in all_parts.items() if ref not in allowed and x1 < part["at"][0] < x2 and y1 < part["at"][1] < y2)
    if inside:
        problems.append(f"parts inside the antenna clearance: {inside}")
    fence = [entry[2] for entry in design.COPPER if entry[0] == design.V and entry[1] == "GND"]
    feed_x = feed[0][4][0][0]
    feed_ys = [p[1] for entry in feed for p in entry[4]]
    beside = [v for v in fence if 0.5 < abs(v[0] - feed_x) < 1.6 and min(feed_ys) - 0.5 < v[1] < max(feed_ys) + 0.5]
    print(f"ground vias beside the feed line: {len(beside)} ({', '.join(f'{v[0] - feed_x:+.1f} mm' for v in beside)})")
    if not (any(v[0] < feed_x for v in beside) and any(v[0] > feed_x for v in beside)):
        problems.append("the feed line has no ground via on both sides")

    # ---- the ESP32 module's own 2.4 GHz antenna
    module = all_parts["U1"]
    antenna_starts = module["at"][1] + module_top(cache_dir) - MODULE_ANTENNA
    print(f"ESP32 antenna starts {antenna_starts - design.BOARD_H:.2f} mm beyond the board's top edge, so nothing lies under it")
    if antenna_starts < design.BOARD_H:
        problems.append("the board reaches under the ESP32 module's antenna")
    print(f"the two antennas are {math.dist((module['at'][0], design.BOARD_H), antenna['at']):.0f} mm apart, at opposite ends of the board")

    problems += transmitter_budget(radio)
    modelled_fit(radio, sorted({radio["spreading_factor"], lowest_factor}, reverse=True))

    if problems:
        print("\n".join(problems))
        raise SystemExit(f"{len(problems)} problems in the radio layout")
    print("radio layout: follows the antenna references; tune the match on a VNA once built")


if __name__ == "__main__":
    main()
