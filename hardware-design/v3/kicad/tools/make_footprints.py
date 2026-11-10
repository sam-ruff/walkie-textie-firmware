"""Prepare the project footprint library for this revision.

Usage: make_footprints.py new.pretty kicad_footprints_dir

- USB-C plug: HRO TYPE-C-31-G-07. The plug sits on one face of the board with
  its shell hanging over the edge. Where the pads and slots sit comes from
  the "Recommended P.C.B. Layout" in its drawing
  (datasheets/TYPE-C-31-G-07_plug_drawing.pdf). Two things follow JLCPCB's
  own footprint for the part (C530607) instead: the contact pads are 0.27 mm
  wide, where the drawing's 0.36 mm leaves no room for solder mask between
  them, and solder paste is printed over the land round each leg's slot,
  which is what solders the legs. One thing is ours: each slot is longer
  than the drawing's at the end nearer the board edge (design.PLUG_LEGS).
- U.FL test connector: KiCad's footprint, marked as allowed to bridge its own
  solder mask opening so DRC does not report the library part itself.
- SOD-123F diode: KiCad's footprint without the diode symbol it draws on the
  fabrication layer, which would cover the designator on the assembly drawing.
- Module and antenna footprints: thermal spokes set square to the pads. The
  module also gets corner marks and a dot at pad 1 on the silkscreen.
- Antenna tuning line: one copper-only pad in the shape of the printed line.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import pcbnew
from kiboard import seed_ids
from make_lib import rect
from pcbnew import VECTOR2I, FromMM

PLUG_NAME = "USB-C_Plug_HRO_TYPE-C-31-G-07"
# In millimetres. Distances "in" are from the back face of the plug's shell, which the board edge stops.
PLUG = {
    "pitch": 0.50,
    "contact": (0.27, 1.00),            # pad for one contact: across the row, along the plug
    "shell_pad_width": 0.60,            # the shell's two surface pads
    "shell_pad_in": (0.29, 1.89),       # where each starts and ends
    "shell_pads_apart": 7.15,
    "leg_land": (0.25, 0.20),           # copper round each leg's slot: beside it, beyond each end
    "on_board": 3.05,                   # how far the plug's back reaches in
    "overhang": 10.70,                  # how far its shell reaches out
    "shell_width": 8.25,
    "back_width": 9.20,
}
PLUG_MASK_MARGIN = 0.025   # mm of solder mask opening beyond each contact pad: leaves a 0.18 mm dam between them
EDGE_KEEP = 0.25           # mm of bare board between the edge as drawn and the nearest copper or paste
UFL = "U.FL_Hirose_U.FL-R-SMT-1_Vertical"
DIODE = "D_SOD-123F"
MODULE = "Seeed_Wio-SX1262"
TUNING_LINE = "W3000_Tuning_Line"


def tuning_line():
    """The printed line as a footprint: its origin is the anchor, which sits on the antenna's far pad."""
    ax, ay = design.TUNING_ANCHOR
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID(design.LIB_NEW, TUNING_LINE))
    fp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
    fp.SetAllowMissingCourtyard(True)
    fp.SetLibDescription("Printed tuning line for the Pulse W3000 at 868 MHz, as in the datasheet's reference layout. Copper only.")
    pad = pcbnew.PAD(fp)
    pad.SetNumber("1")
    pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    layers = pcbnew.LSET()
    layers.AddLayer(pcbnew.F_Cu)
    pad.SetLayerSet(layers)
    pad.SetShape(pcbnew.PAD_SHAPE_CUSTOM)
    pad.SetAnchorPadShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_RECT)
    pad.SetSize(VECTOR2I(FromMM(0.3), FromMM(0.3)))
    pad.SetPosition(VECTOR2I(0, 0))
    outline = pcbnew.VECTOR_VECTOR2I()
    for x, y in design.TUNING_LINE:
        outline.append(VECTOR2I(FromMM(x - ax), FromMM(-(y - ay))))
    pad.AddPrimitivePoly(pcbnew.F_Cu, outline, 0, True)
    fp.Add(pad)
    for field, text in ((fp.Reference(), "REF**"), (fp.Value(), TUNING_LINE)):
        field.SetText(text)
        field.SetLayer(pcbnew.F_Fab)
        field.SetTextSize(VECTOR2I(FromMM(0.4), FromMM(0.4)))
        field.SetTextThickness(FromMM(0.06))
        field.SetPosition(VECTOR2I(FromMM(2.0), FromMM(-2.0)))
    fp.Value().SetVisible(False)
    return fp


def plug_y(inward):
    """Footprint y of a point `inward` mm from the shell's back face. The origin is midway between the rows
    and the shell points down the page, as in KiCad's own USB footprints."""
    return sum(design.PLUG_ROWS.values()) / 2 - inward


