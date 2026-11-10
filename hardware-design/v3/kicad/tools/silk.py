"""Silkscreen and assembly drawing for the corrected board: designators, pin and polarity labels, board name.

Usage: silk.py board.kicad_pcb

Each reference designator is tried above, below, left and right of its part,
at growing distances and in both text directions. It takes the first place
where it clears every pad, every other label, the board edge and the antenna's
printed tuning line, is not under another part, and is plainly nearer its own
part than any other. A module or connector with no such place has it inside
its own outline, where it is covered once the part is on. Any other part with
no such place keeps its designator on the fabrication layer only and is
listed: a designator that could be read as a neighbour's is worse than none.
The labels from design.LABELS are placed as given. A button is named by what
it does (design.SILK_NAMES) and a test pad by what it carries. Those names
are placed before any designator, close to their part, and need only clear
what is already there. A button, or a test pad in design.MUST_NAME, with no
place for its name stops the build.

Every part also carries its designator on the fabrication layer, inside its
outline, which is what the assembly drawing shows. Diodes get a bar there at
their cathode end.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import pcbnew
from kiboard import P, pad_box, seed_ids, xy
from pcbnew import VECTOR2I, FromMM

TEXT_H = 1.0               # the fab's smallest legible character
TEXT_W = 0.75
TEXT_T = 0.15
PAD_MARGIN = 0.15
TEXT_MARGIN = 0.16
EDGE_MARGIN = 0.3
NEARER = 0.4               # a designator is this much nearer its own part than any other
FAB_TEXT = (0.3, 0.8)      # least and most character height of a designator on the fabrication layer
POLARISED = ("D", "LED")   # designators of parts whose pad 1 is a cathode
HEADING_H = 1.1            # character height of the assembly drawing's heading, in board millimetres
PIN_ONE_DOT = 0.4          # diameter of the dot that marks pad 1 on the assembly drawing
DESIGNATOR_AWAY = (0.25, 0.5, 0.9, 1.4, 2.0, 2.6)      # distances from a part at which its designator is tried
NAME_AWAY = (0.25, 0.5, 0.9, 1.4)                      # and the name of a button or a test pad


def named(ref):
    """Whether the silkscreen names a part by what it does or carries: the buttons and the test pads."""
    return ref in design.SILK_NAMES or ref.startswith("TP")


def box_of(item):
    """Extent of the ink. A text item's own bounding box is about 0.5 mm taller than its strokes."""
    is_text = hasattr(item, "GetEffectiveTextShape")
    bb = item.GetEffectiveTextShape().BBox() if is_text else item.GetBoundingBox()
    x1, y2 = xy(VECTOR2I(bb.GetLeft(), bb.GetTop()))
    x2, y1 = xy(VECTOR2I(bb.GetRight(), bb.GetBottom()))
    return (x1, y1, x2, y2)


def overlap(a, b, margin):
    return a[0] < b[2] + margin and b[0] < a[2] + margin and a[1] < b[3] + margin and b[1] < a[3] + margin


def gap(a, b):
    """Distance between two boxes, nothing when they touch or overlap."""
    return math.hypot(max(a[0] - b[2], b[0] - a[2], 0.0), max(a[1] - b[3], b[1] - a[3], 0.0))


def around(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def body_of(fp, pads):
    """A part's body: what its fabrication layer outlines, kept to the board, or its pads where it outlines nothing."""
    drawn = [box_of(g) for g in fp.GraphicalItems() if g.Type() == pcbnew.PCB_SHAPE_T and g.GetLayer() == pcbnew.F_Fab]
    if not drawn:
        return pads
    x1, y1, x2, y2 = around(drawn)
    return (max(x1, 0.0), max(y1, 0.0), min(x2, design.BOARD_W), min(y2, design.BOARD_H))


def style(text):
    text.SetLayer(pcbnew.F_SilkS)
    text.SetTextSize(VECTOR2I(FromMM(TEXT_W), FromMM(TEXT_H)))
    text.SetTextThickness(FromMM(TEXT_T))
    text.SetVisible(True)
    text.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    text.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)


def fab_style(text, at, height, turned):
    text.SetLayer(pcbnew.F_Fab)
    text.SetVisible(True)
    text.SetTextSize(VECTOR2I(FromMM(height * 0.8), FromMM(height)))
    text.SetTextThickness(FromMM(height * 0.15))
    text.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    text.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
    text.SetTextAngleDegrees(90 if turned else 0)
    text.SetPosition(P(*at))


