"""JLCPCB's library entry for a part: the footprint and symbol it will assemble against.

JLCPCB places a part by turning its own footprint for that LCSC number through
the rotation in the placement file. Two parts in the same package can have
footprints drawn different ways round, so the rotation has to come from the
entry for the exact part number, never from the package name.

Entries are kept in a cache directory so that builds and checks run offline and
repeat exactly.
"""
import json
import math
import os
import urllib.request

API = "https://easyeda.com/api/products/{}/components?version=6.4.19.5"
UNIT = 0.254               # the library works in units of 10 mil


def library_entry(lcsc, cache_dir, fetch=False):
    path = os.path.join(cache_dir, f"{lcsc}.json")
    if not os.path.exists(path):
        if not fetch:
            raise SystemExit(f"no JLCPCB library entry for {lcsc} in {cache_dir}: run the build with --fetch")
        request = urllib.request.Request(API.format(lcsc), headers={"User-Agent": "kicad-placement-check"})
        with urllib.request.urlopen(request, timeout=60) as response, open(path, "wb") as fh:
            fh.write(response.read())
    with open(path) as fh:
        return json.load(fh)["result"]


def footprint_pads(entry):
    """{pad number: [(x, y), ...]} in millimetres from the footprint's origin, Y up."""
    data = entry["packageDetail"]["dataStr"]
    ox, oy = float(data["head"]["x"]), float(data["head"]["y"])
    out = {}
    for shape in data["shape"]:
        if shape.startswith("PAD~"):
            field = shape.split("~")
            out.setdefault(field[8], []).append(((float(field[2]) - ox) * UNIT, -(float(field[3]) - oy) * UNIT))
    return out


def symbol_pin_names(entry):
    """{pad number: pin name} from JLCPCB's schematic symbol."""
    out = {}
    for shape in entry["dataStr"]["shape"]:
        if shape.startswith("P~"):
            parts = shape.split("^^")
            if len(parts) > 4:
                out[parts[4].split("~")[4]] = parts[3].split("~")[4]
    return out


def part_number(entry):
    return entry["dataStr"]["head"]["c_para"].get("Manufacturer Part", "")


SHIFT_LEAST = 0.05         # mm: a part is moved only if that brings its pads this much closer to JLCPCB's


def offsets(board_pads, library_pads, x, y, degrees, same_as=None):
    """For each board pad, how far it is from the nearest library pad that stands for it: [(dx, dy)], or None.

    `board_pads` is [(number, (x, y)), ...], with the library footprint placed at (x, y, degrees).
    `same_as` gives JLCPCB's numbers for a board pad where the two libraries number a part differently.
    None means the library footprint has no pad for one of the board's.
    """
    turn = math.radians(degrees)
    out = []
    for number, (px, py) in board_pads:
        theirs = [pad for their_number in (same_as or {}).get(number, [number]) for pad in library_pads.get(their_number, [])]
        if not theirs:
            return None
        placed = [(x + lx * math.cos(turn) - ly * math.sin(turn), y + lx * math.sin(turn) + ly * math.cos(turn)) for lx, ly in theirs]
        tx, ty = min(placed, key=lambda at: math.hypot(px - at[0], py - at[1]))
        out.append((px - tx, py - ty))
    return out


def misfit(board_pads, library_pads, x, y, degrees, same_as=None):
    """How far, at worst, a board pad is from the library pad that stands for it, with the footprint at (x, y, degrees)."""
    found = offsets(board_pads, library_pads, x, y, degrees, same_as)
    return math.inf if found is None else max(math.hypot(dx, dy) for dx, dy in found)


def fit(board_pads, library_pads, x, y, kicad_degrees, same_as=None):
    """Where JLCPCB's footprint has to go for its pads to lie on the board's: (degrees, (x, y), misfit).

    It tries the four quarter-turns from KiCad's rotation. JLCPCB places its footprint by that footprint's
    own origin, so where its origin is not where KiCad's is, the position moves by the difference.
    """
    best = None
    for quarter in (0, 90, 180, 270):
        degrees = (kicad_degrees + quarter) % 360
        found = offsets(board_pads, library_pads, x, y, degrees, same_as)
        if found is None:
            continue
        dx, dy = (sum(part) / len(found) for part in zip(*found))
        at, error = (x, y), round(max(math.hypot(ex, ey) for ex, ey in found), 3)
        moved = round(misfit(board_pads, library_pads, x + dx, y + dy, degrees, same_as), 3)
        if moved < error - SHIFT_LEAST:              # only where moving it brings the pads closer
            at, error = (x + dx, y + dy), moved
        if best is None or (error, quarter) < (best[2], best[3]):
            best = (degrees, at, error, quarter)
    if best is None:
        return kicad_degrees, (x, y), math.inf
    return best[:3]
