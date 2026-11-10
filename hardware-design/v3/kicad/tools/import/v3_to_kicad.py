"""Populate an empty KiCad board from the neutral PCB_V3 model.

Usage: v3_to_kicad.py model.json board.kicad_pcb

The board must already exist (an empty project board). Board coordinates
(origin lower-left, Y up, mm) map to KiCad page coordinates as
x_kicad = 100 + x, y_kicad = 100 - y, and the drill/place origin is put on the
board's lower-left corner so exported files share the drop's coordinates.
"""
import json
import math
import sys

import pcbnew
from pcbnew import VECTOR2I, FromMM, ToMM

OX, OY = 100.0, 100.0
LAYER = {"top": pcbnew.F_Cu, "in1": pcbnew.In1_Cu, "in2": pcbnew.In2_Cu, "bot": pcbnew.B_Cu}
LIB = "PCB_V3"


def P(x, y):
    return VECTOR2I(FromMM(OX + x), FromMM(OY - y))


def lset(*layers):
    s = pcbnew.LSET()
    for layer in layers:
        s.AddLayer(layer)
    return s


def net_of(board, cache, name):
    if not name:
        return None
    if name not in cache:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        cache[name] = net
    return cache[name]


def add_footprint(board, nets, comp):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPID(pcbnew.LIB_ID(LIB, comp["package"]))
    fp.SetReference(comp["ref"])
    fp.SetValue(comp["value"])
    fp.SetAttributes(pcbnew.FP_SMD)
    fp.SetLayer(pcbnew.F_Cu)
    for name, key in (("LCSC", "lcsc"), ("MPN", "mpn"), ("Manufacturer", "manufacturer")):
        fp.SetField(name, comp[key])
    for field in fp.GetFields():
        if field.GetName() not in ("Reference",):
            field.SetVisible(False)
    fp.Reference().SetLayer(pcbnew.F_Fab)
    fp.Reference().SetTextSize(VECTOR2I(FromMM(0.5), FromMM(0.5)))
    fp.Reference().SetTextThickness(FromMM(0.08))
    fp.Value().SetLayer(pcbnew.F_Fab)

    ox, oy = comp["at"]
    th = math.radians(comp["rot"])
    for pd in comp["pads"]:
        vx, vy = pd["at"][0] - ox, pd["at"][1] - oy
        lx = vx * math.cos(th) + vy * math.sin(th)
        ly = -vx * math.sin(th) + vy * math.cos(th)
        pad = pcbnew.PAD(fp)
        pad.SetNumber(pd["num"])
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetShape(pcbnew.PAD_SHAPE_RECT)
        pad.SetSize(VECTOR2I(FromMM(pd["w"]), FromMM(pd["h"])))
        if pd["layer"] == "top":
            layers = [pcbnew.F_Cu, pcbnew.F_Mask] + ([pcbnew.F_Paste] if pd["paste"] else [])
        else:
            layers = [pcbnew.B_Cu, pcbnew.B_Mask] + ([pcbnew.B_Paste] if pd["paste"] else [])
        pad.SetLayerSet(lset(*layers))
        pad.SetPosition(VECTOR2I(FromMM(lx), FromMM(-ly)))
        pad.SetOrientationDegrees(pd["angle"] - comp["rot"])
        pad.SetThermalSpokeAngleDegrees(90)
        net = net_of(board, nets, pd["net"])
        if net is not None:
            pad.SetNet(net)
        fp.Add(pad)
    fp.SetOrientationDegrees(comp["rot"])
    fp.SetPosition(P(ox, oy))
    board.Add(fp)

    # the footprint transform must land every pad where the drop has it
    worst = 0.0
    for p in fp.Pads():
        gx, gy = ToMM(p.GetPosition().x) - OX, OY - ToMM(p.GetPosition().y)
        same = [pd for pd in comp["pads"] if pd["num"] == p.GetNumber()]
        worst = max(worst, min(math.hypot(gx - pd["at"][0], gy - pd["at"][1]) for pd in same))
    if worst > 0.002:
        raise RuntimeError(f"{comp['ref']}: pad placement off by {worst:.4f} mm")
    return fp


def add_segment(board, layer, a, b, width):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a))
    s.SetEnd(P(*b))
    s.SetLayer(layer)
    s.SetWidth(FromMM(width))
    board.Add(s)


def poly_set(outline, holes):
    ps = pcbnew.SHAPE_POLY_SET()
    ps.NewOutline()
    for x, y in outline:
        ps.Append(FromMM(OX + x), FromMM(OY - y))
    for hole in holes:
        h = ps.NewHole()
        for x, y in hole:
            ps.Append(FromMM(OX + x), FromMM(OY - y), -1, h)
    return ps


