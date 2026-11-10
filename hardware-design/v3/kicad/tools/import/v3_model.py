"""Build a neutral board model of the PCB_V3 drop from its fabrication outputs.

Everything geometric comes from the Gerbers and the drill file. The layout SVG,
pick-and-place file and BOM only supply names: which pad belongs to which part
and pin, net names, values and part numbers.

Usage: v3_model.py gerber_dir layout.json lvs.json bom.csv out_model.json
Coordinates are board millimetres, origin at the lower-left corner, Y up.
"""
import collections
import csv
import io
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # gbr.py is one level up
import gbr
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

POUR_CLEARANCE = 0.26
EDGE_INSET = 0.259


def rnd(v, n=4):
    return round(float(v), n)


def pt(p):
    return [rnd(p[0]), rnd(p[1])]


def rect_from_poly(poly):
    """Width, height and angle (degrees, CCW, Y up) of a 4-point rectangle."""
    (x0, y0), (x1, y1), (x2, y2) = poly[0], poly[1], poly[2]
    w = math.hypot(x1 - x0, y1 - y0)
    h = math.hypot(x2 - x1, y2 - y1)
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180.0
    if abs(ang - 180.0) < 1e-6:
        ang = 0.0
    if ang >= 90.0 - 1e-6:
        w, h, ang = h, w, ang - 90.0
    return rnd(w, 3), rnd(h, 3), rnd(ang, 2)


