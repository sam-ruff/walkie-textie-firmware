"""Check the hand-drawn routing against the rules it was drawn to.

Usage: check_routes.py board.kicad_pcb

Every track on this board is drawn by hand in design.py. KiCad's DRC checks
clearances and that no connection is left open. This checks the rules DRC does
not know: what may enter the area around the 868 MHz feed, where the top layer
has to stay clear so that a line crosses on the bottom, and how much top-layer
track lies under the LoRa module. It then lists the longer lines with their
length on each layer and their vias, so a change in routing shows in the log.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import pcbnew
from kiboard import xy
from shapely.geometry import LineString, Point, box

PLANE_NETS = {"GND", "+3V3"}
LORA_MODULE = "U11"
LISTED_FROM = 10.0             # mm: lines at least this long are listed


def body_box(board, ref):
    """The outline of a part's body, from the rectangle on its fabrication layer."""
    footprint = board.FindFootprintByReference(ref)
    corners = [xy(point) for item in footprint.GraphicalItems()
               if item.Type() == pcbnew.PCB_SHAPE_T and item.GetLayer() == pcbnew.F_Fab
               for point in (item.GetStart(), item.GetEnd())]
    if not corners:
        raise SystemExit(f"{ref} has no outline on its fabrication layer, so this check needs updating")
    xs, ys = [x for x, _ in corners], [y for _, y in corners]
    return box(min(xs), min(ys), max(xs), max(ys))


def main():
    board = pcbnew.LoadBoard(sys.argv[1])
    tracks, vias = [], collections.Counter()
    for item in board.GetTracks():
        net = item.GetNetname()
        if item.Type() == pcbnew.PCB_VIA_T:
            vias[net] += 1
            tracks.append((net, None, Point(xy(item.GetPosition())).buffer(pcbnew.ToMM(item.GetWidth(pcbnew.F_Cu)) / 2)))
        else:
            tracks.append((net, item.GetLayer(), LineString([xy(item.GetStart()), xy(item.GetEnd())])))

    problems = []
    feed_nets = set(design.NET_CLASSES["RF"][2]) | {"GND"}
    feed = box(*design.FEED_KEEP_OUT)
    strays = sorted({net for net, _, shape in tracks if net not in feed_nets and shape.intersects(feed)})
    print(f"around the 868 MHz feed: {'only the feed, its match and ground' if not strays else 'also ' + ', '.join(strays)}")
    problems += [f"{net} runs through the area kept for the 868 MHz feed" for net in strays]

    for area, why in design.TOP_CLEAR:
        crossing = sorted({net for net, layer, shape in tracks if layer == pcbnew.F_Cu and shape.intersects(box(*area))})
        print(f"top layer {why}: {'no track' if not crossing else ', '.join(crossing)}")
        problems += [f"{net} has top-layer track {why}" for net in crossing]

    body = body_box(board, LORA_MODULE)
    under = collections.Counter()
    for net, layer, shape in tracks:
        if layer == pcbnew.F_Cu and net not in feed_nets | PLANE_NETS:
            under[net] += shape.intersection(body).length
    under = {net: length for net, length in under.items() if length > 0.01}
    print("top-layer track under the LoRa module: " + (", ".join(f"{net} {length:.2f} mm" for net, length in sorted(under.items())) or "none"))
    problems += [f"{net} has {length:.2f} mm of top-layer track under the LoRa module, over the {design.UNDER_LORA_MODULE} mm allowed to reach a pad"
                 for net, length in sorted(under.items()) if length > design.UNDER_LORA_MODULE]

    lengths = collections.defaultdict(lambda: collections.Counter())
    for net, layer, shape in tracks:
        if layer is not None:
            lengths[net]["top" if layer == pcbnew.F_Cu else "bottom"] += shape.length
    print(f"lines of {LISTED_FROM:.0f} mm or more (top, bottom, vias):")
    for net in sorted(lengths, key=lambda name: -sum(lengths[name].values())):
        total = sum(lengths[net].values())
        if net in PLANE_NETS or total < LISTED_FROM:
            continue
        print(f"  {net:10} {total:5.1f} mm  {lengths[net]['top']:5.1f} {lengths[net]['bottom']:5.1f}  {vias[net]}")

    if problems:
        print("\n".join(problems))
        raise SystemExit(f"{len(problems)} routing rules broken")
    print("routing keeps to its rules")


if __name__ == "__main__":
    main()
