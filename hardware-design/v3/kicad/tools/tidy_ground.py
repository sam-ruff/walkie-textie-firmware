"""Tidy the ground stitching after the automatic passes.

Usage: tidy_ground.py board.kicad_pcb

- Removes a ground via whose hole sits on or too near another via's hole (the
  grid stitcher does not look at ground vias that are already there).
- Finds pieces of the outer-layer ground fill that no via reaches and gives
  each one a via, so every piece is tied to the inner ground plane.
Run it on a filled board, then refill.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from kiboard import Nets, add_via, seed_ids, xy
from copper_grid import Grid, collect, via_room
from shapely.geometry import Point, Polygon

MIN_CENTRES = 0.9          # two vias closer than this are one too many


def islands(zone, layer):
    polys = zone.GetFilledPolysList(layer)
    out = []
    for i in range(polys.OutlineCount()):
        ring = polys.Outline(i)
        shell = [xy(ring.CPoint(k)) for k in range(ring.PointCount())]
        holes = []
        for h in range(polys.HoleCount(i)):
            hole = polys.Hole(i, h)
            holes.append([xy(hole.CPoint(k)) for k in range(hole.PointCount())])
        poly = Polygon(shell, holes)
        if not poly.is_valid:
            poly = poly.buffer(0)
        out.append(poly)
    return out


def main():
    seed_ids(__file__)
    board_path = sys.argv[1]
    board = pcbnew.LoadBoard(board_path)
    nets = Nets(board)

    vias = [t for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    kept, removed = [], 0
    for via in vias:                       # board order: older vias first
        p = xy(via.GetPosition())
        clash = next((q for q in kept if math.hypot(p[0] - q[0], p[1] - q[1]) < MIN_CENTRES), None)
        if clash is not None and via.GetNetname() == "GND":
            board.Delete(via)
            removed += 1
        else:
            kept.append(p)
    print(f"removed {removed} ground vias that sat on or beside another via")

    grid = Grid()
    items = collect(board)
    via_block = via_room(grid, items, "GND", grid.board_mask())
    gnd_vias = [Point(p) for p in kept]
    added = []
    for zone in board.Zones():
        if zone.GetIsRuleArea() or zone.GetNetname() != "GND":
            continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not zone.IsOnLayer(layer):
                continue
            for poly in islands(zone, layer):
                if any(poly.contains(v) for v in gnd_vias):
                    continue
                core = poly.buffer(-0.45)
                spot = None
                if not core.is_empty:
                    x1, y1, x2, y2 = core.bounds
                    best = -1.0
                    y = y1
                    while y <= y2:
                        x = x1
                        while x <= x2:
                            pt = Point(x, y)
                            cx, cy = grid.cell((x, y))
                            if core.contains(pt) and not via_block[cy, cx]:
                                d = poly.exterior.distance(pt)
                                if d > best:
                                    best, spot = d, (round(x, 3), round(y, 3))
                            x += 0.1
                        y += 0.1
                where = poly.representative_point()
                name = "top" if layer == pcbnew.F_Cu else "bottom"
                if spot is None:
                    print(f"  no room for a via in a {name} ground piece of {poly.area:.2f} mm2 near ({where.x:.2f}, {where.y:.2f})")
                    continue
                add_via(board, nets, "GND", spot)
                gnd_vias.append(Point(spot))
                added.append(spot)
                print(f"  via at ({spot[0]:.2f}, {spot[1]:.2f}) for a {name} ground piece of {poly.area:.1f} mm2")
    pcbnew.SaveBoard(board_path, board)
    print(f"added {len(added)} vias to ground pieces that had none")


if __name__ == "__main__":
    main()
