"""Print the pins of symbols in a KiCad symbol library.

Usage: sym_pins.py symbols_dir Library:Symbol ...
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import find, find_all, parse


def load_symbol(symbols_dir, lib, name):
    with open(os.path.join(symbols_dir, lib + ".kicad_sym")) as fh:
        text = fh.read()
    start = text.find(f'\n\t(symbol "{name}"\n')
    if start < 0:
        raise SystemExit(f"{lib}:{name} not found")
    end = text.find("\n\t)\n", start)
    return parse(text[start + 1 : end + 3])


def pins(symbol):
    out = []
    for unit in find_all(symbol, "symbol"):
        for pin in find_all(unit, "pin"):
            at = find(pin, "at")
            hide = find(pin, "hide")
            out.append(
                {
                    "number": str(find(pin, "number")[1]),
                    "name": str(find(pin, "name")[1]),
                    "type": pin[1],
                    "at": (float(at[1]), float(at[2])),
                    "angle": int(float(at[3])) if len(at) > 3 else 0,
                    "length": float(find(pin, "length")[1]),
                    "hidden": hide is not None and hide[1] == "yes",
                    "unit": unit[1],
                }
            )
    return out


def main():
    symbols_dir = sys.argv[1]
    for spec in sys.argv[2:]:
        lib, name = spec.split(":")
        symbol = load_symbol(symbols_dir, lib, name)
        print(f"{spec}: extends {find(symbol, 'extends')}")
        for p in sorted(pins(symbol), key=lambda p: (len(p["number"]), p["number"])):
            flag = " hidden" if p["hidden"] else ""
            print(f"  {p['number']:>4} {p['name']:<22} {p['type']:<14} at {p['at'][0]:7.2f},{p['at'][1]:7.2f} angle {p['angle']:3d} len {p['length']}{flag}")


if __name__ == "__main__":
    main()
