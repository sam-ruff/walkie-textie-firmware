"""Write the fabrication package for the board: Gerbers, drill, drawings, and a BOM and placement file for each order.

Usage: fab_outputs.py project_dir out_dir jlc_library_dir model.json [--fetch]

design.ORDERS names the orders: what each has assembled. They all use the same
Gerbers. The default order's BOM.csv and CPL.csv are at the top of the output
folder and every other order's are in a folder of its own. Both files use
JLCPCB's column names. Coordinates in the Gerbers, the drill file and the
placement files share one origin, the board's lower-left corner. The things
that are not parts (test pads, the printed tuning line, the logo) are in none
of them.

Every part an order fits is placed by the assembler: it has to carry a part
number of theirs and a row in the placement file, or this stops.

Each rotation in a placement file is worked out from JLCPCB's own footprint
for that part number (see jlc.py), so it is the rotation JLCPCB needs, which
for some parts differs from the one KiCad shows.
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import jlc
import parts
import pcbnew
from kiboard import numbered_pads
from project import KICAD_CLI, PROJECT

COPPER = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
LAYERS = COPPER + ["F.Paste", "B.Paste", "F.SilkS", "F.Mask", "B.Mask", "Edge.Cuts"]
PART_FIELDS = ["Reference", "Value", "Footprint", "LCSC", "MPN", "Manufacturer"]
BOM_COLUMNS = ["Comment", "Designator", "Footprint", "LCSC Part #", "MPN", "Manufacturer", "Qty"]
CPL_COLUMNS = {"Ref": "Designator", "Val": "Val", "Package": "Package", "PosX": "Mid X", "PosY": "Mid Y", "Rot": "Rotation", "Side": "Layer"}
# KiCad writes the time of plotting into every file it plots. The design's date takes its place,
# so that two builds of one design write the same files.
PLOT_TIME = re.compile(rb"(CreationDate\W{1,4}D?:?|date )\d{4}([-:])\d\d[-:]\d\d([T :])\d\d:\d\d:\d\d")


def cli(*args):
    res = subprocess.run([KICAD_CLI, *args], capture_output=True, text=True)
    if res.returncode:
        raise SystemExit(f"kicad-cli {' '.join(args[:3])} failed:\n{res.stdout}\n{res.stderr}")


def design_time(match):
    """The design's date, laid out like the plot time it replaces."""
    lead, gap, joint = match.group(1, 2, 3)
    return lead + gap.join(design.DATE.encode().split(b"-")) + joint + b"00:00:00"


def stamp(path):
    """Put the design's date where KiCad wrote the time of plotting."""
    with open(path, "rb") as fh:
        plotted = fh.read()
    dated, found = PLOT_TIME.subn(design_time, plotted)
    if not found:
        raise SystemExit(f"{path}: no plot time found to replace, so two builds would differ")
    with open(path, "wb") as fh:
        fh.write(dated)


