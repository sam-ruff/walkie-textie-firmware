"""Run KiCad's own checks on the project and fail on any finding at any severity.

Usage: verify.py project_dir [--schematic-only]

- ERC on the schematic.
- DRC on the board, including the comparison with the schematic.
Nothing is filtered or waived: a warning fails the check as an error does.
"""
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import KICAD_CLI, PROJECT


def report(args, out):
    res = subprocess.run([KICAD_CLI, *args, "--format", "json", "--severity-all", "-o", out], capture_output=True, text=True)
    if not os.path.exists(out):
        raise SystemExit(f"{' '.join(args[:2])} did not run: {res.stdout} {res.stderr}")
    with open(out) as fh:
        return json.load(fh)


def lines(kind, rows):
    out = []
    for row in rows:
        items = " | ".join(item["description"] for item in row.get("items", []))
        out.append(f"  [{kind}] {row.get('severity', '')} {row.get('type', '')}: {row['description']}: {items}")
    return out


def main():
    project = sys.argv[1]
    found = []
    with tempfile.TemporaryDirectory() as tmp:
        erc = report(["sch", "erc", os.path.join(project, f"{PROJECT}.kicad_sch")], os.path.join(tmp, "erc.json"))
        erc_rows = [v for sheet in erc.get("sheets", []) for v in sheet.get("violations", [])]
        found += lines("ERC", erc_rows)
        print(f"ERC: {len(erc_rows)} findings")
        if "--schematic-only" not in sys.argv:
            drc = report(["pcb", "drc", "--schematic-parity", "--units", "mm", os.path.join(project, f"{PROJECT}.kicad_pcb")],
                         os.path.join(tmp, "drc.json"))
            found += lines("DRC", drc["violations"]) + lines("unconnected", drc["unconnected_items"]) + lines("parity", drc.get("schematic_parity", []))
            print(f"DRC: {len(drc['violations'])} findings, {len(drc['unconnected_items'])} unconnected, "
                  f"{len(drc.get('schematic_parity', []))} differences from the schematic")
    if found:
        print("\n".join(found[:60]))
        raise SystemExit(f"{len(found)} findings")


if __name__ == "__main__":
    main()
