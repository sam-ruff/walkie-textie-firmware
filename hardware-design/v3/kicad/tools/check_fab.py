"""Check the fabrication files themselves, without going through KiCad.

Usage: check_fab.py fab_dir model.json

KiCad's DRC judges the board file. This reads the plotted Gerbers, the drill
file and each order's BOM and placement file, which are what the factory
gets, and checks the things that went wrong on earlier drops of this board:

- the outline is one closed rectangle, with a straight edge where the USB plug
  hangs over it;
- the plug has the two slots its legs go through, a board edge cut at the end
  of its tolerance still lets the widest leg into them, and there is solder
  paste on every one of its pads and on the land round each leg, none of it
  on bare board;
- solder mask openings are far enough apart for the mask between them to hold;
- no drilled hole sits in a solder-mask opening (solder would wick into it);
- the antenna's clearance area is free of copper apart from the antenna's own
  pads, feed and tuning line;
- copper stays back from the board edge;
- the ground plane is one unbroken sheet, including under the 868 MHz feed;
- every order's BOM and placement file name the same parts, the ones that
  order fits, and each has a part number for the assembler.
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import gbr
import parts
from project import PROJECT
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

COPPER = {"top": "F_Cu.gtl", "inner 1": "In1_Cu.g1", "inner 2": "In2_Cu.g2", "bottom": "B_Cu.gbl"}
EDGE_CLEARANCE = 0.2
MAX_PLANE_HOLE = 3.0            # mm: a via's hole in the plane is about 1 mm; anything much longer is a slot
VIA_LAND_AREA = 0.5             # mm2: a via's own land on an inner layer is under this
PLUG_PASTE = 26                 # stencil openings for the plug: its 24 contacts, and one over each shell pad and the leg's land beside it
PLUG_LEG_PASTE = 2.85           # mm2: what JLCPCB's own footprint prints over a shell pad and its leg's land
PASTE_OFF_COPPER = 0.01         # mm2 of one stencil opening that may miss the copper under it
PLUG_LANDS = (3.6, 5.0)         # mm: how far the plug's pads reach in from the board edge, and to each side of its centre line
SLOT_TOLERANCE = 0.02           # mm
MASK_DAM = 0.1                  # mm: the least solder mask JLCPCB keeps between two openings


def layer(fab_dir, suffix):
    return gbr.GerberLayer(os.path.join(fab_dir, "gerbers", f"{PROJECT}-{suffix}")).copper()


def drill_file(path):
    """(round holes as (x, y, diameter), slots as ((x1, y1), (x2, y2), width)) from an Excellon file."""
    tools, hits, slots, tool = {}, [], [], None
    for line in open(path):
        line = line.strip()
        size = re.match(r"T(\d+)C([\d.]+)", line)
        if size:
            tools[int(size.group(1))] = float(size.group(2))
            continue
        select = re.fullmatch(r"T(\d+)", line)
        if select:
            tool = int(select.group(1))
            continue
        slot = re.fullmatch(r"X(-?[\d.]+)Y(-?[\d.]+)G85X(-?[\d.]+)Y(-?[\d.]+)", line)
        if slot and tool:
            x1, y1, x2, y2 = (float(value) for value in slot.groups())
            slots.append(((x1, y1), (x2, y2), tools[tool]))
            continue
        hit = re.fullmatch(r"X(-?[\d.]+)Y(-?[\d.]+)", line)
        if hit and tool:
            hits.append((float(hit.group(1)), float(hit.group(2)), tools[tool]))
    return hits, slots


def thermal_pads(model_path):
    """The one pad where vias are wanted (design.VIA_IN_PAD_OK), as it was delivered."""
    ref, number = design.VIA_IN_PAD_OK
    with open(model_path) as fh:
        part = parts.resolve(json.load(fh))[ref]
    boxes = []
    for pad in part["delivered"]["pads"]:
        if pad["num"] != number:
            continue
        w, h = (pad["h"], pad["w"]) if abs(pad["angle"] % 180 - 90) < 1 else (pad["w"], pad["h"])
        boxes.append(box(pad["at"][0] - w / 2, pad["at"][1] - h / 2, pad["at"][0] + w / 2, pad["at"][1] + h / 2))
    return unary_union(boxes)


def board_shape(fab_dir, problems):
    drawn = layer(fab_dir, "Edge_Cuts.gm1")
    rings = [drawn] if drawn.geom_type == "Polygon" else list(drawn.geoms)
    if len(rings) != 1 or len(rings[0].interiors) != 1:
        problems.append(f"outline is not one closed shape: {len(rings)} pieces")
        return None
    return Polygon(rings[0].interiors[0]).buffer(0.025, join_style=2)      # the line is 0.05 mm wide


def least_dam(openings):
    """(narrowest strip of solder mask between two openings, a point beside it)."""
    narrowest, where = None, None
    for i, a in enumerate(openings):
        for b in openings[i + 1:]:
            gap = a.distance(b)
            if narrowest is None or gap < narrowest:
                narrowest, where = gap, a.representative_point()
    return narrowest, where


def check_plug(fab_dir, slots):
    """The plug's leg slots, how they let it sit against the board edge, and the paste on its pads and legs."""
    problems = []
    legs = design.PLUG_LEGS
    # each slot is the drawing's, made longer at the end nearer the board edge, which is the left one (x = 0)
    slot = (legs["slot"][1] + legs["longer"], legs["slot"][0])
    wanted = [(design.plug_x(legs["in"] - legs["longer"] / 2), design.PLUG_Y + side * legs["apart"] / 2) for side in (-1, 1)]
    found = []
    for (x1, y1), (x2, y2), width in slots:
        centre = ((x1 + x2) / 2, (y1 + y2) / 2)
        found.append((centre, (abs(x2 - x1) + abs(y2 - y1) + width, width)))
    print("plug: slots for its legs at " + ", ".join(f"({x:.3f}, {y:.3f}) {length:.2f} x {width:.2f} mm" for (x, y), (length, width) in sorted(found)))
    for x, y in wanted:
        match = [size for centre, size in found if abs(centre[0] - x) < SLOT_TOLERANCE and abs(centre[1] - y) < SLOT_TOLERANCE]
        if not match:
            problems.append(f"no slot for the plug's leg at ({x:.3f}, {y:.3f})")
        elif abs(match[0][0] - slot[0]) > SLOT_TOLERANCE or abs(match[0][1] - slot[1]) > SLOT_TOLERANCE:
            problems.append(f"the plug's slot at ({x:.3f}, {y:.3f}) is {match[0][0]:.2f} x {match[0][1]:.2f} mm, not {slot[0]:.2f} x {slot[1]:.2f} mm")
    if len(found) != len(wanted):
        problems.append(f"{len(found)} slots are drilled where the plug's legs need {len(wanted)}")

    # The shell's rear face stops against the board edge. Cut proud, the edge pushes the plug outwards,
    # and each leg has only the room between it and the end of its slot to follow. A leg at the wide end
    # of its tolerance has the least.
    widest = legs["leg"] + legs["leg_tolerance"]
    room = (legs["slot"][1] - widest) / 2 + legs["longer"]
    pushed = design.OUTLINE_TOLERANCE - design.PLUG_SET_BACK
    print(f"plug: a leg at its widest, {widest:.2f} mm, has {room:.3f} mm of room towards the edge in its slot; the edge is drawn "
          f"{design.PLUG_SET_BACK:.2f} mm back from the shell's rear face, so an edge cut {design.OUTLINE_TOLERANCE:.1f} mm proud "
          f"pushes the plug {pushed:.2f} mm")
    if pushed > room:
        problems.append("a board edge within its tolerance can keep the plug's legs out of their slots")

    lands = box(0.0, design.PLUG_Y - PLUG_LANDS[1], PLUG_LANDS[0], design.PLUG_Y + PLUG_LANDS[1])
    pasted = [piece for piece in gbr.polys(layer(fab_dir, "F_Paste.gtp")) if piece.intersects(lands)]
    over_legs = [[piece for piece in pasted if piece.contains(Point(x, y))] for x, y in wanted]
    top = layer(fab_dir, "F_Cu.gtl")
    stray = max((piece.difference(top).area for piece in pasted), default=0.0)
    print(f"plug: {len(pasted)} stencil openings where it needs {PLUG_PASTE}; over each leg's land and the shell pad beside it "
          + " and ".join(f"{pieces[0].area:.2f} mm2" if pieces else "none" for pieces in over_legs)
          + f"; the most of any opening that is off copper is {stray:.3f} mm2")
    if len(pasted) != PLUG_PASTE:
        problems.append(f"{len(pasted)} stencil openings for the plug where it needs {PLUG_PASTE}")
    for (x, y), pieces in zip(wanted, over_legs):
        if not pieces or pieces[0].area < PLUG_LEG_PASTE:
            problems.append(f"the plug's leg at ({x:.3f}, {y:.3f}) has less solder paste over it than JLCPCB's own footprint prints")
    if stray > PASTE_OFF_COPPER:
        problems.append(f"solder paste for the plug is printed on bare board: {stray:.3f} mm2 of one opening")
    if layer(fab_dir, "B_Paste.gbp").intersects(lands):
        problems.append("solder paste on the bottom face under the plug, which has no pads there")
    return problems


