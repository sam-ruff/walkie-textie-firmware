"""Compare the delivered PCB_V3 Gerbers with Gerbers plotted from the KiCad import.

Usage: compare_gerbers.py delivered_dir kicad_dir kicad_basename
Prints, per layer, the area that is in one image and not the other.
"""
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # gbr.py is one level up
import gbr
from shapely.geometry import Point
from shapely.ops import unary_union

PAIRS = [
    ("top copper", "Gerber_TopLayer.GTL", "F_Cu"),
    ("inner 1", "Gerber_InnerLayer1.G1", "In1_Cu"),
    ("inner 2", "Gerber_InnerLayer2.G2", "In2_Cu"),
    ("bottom copper", "Gerber_BottomLayer.GBL", "B_Cu"),
    ("top mask", "Gerber_TopSolderMaskLayer.GTS", "F_Mask"),
    ("bottom mask", "Gerber_BottomSolderMaskLayer.GBS", "B_Mask"),
    ("top paste", "Gerber_TopPasteMaskLayer.GTP", "F_Paste"),
    ("bottom paste", "Gerber_BottomPasteMaskLayer.GBP", "B_Paste"),
    ("top silk", "Gerber_TopSilkscreenLayer.GTO", "F_Silkscreen"),
]


def split(layer):
    """(pads/tracks/vias, pour) images of a copper layer."""
    regions = [o for o in layer.objs if o.kind == "region"]
    dark = unary_union([o.geom for o in regions if o.dark]) if regions else Point(0, 0).buffer(0)
    clear = [o.geom for o in regions if not o.dark]
    pour = dark.difference(unary_union(clear)) if clear else dark
    drawn = unary_union([o.geom for o in layer.objs if o.kind != "region"]) if layer.objs else Point(0, 0).buffer(0)
    return drawn, pour


def xor_report(name, a, b):
    only_a = a.difference(b)
    only_b = b.difference(a)
    # ignore slivers thinner than 4 um: arc approximation and rounding
    thick_a = only_a.buffer(-0.002).area
    thick_b = only_b.buffer(-0.002).area
    print(
        f"  {name:26} delivered {a.area:9.3f}  kicad {b.area:9.3f}  "
        f"only-delivered {only_a.area:8.4f} (>4um wide: {thick_a:.4f})  only-kicad {only_b.area:8.4f} (>4um wide: {thick_b:.4f})"
    )
    return thick_a + thick_b


def read_kicad_drill(path):
    tools, holes, cur = {}, [], None
    for line in open(path):
        line = line.strip()
        m = re.match(r"T(\d+)C([\d.]+)", line)
        if m:
            tools[int(m.group(1))] = float(m.group(2))
            continue
        m = re.fullmatch(r"T(\d+)", line)
        if m:
            cur = int(m.group(1))
            continue
        m = re.fullmatch(r"X(-?[\d.]+)Y(-?[\d.]+)", line)
        if m and cur:
            holes.append((float(m.group(1)), float(m.group(2)), tools[cur]))
    return holes


def main():
    ddir, kdir, base = sys.argv[1:4]
    total = 0.0
    for name, dfile, klayer in PAIRS:
        d = gbr.GerberLayer(os.path.join(ddir, dfile))
        k = gbr.GerberLayer(os.path.join(kdir, f"{base}-{klayer}.gbr"))
        print(f"{name}: delivered objects {len(d.objs)}, kicad objects {len(k.objs)}")
        if "copper" in name or "inner" in name:
            dd, dp = split(d)
            kd, kp = split(k)
            total += xor_report("pads, tracks, vias", dd, kd)
            xor_report("ground pour", dp, kp)
            xor_report("whole layer", d.copper(), k.copper())
        else:
            diff = xor_report("image", d.copper(), k.copper())
            if "silk" not in name:
                total += diff

    dh = sorted(set(gbr.read_drill(os.path.join(ddir, "Drill_PTH_Through.DRL"))))
    kh = sorted(set(read_kicad_drill(os.path.join(kdir, f"{base}.drl"))))
    unmatched = [h for h in dh if not any(math.hypot(h[0] - q[0], h[1] - q[1]) < 0.002 and abs(h[2] - q[2]) < 0.002 for q in kh)]
    print(f"drill: delivered {len(dh)} unique holes, kicad {len(kh)}; delivered holes with no kicad match: {len(unmatched)}")
    print(f"TOTAL mismatch outside pours and silk (mm2, slivers under 4 um ignored): {total:.4f}")


if __name__ == "__main__":
    main()
