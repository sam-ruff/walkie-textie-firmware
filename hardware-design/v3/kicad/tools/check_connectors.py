"""Check that each cable connector's pin 1 is where JST's drawing puts it, and that the silkscreen agrees.

Usage: check_connectors.py board.kicad_pcb kicad_footprints_dir

The battery and sensor connectors keep the land patterns of the PCB_V3 drop,
and the battery connector is a copy of the JST part whose own drawing does not
mark pin 1. KiCad's footprint for the JST part is the reference here: seen
from the side the plug goes in, the pins have to count the same way. A lead
made to JST's numbering then puts each wire on the pad of that number. The
legend printed beside each connector is checked against the nets on its pads.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from kiboard import dist, xy
from sexpr import find, find_all, parse

LIBRARY = "Connector_JST.pretty"
# Connector on the board -> KiCad's footprint for the JST part it is, or copies.
JST = {
    "CN1": "JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal",
    "J2": "JST_PH_S4B-PH-SM4-TB_1x04-1MP_P2.00mm_Horizontal",
}
# The sensor connector's legend reads "<pin> <name>"; the battery connector's names a polarity.
NUMBERED = "J2"
POLARITY = ("CN1", {"BAT+": "BAT_RAW", "BAT-": "GND"})


def reference_pads(path):
    """[(pad number, (x, y))] from a KiCad footprint file, with Y turned to point up as on the board."""
    with open(path) as fh:
        tree = parse(fh.read())
    return [(str(pad[1]), (float(find(pad, "at")[1]), -float(find(pad, "at")[2]))) for pad in find_all(tree, "pad")]


def centre(points):
    return (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))


def handedness(pads, signal_numbers):
    """+1 or -1: which way the pins count, seen from above with the plug's side of the connector at the bottom.

    The mounting pads sit on the plug's side of the signal pads, so the turn from
    "pin 1 to pin 2" to "signal pads to mounting pads" has one sign for each way round.
    """
    at = dict(pads)
    signal = [point for number, point in pads if number in signal_numbers]
    mounting = [point for number, point in pads if number not in signal_numbers]
    along = (at["2"][0] - at["1"][0], at["2"][1] - at["1"][1])
    out = (centre(mounting)[0] - centre(signal)[0], centre(mounting)[1] - centre(signal)[1])
    return 1 if along[0] * out[1] - along[1] * out[0] > 0 else -1


def board_pads(board, ref):
    """[(pad number, (x, y), net)] for one part."""
    return [(pad.GetNumber(), xy(pad.GetPosition()), pad.GetNetname()) for pad in board.FindFootprintByReference(ref).Pads()]


def wired_pads(board, ref):
    """The pads of a part that the schematic connects to something."""
    return [pad for pad in board_pads(board, ref) if pad[2] and not pad[2].startswith("unconnected-")]


def silkscreen(board):
    """[(text, (x, y))] printed on the top of the board."""
    return [(item.GetText(), xy(item.GetPosition())) for item in board.GetDrawings()
            if item.Type() == pcbnew.PCB_TEXT_T and item.GetLayer() == pcbnew.F_SilkS]


def check_pin_one(board, footprints_dir):
    problems = []
    for ref, name in JST.items():
        reference = reference_pads(os.path.join(footprints_dir, LIBRARY, f"{name}.kicad_mod"))
        signal_numbers = {number for number, _ in reference if number.isdigit()}
        ours = [(number, at) for number, at, _ in board_pads(board, ref)]
        same = handedness(ours, signal_numbers) == handedness(reference, signal_numbers)
        print(f"{ref}: pins 1 to {len(signal_numbers)} count {'the same way' if same else 'THE OTHER WAY'} as JST's {name.split('_')[2]}")
        if not same:
            problems.append(f"{ref}: pin 1 is at the wrong end, so a lead made to JST's numbering would be reversed")
    return problems


def check_legends(board):
    problems = []
    texts = silkscreen(board)
    net_of = {number: net for number, _, net in wired_pads(board, NUMBERED)}
    named = [re.fullmatch(r"(\d) (\S+)", text) for text, _ in texts]
    named = {match.group(1): match.group(2) for match in named if match}
    wrong = sorted(number for number, net in net_of.items() if named.get(number) != net.lstrip("+"))
    print(f"{NUMBERED}: silkscreen names " + ", ".join(f"pin {number} {name}" for number, name in sorted(named.items())))
    if wrong:
        problems.append(f"{NUMBERED}: the silkscreen does not name the net on pins {', '.join(wrong)}")

    ref, meanings = POLARITY
    wired = [(at, net) for _, at, net in wired_pads(board, ref)]
    for text, net in meanings.items():
        places = [at for label, at in texts if label == text]
        nearest = min(wired, key=lambda pad: dist(pad[0], places[0]))[1] if places else None
        print(f"{ref}: silkscreen {text} is {'beside the pad on ' + nearest if nearest else 'missing'}")
        if nearest != net:
            problems.append(f"{ref}: the silkscreen's {text} does not mark the pad on {net}")
    return problems


def main():
    board_path, footprints_dir = sys.argv[1:3]
    board = pcbnew.LoadBoard(board_path)
    problems = check_pin_one(board, footprints_dir) + check_legends(board)
    if problems:
        print("\n".join(problems))
        raise SystemExit(f"{len(problems)} problems with the connectors")
    print("connectors: pin 1 and the silkscreen agree with JST's numbering and the nets")


if __name__ == "__main__":
    main()