def zip_files(folder, names, path):
    """A zip whose bytes depend only on the files in it: every entry carries the design's date."""
    year, month, day = (int(part) for part in design.DATE.split("-"))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            entry = zipfile.ZipInfo(name, date_time=(year, month, day, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            with open(os.path.join(folder, name), "rb") as fh:
                archive.writestr(entry, fh.read())


def gerbers(board, out_dir):
    target = os.path.join(out_dir, "gerbers")
    shutil.rmtree(target, ignore_errors=True)
    os.makedirs(target)
    cli("pcb", "export", "gerbers", "-o", target + os.sep, "--layers", ",".join(LAYERS), "--subtract-soldermask",
        "--use-drill-file-origin", "--no-x2", "--no-netlist", board)
    cli("pcb", "export", "drill", "-o", target + os.sep, "--format", "excellon", "--drill-origin", "plot",
        "--excellon-units", "mm", "--excellon-separate-th", board)
    names = sorted(os.listdir(target))
    for name in names:
        stamp(os.path.join(target, name))
    zip_files(target, names, os.path.join(out_dir, "gerbers.zip"))
    return names


def natural(ref):
    """Sort key that puts C2 before C10."""
    letters = ref.rstrip("0123456789")
    return letters, int(ref[len(letters):] or 0)


def part_rows(schematic, tmp):
    """{designator: its BOM fields} for every part in the schematic, fitted or not."""
    raw = os.path.join(tmp, "parts.csv")
    cli("sch", "export", "bom", "-o", raw, "--fields", ",".join(PART_FIELDS), "--labels", ",".join(PART_FIELDS), schematic)
    with open(raw, newline="") as fh:
        return {row["Reference"]: row for row in csv.DictReader(fh)}


def placed_rows(board, tmp, cache_dir, fetch, all_parts):
    """{designator: its placement row} for every part on the board, as JLCPCB's footprint for it has to be placed.

    The rotation written is the one that lays JLCPCB's footprint for the part's number on the board's
    pads, which need not be KiCad's, and the position is where that footprint's origin then is.
    """
    raw = os.path.join(tmp, "pos.csv")
    cli("pcb", "export", "pos", "-o", raw, "--format", "csv", "--units", "mm", "--side", "both", "--use-drill-file-origin", board)
    with open(raw, newline="") as fh:
        rows = {row["Ref"]: row for row in csv.DictReader(fh)}
    pads = {fp.GetReference(): numbered_pads(fp) for fp in pcbnew.LoadBoard(board).GetFootprints()}
    moved = []
    for ref, row in rows.items():
        x, y, rotation = float(row["PosX"]), float(row["PosY"]), float(row["Rot"]) % 360
        lcsc = all_parts[ref]["footprint_as"] or all_parts[ref]["lcsc"]
        if lcsc:
            library = jlc.footprint_pads(jlc.library_entry(lcsc, cache_dir, fetch))
            rotation, (fx, fy), _ = jlc.fit(pads[ref], library, x, y, rotation, all_parts[ref]["jlc_pads"])
            if (fx, fy) != (x, y):
                moved.append(f"{ref} by ({fx - x:+.2f}, {fy - y:+.2f}) mm")
                x, y = fx, fy
        row["Rot"] = f"{rotation:.2f}"
        row["PosX"], row["PosY"] = f"{x:.3f}", f"{y:.3f}"
    print(f"placed where JLCPCB's footprint has its origin, which is not where KiCad's is: {', '.join(moved) or 'none'}")
    return rows


def write_order(folder, fitted, part_row, placed_row):
    """One order's BOM.csv and CPL.csv. Returns the problems that would leave a part for someone to fit by hand."""
    os.makedirs(folder, exist_ok=True)
    groups = {}
    for ref in sorted(fitted, key=natural):
        row = part_row[ref]
        groups.setdefault((row["Value"], row["Footprint"], row["LCSC"], row["MPN"], row["Manufacturer"]), []).append(ref)
    with open(os.path.join(folder, "BOM.csv"), "w", newline="") as fh:
        writer = csv.writer(fh, quoting=csv.QUOTE_ALL)
        writer.writerow(BOM_COLUMNS)
        for (value, footprint, lcsc, mpn, maker), refs in groups.items():
            writer.writerow([value, ",".join(refs), footprint, lcsc, mpn, maker, len(refs)])
    with open(os.path.join(folder, "CPL.csv"), "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CPL_COLUMNS.values())
        for ref in sorted(fitted & set(placed_row), key=natural):
            writer.writerow([placed_row[ref][key] for key in CPL_COLUMNS])
    return ([f"{ref} has no part number for the assembler" for ref in sorted(fitted, key=natural) if not part_row[ref]["LCSC"]]
            + [f"{ref} has no row in the placement file" for ref in sorted(fitted - set(placed_row), key=natural)])


def main():
    project, out_dir, cache_dir, model_path = sys.argv[1:5]
    board = os.path.join(project, f"{PROJECT}.kicad_pcb")
    schematic = os.path.join(project, f"{PROJECT}.kicad_sch")
    with open(model_path) as fh:
        all_parts = parts.resolve(json.load(fh))
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)

    files = gerbers(board, out_dir)
    print(f"gerbers: {len(files)} files, zipped")
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        part_row = part_rows(schematic, tmp)
        placed_row = placed_rows(board, tmp, cache_dir, "--fetch" in sys.argv, all_parts)
        for order in design.ORDERS:
            fitted = parts.fitted(all_parts, order)
            folder = out_dir if order == design.DEFAULT_ORDER else os.path.join(out_dir, order)
            found = write_order(folder, fitted, part_row, placed_row)
            problems += [f"order {order}: {problem}" for problem in found]
            changes = design.ORDERS[order]
            differs = "; ".join(f"{word} {' '.join(changes[key])}" for key, word in (("fit", "fits"), ("leave_out", "leaves out")) if changes.get(key))
            print(f"order {order}: {len(fitted)} parts placed{', ' + differs if differs else ''}")
        cli("sch", "export", "pdf", "-o", os.path.join(out_dir, "schematic.pdf"), schematic)
        # The assembly drawing: every part's outline and designator, as large as the sheet takes, with the
        # parts the default order leaves out crossed through. Its heading is the text silk.py puts on the
        # comments layer.
        cli("pcb", "export", "pdf", "-o", os.path.join(tmp, "assembly.pdf"), "--layers", "F.Fab,Edge.Cuts,Cmts.User",
            "--mode-single", "--black-and-white", "--scale", "0",
            "--crossout-DNP-footprints-on-fab-layers", "--no-property-popups", board)
        shutil.copyfile(os.path.join(tmp, "assembly.pdf"), os.path.join(out_dir, "assembly.pdf"))
    for name in ("schematic.pdf", "assembly.pdf"):
        stamp(os.path.join(out_dir, name))

    supplied = sorted(ref for ref, part in all_parts.items() if part["supplied"])
    print(f"placed from stock sent to the assembler: {' '.join(supplied) or 'none'}")
    if problems:
        print("\n".join(problems))
        raise SystemExit(f"{len(problems)} parts that the assembler could not place")
    print("every part of every order has an assembler's part number and a placement row")


if __name__ == "__main__":
    main()