def main():
    gd, layp, lvsp, bomp, outp = sys.argv[1:6]
    lay = json.load(open(layp))
    lvs = json.load(open(lvsp))
    files = {
        "top": "Gerber_TopLayer.GTL",
        "in1": "Gerber_InnerLayer1.G1",
        "in2": "Gerber_InnerLayer2.G2",
        "bot": "Gerber_BottomLayer.GBL",
        "gto": "Gerber_TopSilkscreenLayer.GTO",
        "gko": "Gerber_BoardOutlineLayer.GKO",
        "gtp": "Gerber_TopPasteMaskLayer.GTP",
    }
    L = {k: gbr.GerberLayer(os.path.join(gd, f)) for k, f in files.items()}
    copper = {k: gbr.polys(L[k].copper()) for k in ("top", "in1", "in2", "bot")}

    def net_at(layer, x, y):
        p = Point(x, y)
        for i, g in enumerate(copper[layer]):
            if g.contains(p):
                return lvs["poly_net"][layer][i] or ""
        raise ValueError(f"no copper at {layer} {x},{y}")

    # ---- BOM
    raw = open(bomp, "rb").read()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig")
    bom = {}
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        for ref in row["Designator"].split(","):
            bom[ref.strip()] = {
                "value": row["Name"],
                "package": row["Footprint"],
                "mpn": row["Manufacturer Part"],
                "manufacturer": row["Manufacturer"],
                "lcsc": row["Supplier Part"],
            }

    # ---- components and top pads
    comps = {}
    for ref, c in lay["comps"].items():
        comps[ref] = {
            "ref": ref,
            "at": pt(c["at"]),
            "rot": float(c["rot"]),
            "side": "top",
            "pads": [],
            **bom[ref],
        }
    orphans = []
    for p in lay["pads"]:
        w, h, ang = rect_from_poly(p["poly"])
        pad = {
            "num": p["num"],
            "net": p["net"],
            "at": pt(p["at"]),
            "w": w,
            "h": h,
            "angle": ang,
            "layer": "top",
            "paste": any(o.geom.contains(Point(p["at"])) for o in L["gtp"].objs),
        }
        got = net_at("top", *p["at"])
        if got != p["net"]:
            raise ValueError(f"pad {p.get('ref')}.{p['num']}: layout says {p['net']!r}, copper says {got!r}")
        if p.get("ref"):
            comps[p["ref"]]["pads"].append(pad)
        else:
            orphans.append(pad)
    # pads the schematic did not name twice (the module's split ground pad): nearest part whose pads enclose them
    for pad in orphans:
        best = None
        for c in comps.values():
            xs = [q["at"][0] for q in c["pads"]]
            ys = [q["at"][1] for q in c["pads"]]
            if min(xs) <= pad["at"][0] <= max(xs) and min(ys) <= pad["at"][1] <= max(ys):
                area = (max(xs) - min(xs)) * (max(ys) - min(ys))
                if best is None or area < best[0]:
                    best = (area, c)
        if best is None:
            raise ValueError(f"orphan pad {pad}")
        best[1]["pads"].append(pad)

    # ---- bottom pads: the plug's B row, numbered against the A row above it
    plug = comps["U8"]
    a_row = {q["num"]: q for q in plug["pads"] if q["num"].startswith("A")}
    for o in L["bot"].objs:
        if o.kind != "flash" or o.ap.kind != "R":
            continue
        x, y = o.pts[0]
        above = min(a_row.values(), key=lambda q: abs(q["at"][1] - y))
        num = f"B{13 - int(above['num'][1:])}"
        plug["pads"].append(
            {
                "num": num,
                "net": net_at("bot", x, y),
                "at": pt((x, y)),
                "w": rnd(o.ap.params[0], 3),
                "h": rnd(o.ap.params[1], 3),
                "angle": 0.0,
                "layer": "bot",
                "paste": True,
            }
        )

    # ---- tracks
    tracks = []
    for layer in ("top", "bot"):
        for o in L[layer].objs:
            if o.kind != "draw":
                continue
            (x0, y0), (x1, y1) = o.pts[0], o.pts[-1]
            tracks.append(
                {
                    "layer": layer,
                    "net": net_at(layer, (x0 + x1) / 2, (y0 + y1) / 2),
                    "a": pt((x0, y0)),
                    "b": pt((x1, y1)),
                    "w": rnd(o.ap.params[0], 3),
                }
            )

    # ---- vias: one per drilled hole, pad size from the copper flash at that point
    vias = []
    flashes = [o for o in L["top"].objs if o.kind == "flash" and o.ap.kind == "C"]
    for x, y, dia in gbr.read_drill(os.path.join(gd, "Drill_PTH_Through.DRL")):
        fl = min(flashes, key=lambda o: math.hypot(o.pts[0][0] - x, o.pts[0][1] - y))
        if math.hypot(fl.pts[0][0] - x, fl.pts[0][1] - y) > 0.01:
            raise ValueError(f"hole at {x},{y} has no via pad")
        vias.append({"at": pt((x, y)), "net": net_at("top", x, y), "size": rnd(fl.ap.params[0], 3), "drill": rnd(dia, 3)})

    # ---- outline: the closed main shape, plus the loose second shape exactly as drawn
    main_draws = [o for o in L["gko"].objs if abs(o.ap.params[0] - 0.3) < 1e-6]
    other_draws = [o for o in L["gko"].objs if abs(o.ap.params[0] - 0.3) >= 1e-6]
    ring = [main_draws[0].pts[0]]
    for o in main_draws:
        ring.append(o.pts[-1])
    main_ring = [pt(p) for p in ring]
    board = Polygon([(p[0], p[1]) for p in main_ring]).buffer(0)

    # ---- filled copper as delivered: every region piece with the net it sits on
    def rings(g):
        return {
            "outline": [pt(p) for p in list(g.exterior.coords)[:-1]],
            "holes": [[pt(p) for p in list(r.coords)[:-1]] for r in g.interiors],
        }

    fills = []
    pour = {}
    for layer in ("top", "in1", "in2", "bot"):
        img = Polygon()
        for o in L[layer].objs:
            if o.kind == "region":
                img = img.union(o.geom) if o.dark else img.difference(o.geom)
        for g in gbr.polys(gbr.polygonal(img)):
            rp = g.representative_point()
            fills.append({"layer": layer, "net": net_at(layer, rp.x, rp.y), "area": rnd(g.area, 3), **rings(g)})
        pour[layer] = unary_union([Polygon(f["outline"], f["holes"]) for f in fills if f["layer"] == layer and f["net"] == "GND"])

    # ---- ground zone outlines: the board, less the areas the designer kept the fill out of.
    # The inner layers carry nothing but the plane, so cut-outs found there are deliberate
    # and apply to every layer; outer layers add any further large ones of their own.
    reach = board.buffer(-EDGE_INSET)

    def cutouts(layer, min_area):
        others = [o.geom for o in L[layer].objs if o.kind != "region"]
        others += [Polygon(f["outline"], f["holes"]) for f in fills if f["layer"] == layer and f["net"] != "GND"]
        blocked = unary_union(others).buffer(POUR_CLEARANCE + 0.02)
        free = reach.difference(pour[layer].buffer(0.03)).difference(blocked)
        found = []
        for g in gbr.polys(free):
            core = g.buffer(-0.6)
            if core.is_empty:
                continue
            for piece in gbr.polys(core.buffer(0.6).intersection(g).simplify(0.02)):
                if piece.area > min_area:
                    found.append(piece)
        return found

    common = cutouts("in1", 1.5)
    zones = []
    for layer in ("top", "in1", "in2", "bot"):
        own = [c for c in cutouts(layer, 5.0) if c.intersection(unary_union(common)).area < 0.5 * c.area]
        cuts = common + own
        zone_area = reach.difference(unary_union(cuts))
        for g in gbr.polys(zone_area):
            if g.area < 1.0:
                continue
            zones.append({"layer": layer, "net": "GND", **rings(g.simplify(0.01))})
        nets_here = collections.Counter(f["net"] for f in fills if f["layer"] == layer)
        print(
            f"{layer}: delivered fill pieces by net {dict(nets_here)}; ground {pour[layer].area:.1f} mm2; "
            f"cut-outs common {[round(c.area, 1) for c in common]} own {[round(c.area, 1) for c in own]}"
        )

    # ---- silkscreen as drawn
    silk = []
    for o in L["gto"].objs:
        if o.kind == "draw":
            for a, b in zip(o.pts[:-1], o.pts[1:]):
                silk.append({"kind": "line", "a": pt(a), "b": pt(b), "w": rnd(o.ap.params[0], 4)})
        elif o.kind == "region":
            silk.append({"kind": "poly", "pts": [pt(p) for p in o.pts]})

    model = {
        "source": "PCB_V3 drop of 6 September 2026",
        "outline": {
            "main": main_ring,
            "second_shape": [{"pts": [pt(p) for p in o.pts], "w": rnd(o.ap.params[0], 3)} for o in other_draws],
        },
        "comps": sorted(comps.values(), key=lambda c: c["ref"]),
        "tracks": tracks,
        "vias": vias,
        "zones": zones,
        "fills": fills,
        "silk": silk,
    }
    json.dump(model, open(outp, "w"), indent=1)

    npads = sum(len(c["pads"]) for c in model["comps"])
    print(f"components {len(model['comps'])}, pads {npads} ({sum(1 for c in model['comps'] for p in c['pads'] if p['layer'] == 'bot')} bottom)")
    print(f"tracks {len(tracks)} {dict(collections.Counter(t['layer'] for t in tracks))}, vias {len(vias)}")
    print(f"track widths {dict(collections.Counter(t['w'] for t in tracks))}")
    print(f"nets on pads/tracks/vias: {len({p['net'] for c in model['comps'] for p in c['pads']} | {t['net'] for t in tracks} | {v['net'] for v in vias} - {''})}")
    print(f"zones {len(zones)}: {[(z['layer'], len(z['outline']), len(z['holes'])) for z in zones]}")
    print(f"silk primitives {len(silk)}")
    print("plug B row:", [(p["num"], p["net"]) for p in sorted(plug["pads"], key=lambda q: q["at"][1]) if p["layer"] == "bot"])


if __name__ == "__main__":
    main()
