"""Add the hand-drawn copper from design.COPPER and tidy the copper kept from the drop.

Usage: add_copper.py board.kicad_pcb

Kept tracks and vias that now sit on or too near a pad of another net (a part
was added or moved there) are removed and listed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import pcbnew
from kiboard import Nets, add_copper_poly, add_track, add_via, pad_box, pad_near, seed_ids, xy
from pcbnew import ToMM

MIN_GAP = 0.15


def seg_box_gap(a, b, half_w, box):
    """Smallest gap between a track segment (round ends) and an axis-aligned box. Sampled along the segment."""
    best = 1e9
    steps = max(2, int((abs(b[0] - a[0]) + abs(b[1] - a[1])) / 0.05) + 1)
    for i in range(steps + 1):
        x = a[0] + (b[0] - a[0]) * i / steps
        y = a[1] + (b[1] - a[1]) * i / steps
        dx = max(box[0] - x, 0.0, x - box[2])
        dy = max(box[1] - y, 0.0, y - box[3])
        best = min(best, (dx * dx + dy * dy) ** 0.5 - half_w)
    return best


def main():
    seed_ids(__file__)
    board_path = sys.argv[1]
    board = pcbnew.LoadBoard(board_path)
    nets = Nets(board)

    pads = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            layers = [l for l in (pcbnew.F_Cu, pcbnew.B_Cu) if pad.IsOnLayer(l)]
            pads.append((fp.GetReference(), pad.GetNumber(), pad.GetNetname(), pad_box(pad), layers))

    removed = []
    for item in list(board.GetTracks()):
        net = item.GetNetname()
        if item.Type() == pcbnew.PCB_VIA_T:
            a = b = xy(item.GetPosition())
            half = ToMM(item.GetWidth(pcbnew.F_Cu)) / 2
            layers = (pcbnew.F_Cu, pcbnew.B_Cu)
        else:
            a, b = xy(item.GetStart()), xy(item.GetEnd())
            half = ToMM(item.GetWidth()) / 2
            layers = (item.GetLayer(),)
        for ref, num, pad_net, box, pad_layers in pads:
            if pad_net == net or not set(layers) & set(pad_layers):
                continue
            if seg_box_gap(a, b, half, box) < MIN_GAP:
                removed.append(f"  {net} {'via' if a == b else 'track'} at ({a[0]:.2f}, {a[1]:.2f}): too near {ref} pad {num} ({pad_net or 'no net'})")
                board.Delete(item)
                break

    all_pads = [(ref, num, box) for ref, num, _, box, _ in pads]
    crowded = []
    for entry in design.COPPER:
        if entry[0] != design.V:
            continue
        pad = pad_near(entry[2], 0.15 + design.VIA_TO_PAD, all_pads, design.VIA_IN_PAD_OK)
        if pad:
            crowded.append(f"  {entry[1]} via at {entry[2]}: within {design.VIA_TO_PAD} mm of {pad}")
    if crowded:
        print("\n".join(crowded))
        raise SystemExit("hand-placed vias too close to a pad: move them in design.COPPER")

    counts = {"track": 0, "via": 0, "poly": 0}
    for entry in design.COPPER:
        kind = entry[0]
        if kind == design.T:
            _, net, layer, width, pts = entry
            for a, b in zip(pts[:-1], pts[1:]):
                add_track(board, nets, net, layer, width, a, b)
                counts["track"] += 1
        elif kind == design.V:
            _, net, at = entry
            add_via(board, nets, net, at)
            counts["via"] += 1
        elif kind == design.POLY:
            _, net, layer, pts = entry
            add_copper_poly(board, nets, net, layer, pts)
            counts["poly"] += 1

    pcbnew.SaveBoard(board_path, board)
    print(f"hand-drawn copper: {counts['track']} track segments, {counts['via']} vias, {counts['poly']} filled shapes")
    print(f"kept copper removed because of new or moved parts: {len(removed)}")
    print("\n".join(removed))


if __name__ == "__main__":
    main()
