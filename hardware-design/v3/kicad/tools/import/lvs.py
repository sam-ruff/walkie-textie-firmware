"""Three-way net check: schematic netlist vs layout database (SVG) vs real Gerber copper.

Usage: lvs.py gerber_dir layout.json sch_netlist.json out.json
"""
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # gbr.py is one level up
import gbr
from shapely.geometry import Point, Polygon
from shapely.strtree import STRtree

gd, layp, schp, outp = sys.argv[1:5]
lay = json.load(open(layp)); sch = json.load(open(schp))
names = {'top': 'Gerber_TopLayer.GTL', 'in1': 'Gerber_InnerLayer1.G1', 'in2': 'Gerber_InnerLayer2.G2', 'bot': 'Gerber_BottomLayer.GBL'}
layers = {k: gbr.GerberLayer(os.path.join(gd, f)) for k, f in names.items()}
cu = {k: gbr.polys(L.copper()) for k, L in layers.items()}
trees = {k: STRtree(v) for k, v in cu.items()}
holes = sorted(set(gbr.read_drill(os.path.join(gd, 'Drill_PTH_Through.DRL'))))

parent = {}
def find(a):
    parent.setdefault(a, a)
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[ra] = rb
for k in cu:
    for i in range(len(cu[k])): find((k, i))

def hit(layer, geom):
    return [int(i) for i in trees[layer].query(geom) if cu[layer][int(i)].intersects(geom)]

hole_nodes = []
for (x, y, dia) in holes:
    barrel = Point(x, y).buffer(dia / 2)
    nodes = []
    for k in cu:
        for i in hit(k, barrel): nodes.append((k, i))
    for n in nodes[1:]: union(nodes[0], n)
    hole_nodes.append(((x, y, dia), nodes))

# ---- top pads from the layout database
issues = []
padnet = []   # (ref, num, layout net, copper root, layer)
for p in lay['pads']:
    g = Polygon(p['poly'])
    hs = hit('top', Point(p['at']))
    hall = hit('top', g)
    if not hs:
        issues.append(f"pad {p.get('ref')}.{p['num']} at {p['at']}: no copper under the pad centre in GTL"); continue
    if len(set(find(('top', i)) for i in hall)) > 1:
        issues.append(f"pad {p.get('ref')}.{p['num']} at {p['at']}: pad area touches more than one copper net in GTL")
    padnet.append((p.get('ref', 'U1'), p['num'], p['net'], find(('top', hs[0])), 'top', tuple(p['at'])))
# ---- bottom pads: the 12 R1.5x0.3 flashes
botpads = [o for o in layers['bot'].objs if o.kind == 'flash' and o.ap.kind == 'R']
for o in sorted(botpads, key=lambda o: o.pts[0][1]):
    hs = hit('bot', Point(o.pts[0]))
    padnet.append(('U8', f"bot@y={o.pts[0][1]:.3f}", None, find(('bot', hs[0])), 'bot', tuple(round(v, 4) for v in o.pts[0])))

# ---- name each copper net from the layout database names found on it
root_names = collections.defaultdict(collections.Counter)
for ref, num, net, root, layer, at in padnet:
    if net is not None: root_names[root][net] += 1
via_info = []
for v in lay['vias']:
    pt = Point(v['at'])
    roots = set()
    for k in cu:
        for i in hit(k, pt.buffer(v['hole_d'] / 2)): roots.add(find((k, i)))
    via_info.append((v, roots))
    if len(roots) != 1:
        issues.append(f"via at {v['at']} net {v['net']}: touches {len(roots)} copper nets")
    for r in roots: root_names[r][v['net']] += 1

print('=== copper nets (Gerber) vs layout database net names ===')
shorts = [(r, c) for r, c in root_names.items() if len(c) > 1]
name_roots = collections.defaultdict(set)
for r, c in root_names.items():
    for n in c: name_roots[n].add(r)