def check_orders(fab_dir, model_path):
    """Each order's BOM and placement file against the parts that order fits."""
    problems = []
    with open(model_path) as fh:
        all_parts = parts.resolve(json.load(fh))
    for order in design.ORDERS:
        folder = fab_dir if order == design.DEFAULT_ORDER else os.path.join(fab_dir, order)
        with open(os.path.join(folder, "CPL.csv"), newline="") as fh:
            placed = {row["Designator"] for row in csv.DictReader(fh)}
        with open(os.path.join(folder, "BOM.csv"), newline="") as fh:
            rows = list(csv.DictReader(fh))
        listed = {ref.strip() for row in rows for ref in row["Designator"].split(",")}
        wanted = parts.fitted(all_parts, order)
        unnumbered = sorted(ref.strip() for row in rows if not row["LCSC Part #"] for ref in row["Designator"].split(","))
        print(f"order {order}: placement file {len(placed)} parts, BOM {len(listed)} parts in {len(rows)} lines, {len(unnumbered)} without a part number")
        if placed != wanted or listed != wanted:
            problems.append(f"order {order}: BOM and placement file do not both name the parts it fits: {sorted((placed | listed) ^ wanted)}")
        problems += [f"order {order}: {ref} has no part number for the assembler" for ref in unnumbered]
    return problems


