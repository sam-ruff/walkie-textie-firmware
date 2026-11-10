"""Write a KiCad footprint library holding the land patterns of the PCB_V3 drop.

Each EasyEDA package used on the board becomes one footprint, with its pads in
the package's own frame (rotation 0), a fab outline and a courtyard. Every
instance of a package is checked against the first one, so a package whose pads
differ between parts is reported instead of being silently averaged.

Usage: make_lib.py model.json out_dir.pretty
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from kiboard import seed_ids
from pcbnew import VECTOR2I, FromMM

COURTYARD_MARGIN = 0.15


def local_pads(comp):
    """Pads in the footprint frame: KiCad axes (Y down), rotation removed."""
    ox, oy = comp["at"]
    th = math.radians(comp["rot"])
    out = []
    for pd in comp["pads"]:
        vx, vy = pd["at"][0] - ox, pd["at"][1] - oy
        lx = vx * math.cos(th) + vy * math.sin(th)
        ly = -vx * math.sin(th) + vy * math.cos(th)
        ang = (pd["angle"] - comp["rot"]) % 180.0
        w, h = pd["w"], pd["h"]
        if abs(ang - 90.0) < 0.01:
            w, h, ang = h, w, 0.0
        if abs(ang - 180.0) < 0.01:
            ang = 0.0
        out.append({"num": pd["num"], "x": round(lx, 3), "y": round(-ly, 3), "w": w, "h": h, "angle": round(ang, 2), "layer": pd["layer"], "paste": pd["paste"]})
    return sorted(out, key=lambda p: (p["num"], p["x"], p["y"]))


def same(a, b, tol=0.011):
    if len(a) != len(b):
        return False
    for p, q in zip(a, b):
        if p["num"] != q["num"] or p["layer"] != q["layer"]:
            return False
        if any(abs(p[k] - q[k]) > tol for k in ("x", "y", "w", "h")):
            return False
    return True


def rect(fp, layer, x1, y1, x2, y2, width):
    s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_RECTANGLE)
    s.SetStart(VECTOR2I(FromMM(x1), FromMM(y1)))
    s.SetEnd(VECTOR2I(FromMM(x2), FromMM(y2)))
    s.SetLayer(layer)
    s.SetWidth(FromMM(width))
    fp.Add(s)


def silk_line(fp, x1, y1, x2, y2):
    s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(VECTOR2I(FromMM(x1), FromMM(y1)))
    s.SetEnd(VECTOR2I(FromMM(x2), FromMM(y2)))
    s.SetLayer(pcbnew.F_SilkS)
    s.SetWidth(FromMM(0.15))
    fp.Add(s)


def silk_dot(fp, x, y, r=0.15):
    s = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_CIRCLE)
    s.SetCenter(VECTOR2I(FromMM(x), FromMM(y)))
    s.SetEnd(VECTOR2I(FromMM(x + r / 2), FromMM(y)))
    s.SetLayer(pcbnew.F_SilkS)
    s.SetWidth(FromMM(r))
    fp.Add(s)


def polarity_marks(fp, name, pads):
    """The drop prints no usable polarity or pin 1 marks, so each package gets a minimal one."""
    by_num = {}
    for p in pads:
        by_num.setdefault(p["num"], p)
    one = by_num.get("1")
    if name.endswith("-BI"):                             # bidirectional TVS: no polarity to mark
        return
    if name.startswith(("SOD-", "LED")):                 # bar beside the cathode, pad 1
        x = one["x"] - one["w"] / 2 - 0.3 if one["x"] < 0 else one["x"] + one["w"] / 2 + 0.3
        silk_line(fp, x, -one["h"] / 2, x, one["h"] / 2)
    elif name.startswith(("SOT-583", "TSOT-23")):        # dot outside pin 1
        silk_dot(fp, one["x"] - one["w"] / 2 - 0.4, one["y"])
    elif name.startswith("WIRELM-SMD_ESP32"):
        silk_dot(fp, one["x"] - one["w"] / 2 - 0.45, one["y"], 0.2)
    elif name.startswith("CONN-SMD"):                    # dot beside the free end of pin 1
        end = one["y"] + (one["h"] / 2 - 0.5) * (1 if one["y"] > 0 else -1)
        side = 1 if one["x"] > 0 else -1
        silk_dot(fp, one["x"] + side * (one["w"] / 2 + 0.45), end, 0.2)
    elif name.startswith("KEY-SMD"):                     # body edges between the two pads
        left = min(p["x"] + p["w"] / 2 for p in pads) + 0.3
        right = max(p["x"] - p["w"] / 2 for p in pads) - 0.3
        for y in (-1.25, 1.25):
            silk_line(fp, left, y, right, y)


def build(name, pads):
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID("PCB_V3", name))
    fp.SetAttributes(pcbnew.FP_SMD)
    fp.SetLibDescription("Land pattern as delivered in the PCB_V3 drop (EasyEDA package of the same name)")
    for pd in pads:
        pad = pcbnew.PAD(fp)
        pad.SetNumber(pd["num"])
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetShape(pcbnew.PAD_SHAPE_RECT)
        pad.SetSize(VECTOR2I(FromMM(pd["w"]), FromMM(pd["h"])))
        side = (pcbnew.F_Cu, pcbnew.F_Mask, pcbnew.F_Paste) if pd["layer"] == "top" else (pcbnew.B_Cu, pcbnew.B_Mask, pcbnew.B_Paste)
        ls = pcbnew.LSET()
        for layer in side if pd["paste"] else side[:2]:
            ls.AddLayer(layer)
        pad.SetLayerSet(ls)
        pad.SetPosition(VECTOR2I(FromMM(pd["x"]), FromMM(pd["y"])))
        pad.SetOrientationDegrees(pd["angle"])
        pad.SetThermalSpokeAngleDegrees(90)
        fp.Add(pad)
    xs = [p["x"] - max(p["w"], p["h"]) / 2 if p["angle"] else p["x"] - p["w"] / 2 for p in pads] + [
        p["x"] + max(p["w"], p["h"]) / 2 if p["angle"] else p["x"] + p["w"] / 2 for p in pads
    ]
    ys = [p["y"] - max(p["w"], p["h"]) / 2 if p["angle"] else p["y"] - p["h"] / 2 for p in pads] + [
        p["y"] + max(p["w"], p["h"]) / 2 if p["angle"] else p["y"] + p["h"] / 2 for p in pads
    ]
    x1, x2, y1, y2 = min(xs), max(xs), min(ys), max(ys)
    rect(fp, pcbnew.F_Fab, x1, y1, x2, y2, 0.1)
    polarity_marks(fp, name, pads)
    m = COURTYARD_MARGIN
    rect(fp, pcbnew.F_CrtYd, round(x1 - m, 2), round(y1 - m, 2), round(x2 + m, 2), round(y2 + m, 2), 0.05)
    fp.Reference().SetText("REF**")
    fp.Reference().SetLayer(pcbnew.F_SilkS)
    fp.Reference().SetPosition(VECTOR2I(0, FromMM(y1 - 0.9)))
    fp.Reference().SetTextSize(VECTOR2I(FromMM(0.8), FromMM(0.8)))
    fp.Reference().SetTextThickness(FromMM(0.13))
    fp.Value().SetText(name)
    fp.Value().SetLayer(pcbnew.F_Fab)
    fp.Value().SetPosition(VECTOR2I(0, FromMM(y2 + 0.9)))
    fp.Value().SetTextSize(VECTOR2I(FromMM(0.5), FromMM(0.5)))
    fp.Value().SetTextThickness(FromMM(0.08))
    return fp, (x1, y1, x2, y2)


def main():
    seed_ids(__file__)
    model_path, lib_dir = sys.argv[1:3]
    model = json.load(open(model_path))
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    os.makedirs(lib_dir, exist_ok=True)
    by_pkg = {}
    for comp in model["comps"]:
        by_pkg.setdefault(comp["package"], []).append(comp)
    for pkg, comps in sorted(by_pkg.items()):
        first = local_pads(comps[0])
        odd = [c["ref"] for c in comps[1:] if not same(first, local_pads(c))]
        fp, box = build(pkg, first)
        io.FootprintSave(lib_dir, fp)
        note = f"  !! pads differ on {odd}" if odd else ""
        print(f"{pkg:44} {len(comps):2d} part(s) {len(first):3d} pads  box {box[0]:.2f},{box[1]:.2f} .. {box[2]:.2f},{box[3]:.2f}{note}")


if __name__ == "__main__":
    main()
