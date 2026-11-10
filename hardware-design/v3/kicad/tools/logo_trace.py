"""Trace the goblin avatar into a silkscreen footprint.

Usage: logo_trace.py avatar.png out_dir.pretty preview.png [--width-mm 9.0] [--style filled|lines]

The picture is a drawing with dark outlines, green skin and a white robe on a
plain background. Silkscreen has one colour, so:

- lines:  ink where the drawing has its dark outlines.
- filled: the robe is solid ink and the outlines that touch it are left out,
          so its folds show as gaps; everything else is drawn as outlines.

The footprint is board-only: no pads, not in the BOM or the placement file.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import contourpy
import numpy as np
import pcbnew
from kiboard import seed_ids
from PIL import Image, ImageDraw, ImageFilter
from pcbnew import VECTOR2I, FromMM
from project import PROJECT as LIB
from shapely import affinity
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

NAME = "Logo_Goblin"
UPSCALE = 3
MIN_FEATURE = 0.15         # mm: the fab's narrowest silkscreen line
MIN_ROBE_PX = 1500         # enclosed light areas smaller than this are highlights, not robe
LINE_REACH = 11            # px: an outline this close to the robe is left out in the filled style


def classes(rgb):
    r, g, b = (rgb[..., i].astype(int) for i in range(3))
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    dark = luminance < 85
    green = ~dark & (g > r + 25) & (g > b + 25)
    light = ~dark & ~green
    return dark, green, light


def components(mask):
    """Label 4-connected regions with a flood fill. Returns (labels, count)."""
    labels = np.zeros(mask.shape, dtype=np.int32)
    count = 0
    height, width = mask.shape
    for sy, sx in zip(*np.nonzero(mask)):
        if labels[sy, sx]:
            continue
        count += 1
        stack = [(sy, sx)]
        labels[sy, sx] = count
        while stack:
            y, x = stack.pop()
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not labels[ny, nx]:
                    labels[ny, nx] = count
                    stack.append((ny, nx))
    return labels, count


def robe_mask(light):
    """Light areas enclosed by the drawing: not the background, not a small highlight."""
    labels, count = components(light)
    edge = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    robe = np.zeros(light.shape, dtype=bool)
    for label in range(1, count + 1):
        if label in edge:
            continue
        region = labels == label
        if region.sum() >= MIN_ROBE_PX:
            robe |= region
    return robe


def grow(mask, reach):
    image = Image.fromarray((mask * 255).astype(np.uint8))
    return np.asarray(image.filter(ImageFilter.MaxFilter(2 * reach + 1))) > 127


def ink_mask(rgb, style):
    dark, _green, light = classes(rgb)
    if style == "lines":
        return dark
    robe = robe_mask(light)
    return robe | (dark & ~grow(robe, LINE_REACH))


def smooth(mask):
    image = Image.fromarray((mask * 255).astype(np.uint8))
    big = image.resize((mask.shape[1] * UPSCALE, mask.shape[0] * UPSCALE), Image.BICUBIC)
    return np.asarray(big.filter(ImageFilter.GaussianBlur(UPSCALE * 0.8)), dtype=float) / 255.0


def trace(field):
    """Polygons (in upscaled pixels) around everything above half ink."""
    padded = np.pad(field, 1)
    generator = contourpy.contour_generator(z=padded, fill_type=contourpy.FillType.OuterOffset)
    points, offsets = generator.filled(0.5, 10.0)
    shapes = []
    for pts, offs in zip(points, offsets):
        rings = [pts[offs[i] : offs[i + 1]] - 1.0 for i in range(len(offs) - 1)]
        shape = Polygon(rings[0], rings[1:])
        shapes.append(shape if shape.is_valid else shape.buffer(0))
    return unary_union(shapes)


def clean(shape):
    """Drop what the fab cannot print: slivers, hairline gaps and specks."""
    half = MIN_FEATURE / 2
    shape = shape.buffer(-half * 0.8).buffer(half * 0.8)      # slivers
    shape = shape.buffer(half * 0.6).buffer(-half * 0.6)      # hairline gaps
    parts = [shape] if shape.geom_type == "Polygon" else list(shape.geoms)
    kept = []
    for part in parts:
        if part.area < MIN_FEATURE**2:
            continue
        holes = [h for h in part.interiors if Polygon(h).area >= MIN_FEATURE**2]
        kept.append(Polygon(part.exterior, holes))
    return kept


def without_holes(shape):
    """KiCad's polygon primitive has one outline, so cut a polygon through each of its holes."""
    if shape.is_empty:
        return []
    if shape.geom_type != "Polygon":
        return [piece for part in shape.geoms for piece in without_holes(part)]
    if not shape.interiors:
        return [shape]
    cut = Polygon(shape.interiors[0]).centroid.x
    x1, y1, x2, y2 = shape.bounds
    left = shape.intersection(box(x1 - 1, y1 - 1, cut, y2 + 1))
    right = shape.intersection(box(cut, y1 - 1, x2 + 1, y2 + 1))
    return without_holes(left) + without_holes(right)


