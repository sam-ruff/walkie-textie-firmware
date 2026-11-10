"""Check the board's pad nets against the schematic and name its unconnected pads as KiCad does.

Usage: sync_nets.py board.kicad_pcb schematic.kicad_sch

The schematic's netlist is exported with kicad-cli. Every pad must carry the
net its pin has there. A pin that is marked not connected has a net of its own
in the netlist, named by KiCad after the pin; the matching pad gets that name,
which is what "Update PCB from Schematic" would do.
"""
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from kiboard import Nets, seed_ids
from project import KICAD_CLI
from sexpr import find, find_all, parse


def schematic_netlist(schematic):
    """({(reference, pin number): net name}, {reference: symbol id}) from the schematic."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "netlist.net")
        res = subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", out, schematic], capture_output=True, text=True)
        if not os.path.exists(out):
            raise SystemExit(f"netlist export failed: {res.stdout} {res.stderr}")
        with open(out) as fh:
            tree = parse(fh.read())
    table = {}
    for net in find_all(find(tree, "nets"), "net"):
        name = str(find(net, "name")[1])
        for node in find_all(net, "node"):
            table[(str(find(node, "ref")[1]), str(find(node, "pin")[1]))] = name
    symbols = {str(find(comp, "ref")[1]): str(find(comp, "tstamps")[1]) for comp in find_all(find(tree, "components"), "comp")}
    return table, symbols


def main():
    seed_ids(__file__)
    board_path, schematic = sys.argv[1:3]
    expected, symbols = schematic_netlist(schematic)
    board = pcbnew.LoadBoard(board_path)
    nets = Nets(board)
    problems = []
    named = 0
    seen = set()
    for fp in board.GetFootprints():
        if fp.GetAttributes() & pcbnew.FP_BOARD_ONLY:
            continue
        ref = fp.GetReference()
        if ref in symbols:
            # tie the footprint to its symbol, so "Update PCB from Schematic" finds it without matching by name
            fp.SetPath(pcbnew.KIID_PATH(f"/{symbols[ref]}"))
            fp.SetSheetname("/")
            fp.SetSheetfile(os.path.basename(schematic))
        for pad in fp.Pads():
            if not pad.GetNumber():     # a paste opening with no number has no pin
                continue
            key = (ref, pad.GetNumber())
            seen.add(key)
            want = expected.get(key)
            have = pad.GetNetname()
            if want is None:
                problems.append(f"{ref} pad {pad.GetNumber()}: no such pin in the schematic")
            elif not have and want.startswith("unconnected-"):
                pad.SetNet(nets.get(want))
                named += 1
            elif have != want:
                problems.append(f"{ref} pad {pad.GetNumber()}: board has {have or 'no net'!r}, schematic has {want!r}")
    problems += [f"{ref} pin {pin}: in the schematic but not on the board" for ref, pin in sorted(set(expected) - seen)]
    if problems:
        print("\n".join(problems))
        raise SystemExit(f"{len(problems)} differences between the board and the schematic")
    board.BuildListOfNets()
    pcbnew.SaveBoard(board_path, board)
    print(f"board matches the schematic on {len(seen)} pads; {named} unconnected pads named")


if __name__ == "__main__":
    main()