def plug_pad(fp, number, x, inward, size, through=None):
    """One pad of the plug, centred `inward` mm from the shell's back face."""
    pad = pcbnew.PAD(fp)
    pad.SetNumber(number)
    pad.SetSize(VECTOR2I(FromMM(size[0]), FromMM(size[1])))
    if through:
        pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        pad.SetShape(pcbnew.PAD_SHAPE_OVAL)
        pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_OBLONG)
        pad.SetDrillSize(VECTOR2I(FromMM(through[0]), FromMM(through[1])))
        # Solder paste on the top land, over the slot: that paste is what solders the leg. JLCPCB's
        # footprint for the part has the same.
        layers = pcbnew.PAD.PTHMask()
        layers.AddLayer(pcbnew.F_Paste)
        pad.SetLayerSet(layers)
        # no land on the inner layers, where the leg joins nothing: the planes then only step round the slot
        pad.SetRemoveUnconnected(True)
        pad.SetKeepTopBottom(True)
    else:
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetShape(pcbnew.PAD_SHAPE_RECT)
        pad.SetLayerSet(pcbnew.PAD.SMDMask())
    pad.SetPosition(VECTOR2I(FromMM(x), FromMM(plug_y(inward))))
    pad.SetThermalSpokeAngleDegrees(90)
    fp.Add(pad)
    return pad


def silk_line(fp, start, end, width=0.15):
    line = pcbnew.PCB_SHAPE(fp)
    line.SetShape(pcbnew.SHAPE_T_SEGMENT)
    line.SetStart(VECTOR2I(FromMM(start[0]), FromMM(start[1])))
    line.SetEnd(VECTOR2I(FromMM(end[0]), FromMM(end[1])))
    line.SetLayer(pcbnew.F_SilkS)
    line.SetWidth(FromMM(width))
    fp.Add(line)


def plug():
    """The plug's land pattern, shell pointing down the page. Row A is the one further in from the edge."""
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID(design.LIB_NEW, PLUG_NAME))
    fp.SetAttributes(pcbnew.FP_SMD)
    legs = design.PLUG_LEGS
    fp.SetLibDescription(
        "HRO TYPE-C-31-G-07 USB Type-C plug, 24 contacts in two rows on one face of the board, shell on two legs through "
        "slots and two surface pads. Pad and slot positions from the drawing's recommended layout; contact pad width and "
        "the solder paste on the legs' lands from JLCPCB's footprint for C530607. The shell overhangs the board edge, "
        f"which is drawn {design.PLUG_SET_BACK:.2f} mm back from the shell's rear face, and each slot is "
        f"{legs['longer']:.2f} mm longer than the drawing's at the end nearer that edge."
    )
    last = 5.5 * PLUG["pitch"]
    for n in range(1, 13):
        # seen from above with the shell pointing down, A12 and B1 are on the left
        a = plug_pad(fp, f"A{n}", -last + (12 - n) * PLUG["pitch"], design.PLUG_ROWS["A"], PLUG["contact"])
        b = plug_pad(fp, f"B{n}", -last + (n - 1) * PLUG["pitch"], design.PLUG_ROWS["B"], PLUG["contact"])
        for pad in (a, b):
            pad.SetLocalSolderMaskMargin(FromMM(PLUG_MASK_MARGIN))
            # every contact that is used is reached by a track, so the ground fill stays off these narrow pads
            pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_NONE)

    edge = design.PLUG_SET_BACK                               # the board edge, measured like everything else here
    # the shell's surface pads start where the drawing has them, or as near the board edge as copper may come
    start, end = max(PLUG["shell_pad_in"][0], edge + EDGE_KEEP), PLUG["shell_pad_in"][1]
    inner = PLUG["shell_pads_apart"] / 2 - PLUG["shell_pad_width"] / 2
    # each slot as the drawing has it, made longer at the end nearer the edge, and the land round it
    slot = (legs["slot"][0], legs["slot"][1] + legs["longer"])
    slot_in = legs["in"] - legs["longer"] / 2
    land = (slot[0] + 2 * PLUG["leg_land"][0], slot[1] + 2 * PLUG["leg_land"][1])
    outer = legs["apart"] / 2 + land[0] / 2
    for leg, tab, side in (("25", "27", -1), ("26", "28", 1)):
        plug_pad(fp, leg, side * legs["apart"] / 2, slot_in, land, through=slot)
        plug_pad(fp, tab, side * PLUG["shell_pads_apart"] / 2, (start + end) / 2, (PLUG["shell_pad_width"], end - start))

    back, shell = PLUG["back_width"] / 2, PLUG["shell_width"] / 2
    rect(fp, pcbnew.F_Fab, -back, plug_y(PLUG["on_board"]), back, plug_y(0), 0.1)
    rect(fp, pcbnew.F_Fab, -shell, plug_y(0), shell, plug_y(-PLUG["overhang"]), 0.1)
    reach = outer + 0.25
    rect(fp, pcbnew.F_CrtYd, -reach, plug_y(PLUG["on_board"] + 0.6), reach, plug_y(edge), 0.05)
    # a line behind the plug's back, between its legs, that still shows once the plug is on
    behind = plug_y(PLUG["on_board"] + 0.25)
    silk_line(fp, (-inner + 0.2, behind), (inner - 0.2, behind))
    fp.Reference().SetText("REF**")
    fp.Reference().SetLayer(pcbnew.F_SilkS)
    fp.Reference().SetPosition(VECTOR2I(0, FromMM(plug_y(PLUG["on_board"] + 1.2))))
    fp.Value().SetText(PLUG_NAME)
    fp.Value().SetLayer(pcbnew.F_Fab)
    fp.Value().SetPosition(VECTOR2I(0, FromMM(plug_y(-3.0))))
    for field in (fp.Reference(), fp.Value()):
        field.SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8)))
        field.SetTextThickness(FromMM(0.13))
    return fp


