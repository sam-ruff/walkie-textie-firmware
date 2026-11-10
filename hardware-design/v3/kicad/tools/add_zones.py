"""Add the planes and the antenna keep-out, then fill.

Usage: add_zones.py board.kicad_pcb

Ground on the top, first inner and bottom layers; the switched 3.3 V rail on the
second inner layer, as the brief asks. A rule area keeps every layer's fill out
of the 868 MHz antenna's clearance area.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import pcbnew
from kiboard import LAYERS, Nets, OX, OY, lset, seed_ids
from pcbnew import FromMM

EDGE_INSET = 0.3


def outline(zone, pts):
    poly = zone.Outline()
    poly.NewOutline()
    for x, y in pts:
        poly.Append(FromMM(OX + x), FromMM(OY - y))


def main():
    seed_ids(__file__)
    board_path = sys.argv[1]
    board = pcbnew.LoadBoard(board_path)
    nets = Nets(board)
    if any(not z.GetIsRuleArea() for z in board.Zones()):
        # the planes are already there: only the fill needs redoing
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
        pcbnew.SaveBoard(board_path, board)
        print(f"refilled: {[z.GetZoneName() for z in board.Zones()]}")
        return
    has_keepout = any(z.GetIsRuleArea() for z in board.Zones())

    w, h, e = design.BOARD_W, design.BOARD_H, EDGE_INSET
    area = [(e, e), (w - e, e), (w - e, h - e), (e, h - e)]
    for layer, net in (("top", "GND"), ("in1", "GND"), ("in2", "+3V3"), ("bot", "GND")):
        zone = pcbnew.ZONE(board)
        zone.SetLayer(LAYERS[layer])
        zone.SetNet(nets.get(net))
        zone.SetZoneName(f"{net}_{layer}")
        outline(zone, area)
        zone.SetLocalClearance(FromMM(0.2))
        zone.SetMinThickness(FromMM(0.2))
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        zone.SetThermalReliefGap(FromMM(0.2))
        zone.SetThermalReliefSpokeWidth(FromMM(0.3))
        zone.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        zone.SetAssignedPriority(0)
        board.Add(zone)

    if not has_keepout:
        x1, y1, x2, y2 = design.ANT_CLEAR
        keep = pcbnew.ZONE(board)
        keep.SetIsRuleArea(True)
        keep.SetZoneName("868 MHz antenna clearance")
        keep.SetLayerSet(lset(pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu))
        outline(keep, [(x1, y1 - 1.0), (x2 + 1.0, y1 - 1.0), (x2 + 1.0, y2), (x1, y2)])
        keep.SetDoNotAllowZoneFills(True)
        keep.SetDoNotAllowTracks(False)
        keep.SetDoNotAllowVias(False)
        keep.SetDoNotAllowPads(False)
        keep.SetDoNotAllowFootprints(False)
        board.Add(keep)

    pcbnew.SaveBoard(board_path, board)
    board = pcbnew.LoadBoard(board_path)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(board_path, board)
    print(f"zones: {[z.GetZoneName() for z in board.Zones()]}")


if __name__ == "__main__":
    main()