def main():
    fab_dir, model_path = sys.argv[1:3]
    problems = []

    board = board_shape(fab_dir, problems)
    if board is None:
        raise SystemExit("\n".join(problems))
    x1, y1, x2, y2 = board.bounds
    print(f"outline: one closed shape, {x2 - x1:.3f} x {y2 - y1:.3f} mm")
    square = box(0.0, 0.0, design.BOARD_W, design.BOARD_H)
    if board.symmetric_difference(square).area > 0.05:
        problems.append("the outline is not the plain rectangle the plug's straight edge needs")

    copper = {name: layer(fab_dir, suffix) for name, suffix in COPPER.items()}
    masks = {"top": layer(fab_dir, "F_Mask.gts"), "bottom": layer(fab_dir, "B_Mask.gbs")}

    hits, slots = drill_file(os.path.join(fab_dir, "gerbers", f"{PROJECT}-PTH.drl"))
    problems += check_plug(fab_dir, slots)
    for name, mask in masks.items():
        dam, where = least_dam(gbr.polys(mask))
        if dam is None:
            continue
        print(f"solder mask, {name}: the narrowest strip between two openings is {dam:.3f} mm, near ({where.x:.1f}, {where.y:.1f})")
        if dam < MASK_DAM - 0.0005:
            problems.append(f"only {dam:.3f} mm of solder mask between two openings on the {name} face near ({where.x:.1f}, {where.y:.1f})")
    places = {(round(x, 3), round(y, 3)) for x, y, _ in hits}
    wanted = thermal_pads(model_path)
    in_pad = [(x, y, d) for x, y, d in hits if any(mask.intersects(Point(x, y).buffer(d / 2)) for mask in masks.values())]
    thermal = [hit for hit in in_pad if wanted.contains(Point(hit[0], hit[1]))]
    in_opening = [(x, y) for x, y, d in in_pad if (x, y, d) not in thermal]
    print(f"drill: {len(hits)} round holes at {len(places)} places; {len(thermal)} in the ESP32 ground paddle, {len(in_opening)} in any other solder-mask opening")
    if len(places) != len(hits):
        problems.append("a hole is drilled twice")
    problems += [f"hole at ({x:.2f}, {y:.2f}) is in a solder-mask opening" for x, y in in_opening]

    clear = box(*design.ANT_CLEAR)
    for name, shape in copper.items():
        inside = shape.intersection(clear)
        print(f"copper in the antenna clearance, {name}: {inside.area:.2f} mm2")
        if name != "top" and inside.area > 0.01:
            problems.append(f"{name} copper inside the antenna clearance")
    antenna = unary_union([Polygon(design.TUNING_LINE), box(31.3, 0.4, 32.7, 9.5), box(31.3, 0.4, 39.3, 2.2), box(29.9, 8.3, 32.7, 9.5)])
    stray = copper["top"].intersection(clear).difference(antenna.buffer(0.05))
    if stray.area > 0.01:
        problems.append(f"top copper in the antenna clearance that is not the antenna's: {stray.area:.2f} mm2 near {stray.representative_point().wkt}")

    edge = board.exterior
    for name, shape in copper.items():
        gap = shape.distance(edge)
        print(f"copper to board edge, {name}: {gap:.3f} mm")
        if gap < EDGE_CLEARANCE - 0.005:
            problems.append(f"{name} copper is {gap:.3f} mm from the board edge")
        if not board.buffer(0.001).contains(shape):
            problems.append(f"{name} copper outside the outline")

    # The ground plane is what every signal returns through and what keeps the board quiet in an
    # emissions test. It has to be one sheet: holes for vias are fine, a slot is not.
    pieces = sorted(gbr.polys(copper["inner 1"]), key=lambda piece: piece.area, reverse=True)
    ground = pieces[0]
    islands = [piece for piece in pieces[1:] if piece.area > VIA_LAND_AREA]      # the rest are the lands of vias passing through
    land = board.difference(clear)
    covered = ground.intersection(land).area / land.area
    gaps = [Polygon(ring).bounds for ring in ground.interiors]
    longest = max((max(x2 - x1, y2 - y1) for x1, y1, x2, y2 in gaps), default=0.0)
    print(f"ground plane (inner 1): one sheet covering {covered:.1%} of the board outside the antenna clearance, "
          f"{len(gaps)} holes for vias and the plug's legs, the longest {longest:.2f} mm, {len(islands)} separate pieces")
    if islands or covered < 0.95 or longest > MAX_PLANE_HOLE:
        problems.append("the ground plane on inner layer 1 is broken up")
    feed = unary_union([LineString(entry[4]).buffer(0.5) for entry in design.COPPER
                        if entry[0] == design.T and entry[1] in ("RF_ANT", "RF_FEED")]).difference(clear)
    if feed.difference(ground).area > 0.01:
        problems.append("the ground plane does not run unbroken under the 868 MHz feed")
    else:
        print("ground plane runs unbroken under the 868 MHz feed")

    problems += check_orders(fab_dir, model_path)

    if problems:
        print("\n".join(problems))
        raise SystemExit(f"{len(problems)} problems in the fabrication files")
    print("fabrication files: no problems found")


if __name__ == "__main__":
    main()