def fab_designator(fp, body):
    """Put the part's designator on the fabrication layer, inside its outline and as large as fits."""
    for item in list(fp.GraphicalItems()):
        if item.Type() == pcbnew.PCB_TEXT_T and item.GetLayer() == pcbnew.F_Fab:
            fp.Remove(item)                      # KiCad's own footprints carry one already, at a size of their own
    width, height = body[2] - body[0], body[3] - body[1]
    turned = height > width
    along, across = max(width, height), min(width, height)
    name = fp.GetReference()
    size = max(FAB_TEXT[0], min(FAB_TEXT[1], across * 0.7, along * 0.9 / (len(name) * 0.8)))
    centre = ((body[0] + body[2]) / 2, (body[1] + body[3]) / 2)
    reference = fp.Reference()
    if reference.GetLayer() == pcbnew.F_Fab:     # not on the silkscreen: the designator itself goes here
        fab_style(reference, centre, size, turned)
        return
    text = pcbnew.PCB_TEXT(fp)
    text.SetText("${REFERENCE}")
    fab_style(text, centre, size, turned)
    fp.Add(text)


def heading(board):
    """The assembly drawing's heading, under the board on the comments layer."""
    lines = [f"{design.TITLE} V{design.REVISION}  {design.DATE}",
             f"Assembly drawing for the default order ({design.DEFAULT_ORDER}).",
             "Parts crossed through are left out of it.",
             "A bar marks a diode's cathode and a dot marks pad 1."]
    for row, line in enumerate(lines):
        text = pcbnew.PCB_TEXT(board)
        text.SetText(line)
        text.SetLayer(pcbnew.Cmts_User)
        text.SetTextSize(VECTOR2I(FromMM(HEADING_H * 0.8), FromMM(HEADING_H)))
        text.SetTextThickness(FromMM(HEADING_H * 0.15))
        text.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        text.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        text.SetPosition(P(0.0, -1.5 - row * HEADING_H * 1.7))
        board.Add(text)


def fab_pin_one(board, fp):
    """A dot on the fabrication layer at pad 1 of a part with three pads or more: drawn on the board, like the bar below."""
    first = fp.FindPadByNumber("1") or fp.FindPadByNumber("A1")
    if first is None:
        return
    dot = pcbnew.PCB_SHAPE(board)
    dot.SetShape(pcbnew.SHAPE_T_CIRCLE)
    centre = first.GetPosition()
    dot.SetCenter(centre)
    dot.SetEnd(VECTOR2I(centre.x + FromMM(PIN_ONE_DOT / 2), centre.y))
    dot.SetFilled(True)
    dot.SetLayer(pcbnew.F_Fab)
    dot.SetWidth(FromMM(0.05))
    board.Add(dot)


def fab_cathode(board, fp, body):
    """A bar across a diode's outline on the fabrication layer, at the end where pad 1, its cathode, is.

    It is drawn on the board and not in the footprint, which then still matches its library.
    """
    x, y = xy(fp.FindPadByNumber("1").GetPosition())
    x1, y1, x2, y2 = body
    if x2 - x1 >= y2 - y1:
        at = x1 + 0.15 * (x2 - x1) if x < (x1 + x2) / 2 else x2 - 0.15 * (x2 - x1)
        start, end = (at, y1), (at, y2)
    else:
        at = y1 + 0.15 * (y2 - y1) if y < (y1 + y2) / 2 else y2 - 0.15 * (y2 - y1)
        start, end = (x1, at), (x2, at)
    bar = pcbnew.PCB_SHAPE(board)
    bar.SetShape(pcbnew.SHAPE_T_SEGMENT)
    bar.SetStart(P(*start))
    bar.SetEnd(P(*end))
    bar.SetLayer(pcbnew.F_Fab)
    bar.SetWidth(FromMM(0.15))
    board.Add(bar)


