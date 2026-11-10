"""Build the corrected board: outline, placed footprints with nets, and the copper kept from the drop.

Usage: build_board.py model.json out.kicad_pcb v3.pretty new.pretty kicad_footprints_dir

Routing, zones and stitching are added by later steps. This step is the place
where the design in design.py meets the delivered copper, so it prints every
kept part whose nets differ from what the drop had on those pads.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import parts
import pcbnew
from kiboard import Nets, P, add_track, add_via, pad_box, pad_near, seed_ids
from pcbnew import FromMM


def load_footprint(spec, libs):
    lib, name = spec
    if lib == design.KICAD:
        folder, fp_name = name.split(":")
        path = os.path.join(libs[design.KICAD], folder + ".pretty")
        lib_id = pcbnew.LIB_ID(folder, fp_name)
    else:
        path, fp_name = libs[lib], name
        lib_id = pcbnew.LIB_ID(lib, fp_name)
    fp = pcbnew.FootprintLoad(path, fp_name)
    if fp is None:
        raise SystemExit(f"footprint {spec} not found in {path}")
    fp.SetFPID(lib_id)
    return fp


def in_box(pt, box):
    return box[0] <= pt[0] <= box[2] and box[1] <= pt[1] <= box[3]


def main():
    seed_ids(__file__)
    model_path, out_path, v3_lib, new_lib, kicad_dir = sys.argv[1:6]
    model = json.load(open(model_path))
    delivered = {c["ref"]: c for c in model["comps"]}
    libs = {design.LIB_V3: v3_lib, design.LIB_NEW: new_lib, design.KICAD: kicad_dir}

    board = pcbnew.NewBoard(out_path)          # also starts the project file that holds the rules
    board.SetCopperLayerCount(4)
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)
    title = board.GetTitleBlock()
    title.SetTitle(design.TITLE)
    title.SetRevision(design.REVISION)
    title.SetDate(design.DATE)
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(FromMM(0.8))
    ds.SetAuxOrigin(P(0, 0))
    ds.SetGridOrigin(P(0, 0))
    ds.m_SolderMaskExpansion = FromMM(0.051)
    ds.m_SolderMaskMinWidth = 0
    ds.m_SolderPasteMargin = 0
    ds.m_TentViasFront = True
    ds.m_TentViasBack = True
    # JLCPCB multilayer limits are 0.09 mm track and gap; these are the looser values this board is drawn to
    ds.m_MinClearance = FromMM(0.15)
    ds.m_TrackMinWidth = FromMM(0.15)
    ds.m_ViasMinSize = FromMM(0.5)
    ds.m_MinThroughDrill = FromMM(0.3)
    ds.m_ViasMinAnnularWidth = FromMM(0.1)
    ds.m_CopperEdgeClearance = FromMM(0.2)
    ds.m_HoleClearance = FromMM(0.2)
    ds.m_HoleToHoleMin = FromMM(0.25)
    # JLCPCB legend limits: 1.0 mm characters, 0.15 mm stroke, 0.15 mm from a pad
    ds.m_MinSilkTextHeight = FromMM(1.0)
    ds.m_MinSilkTextThickness = FromMM(0.15)
    ds.m_SilkClearance = FromMM(0.15)
    default_class = ds.m_NetSettings.GetDefaultNetclass()
    default_class.SetClearance(FromMM(0.15))
    default_class.SetTrackWidth(FromMM(0.2))
    default_class.SetViaDiameter(FromMM(0.6))
    default_class.SetViaDrill(FromMM(0.3))
    for name, (clearance, width, members) in design.NET_CLASSES.items():
        net_class = pcbnew.NETCLASS(name)
        net_class.SetClearance(FromMM(clearance))
        net_class.SetTrackWidth(FromMM(width))
        net_class.SetViaDiameter(FromMM(0.6))
        net_class.SetViaDrill(FromMM(0.3))
        ds.m_NetSettings.SetNetclass(name, net_class)
        for member in members:
            ds.m_NetSettings.SetNetclassPatternAssignment(member, name)

    nets = Nets(board)

    # ---- outline
    pts = design.OUTLINE
    for a, b in zip(pts, pts[1:] + pts[:1]):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*a))
        s.SetEnd(P(*b))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(FromMM(0.05))
        board.Add(s)

    # ---- footprints
    used_delivered = set()
    notes = []
    for ref, part in parts.resolve(model).items():
        was, old = part["was"], part["delivered"]
        if old:
            used_delivered.add(was)
            # what did the drop have on these pads?
            for pad in old["pads"]:
                new_net = part["nets"].get(pad["num"], "")
                old_name = design.NET_WAS.get(new_net, new_net)
                if old_name != pad["net"]:
                    notes.append(f"  {ref}{' (was ' + was + ')' if was != ref else ''} pad {pad['num']}: drop had {pad['net'] or 'no net'!r}, now {new_net or 'no net'!r}")
        fp = load_footprint(part["footprint"], libs)
        fp.SetReference(ref)
        fp.SetValue(part["value"])
        for name, value in parts.assembly_fields(part):
            fp.SetField(name, value)
        for field in fp.GetFields():
            if field.GetName() not in ("Reference", "Value"):
                field.SetVisible(False)
        # the schematic sets the same three flags, so the two can be compared
        attrs = fp.GetAttributes() & ~(pcbnew.FP_DNP | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
        if part["dnp"]:
            attrs |= pcbnew.FP_DNP
        if part["no_bom"]:
            attrs |= pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM
        fp.SetAttributes(attrs)
        seen = set()
        for pad in fp.Pads():
            num = pad.GetNumber()
            if not num:                 # a paste opening with no number, as KiCad draws on a thermal pad
                continue
            seen.add(num)
            if num not in part["nets"]:
                raise SystemExit(f"{ref}: design gives no net for pad {num}")
            net = nets.get(part["nets"][num])
            if net is not None:
                pad.SetNet(net)
            if part["mask_margin"] is not None:
                pad.SetLocalSolderMaskMargin(FromMM(part["mask_margin"]))
            if num in part["track_only"]:
                pad.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_NONE)
        missing = set(part["nets"]) - seen
        if missing:
            raise SystemExit(f"{ref}: footprint has no pad {sorted(missing)}")
        fp.SetOrientationDegrees(part["rot"])
        fp.SetPosition(P(*part["at"]))
        board.Add(fp)

    part_count = len(board.GetFootprints())

    # ---- logo: silkscreen only, not a part
    logo = load_footprint((design.LIB_NEW, design.LOGO["name"]), libs)
    logo.SetReference("G1")
    logo.Reference().SetVisible(False)
    logo.Value().SetVisible(False)
    logo.SetOrientationDegrees(design.LOGO["rot"])
    logo.SetPosition(P(*design.LOGO["at"]))
    board.Add(logo)

    unused = set(delivered) - used_delivered
    undocumented = unused - set(design.REMOVED)
    if undocumented:
        raise SystemExit(f"parts of the drop neither kept nor listed as removed: {sorted(undocumented)}")

    # ---- copper kept from the drop
    back = {old: new for new, old in design.NET_WAS.items()}
    kept = []
    for t in model["tracks"]:
        net = back.get(t["net"], t["net"])
        boxes = design.KEEP_BOXES.get(net)
        if net in design.KEEP_NETS or (boxes and any(in_box(t["a"], b) and in_box(t["b"], b) for b in boxes)):
            kept.append({"net": net, "layer": t["layer"], "w": t["w"], "a": tuple(t["a"]), "b": tuple(t["b"])})
    # The drop ends some tracks on the middle of another track. KiCad wants a shared end point there.
    changed = True
    while changed:
        changed = False
        for t in kept:
            for end in (t["a"], t["b"]):
                for other in kept:
                    if other is t or other["net"] != t["net"] or other["layer"] != t["layer"]:
                        continue
                    (x1, y1), (x2, y2) = other["a"], other["b"]
                    length = math.hypot(x2 - x1, y2 - y1)
                    if length < 0.05:
                        continue
                    along = ((end[0] - x1) * (x2 - x1) + (end[1] - y1) * (y2 - y1)) / length
                    off = abs((end[0] - x1) * (y2 - y1) - (end[1] - y1) * (x2 - x1)) / length
                    if off < 0.01 and 0.02 < along < length - 0.02:
                        mid = (round(x1 + (x2 - x1) * along / length, 4), round(y1 + (y2 - y1) * along / length, 4))
                        kept.append({**other, "a": mid})
                        other["b"] = mid
                        if end is t["a"]:
                            t["a"] = mid
                        else:
                            t["b"] = mid
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break
    kept_tracks = kept_vias = 0
    for t in kept:
        add_track(board, nets, t["net"], t["layer"], t["w"], t["a"], t["b"])
        kept_tracks += 1
    seen_vias = set()
    pads = [(fp.GetReference(), pad.GetNumber(), pad_box(pad)) for fp in board.GetFootprints() for pad in fp.Pads()]
    under_pads = []
    for v in model["vias"]:
        net = back.get(v["net"], v["net"])
        boxes = design.KEEP_BOXES.get(net)
        keep = net in design.KEEP_NETS or (boxes and any(in_box(v["at"], b) for b in boxes))
        key = tuple(v["at"])
        if v["at"][1] > design.BOARD_H - 0.8:      # sat at the foot of the removed side areas, now on the edge
            keep = False
        # A via left in a pad would take that pad's net when KiCad loads the board, whatever it was drawn as.
        pad = pad_near(v["at"], v["drill"] / 2 + design.VIA_TO_PAD, pads, design.VIA_IN_PAD_OK) if keep else None
        if pad:
            under_pads.append(f"  {net} via at ({v['at'][0]:.2f}, {v['at'][1]:.2f}): {pad} is there now")
            keep = False
        if keep and key not in seen_vias:          # the drop drills one hole twice
            seen_vias.add(key)
            add_via(board, nets, net, v["at"], size=v["size"], drill=round(v["drill"], 2))
            kept_vias += 1

    board.BuildListOfNets()
    pcbnew.SaveBoard(out_path, board)
    print(f"{part_count} parts, {board.GetNetCount() - 1} nets, kept {kept_tracks} of {len(model['tracks'])} track segments and {kept_vias} of {len(model['vias'])} vias")
    print(f"parts of the drop not carried over: {sorted(unused)}")
    print("kept parts whose pad nets differ from the drop:")
    print("\n".join(notes) if notes else "  none")
    print("vias of the drop left out because a pad is there now:")
    print("\n".join(under_pads) if under_pads else "  none")


if __name__ == "__main__":
    main()
