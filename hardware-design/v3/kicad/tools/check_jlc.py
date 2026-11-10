"""Check every order's BOM and placement file against JLCPCB's own library entry for each part.

Usage: check_jlc.py fab_dir board.kicad_pcb jlc_library_dir model.json [--fetch]

For every part an order places this takes JLCPCB's footprint for its LCSC
number, puts it at the position and rotation in the placement file as written,
and compares each pad with the pad of the same number on the board. A part
that would be fitted turned or offset shows up as pads that do not line up.

It also checks that the part number JLCPCB holds for each LCSC number is the
one in the BOM, and that every connected pad has the function in JLCPCB's
symbol for that part that it has in the schematic symbol. A substitute with
another pinout, or a diode the other way round, shows up there.

A part sent to JLCPCB for it to place can have a library entry with no
footprint. It is then compared with the entry the design names in its place.
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import jlc
import parts as parts_module
import pcbnew
from kiboard import numbered_pads
from make_schematic import BOXES, OWN_LIB, symbol_for
from project import KICAD_SYMBOLS
from sym_pins import load_symbol, pins

TOLERANCE = 0.35           # mm: KiCad's and JLCPCB's land patterns differ by up to about 0.3 mm on the same part
CATHODE = {"K", "C", "-"}
ANODE = {"A", "+"}
# Pads where the schematic symbol and JLCPCB's symbol name one function two ways:
# (designator, pad) -> (name in the schematic, name in JLCPCB's symbol).
SAME_FUNCTION = {
    ("U1", "13"): ("USB_D-", "IO19"),
    ("U1", "14"): ("USB_D+", "IO20"),
    ("U10", "5"): ("~{DRV}", "DRVn"),
    ("U13", "2"): ("~{RESET}", "RESET#"),
    ("J1", "A5"): ("CC", "CC1"),
    ("J1", "A6"): ("D+", "DP1"),
    ("J1", "A7"): ("D-", "DN1"),
    ("J1", "25"): ("SHELL", "EH"),
    ("J1", "26"): ("SHELL", "EH"),
    ("J1", "27"): ("SHELL", "EH"),
    ("J1", "28"): ("SHELL", "EH"),
    ("J3", "1"): ("In", "SIN"),
    ("J3", "2"): ("Ext", "GND"),
    # JLCPCB's symbol lets either end of the antenna be the feed. The other end goes to the printed
    # tuning line and not to ground, as in both 868 MHz layouts of the Pulse datasheet.
    ("ANT1", "1"): ("FEED", "Feed/GND"),
    ("ANT1", "2"): ("PCB_Trace", "GND/Feed"),
}


def same_part(ours, theirs):
    def squash(text):
        return re.sub(r"[^A-Z0-9]", "", text.upper())

    a, b = squash(ours), squash(theirs)
    return bool(a) and bool(b) and (a in b or b in a)


def schematic_pin_names(ref):
    """{pad number: pin name} from the symbol the schematic draws for a part."""
    lib, name, _ = symbol_for(ref)
    if lib == OWN_LIB:
        return {number: pin_name for side in ("left", "right") for number, pin_name, _ in BOXES[name].get(side, [])}
    return {pin["number"]: pin["name"] for pin in pins(load_symbol(KICAD_SYMBOLS, lib, name))}


def same_function(ours, theirs):
    if ours is None:
        return False
    if ours.upper() == theirs.upper():
        return True
    return (ours in CATHODE and theirs in CATHODE) or (ours in ANODE and theirs in ANODE)


def function_problems(ref, entry, nets, same_as):
    """Connected pads that JLCPCB's symbol for the part gives another function than the schematic symbol does.

    `nets` is {pad number: net name}, and `same_as` gives JLCPCB's numbers for a pad it numbers differently.
    A symbol of JLCPCB's that only numbers its pins says nothing and is skipped.
    """
    theirs = jlc.symbol_pin_names(entry)
    if all(name.isdigit() for name in theirs.values()):
        return []
    ours = schematic_pin_names(ref)
    here = {their: our for our, their_numbers in same_as.items() for their in their_numbers}
    out = []
    for their_number, their_name in sorted(theirs.items()):
        number = here.get(their_number, their_number)
        net = nets.get(number, "")
        if not net or net.startswith("unconnected-"):
            continue
        if same_function(ours.get(number), their_name) or SAME_FUNCTION.get((ref, number)) == (ours.get(number), their_name):
            continue
        out.append(f"{ref}: pad {number} (net {net}) is {their_name!r} in JLCPCB's part and {ours.get(number)!r} in the schematic symbol")
    return out


def order_files(fab_dir):
    """({designator: BOM row}, {designator: (x, y, rotation)}) over every order's files, and where two orders disagree."""
    bom, placed, problems = {}, {}, []
    for order in design.ORDERS:
        folder = fab_dir if order == design.DEFAULT_ORDER else os.path.join(fab_dir, order)
        with open(os.path.join(folder, "BOM.csv"), newline="") as fh:
            rows = {ref.strip(): row for row in csv.DictReader(fh) for ref in row["Designator"].split(",")}
        with open(os.path.join(folder, "CPL.csv"), newline="") as fh:
            places = {row["Designator"]: (float(row["Mid X"]), float(row["Mid Y"]), float(row["Rotation"])) for row in csv.DictReader(fh)}
        for ref, row in rows.items():
            if bom.setdefault(ref, row)["LCSC Part #"] != row["LCSC Part #"]:
                problems.append(f"{ref} has one part number in one order and another in order {order}")
        for ref, place in places.items():
            if placed.setdefault(ref, place) != place:
                problems.append(f"{ref} is placed one way in one order and another way in order {order}")
    return bom, placed, problems