def main():
    model_path, board_path = sys.argv[1:3]
    delivered_fill = "--delivered-fill" in sys.argv
    model = json.load(open(model_path))
    board = pcbnew.LoadBoard(board_path)
    if board is None:
        raise SystemExit(f"cannot load {board_path}")
    if len(board.GetFootprints()) or len(board.GetTracks()):
        raise SystemExit("board is not empty; start from a fresh project board")

    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(FromMM(0.8))
    ds.SetAuxOrigin(P(0, 0))
    ds.SetGridOrigin(P(0, 0))
    ds.m_SolderMaskExpansion = FromMM(0.051)
    ds.m_SolderPasteMargin = 0
    ds.m_TentViasFront = True
    ds.m_TentViasBack = True
    # what the drop was drawn to: 0.154 mm closest copper, 0.22 mm narrowest track
    ds.m_MinClearance = FromMM(0.15)
    ds.m_TrackMinWidth = FromMM(0.2)
    ds.m_ViasMinSize = FromMM(0.5)
    ds.m_MinThroughDrill = FromMM(0.3)
    ds.m_ViasMinAnnularWidth = FromMM(0.09)
    ds.m_CopperEdgeClearance = FromMM(0.2)
    ds.m_HoleClearance = FromMM(0.2)
    ds.m_HoleToHoleMin = FromMM(0.25)
    default_class = ds.m_NetSettings.GetDefaultNetclass()
    default_class.SetClearance(FromMM(0.15))
    default_class.SetTrackWidth(FromMM(0.22))
    default_class.SetViaDiameter(FromMM(0.5))
    default_class.SetViaDrill(FromMM(0.3))

    nets = {}
    for comp in model["comps"]:
        add_footprint(board, nets, comp)

    for t in model["tracks"]:
        tr = pcbnew.PCB_TRACK(board)
        tr.SetStart(P(*t["a"]))
        tr.SetEnd(P(*t["b"]))
        tr.SetWidth(FromMM(t["w"]))
        tr.SetLayer(LAYER[t["layer"]])
        net = net_of(board, nets, t["net"])
        if net is not None:
            tr.SetNet(net)
        board.Add(tr)

    for v in model["vias"]:
        via = pcbnew.PCB_VIA(board)
        via.SetViaType(pcbnew.VIATYPE_THROUGH)
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        via.SetPosition(P(*v["at"]))
        via.SetWidth(pcbnew.F_Cu, FromMM(v["size"]))
        via.SetDrill(FromMM(round(v["drill"], 2)))
        net = net_of(board, nets, v["net"])
        if net is not None:
            via.SetNet(net)
        board.Add(via)

    # copper areas on nets other than ground: kept as drawn, tied to their net
    for f in model["fills"]:
        if f["net"] == "GND":
            continue
        shape = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
        shape.SetPolyShape(poly_set(f["outline"], f["holes"]))
        shape.SetLayer(LAYER[f["layer"]])
        shape.SetWidth(0)
        shape.SetFilled(True)
        net = net_of(board, nets, f["net"])
        if net is not None:
            shape.SetNet(net)
        board.Add(shape)

    for i, z in enumerate(model["zones"]):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(LAYER[z["layer"]])
        zone.SetNet(net_of(board, nets, z["net"]))
        zone.SetZoneName(f"GND_{z['layer']}")
        poly = zone.Outline()
        poly.NewOutline()
        for x, y in z["outline"]:
            poly.Append(FromMM(OX + x), FromMM(OY - y))
        for hole in z["holes"]:
            h = poly.NewHole()
            for x, y in hole:
                poly.Append(FromMM(OX + x), FromMM(OY - y), -1, h)
        if delivered_fill:
            filled = pcbnew.SHAPE_POLY_SET()
            for f in model["fills"]:
                if f["layer"] == z["layer"] and f["net"] == "GND":
                    filled.Append(poly_set(f["outline"], f["holes"]))
            filled.Fracture()
            zone.SetFilledPolysList(LAYER[z["layer"]], filled)
            zone.SetIsFilled(True)
            zone.SetNeedRefill(False)
        zone.SetLocalClearance(FromMM(0.254))
        zone.SetMinThickness(FromMM(0.2))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetThermalReliefGap(FromMM(0.254))
        zone.SetThermalReliefSpokeWidth(FromMM(0.3))
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        zone.SetAssignedPriority(0)
        board.Add(zone)

    ring = model["outline"]["main"]
    for a, b in zip(ring[:-1], ring[1:]):
        if a != b:
            add_segment(board, pcbnew.Edge_Cuts, a, b, 0.05)
    for shape in model["outline"]["second_shape"]:
        for a, b in zip(shape["pts"][:-1], shape["pts"][1:]):
            if a != b:
                add_segment(board, pcbnew.Edge_Cuts, a, b, 0.05)

    for s in model["silk"]:
        if s["kind"] == "line":
            if s["a"] == s["b"]:
                dot = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
                dot.SetCenter(P(*s["a"]))
                dot.SetEnd(P(s["a"][0] + s["w"] / 4, s["a"][1]))
                dot.SetLayer(pcbnew.F_SilkS)
                dot.SetWidth(FromMM(s["w"] / 2))
                board.Add(dot)
            else:
                add_segment(board, pcbnew.F_SilkS, s["a"], s["b"], s["w"])
        else:
            poly = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
            pts = pcbnew.VECTOR_VECTOR2I()
            for x, y in s["pts"]:
                pts.append(P(x, y))
            poly.SetPolyPoints(pts)
            poly.SetLayer(pcbnew.F_SilkS)
            poly.SetWidth(0)
            poly.SetFilled(True)
            board.Add(poly)

    board.BuildListOfNets()
    board.BuildConnectivity()
    pcbnew.SaveBoard(board_path, board)
    if not delivered_fill:
        # reload so the fill sees the rules just written to the project file
        board = pcbnew.LoadBoard(board_path)
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(board_path, board)
    print(
        f"saved {board_path}: {len(board.GetFootprints())} footprints, "
        f"{sum(len(f.Pads()) for f in board.GetFootprints())} pads, {len(board.GetTracks())} tracks and vias, "
        f"{len(board.Zones())} zones, {board.GetNetCount() - 1} nets"
    )


if __name__ == "__main__":
    main()