def plain_outline(fp):
    """Take off what a library footprint draws inside its fabrication outline, such as a diode's symbol.

    The assembly drawing puts the designator there, and the symbol makes it unreadable.
    """
    lines = [item for item in fp.GraphicalItems() if item.Type() == pcbnew.PCB_SHAPE_T and item.GetLayer() == pcbnew.F_Fab]
    ends = [point for line in lines for point in (line.GetStart(), line.GetEnd())]
    left, right = min(point.x for point in ends), max(point.x for point in ends)
    top, bottom = min(point.y for point in ends), max(point.y for point in ends)
    for line in lines:
        if not all(point.x in (left, right) or point.y in (top, bottom) for point in (line.GetStart(), line.GetEnd())):
            fp.Remove(line)


def mark_module(fp):
    """Corner marks round a module's outline and a dot beside pad 1, on the silkscreen, clear of its pads."""
    drawn = [item.GetBoundingBox() for item in fp.GraphicalItems() if item.Type() == pcbnew.PCB_SHAPE_T and item.GetLayer() == pcbnew.F_Fab]
    left, right = min(pcbnew.ToMM(box.GetLeft()) for box in drawn), max(pcbnew.ToMM(box.GetRight()) for box in drawn)
    top, bottom = min(pcbnew.ToMM(box.GetTop()) for box in drawn), max(pcbnew.ToMM(box.GetBottom()) for box in drawn)
    out, arm = 0.15, 0.6
    for x, into in ((left - out, 1), (right + out, -1)):
        for y, down in ((top - out, 1), (bottom + out, -1)):
            silk_line(fp, (x, y), (x + into * arm, y))
            silk_line(fp, (x, y), (x, y + down * arm * 2))
    first = pcbnew.ToMM(fp.FindPadByNumber("1").GetPosition())
    side = -1 if first[0] < (left + right) / 2 else 1
    end = -1 if first[1] < (top + bottom) / 2 else 1
    dot = pcbnew.PCB_SHAPE(fp)
    dot.SetShape(pcbnew.SHAPE_T_CIRCLE)
    centre = VECTOR2I(FromMM((left if side < 0 else right) + side * -0.2), FromMM((top if end < 0 else bottom) + end * 0.75))
    dot.SetCenter(centre)
    dot.SetEnd(VECTOR2I(centre.x + FromMM(0.15), centre.y))
    dot.SetFilled(True)
    dot.SetLayer(pcbnew.F_SilkS)
    dot.SetWidth(FromMM(0.1))
    fp.Add(dot)


def main():
    seed_ids(__file__)
    new_lib, kicad_dir = sys.argv[1:3]
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)

    fp = plug()
    io.FootprintSave(new_lib, fp)
    print(f"wrote {PLUG_NAME}: {len(fp.Pads())} pads")

    ufl = pcbnew.FootprintLoad(os.path.join(kicad_dir, "Connector_Coaxial.pretty"), UFL)
    ufl.SetFPID(pcbnew.LIB_ID(design.LIB_NEW, UFL))
    ufl.SetAllowSolderMaskBridges(True)
    io.FootprintSave(new_lib, ufl)
    print(f"wrote {UFL}")

    diode = pcbnew.FootprintLoad(os.path.join(kicad_dir, "Diode_SMD.pretty"), DIODE)
    diode.SetFPID(pcbnew.LIB_ID(design.LIB_NEW, DIODE))
    plain_outline(diode)
    io.FootprintSave(new_lib, diode)
    print(f"wrote {DIODE}")

    for name in (MODULE, "Pulse_W3000"):
        part = pcbnew.FootprintLoad(new_lib, name)
        part.SetFPID(pcbnew.LIB_ID(design.LIB_NEW, name))
        part.SetAttributes(pcbnew.FP_SMD)
        for pad in part.Pads():
            pad.SetThermalSpokeAngleDegrees(90)
        if name == MODULE:
            mark_module(part)
        io.FootprintSave(new_lib, part)
        print(f"normalised {name}")

    io.FootprintSave(new_lib, tuning_line())
    print(f"wrote {TUNING_LINE}")


if __name__ == "__main__":
    main()
