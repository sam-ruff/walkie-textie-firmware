"""Minimal RS-274X / Excellon reader for the EasyEDA output dialect, built on shapely.

Handles: FSLAX45Y45, MOMM, AM macros (primitives 1, 4, 5, 20, 21), AD (C, R, O, P, macro),
LPD/LPC, G01/G02/G03 (G75 multi-quadrant), G36/G37 regions, D01/D02/D03.
"""
import math
import re
from dataclasses import dataclass, field

from shapely import affinity, make_valid
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

CIRCLE_RES = 24  # segments per quarter circle


def polygonal(g):
    """Return only the polygonal part of a geometry (drops stray lines/points)."""
    if g.is_empty:
        return Polygon()
    if g.geom_type in ('Polygon', 'MultiPolygon'):
        return g
    if g.geom_type == 'GeometryCollection':
        parts = [p for p in g.geoms if p.geom_type in ('Polygon', 'MultiPolygon') and not p.is_empty]
        return unary_union(parts) if parts else Polygon()
    return Polygon()


def fix(g):
    if not g.is_valid:
        g = polygonal(make_valid(g))
    return g


@dataclass
class Aperture:
    code: int
    kind: str            # C, R, O, P, M(acro)
    params: list
    shape: object = None  # shapely geometry centred on origin

    @property
    def desc(self):
        return f"{self.kind}{'x'.join(f'{p:g}' for p in self.params)}"


@dataclass
class Obj:
    dark: bool
    kind: str            # flash, draw, region
    geom: object
    ap: Aperture = None
    pts: list = field(default_factory=list)   # flash: [(x, y)], draw: [(x0, y0), (x1, y1)], region: contour


def _macro_shape(body, params):
    """Evaluate an aperture macro body (list of primitive strings) with $n params."""
    def val(tok):
        tok = tok.strip()
        tok = re.sub(r'\$(\d+)', lambda m: repr(float(params[int(m.group(1)) - 1])), tok)
        tok = tok.replace('x', '*').replace('X', '*')
        if not re.fullmatch(r'[0-9eE\.\+\-\*/\(\) ]+', tok):
            raise ValueError(f'unsupported macro expression {tok!r}')
        return float(eval(tok, {'__builtins__': {}}, {}))
    add, sub = [], []
    for prim in body:
        if not prim or prim.startswith('0 ') or prim == '0':
            continue
        t = prim.split(',')
        code = int(val(t[0]))
        v = [val(x) for x in t[1:]]
        if code == 1:       # circle: exposure, diameter, cx, cy[, rot]
            g = Point(v[2], v[3]).buffer(v[1] / 2, CIRCLE_RES)
            if len(v) > 4:
                g = affinity.rotate(g, v[4], origin=(0, 0))
            exp = v[0]
        elif code == 4:     # outline: exposure, n, x0, y0 ... xn, yn, rot
            n = int(v[1])
            pts = [(v[2 + 2 * i], v[3 + 2 * i]) for i in range(n + 1)]
            g = affinity.rotate(fix(Polygon(pts)), v[2 + 2 * (n + 1)], origin=(0, 0))
            exp = v[0]
        elif code == 5:     # polygon: exposure, nverts, cx, cy, diameter, rot
            n = int(v[1])
            pts = [(v[2] + v[4] / 2 * math.cos(2 * math.pi * i / n), v[3] + v[4] / 2 * math.sin(2 * math.pi * i / n)) for i in range(n)]
            g = affinity.rotate(Polygon(pts), v[5], origin=(0, 0))
            exp = v[0]
        elif code == 20:    # vector line: exposure, width, x0, y0, x1, y1, rot
            g = LineString([(v[2], v[3]), (v[4], v[5])]).buffer(v[1] / 2, cap_style='flat')
            g = affinity.rotate(g, v[6], origin=(0, 0))
            exp = v[0]
        elif code == 21:    # centre line: exposure, w, h, cx, cy, rot
            g = box(v[3] - v[1] / 2, v[4] - v[2] / 2, v[3] + v[1] / 2, v[4] + v[2] / 2)
            g = affinity.rotate(g, v[5], origin=(0, 0))
            exp = v[0]
        else:
            raise ValueError(f'unsupported macro primitive {code}')
        (add if exp else sub).append(g)
    g = unary_union(add) if add else Polygon()
    if sub:
        g = g.difference(unary_union(sub))
    return g


