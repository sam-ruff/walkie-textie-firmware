"""Read a part's value and rating from the way the BOM writes them."""
import re

OHMS = {"R": 1.0, "k": 1e3, "M": 1e6}
FARADS = {"pF": 1e-12, "nF": 1e-9, "uF": 1e-6}
# Tolerance letter in UNI-ROYAL and FOJAN 0402 part numbers.
TOLERANCE = {"F": 0.01, "J": 0.05}
# Samsung CL series part numbers carry the rated voltage as the letter after the tolerance.
SAMSUNG_VOLTS = {"R": 4.0, "Q": 6.3, "P": 10.0, "O": 16.0, "A": 25.0, "L": 35.0, "B": 50.0, "C": 100.0}


def ohms(value):
    match = re.fullmatch(r"([\d.]+)([RkM])", value)
    if not match:
        raise SystemExit(f"cannot read a resistance from {value!r}")
    return float(match.group(1)) * OHMS[match.group(2)]


def farads(value):
    match = re.fullmatch(r"([\d.]+)\s*(pF|nF|uF)", value)
    if not match:
        raise SystemExit(f"cannot read a capacitance from {value!r}")
    return float(match.group(1)) * FARADS[match.group(2)]


def tolerance(part):
    match = re.search(r"0402(?:WG)?([FJ])", part["mpn"])
    if not match:
        raise SystemExit(f"cannot read a tolerance from {part['ref']}'s part number {part['mpn']!r}, so this check needs updating")
    return TOLERANCE[match.group(1)]


def span(part):
    """(least, nominal, most) resistance of a part in ohms."""
    nominal, spread = ohms(part["value"]), tolerance(part)
    return nominal * (1 - spread), nominal, nominal * (1 + spread)


def divided(top, bottom):
    """(least, nominal, most) of (top + bottom) / bottom for two resistors given as spans."""
    return (top[0] + bottom[2]) / bottom[2], (top[1] + bottom[1]) / bottom[1], (top[2] + bottom[0]) / bottom[0]


def rated_volts(part_number):
    match = re.match(r"CL\d\d[A-Z]\d{3}[A-Z]([A-Z])", part_number)
    if not match or match.group(1) not in SAMSUNG_VOLTS:
        raise SystemExit(f"cannot read a voltage rating from {part_number!r}, so this check needs updating")
    return SAMSUNG_VOLTS[match.group(1)]


def between(all_parts, prefix, net_a, net_b):
    """Fitted parts of one kind, by the letters of their designator, that join two nets."""
    return [part for part in all_parts.values()
            if part["ref"].rstrip("0123456789") == prefix and not part["dnp"] and set(part["nets"].values()) == {net_a, net_b}]


def one(found, what):
    if len(found) != 1:
        raise SystemExit(f"expected one {what}, found {[part['ref'] for part in found]}: this check needs updating")
    return found[0]


def resistor_between(all_parts, net_a, net_b):
    """The one fitted resistor joining two nets."""
    return one(between(all_parts, "R", net_a, net_b), f"resistor between {net_a} and {net_b}")


def names(some_parts):
    return " and ".join(f"{part['ref']} {part['value']}" for part in some_parts)
