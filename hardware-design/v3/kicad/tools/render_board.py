"""Render a KiCad board to PNG through kicad-cli's SVG export.

Usage: render_board.py board.kicad_pcb out.png layers [x1 y1 x2 y2] [--px-per-mm N]
`layers` is a comma-separated KiCad layer list. The optional window is in board
millimetres (origin lower-left, Y up, board corner at KiCad 100,100).
Needs cairosvg, so run it with an interpreter that has it.
"""
import os
import re
import subprocess
import sys
import tempfile

import cairosvg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from project import KICAD_CLI

OX, OY = 100.0, 100.0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    board, out, layers = args[0], args[1], args[2]
    window = [float(v) for v in args[3:7]] if len(args) >= 7 else None
    ppm = 24.0
    if "--px-per-mm" in sys.argv:
        ppm = float(sys.argv[sys.argv.index("--px-per-mm") + 1])
    # A window is cut from the whole page, whose coordinates are KiCad's. Without one, the page is the board.
    page_mode = "0" if window else "2"
    with tempfile.TemporaryDirectory() as tmp:
        svg = os.path.join(tmp, "b.svg")
        subprocess.run(
            [KICAD_CLI, "pcb", "export", "svg", "--layers", layers, "--mode-single", "--page-size-mode", page_mode,
             "--exclude-drawing-sheet", "-o", svg, board],
            check=True, capture_output=True,
        )
        text = open(svg).read()
        m = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([-\d.]+) ([-\d.]+)"', text)
        vx, vy, vw, vh = (float(v) for v in m.groups())
        if window:
            x1, y1, x2, y2 = window
            vx, vy, vw, vh = OX + x1, OY - y2, x2 - x1, y2 - y1
            text = re.sub(r'viewBox="[^"]+"', f'viewBox="{vx} {vy} {vw} {vh}"', text, count=1)
            text = re.sub(r'width="[^"]+"', f'width="{vw}mm"', text, count=1)
            text = re.sub(r'height="[^"]+"', f'height="{vh}mm"', text, count=1)
        cairosvg.svg2png(bytestring=text.encode(), write_to=out, output_width=int(vw * ppm), output_height=int(vh * ppm), background_color="white")
    where = f"window x {vx - OX:.1f}..{vx - OX + vw:.1f}, y {OY - vy - vh:.1f}..{OY - vy:.1f}" if window else "whole board"
    print(f"wrote {out} ({int(vw * ppm)}x{int(vh * ppm)} px, {where})")


if __name__ == "__main__":
    main()
