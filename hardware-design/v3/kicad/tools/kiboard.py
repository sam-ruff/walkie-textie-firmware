"""Small helpers shared by the board scripts: coordinates, layers, nets, pads.

Board coordinates are millimetres from the board's lower-left corner with Y up.
KiCad page coordinates put that corner at (100, 100) with Y down.
"""
import math
import os
import zlib

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

OX, OY = 100.0, 100.0
LAYERS = {"top": pcbnew.F_Cu, "in1": pcbnew.In1_Cu, "in2": pcbnew.In2_Cu, "bot": pcbnew.B_Cu}


def seed_ids(script):
    """Make the ids KiCad gives new items repeatable, so two builds of one design write the same files.

    Each script gets its own sequence, named after its file, so their ids never collide.
    """
    pcbnew.KIID.SeedGenerator(zlib.crc32(os.path.basename(script).encode()))


def P(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY - y))


def xy(v):
    """KiCad position -> board millimetres."""
    return (ToMM(v.x) - OX, OY - ToMM(v.y))


def lset(*layers):
    s = pcbnew.LSET()
    for layer in layers:
        s.AddLayer(layer)
    return s


class Nets:
    def __init__(self, board):
        self.board = board
        self.cache = {}
        for name, net in board.GetNetsByName().items():
            self.cache[str(name)] = net

    def get(self, name):
        if not name:
            return None
        if name not in self.cache:
            net = pcbnew.NETINFO_ITEM(self.board, name)
            self.board.Add(net)
            self.cache[name] = net
        return self.cache[name]


def poly_set(points, holes=()):
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in points:
        ps.Append(FromMM(OX + x), FromMM(OY - y))
    for hole in holes:
        h = ps.NewHole()
        for x, y in hole:
            ps.Append(FromMM(OX + x), FromMM(OY - y), -1, h)
    return ps


def add_track(board, nets, net, layer, width, a, b):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a))
    t.SetEnd(P(*b))
    t.SetWidth(FromMM(width))
    t.SetLayer(LAYERS[layer])
    n = nets.get(net)
    if n is not None:
        t.SetNet(n)
    board.Add(t)
    return t


def add_via(board, nets, net, at, size=0.6, drill=0.3):
    v = pcbnew.PCB_VIA(board)
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetPosition(P(*at))
    v.SetWidth(pcbnew.F_Cu, FromMM(size))
    v.SetDrill(FromMM(drill))
    n = nets.get(net)
    if n is not None:
        v.SetNet(n)
    board.Add(v)
    return v


def add_copper_poly(board, nets, net, layer, points):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    s.SetPolyShape(poly_set(points))
    s.SetLayer(LAYERS[layer])
    s.SetWidth(0)
    s.SetFilled(True)
    n = nets.get(net)
    if n is not None:
        s.SetNet(n)
    board.Add(s)
    return s


def pad_table(board):
    """{(ref, pad number): [(x, y), ...]} in board millimetres."""
    table = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            table.setdefault((fp.GetReference(), pad.GetNumber()), []).append(xy(pad.GetPosition()))
    return table


def numbered_pads(footprint):
    """[(pad number, (x, y))] in board millimetres. A paste opening with no number is not a pad of the part."""
    return [(pad.GetNumber(), xy(pad.GetPosition())) for pad in footprint.Pads() if pad.GetNumber()]


def pad_box(pad):
    """Axis-aligned bounding box of a pad in board millimetres: x1, y1, x2, y2."""
    bb = pad.GetBoundingBox()
    x1, y2 = xy(VECTOR2I(bb.GetLeft(), bb.GetTop()))
    x2, y1 = xy(VECTOR2I(bb.GetRight(), bb.GetBottom()))
    return (x1, y1, x2, y2)


def pad_near(point, reach, pads, allowed=None):
    """Name of the first pad within `reach` of a point, or None. `pads` are (ref, number, box)."""
    for ref, number, box in pads:
        if (ref, number) == allowed:
            continue
        if box[0] - reach <= point[0] <= box[2] + reach and box[1] - reach <= point[1] <= box[3] + reach:
            return f"{ref} pad {number}"
    return None


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])
