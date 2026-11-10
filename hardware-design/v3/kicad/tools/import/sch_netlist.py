"""Extract a netlist from EasyEDA Std schematic SVG exports.

Usage: sch_netlist.py out.json sheet1.svg [sheet2.svg ...]
"""
import sys, json, collections
import xml.etree.ElementTree as ET

NS = '{http://www.w3.org/2000/svg}'
EPS = 0.01

def tag(e):
    return e.tag.replace(NS, '')

def pt(s):
    x, y = s.split(',')
    return (round(float(x), 2), round(float(y), 2))

class UF:
    def __init__(self):
        self.p = {}
    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a
    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb

def on_seg(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cross) > EPS * max(1.0, abs(bx - ax) + abs(by - ay)):
        return False
    return (min(ax, bx) - EPS <= px <= max(ax, bx) + EPS and
            min(ay, by) - EPS <= py <= max(ay, by) + EPS)

def parse_sheet(path, sheet):
    root = ET.parse(path).getroot()
    parts, labels, flags, wires, juncs, ncs = [], [], [], [], [], []
    for e in root.iter():
        pid = e.attrib.get('c_partid', '')
        if pid.startswith('part_lib_gge'):
            ref = val = None
            for g in e:
                if g.attrib.get('c_partid') == 'part_annotation':
                    for t in g:
                        note = t.attrib.get('c_note')
                        if note == 'note_pre': ref = (t.text or '').strip()
                        if note == 'note_name': val = (t.text or '').strip()
            para = e.attrib.get('c_para', '')
            kv = para.split('`')
            pd = dict(zip(kv[0::2], kv[1::2]))
            pins = []
            for g in e.iter():
                if g.attrib.get('c_partid') != 'part_pin': continue
                name = num = None
                for t in g:
                    if 'c_pinname' in t.attrib: name = t.attrib['c_pinname']
                    if 'c_pinnumber' in t.attrib: num = t.attrib['c_pinnumber']
                pins.append({'num': num, 'name': name, 'at': pt(g.attrib['c_origin']),
                             'spicepin': g.attrib.get('c_spicepin')})
            parts.append({'ref': ref, 'val': val, 'pkg': pd.get('package'),
                          'lcsc': pd.get('Supplier Part'), 'mpn': pd.get('Manufacturer Part'),
                          'pins': pins, 'sheet': sheet, 'bom': e.attrib.get('add_into_bom'),
                          'to_pcb': e.attrib.get('convert_to_pcb')})
        elif pid == 'part_netLabel_text':
            txt = ''.join((t.text or '') for t in e if tag(t) == 'text').strip()
            labels.append((pt(e.attrib['c_origin']), txt))
        elif pid.startswith('part_netLabel_'):
            txt = None
            for t in e.iter():
                if t.attrib.get('c_note') == 'note_netflag': txt = (t.text or '').strip()
            flags.append((pt(e.attrib['c_origin']), txt, pid))
        elif pid == 'part_junction':
            c = None
            for t in e.iter():
                if tag(t) == 'circle': c = (round(float(t.attrib['cx']), 2), round(float(t.attrib['cy']), 2))
            juncs.append(c)
        elif pid == 'part_no_connect_flag':
            o = e.attrib.get('c_origin')
            ncs.append(pt(o) if o else None)
        elif e.attrib.get('c_etype') == 'wire' and tag(e) == 'polyline':
            v = [float(x) for x in e.attrib['points'].split()]
            pts = [(round(v[i], 2), round(v[i + 1], 2)) for i in range(0, len(v), 2)]
            wires.append(pts)
    return parts, labels, flags, wires, juncs, ncs