def footprint(pieces, width_mm, height_mm):
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID(LIB, NAME))
    fp.SetAttributes(pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_EXCLUDE_FROM_BOM)
    fp.SetAllowMissingCourtyard(True)
    fp.SetLibDescription(f"Goblin logo for the silkscreen, {width_mm:.1f} x {height_mm:.1f} mm")
    for piece in pieces:
        outline = pcbnew.SHAPE_POLY_SET()
        outline.NewOutline()
        for x, y in list(piece.exterior.coords)[:-1]:
            outline.Append(FromMM(float(x)), FromMM(float(y)))
        shape = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_POLY)
        shape.SetPolyShape(outline)
        shape.SetLayer(pcbnew.F_SilkS)
        shape.SetWidth(0)
        shape.SetFilled(True)
        fp.Add(shape)
    for field, text in ((fp.Reference(), "G***"), (fp.Value(), NAME)):
        field.SetText(text)
        field.SetLayer(pcbnew.F_Fab)
        field.SetVisible(False)
        field.SetPosition(VECTOR2I(0, 0))
    return fp


def preview(pieces, width_mm, height_mm, path, px_per_mm=40):
    size = (int(width_mm * px_per_mm) + 40, int(height_mm * px_per_mm) + 40)
    image = Image.new("RGB", size, (20, 90, 50))
    draw = ImageDraw.Draw(image)
    for piece in pieces:
        pts = [((x + width_mm / 2) * px_per_mm + 20, (y + height_mm / 2) * px_per_mm + 20) for x, y in piece.exterior.coords]
        draw.polygon(pts, fill=(245, 245, 240))
    image.save(path)


def main():
    seed_ids(__file__)
    avatar, lib_dir, preview_path = sys.argv[1:4]
    width_mm = float(sys.argv[sys.argv.index("--width-mm") + 1]) if "--width-mm" in sys.argv else 9.0
    style = sys.argv[sys.argv.index("--style") + 1] if "--style" in sys.argv else "filled"

    rgb = np.asarray(Image.open(avatar).convert("RGB"))
    shape = trace(smooth(ink_mask(rgb, style)))
    x1, y1, x2, y2 = shape.bounds
    scale = width_mm / (x2 - x1)
    height_mm = (y2 - y1) * scale
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    shape = affinity.scale(affinity.translate(shape, -cx, -cy), scale, scale, origin=(0, 0))
    pieces = [piece.simplify(0.01) for part in clean(shape) for piece in without_holes(part)]
    pieces = [piece for piece in pieces if not piece.is_empty and piece.geom_type == "Polygon"]

    os.makedirs(lib_dir, exist_ok=True)
    io = pcbnew.PCB_IO_MGR.FindPlugin(pcbnew.PCB_IO_MGR.KICAD_SEXP)
    io.FootprintSave(lib_dir, footprint(pieces, width_mm, height_mm))
    preview(pieces, width_mm, height_mm, preview_path)
    corners = sum(len(piece.exterior.coords) for piece in pieces)
    outline_px = width_mm / (x2 - x1) * UPSCALE
    print(f"{NAME}: {width_mm:.2f} x {height_mm:.2f} mm, {len(pieces)} polygons, {corners} corners, one source pixel = {outline_px:.3f} mm")


if __name__ == "__main__":
    main()
