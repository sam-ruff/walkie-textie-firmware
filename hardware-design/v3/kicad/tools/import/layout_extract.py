"""Extract pads, vias and tracks (in board mm) from the EasyEDA PCB SVG export, and attach pads to components.

Usage: layout_extract.py layout.svg pickandplace.csv sch_netlist.json out.json
"""
import sys, json, math, collections, csv, io, re
import xml.etree.ElementTree as ET

NS = '{http://www.w3.org/2000/svg}'
U = 0.254
X0, Y0 = 4020.0, 3398.0          # SVG coordinates of the board's lower-left corner

def mm(x, y):
    return (round((float(x) - X0) * U, 4), round((Y0 - float(y)) * U, 4))

def tag(e):
    return e.tag.replace(NS, '')

svg, cplp, schp, outp = sys.argv[1:5]
root = ET.parse(svg).getroot()
pads, vias, tracks = [], [], []
for e in root.iter():
    pid = e.attrib.get('c_partid')
    if pid == 'part_pad':
        cx, cy = e.attrib['c_origin'].split(',')
        poly = None
        for c in e:
            if c.attrib.get('c_etype') == 'pad_shell' and tag(c) == 'polygon':
                v = [float(t) for t in c.attrib['points'].split()]
                poly = [mm(v[i], v[i + 1]) for i in range(0, len(v), 2)]
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        pads.append({'num': e.attrib['number'], 'net': e.attrib.get('net', ''), 'at': mm(cx, cy), 'poly': poly,
                     'w': round(max(xs) - min(xs), 3), 'h': round(max(ys) - min(ys), 3), 'layer': e.attrib['layerid'],
                     'rot': e.attrib.get('c_rotation'), 'id': e.attrib['id']})
    elif pid == 'part_via':
        cx, cy = e.attrib['c_origin'].split(',')
        rs = [float(c.attrib['r']) * U for c in e if tag(c) == 'circle']
        vias.append({'net': e.attrib.get('net', ''), 'at': mm(cx, cy), 'pad_d': round(2 * max(rs), 3), 'hole_d': round(2 * min(rs), 3)})
for e in root:
    if tag(e) == 'polyline' and e.attrib.get('layerid') == '1' and 'net' in e.attrib:
        v = [float(t) for t in e.attrib['points'].split()]
        tracks.append({'net': e.attrib['net'], 'w': round(float(e.attrib['stroke-width']) * U, 4),
                       'pts': [mm(v[i], v[i + 1]) for i in range(0, len(v), 2)], 'layer': 'top'})

raw = open(cplp, 'rb').read().decode('utf-16')
rows = list(csv.DictReader(io.StringIO(raw), delimiter='\t'))
comps = {}
for r in rows:
    f = lambda k: float(r[k].replace('mm', ''))
    comps[r['Designator']] = {'ref': r['Designator'], 'fp': r['Footprint'], 'at': (f('Mid X'), f('Mid Y')), 'pad1': (f('Pad X'), f('Pad Y')),
                              'rot': float(r['Rotation']), 'val': r['Comment'], 'layer': r['Layer']}
sch = json.load(open(schp))
pins_of = collections.defaultdict(dict)
for net, pl in sch['nets'].items():
    for ref, num, name, nc, wired in pl:
        pins_of[ref][num] = {'net': net, 'name': name}

# attach pads to components: small parts first, then by increasing footprint size
def d(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])
free = set(range(len(pads)))
order = sorted(comps.values(), key=lambda c: len(pins_of[c['ref']]))
assign = {}
problems = []
for c in order:
    want = set(pins_of[c['ref']].keys())
    n = len(want)
    cand = sorted(free, key=lambda i: d(pads[i]['at'], c['at']))
    got = {}
    for i in cand:
        num = pads[i]['num']
        if num in want and num not in got:
            got[num] = i
        if len(got) == n:
            break
    # sanity: pad 1 must coincide with the pick-and-place 'Pad X/Y'
    for num, i in got.items():
        assign[i] = (c['ref'], num); free.discard(i)
    p1 = [i for num, i in got.items() if d(pads[i]['at'], c['pad1']) < 0.06]
    spread = max((d(pads[i]['at'], c['at']) for i in got.values()), default=0)
    c['npads_top'] = len(got); c['spread'] = round(spread, 2)
    c['pad1_num'] = pads[p1[0]]['num'] if p1 else None
    if len(got) != n:
        problems.append(f"{c['ref']}: schematic has {n} pins, found {len(got)} top pads (missing {sorted(want - set(got))})")
for i in sorted(free):
    problems.append(f"unassigned top pad num={pads[i]['num']} net={pads[i]['net']} at={pads[i]['at']}")
for i, (ref, num) in assign.items():
    pads[i]['ref'] = ref
json.dump({'pads': pads, 'vias': vias, 'tracks': tracks, 'comps': comps}, open(outp, 'w'), indent=1)
print(f'pads={len(pads)} vias={len(vias)} top tracks={len(tracks)} comps={len(comps)}')
print('via sizes (pad/hole):', dict(collections.Counter((v['pad_d'], v['hole_d']) for v in vias)))
print('via nets:', dict(collections.Counter(v['net'] for v in vias)))
for c in sorted(comps.values(), key=lambda c: (re.match(r'[A-Z]+', c['ref']).group(), int(re.search(r'\d+', c['ref']).group()))):
    print(f"  {c['ref']:5} pins(sch)={len(pins_of[c['ref']]):2} top pads={c['npads_top']:2} spread={c['spread']:5} mm  pad@CPL-pad-pos={c['pad1_num']}  rot={c['rot']:g}  {c['fp']}")
print('PROBLEMS:')
for p in problems: print('  ', p)
