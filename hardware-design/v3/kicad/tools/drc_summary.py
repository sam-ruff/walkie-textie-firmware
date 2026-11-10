"""Run KiCad DRC on a board and print a compact summary.

Usage: drc_summary.py board.kicad_pcb [--refill] [--parity] [--show type[,type...]] [--max N]
Positions are printed in board millimetres (origin lower-left, Y up).
"""
import collections
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import KICAD_CLI

OX, OY = 100.0, 100.0


def main():
    board = sys.argv[1]
    show = set()
    if "--show" in sys.argv:
        show = set(sys.argv[sys.argv.index("--show") + 1].split(","))
    limit = 40
    if "--max" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--max") + 1])
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "drc.json")
        cmd = [KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all", "--units", "mm", "-o", out]
        if "--refill" in sys.argv:
            cmd += ["--refill-zones", "--save-board"]
        if "--parity" in sys.argv:
            cmd += ["--schematic-parity"]
        res = subprocess.run(cmd + [board], capture_output=True, text=True)
        if not os.path.exists(out):
            print(res.stdout, res.stderr)
            raise SystemExit("DRC did not produce a report")
        report = json.load(open(out))

    def where(item):
        p = item.get("pos", {})
        return f"({p.get('x', 0) - OX:.2f}, {OY - p.get('y', 0):.2f})"

    groups = collections.Counter((v["type"], v["severity"]) for v in report["violations"])
    print(f"violations {len(report['violations'])}, unconnected {len(report['unconnected_items'])}, parity {len(report.get('schematic_parity', []))}")
    for (kind, sev), n in sorted(groups.items(), key=lambda kv: (kv[0][1], -kv[1])):
        print(f"  {n:4d} {sev:8} {kind}")
    shown = 0
    for v in report["violations"]:
        if v["type"] in show or "all" in show:
            if shown >= limit:
                print("  ...")
                break
            items = " | ".join(f"{i['description']} {where(i)}" for i in v["items"])
            print(f"  [{v['type']}] {v['description']}: {items}")
            shown += 1
    if "unconnected" in show or "all" in show:
        for u in report["unconnected_items"][:limit]:
            items = " | ".join(f"{i['description']} {where(i)}" for i in u["items"])
            print(f"  [unconnected] {items}")
    if "parity" in show or "all" in show:
        for u in report.get("schematic_parity", [])[:limit]:
            items = " | ".join(i["description"] for i in u["items"])
            print(f"  [parity] {u['description']}: {items}")


if __name__ == "__main__":
    main()