def main():
    out = sys.argv[1]
    uf = UF()
    allparts, notes = [], []
    named = collections.defaultdict(set)   # net name -> set of uf keys
    for si, path in enumerate(sys.argv[2:]):
        sheet = path.split('/')[-1].replace('.svg', '')
        parts, labels, flags, wires, juncs, ncs = parse_sheet(path, sheet)
        segs = []
        for wi, pts in enumerate(wires):
            for i in range(len(pts)):
                uf.union((sheet, 'w', wi), (sheet, 'p', pts[i]))
            for i in range(len(pts) - 1):
                segs.append((pts[i], pts[i + 1], wi))
        # wire vertices coincident with other wires' vertices are joined through the shared point key
        # wire endpoints landing on the interior of another wire's segment
        for wi, pts in enumerate(wires):
            for p in (pts[0], pts[-1]):
                for a, b, wj in segs:
                    if wj == wi or p in (a, b): continue
                    if on_seg(p, a, b):
                        uf.union((sheet, 'w', wi), (sheet, 'w', wj))
                        if p not in juncs:
                            notes.append(f'{sheet}: wire end {p} lands mid-segment on another wire without a junction dot (treated as connected)')
        # junctions join every wire passing through
        for j in juncs:
            hit = [wj for a, b, wj in segs if on_seg(j, a, b)]
            for h in hit: uf.union((sheet, 'w', hit[0]), (sheet, 'w', h))
            uf.union((sheet, 'p', j), (sheet, 'w', hit[0])) if hit else None
        def attach(p, key, what):
            uf.union(key, (sheet, 'p', p))
            hit = False
            for a, b, wj in segs:
                if on_seg(p, a, b):
                    uf.union(key, (sheet, 'w', wj)); hit = True
                    if p not in (a, b) and what.startswith('pin'):
                        notes.append(f'{sheet}: {what} at {p} touches the middle of a wire (treated as connected)')
            return hit
        for part in parts:
            for pin in part['pins']:
                key = (sheet, 'pin', part['ref'], pin['num'], pin['at'])
                pin['key'] = key
                pin['wired'] = attach(pin['at'], key, f"pin {part['ref']}.{pin['num']}")
                pin['nc'] = pin['at'] in ncs
        for p, txt in labels:
            key = (sheet, 'label', p, txt)
            if not attach(p, key, 'label'):
                notes.append(f'{sheet}: net label {txt!r} at {p} is not on a wire')
            named[txt].add(key)
        for p, txt, pid in flags:
            key = (sheet, 'flag', p, txt)
            attach(p, key, 'flag')
            named[txt].add(key)
        allparts += parts
    for name, keys in named.items():
        keys = list(keys)
        for k in keys[1:]: uf.union(keys[0], k)
    rootname = collections.defaultdict(set)
    for name, keys in named.items():
        for k in keys: rootname[uf.find(k)].add(name)
    nets = collections.defaultdict(list)
    for part in allparts:
        for pin in part['pins']:
            r = uf.find(pin['key'])
            nets[r].append((part['ref'], pin['num'], pin['name'], pin['nc'], pin['wired']))
    result, anon = {}, 0
    for r, pins in nets.items():
        names = sorted(rootname.get(r, []))
        if len(names) > 1:
            notes.append(f'net has several names (shorted labels): {names}')
        if names:
            nm = '/'.join(names)
        else:
            if len(pins) == 1:
                ref, num, name, nc, wired = pins[0]
                nm = f'__unconnected__{ref}.{num}'
            else:
                anon += 1
                nm = f'N${anon}'
        result.setdefault(nm, []).extend(pins)
    json.dump({'nets': {k: [list(p) for p in v] for k, v in result.items()},
               'parts': [{k: v for k, v in p.items() if k != 'pins'} | {'pins': [{'num': q['num'], 'name': q['name']} for q in p['pins']]} for p in allparts],
               'notes': notes}, open(out, 'w'), indent=1)
    def keyf(s):
        import re
        m = re.match(r'([A-Za-z]+)(\d+)', s[0]); return (m.group(1), int(m.group(2))) if m else (s[0], 0)
    print('PARTS:', len(allparts))
    for p in sorted(allparts, key=lambda p: keyf((p['ref'] or '?',))):
        print(f"  {p['ref']:6} {p['val']!s:28} {p['pkg']!s:40} {p['lcsc']!s:10} pins={len(p['pins'])} sheet={p['sheet']} bom={p['bom']} pcb={p['to_pcb']}")
    print('\nNETS:')
    for nm in sorted(result, key=lambda n: (n.startswith('__'), n)):
        pins = sorted(result[nm], key=keyf)
        if nm.startswith('__unconnected__'):
            ref, num, name, nc, wired = pins[0]
            print(f"  {'(single pin)':16} {ref}.{num} [{name}] {'NC-flag' if nc else 'NO NC FLAG'} {'wired-stub' if wired else ''}")
        else:
            print(f"  {nm:16} " + ', '.join(f"{ref}.{num}[{name}]" for ref, num, name, nc, wired in pins))
    print('\nNOTES:')
    for n in sorted(set(notes)): print('  ', n)

main()