def main():
    fab_dir, board_path, cache_dir, model_path = sys.argv[1:5]
    fetch = "--fetch" in sys.argv
    bom, placed, problems = order_files(fab_dir)
    with open(model_path) as fh:
        all_parts = parts_module.resolve(json.load(fh))
    board = pcbnew.LoadBoard(board_path)
    footprints = {fp.GetReference(): fp for fp in board.GetFootprints()}
    pads = {ref: numbered_pads(fp) for ref, fp in footprints.items()}
    nets = {ref: {pad.GetNumber(): pad.GetNetname() for pad in fp.Pads() if pad.GetNumber()} for ref, fp in footprints.items()}

    worst = (0.0, "")
    turned = []
    checked = 0
    named = 0
    for ref in sorted(placed):
        kicad_rotation = footprints[ref].GetOrientationDegrees() % 360
        x, y, rotation = placed[ref]
        lcsc = bom[ref]["LCSC Part #"]
        stand_in = all_parts[ref]["footprint_as"]
        if not lcsc:
            problems.append(f"{ref} is placed but has no part number for JLCPCB")
            continue
        same_as = all_parts[ref]["jlc_pads"]
        entry = jlc.library_entry(stand_in or lcsc, cache_dir, fetch)
        error = jlc.misfit(pads[ref], jlc.footprint_pads(entry), x, y, rotation, same_as)
        if abs(kicad_rotation - rotation) > 0.01:
            turned.append(f"{ref} {kicad_rotation:.0f} to {rotation:.0f}")
        if stand_in:
            print(f"  {ref}: {lcsc} is a part sent to JLCPCB and its entry has no footprint; compared with {stand_in} ({jlc.part_number(entry)})")
        elif not same_part(bom[ref]["MPN"], jlc.part_number(entry)):
            problems.append(f"{ref}: BOM says {bom[ref]['MPN']!r} for {lcsc}, JLCPCB holds {jlc.part_number(entry)!r}")
        if error > TOLERANCE:
            problems.append(f"{ref} ({lcsc}): pads are {error:.2f} mm from where JLCPCB's footprint has them at rotation {rotation:.0f}")
        worst = max(worst, (error, ref))
        problems += function_problems(ref, entry, nets[ref], same_as)
        named += not all(name.isdigit() for name in jlc.symbol_pin_names(entry).values())
        checked += 1

    print(f"{checked} parts compared with JLCPCB's footprints; largest pad offset {worst[0]:.2f} mm ({worst[1]})")
    print(f"rotations that differ from KiCad's because JLCPCB draws the footprint another way round: {', '.join(turned) or 'none'}")
    print(f"{named} parts whose pins JLCPCB names: every connected pad has the same function in the schematic")
    if problems:
        print("\n".join(problems))
        raise SystemExit(f"{len(problems)} differences from JLCPCB's library")
    print("placement file, part numbers and pin functions agree with JLCPCB's library")


if __name__ == "__main__":
    main()