class GerberLayer:
    def __init__(self, path):
        self.path = path
        self.name = path.split('/')[-1]
        self.apertures = {}
        self.macros = {}
        self.objs = []
        self.scale = 1e-5
        self._parse(open(path, encoding='latin-1').read())

    def _ap_shape(self, kind, p):
        if kind == 'C':
            return Point(0, 0).buffer(p[0] / 2, CIRCLE_RES) if p[0] > 0 else Point(0, 0).buffer(1e-6)
        if kind == 'R':
            return box(-p[0] / 2, -p[1] / 2, p[0] / 2, p[1] / 2)
        if kind == 'O':
            w, h = p[0], p[1]
            if w >= h:
                return LineString([(-(w - h) / 2, 0), ((w - h) / 2, 0)]).buffer(h / 2, CIRCLE_RES)
            return LineString([(0, -(h - w) / 2), (0, (h - w) / 2)]).buffer(w / 2, CIRCLE_RES)
        if kind == 'P':
            n = int(p[1])
            rot = math.radians(p[2]) if len(p) > 2 else 0.0
            return Polygon([(p[0] / 2 * math.cos(rot + 2 * math.pi * i / n), p[0] / 2 * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)])
        raise ValueError(kind)

    def _parse(self, text):
        text = text.replace('\r', '').replace('\n', '')
        pos = 0
        cmds = []
        for m in re.finditer(r'%([^%]*)%', text):
            cmds += [('d', c) for c in text[pos:m.start()].split('*') if c]
            cmds.append(('x', m.group(1)))
            pos = m.end()
        cmds += [('d', c) for c in text[pos:].split('*') if c]

        dark = True
        cur_ap = None
        x = y = 0.0
        interp = 1          # 1 linear, 2 cw, 3 ccw
        in_region = False
        contour = []

        def close_contour():
            nonlocal contour
            if len(contour) >= 3:
                g = fix(Polygon(contour))
                if not g.is_empty:
                    self.objs.append(Obj(dark, 'region', g, None, list(contour)))
            contour = []

        for typ, c in cmds:
            if typ == 'x':
                blocks = [b for b in c.split('*') if b]
                head = blocks[0]
                if head.startswith('FS'):
                    m = re.match(r'FSLAX(\d)(\d)Y(\d)(\d)', head)
                    self.scale = 10.0 ** (-int(m.group(2)))
                elif head.startswith('MO'):
                    if head != 'MOMM':
                        raise ValueError('only millimetre files are supported')
                elif head.startswith('AM'):
                    self.macros[head[2:]] = blocks[1:]
                elif head.startswith('AD'):
                    m = re.match(r'ADD(\d+)([A-Za-z_][A-Za-z0-9_]*)(?:,(.*))?$', head)
                    code, name, ps = int(m.group(1)), m.group(2), m.group(3)
                    params = [float(v) for v in ps.split('X')] if ps else []
                    if name in ('C', 'R', 'O', 'P'):
                        ap = Aperture(code, name, params, self._ap_shape(name, params))
                    else:
                        ap = Aperture(code, 'M', params, _macro_shape(self.macros[name], params))
                        ap.macro = name
                    self.apertures[code] = ap
                elif head.startswith('LP'):
                    dark = head[2] == 'D'
                continue
            # plain data block
            if c.startswith('G04'):
                continue
            m = re.fullmatch(r'D(\d+)', c)
            if m and int(m.group(1)) >= 10:
                cur_ap = self.apertures[int(m.group(1))]
                continue
            if c in ('G36',):
                in_region = True
                contour = []
                continue
            if c in ('G37',):
                close_contour()
                in_region = False
                continue
            if c in ('G75', 'G74', 'M02', 'G90', 'G91', 'G70', 'G71'):
                continue
            g = re.match(r'G0?([123])(.*)$', c)
            if g:
                interp = int(g.group(1))
                c = g.group(2)
                if not c:
                    continue
            m = re.fullmatch(r'(?:X(-?\d+))?(?:Y(-?\d+))?(?:I(-?\d+))?(?:J(-?\d+))?(?:D0?([123]))?', c)
            if not m:
                raise ValueError(f'unhandled gerber block {c!r} in {self.name}')
            nx = int(m.group(1)) * self.scale if m.group(1) is not None else x
            ny = int(m.group(2)) * self.scale if m.group(2) is not None else y
            i = int(m.group(3)) * self.scale if m.group(3) is not None else 0.0
            j = int(m.group(4)) * self.scale if m.group(4) is not None else 0.0
            op = int(m.group(5)) if m.group(5) else None
            if op is None:
                raise ValueError(f'coordinate block without operation {c!r}')
            if op == 2:
                if in_region:
                    close_contour()
                    contour = [(nx, ny)]
            elif op == 1:
                if interp == 1:
                    path = [(x, y), (nx, ny)]
                else:
                    cx, cy = x + i, y + j
                    r = math.hypot(i, j)
                    a0 = math.atan2(y - cy, x - cx)
                    a1 = math.atan2(ny - cy, nx - cx)
                    if interp == 2:      # clockwise
                        if a1 >= a0 - 1e-12:
                            a1 -= 2 * math.pi
                    else:
                        if a1 <= a0 + 1e-12:
                            a1 += 2 * math.pi
                    n = max(2, int(abs(a1 - a0) / (math.pi / 2 / CIRCLE_RES)) + 1)
                    path = [(cx + r * math.cos(a0 + (a1 - a0) * k / n), cy + r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]
                    path[0], path[-1] = (x, y), (nx, ny)
                if in_region:
                    if not contour:
                        contour = [path[0]]
                    contour += path[1:]
                else:
                    ap = cur_ap
                    if ap.kind == 'C':
                        if len(path) == 2 and path[0] == path[1]:
                            geom = Point(path[0]).buffer(max(ap.params[0], 2e-6) / 2, CIRCLE_RES)
                        else:
                            geom = LineString(path).buffer(max(ap.params[0], 2e-6) / 2, CIRCLE_RES)
                    else:
                        a = affinity.translate(ap.shape, path[0][0], path[0][1])
                        b = affinity.translate(ap.shape, path[-1][0], path[-1][1])
                        geom = unary_union([a, b]).convex_hull
                    self.objs.append(Obj(dark, 'draw', geom, ap, path))
            elif op == 3:
                geom = affinity.translate(cur_ap.shape, nx, ny)
                self.objs.append(Obj(dark, 'flash', geom, cur_ap, [(nx, ny)]))
            x, y = nx, ny

    def copper(self):
        """Final image: dark objects unioned, clear objects subtracted, in file order."""
        cur = Polygon()
        group, gdark = [], True
        def flush():
            nonlocal cur, group
            if not group:
                return
            u = unary_union(group)
            cur = cur.union(u) if gdark else cur.difference(u)
            group = []
        for o in self.objs:
            if o.dark != gdark:
                flush()
                gdark = o.dark
            group.append(o.geom)
        flush()
        return polygonal(cur)


def polys(g):
    if g.is_empty:
        return []
    if g.geom_type == 'Polygon':
        return [g]
    return list(g.geoms)


def read_drill(path):
    """Excellon reader for 'METRIC,LZ' 3:3 files. Returns list of (x, y, diameter)."""
    tools, holes, cur = {}, [], None
    ndec = 3
    for line in open(path, encoding='latin-1'):
        line = line.strip()
        m = re.match(r';FILE_FORMAT=(\d):(\d)', line)
        if m:
            ndec = int(m.group(2))
            nint = int(m.group(1))
            continue
        m = re.match(r'T(\d+)C([\d.]+)', line)
        if m:
            tools[int(m.group(1))] = float(m.group(2))
            continue
        m = re.fullmatch(r'T(\d+)', line)
        if m:
            cur = int(m.group(1))
            continue
        m = re.fullmatch(r'X(-?\d+)Y(-?\d+)', line)
        if m and cur is not None:
            def conv(s):
                neg = s.startswith('-')
                s = s.lstrip('-').ljust(nint + ndec, '0')   # leading zeros kept, trailing dropped
                v = int(s) / 10 ** ndec
                return -v if neg else v
            holes.append((conv(m.group(1)), conv(m.group(2)), tools[cur]))
    return holes
