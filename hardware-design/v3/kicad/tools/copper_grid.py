"""The board's outer-layer copper drawn on a fine grid, for the scripts that place ground vias.

`collect` lists every pad, track, via and filled shape. `Grid` draws them into
bitmaps, and `via_room` marks where a via of one net cannot go.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import numpy as np
import pcbnew
from kiboard import pad_box, xy
from pcbnew import ToMM
from PIL import Image, ImageDraw

G = 0.05                      # grid pitch, mm
CLEAR = 0.2                   # copper clearance; the rule is 0.15 mm, the rest covers the grid's rounding
VIA_D = 0.6
VIA_DRILL = 0.3
OWN_PAD_GAP = VIA_DRILL / 2 + design.VIA_TO_PAD + G      # via centre to a pad of its own net
EDGE = 0.35                   # copper centre to board edge
LAYER_NAMES = {pcbnew.F_Cu: "top", pcbnew.B_Cu: "bot"}


def collect(board):
    """Everything copper on the outer layers: (layer set, net, kind, geometry)."""
    items = []
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            layers = {LAYER_NAMES[l] for l in LAYER_NAMES if pad.IsOnLayer(l)}
            items.append((layers, pad.GetNetname(), "box", pad_box(pad)))
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            items.append(({"top", "bot"}, t.GetNetname(), "dot", (xy(t.GetPosition()), ToMM(t.GetWidth(pcbnew.F_Cu)) / 2)))
        elif t.GetLayer() in LAYER_NAMES:
            items.append(({LAYER_NAMES[t.GetLayer()]}, t.GetNetname(), "seg", (xy(t.GetStart()), xy(t.GetEnd()), ToMM(t.GetWidth()) / 2)))
    for d in board.GetDrawings():
        if d.Type() == pcbnew.PCB_SHAPE_T and d.GetLayer() in LAYER_NAMES and d.GetShape() == pcbnew.SHAPE_T_POLY:
            outline = d.GetPolyShape().Outline(0)
            pts = [xy(outline.CPoint(i)) for i in range(outline.PointCount())]
            items.append(({LAYER_NAMES[d.GetLayer()]}, d.GetNetname(), "poly", pts))
    return items


class Grid:
    def __init__(self):
        self.nx = int(round(design.BOARD_W / G)) + 1
        self.ny = int(round(design.BOARD_H / G)) + 1

    def cell(self, p):
        return (min(max(int(round(p[0] / G)), 0), self.nx - 1), min(max(int(round(p[1] / G)), 0), self.ny - 1))

    def draw(self, img, kind, geom, grow):
        d = ImageDraw.Draw(img)
        if kind == "box":
            x1, y1, x2, y2 = geom
            d.rectangle([(x1 - grow) / G, (y1 - grow) / G, (x2 + grow) / G, (y2 + grow) / G], fill=1)
        elif kind == "dot":
            (x, y), r = geom
            r += grow
            d.ellipse([(x - r) / G, (y - r) / G, (x + r) / G, (y + r) / G], fill=1)
        elif kind == "seg":
            a, b, half = geom
            r = half + grow
            d.line([a[0] / G, a[1] / G, b[0] / G, b[1] / G], fill=1, width=max(1, int(round(2 * r / G))))
            for p in (a, b):
                d.ellipse([(p[0] - r) / G, (p[1] - r) / G, (p[0] + r) / G, (p[1] + r) / G], fill=1)
        elif kind == "poly":
            d.polygon([(x / G, y / G) for x, y in geom], fill=1)
            if grow > 0:
                for a, b in zip(geom, geom[1:] + geom[:1]):
                    d.line([a[0] / G, a[1] / G, b[0] / G, b[1] / G], fill=1, width=max(1, int(round(2 * grow / G))))
                    d.ellipse([(a[0] - grow) / G, (a[1] - grow) / G, (a[0] + grow) / G, (a[1] + grow) / G], fill=1)

    def board_mask(self):
        """Cells no copper centre may use: outside the outline or within EDGE of it, the antenna clearance and the feed's keep-out."""
        img = Image.new("1", (self.nx, self.ny), 1)
        d = ImageDraw.Draw(img)
        d.rectangle([EDGE / G, EDGE / G, (design.BOARD_W - EDGE) / G, (design.BOARD_H - EDGE) / G], fill=0)
        x1, y1, x2, y2 = design.ANT_CLEAR
        d.rectangle([x1 / G, (y1 - 1) / G, (x2 + 1) / G, y2 / G], fill=1)
        x1, y1, x2, y2 = design.FEED_KEEP_OUT
        d.rectangle([x1 / G, y1 / G, x2 / G, y2 / G], fill=1)
        return img


def via_room(grid, items, net, base):
    """Cells where a via of `net` cannot go: too near other copper on either layer, or in or against a pad of its own."""
    via_grow = VIA_D / 2 + CLEAR
    taken = None
    for layer in ("top", "bot"):
        img = base.copy()
        for layers, item_net, kind, geom in items:
            if layer not in layers:
                continue
            if item_net == net and net:
                if kind == "box":
                    grid.draw(img, kind, geom, OWN_PAD_GAP)
                continue
            grid.draw(img, kind, geom, via_grow)
        here = np.array(img, dtype=bool)
        taken = here if taken is None else (taken | here)
    return taken