opens = [(n, rs) for n, rs in name_roots.items() if len(rs) > 1]
print(f'copper nets carrying pads/vias: {len(root_names)}; layout net names: {len(name_roots)}')
print('SHORTS (one copper net, several layout nets):', [dict(c) for r, c in shorts] or 'none')
print('OPENS  (one layout net split across copper nets):', [(n, len(rs)) for n, rs in opens] or 'none')

# ---- which layers does each net use / per-layer polygon stats
root_layers = collections.defaultdict(lambda: collections.Counter())
for k in cu:
    for i, pg in enumerate(cu[k]):
        root_layers[find((k, i))][k] += pg.area
print('\n=== nets: copper area per layer (mm2) ===')
rootname = {r: max(c, key=c.get) for r, c in root_names.items()}
for r, c in sorted(root_layers.items(), key=lambda kv: -sum(kv[1].values())):
    nm = rootname.get(r, '(no pad/via: isolated copper)')
    print(f"  {nm:34} " + '  '.join(f"{k}={c[k]:8.2f}" for k in ('top', 'in1', 'in2', 'bot') if c[k] > 0))

# ---- bottom USB pads
print('\n=== USB plug bottom-row pads (GBL), south to north ===')
for ref, num, net, root, layer, at in padnet:
    if layer == 'bot':
        print(f"  {at}  -> copper net {rootname.get(root, '(isolated pad, no net)')}")

# ---- layout DB vs schematic: partition equivalence
print('\n=== layout database vs schematic netlist (pin by pin) ===')
schpin = {}
for net, pl in sch['nets'].items():
    for ref, num, name, nc, wired in pl: schpin[(ref, num)] = (net, name)
m_l2s = collections.defaultdict(collections.Counter); m_s2l = collections.defaultdict(collections.Counter)
missing = []
for ref, num, net, root, layer, at in padnet:
    if layer != 'top': continue
    key = (ref, num)
    if key not in schpin: missing.append(key); continue
    snet = schpin[key][0]
    m_l2s[net][snet] += 1; m_s2l[snet][net] += 1
bad = False
for lnet, c in sorted(m_l2s.items()):
    real = {k: v for k, v in c.items() if not k.startswith('__unconnected__')}
    if len(real) > 1 or (real and len(c) > len(real)):
        bad = True; print(f'  MISMATCH layout net {lnet!r} spans schematic nets {dict(c)}')
for snet, c in sorted(m_s2l.items()):
    if len(c) > 1:
        bad = True; print(f'  MISMATCH schematic net {snet!r} spans layout nets {dict(c)}')
print('  layout pads with no schematic pin:', missing or 'none')
if not bad: print('  every top-side pad carries the net the schematic gives its pin (names map one-to-one)')
mapping = {s: list(c)[0] for s, c in m_s2l.items()}
unnamed = {s: l for s, l in mapping.items() if s.startswith('N$')}
print('  anonymous schematic nets -> layout names:', unnamed)
print('  unconnected schematic pins -> layout net:', {s.replace('__unconnected__', ''): l for s, l in mapping.items() if s.startswith('__unconnected__') and l})

print('\n=== other issues ===')
for i in issues: print('  ', i)
if not issues: print('   none')

# ---- save the net assignment for later scripts
out = {'pads': [{'ref': a, 'num': b, 'net': c, 'root': str(d), 'layer': e, 'at': f} for a, b, c, d, e, f in padnet],
       'rootname': {str(k): v for k, v in rootname.items()},
       'poly_net': {k: [rootname.get(find((k, i)), None) for i in range(len(cu[k]))] for k in cu},
       'holes': [{'at': h[:2], 'd': h[2], 'layers': sorted(set(n[0] for n in nodes)), 'net': (rootname.get(find(nodes[0])) if nodes else None)} for h, nodes in hole_nodes]}
json.dump(out, open(outp, 'w'), indent=1)