def main():
    seed_ids(__file__)
    board_path = sys.argv[1]
    board = pcbnew.LoadBoard(board_path)
    stale = [d for d in board.GetDrawings() if (d.Type() == pcbnew.PCB_TEXT_T and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_Cu, pcbnew.Cmts_User))
             or (d.Type() == pcbnew.PCB_SHAPE_T and d.GetLayer() == pcbnew.F_Fab)]
    for d in stale:
        board.Delete(d)

    # the logo and the printed tuning line (TL) are not parts anyone fits or probes: no designator
    parts = [f for f in board.GetFootprints() if not f.GetAttributes() & pcbnew.FP_BOARD_ONLY and not f.GetReference().startswith("TL")]
    pads_of = {f.GetReference(): around([pad_box(p) for p in f.Pads() if p.IsOnLayer(pcbnew.F_Cu)]) for f in parts}
    body = {f.GetReference(): body_of(f, pads_of[f.GetReference()]) for f in parts}

    obstacles = []                                   # (box, margin, what it is)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if pad.IsOnLayer(pcbnew.F_Cu):
                obstacles.append((pad_box(pad), PAD_MARGIN, f"{fp.GetReference()} pad {pad.GetNumber()}"))
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.F_SilkS:
                obstacles.append((box_of(g), TEXT_MARGIN, f"{fp.GetReference()} outline"))
    limit = (EDGE_MARGIN, EDGE_MARGIN, design.BOARD_W - EDGE_MARGIN, design.BOARD_H - EDGE_MARGIN)

    def clashes(box):
        found = [what for ob, m, what in obstacles if overlap(box, ob, m)]
        if box[0] < limit[0] or box[1] < limit[1] or box[2] > limit[2] or box[3] > limit[3]:
            found.append("board edge")
        return found

    def fits(box, me):
        if clashes(box):
            return False
        if any(overlap(box, other, 0.0) for ref, other in body.items() if ref != me):
            return False                             # it would be under another part once the board is built
        if named(me):
            return True                              # a word like WAKE or IO4 is not read as a neighbour's designator
        own = gap(box, pads_of[me])
        return all(gap(box, other) > own + NEARER for ref, other in pads_of.items() if ref != me)

    # fixed labels first: they are the ones a person needs at a connector or a button
    for text, at, rot, size in design.LABELS:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        style(t)
        t.SetTextSize(VECTOR2I(FromMM(size * TEXT_W / TEXT_H), FromMM(size)))
        t.SetTextThickness(FromMM(max(TEXT_T, size * 0.15)))
        t.SetPosition(P(*at))
        t.SetTextAngleDegrees(rot)
        board.Add(t)
        box = box_of(t)
        found = clashes(box)
        if found:
            print(f"  label {text!r} at {at} overlaps {', '.join(found)}")
        obstacles.append((box, TEXT_MARGIN, f"label {text!r}"))

    for text, at, size in design.COPPER_MARKS:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetLayer(pcbnew.B_Cu)
        t.SetTextSize(VECTOR2I(FromMM(size), FromMM(size)))
        t.SetTextThickness(FromMM(size * 0.18))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
        t.SetMirrored(True)
        t.SetPosition(P(*at))
        board.Add(t)

    hidden = []
    footprints = sorted(parts, key=lambda f: (not named(f.GetReference()), -len(f.Pads()), f.GetReference()))
    for fp in footprints:
        me = fp.GetReference()
        fp.Value().SetVisible(False)
        ref = fp.Reference()
        if me.startswith("TP"):
            # a test pad is labelled with what it carries; its designator stays on the fab layer
            ref.SetLayer(pcbnew.F_Fab)
            ref = fp.Value()
        elif me in design.SILK_NAMES:
            # a button is labelled with what it does, in a text of the board's own
            ref.SetLayer(pcbnew.F_Fab)
            ref = pcbnew.PCB_TEXT(board)
            ref.SetText(design.SILK_NAMES[me])
            board.Add(ref)
        style(ref)
        bx1, by1, bx2, by2 = pads_of[me]
        cx, cy = (bx1 + bx2) / 2, (by1 + by2) / 2
        length = len(ref.GetText()) * TEXT_W * 0.95
        options = []
        # a name stays close to its part, because nothing else says whose it is
        for away in NAME_AWAY if named(me) else DESIGNATOR_AWAY:
            for rot, w, h in ((0, length, TEXT_H), (90, TEXT_H, length)):
                for x in (cx, bx1 + w / 2, bx2 - w / 2, bx1 - w / 2, bx2 + w / 2):
                    options += [(rot, (x, by2 + away + h / 2)), (rot, (x, by1 - away - h / 2))]
                for y in (cy, by1 + h / 2, by2 - h / 2, by1 - h / 2, by2 + h / 2):
                    options += [(rot, (bx2 + away + w / 2, y)), (rot, (bx1 - away - w / 2, y))]
        if bx2 - bx1 > 6 and by2 - by1 > 6:
            # a module or connector with no place beside it: inside its own outline, where it is at least
            # there to read on a bare board
            for dx, dy in ((0, 0), (0, 0.25), (0, -0.25), (0.25, 0), (-0.25, 0), (0.25, 0.25), (-0.25, -0.25)):
                options.append((0, (cx + dx * (bx2 - bx1), cy + dy * (by2 - by1))))
        placed = False
        for rot, at in options:
            ref.SetTextAngleDegrees(rot)
            ref.SetPosition(P(*at))
            box = box_of(ref)
            if fits(box, me):
                obstacles.append((box, TEXT_MARGIN, me))
                placed = True
                break
        if not placed and (me in design.SILK_NAMES or me in design.MUST_NAME):
            raise SystemExit(f"no place on the silkscreen for {ref.GetText()!r} beside {me}")
        if not placed:
            ref.SetLayer(pcbnew.F_Fab)
            if ref is not fp.Reference():
                ref.SetVisible(False)                # a test pad's name that found no place is dropped: its designator names it
            hidden.append(me)
        fab_designator(fp, body[me])
        if me.rstrip("0123456789") in POLARISED:
            fab_cathode(board, fp, body[me])
        elif len([pad for pad in fp.Pads() if pad.GetNumber()]) >= 3:
            fab_pin_one(board, fp)
    heading(board)
    pcbnew.SaveBoard(board_path, board)
    print(f"designators on the silkscreen: {len(footprints) - len(hidden)} of {len(footprints)}")
    if hidden:
        print(f"no place beside their own part, on the fabrication layer only: {' '.join(sorted(hidden))}")


if __name__ == "__main__":
    main()
