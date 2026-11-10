"""Write the layer stack-up from design.STACKUP into a board file.

Usage: set_stackup.py board.kicad_pcb

The Python bindings do not expose the stack-up, so the block goes straight into
the file's setup section. KiCad keeps it through later loads and saves.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design

OUTER_TOP = [("F.SilkS", "Top Silk Screen", None), ("F.Paste", "Top Solder Paste", None), ("F.Mask", "Top Solder Mask", 0.01)]
OUTER_BOTTOM = [("B.Mask", "Bottom Solder Mask", 0.01), ("B.Paste", "Bottom Solder Paste", None), ("B.SilkS", "Bottom Silk Screen", None)]


def layer(name, kind, thickness=None, material=None, epsilon=None):
    parts = [f'(layer "{name}"', f'(type "{kind}")']
    if thickness is not None:
        parts.append(f"(thickness {thickness:g})")
    if material is not None:
        parts.append(f'(material "{material}")')
    if epsilon is not None:
        parts += [f"(epsilon_r {epsilon:g})", "(loss_tangent 0.02)"]
    return "\t\t\t" + " ".join(parts) + ")"


def block():
    lines = ["\t\t(stackup"]
    lines += [layer(*entry) for entry in OUTER_TOP]
    lines += [layer(*entry) for entry in design.STACKUP]
    lines += [layer(*entry) for entry in OUTER_BOTTOM]
    lines += [f'\t\t\t(copper_finish "{design.COPPER_FINISH}")', "\t\t\t(dielectric_constraints yes)", "\t\t)"]
    return "\n".join(lines) + "\n"


def main():
    path = sys.argv[1]
    with open(path) as fh:
        text = fh.read()
    if "(stackup" in text:
        raise SystemExit("the board already has a stack-up")
    marker = "\t(setup\n"
    if text.count(marker) != 1:
        raise SystemExit("could not find the board's setup section")
    with open(path, "w") as fh:
        fh.write(text.replace(marker, marker + block()))
    total = sum(entry[2] for entry in design.STACKUP)
    print(f"stack-up written: {len(design.STACKUP)} layers, {total:.4f} mm without solder mask")


if __name__ == "__main__":
    main()
