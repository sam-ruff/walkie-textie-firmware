"""Ground stitching where the brief asks for it at 3 mm or closer.

Usage: stitch_edges.py board.kicad_pcb

Puts 0.3 mm / 0.6 mm ground vias around the board edge and around the 868 MHz
antenna's clearance area, stepping along each line and sliding a via sideways
when a pad, track or other via is in the way. A place that already has a ground
via within reach is left alone. Prints the largest gap it had to leave.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import pcbnew
from kiboard import Nets, add_via, seed_ids
from copper_grid import G, Grid, collect, via_room

STEP = 2.0                 # target pitch along a line
EDGE_INSET = 0.85          # via centre to board edge
CLEAR_INSET = 0.65         # via centre to the antenna clearance boundary, on the ground side
REACH = 1.3                # an existing ground via this close already does the job
SLIDE = 1.0                # how far a via may move along its line to find room
GRID = 4.0                 # pitch of the fill-in grid


def lines():
    w, h = design.BOARD_W, design.BOARD_H
    x1, y1, x2, y2 = design.ANT_CLEAR
    e, c = EDGE_INSET, CLEAR_INSET
    return {
        "left edge": [(e, e), (e, h - e)],
        "top edge": [(e, h - e), (w - e, h - e)],
        "right edge": [(w - e, h - e), (w - e, y2 + c)],
        "bottom edge": [(x1 - c, e), (e, e)],
        "antenna clearance, top": [(w - e, y2 + c), (x1 - c, y2 + c)],
        "antenna clearance, side": [(x1 - c, y2 + c), (x1 - c, e)],
    }


def main():
    seed_ids(__file__)
    board_path = sys.argv[1]
    board = pcbnew.LoadBoard(board_path)
    nets = Nets(board)
    grid = Grid()
    items = collect(board)
    via_block = via_room(grid, items, "GND", grid.board_mask())
    gnd_vias = [geom[0] for layers, net, kind, geom in items if kind == "dot" and net == "GND"]

    def free(p):
        cx, cy = grid.cell(p)
        return not via_block[cy, cx] and all(math.hypot(p[0] - q[0], p[1] - q[1]) >= 1.0 for q in gnd_vias)

    centre = (design.BOARD_W / 2, design.BOARD_H / 2)
    added = 0
    for name, (a, b) in lines().items():
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        ux, uy = (b[0] - a[0]) / length, (b[1] - a[1]) / length
        # unit normal for stepping sideways when the line itself is occupied: into the board for an
        # edge, away from the clearance area for its boundary
        nx_, ny_ = -uy, ux
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if name.startswith("antenna"):
            x1, y1, x2, y2 = design.ANT_CLEAR
            want = (mid[0] - (x1 + x2) / 2, mid[1] - (y1 + y2) / 2)
        else:
            want = (centre[0] - mid[0], centre[1] - mid[1])
        if want[0] * nx_ + want[1] * ny_ < 0:
            nx_, ny_ = -nx_, -ny_
        n = max(1, math.ceil(length / STEP))
        placed = []
        for i in range(n + 1):
            s = length * i / n
            choice = None
            for inward in (0.0, 0.7, 1.4):
                for ds in sorted((k * G * 2 for k in range(-int(SLIDE / (G * 2)), int(SLIDE / (G * 2)) + 1)), key=abs):
                    if not 0 <= s + ds <= length:
                        continue
                    p = (round(a[0] + ux * (s + ds) + nx_ * inward, 3), round(a[1] + uy * (s + ds) + ny_ * inward, 3))
                    if any(math.hypot(p[0] - q[0], p[1] - q[1]) < REACH for q in gnd_vias):
                        choice = "covered"
                        placed.append(s + ds)
                        break
                    if free(p):
                        choice = p
                        placed.append(s + ds)
                        break
                if choice is not None:
                    break
            if choice is None or choice == "covered":
                continue
            add_via(board, nets, "GND", choice)
            gnd_vias.append(choice)
            added += 1
        placed = sorted(placed)
        gaps = [q - p for p, q in zip([0.0] + placed, placed + [length])]
        print(f"  {name:26} {length:5.1f} mm, largest gap between ground vias {max(gaps):.1f} mm")
    print(f"added {added} ground vias on the edge and clearance lines")

    # a coarse grid over the rest of the board ties the outer fills to the inner ground plane
    filled = 0
    y = GRID / 2
    while y < design.BOARD_H:
        x = GRID / 2
        while x < design.BOARD_W:
            p = (round(x, 3), round(y, 3))
            if free(p) and all(math.hypot(p[0] - q[0], p[1] - q[1]) >= GRID * 0.6 for q in gnd_vias):
                add_via(board, nets, "GND", p)
                gnd_vias.append(p)
                filled += 1
            x += GRID
        y += GRID
    pcbnew.SaveBoard(board_path, board)
    print(f"added {filled} ground vias on a {GRID:g} mm grid")


if __name__ == "__main__":
    main()
