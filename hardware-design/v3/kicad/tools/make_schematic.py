"""Write the schematic of the corrected board from the same data the board is built from.

Usage: make_schematic.py model.json project_dir kicad_symbols_dir

Connectivity is a global label on every pin: two pins are joined when their
labels carry the same net name, so no wires are drawn. Pins the design leaves
open get a no-connect marker. Symbols come from KiCad's own library where its
pin numbers match the footprint, and are drawn here as plain boxes otherwise;
those go into the project's symbol library as well.
"""
import copy
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import parts as parts_module
from project import PROJECT
from sexpr import Q, dump, find, find_all
from sym_pins import load_symbol, pins

OWN_LIB = PROJECT
GENERATOR = "lora_sensor_build"
NAMESPACE = uuid.UUID("5d0b6c9e-3d0a-4a53-9a55-6f0d5c1e7a11")
GRID = 2.54
ROW_PITCH = 4 * GRID
PIN_LENGTH = 3.81          # long enough for a three-character pin number such as A10

# Reference prefix -> (library, symbol, rotation). Two-pin parts lie flat, pin 1 on the left.
BY_PREFIX = {
    "R": ("Device", "R", 90),
    "C": ("Device", "C", 90),
    "L": ("Device", "L", 90),
    "SW": ("Switch", "SW_Push", 0),
    "TP": ("Connector", "TestPoint", 90),
    "LED": ("Device", "LED", 0),
}
BY_REF = {
    "L3": ("Device", "FerriteBead", 90),
    "D1": ("Device", "D_TVS", 0),
    "D2": ("Device", "D_TVS", 0),
    "D3": ("Device", "D_Zener", 0),
    "D4": ("Device", "D_Schottky", 0),
    "D5": ("Device", "D", 0),
    "Q1": ("Transistor_FET", "Q_PMOS_GSD", 0),
    "Q2": ("Transistor_BJT", "Q_NPN_BEC", 0),
    "U1": ("RF_Module", "ESP32-S3-WROOM-1", 0),
    "U4": ("Power_Management", "TPS2116DRL", 0),
    "U10": ("Timer", "TPL5111", 0),
    "U12": ("Power_Protection", "USBLC6-2P6", 0),
    "J3": ("Connector", "Conn_Coaxial", 0),
    "ANT1": ("Device", "Antenna_Chip", 0),
    "U5": (OWN_LIB, "TPS631000", 0),
    "U11": (OWN_LIB, "Wio-SX1262", 0),
    "U13": (OWN_LIB, "TLV803S", 0),
    "U14": (OWN_LIB, "TPS259531", 0),
    "J1": (OWN_LIB, "USB_C_Plug_24P", 0),
    "J2": (OWN_LIB, "I2C_Sensor_JST_PH4", 0),
    "CN1": (OWN_LIB, "Battery_JST_PH2", 0),
    "TL1": (OWN_LIB, "Printed_Line", 0),
}

# Symbols drawn here: pins as (number, name, electrical type), top to bottom on each side.
BOXES = {
    "TPS631000": {
        "prefix": "U",
        "description": "TPS631000 buck-boost converter, SOT-583",
        "left": [("4", "VIN", "power_in"), ("5", "EN", "input"), ("6", "MODE", "input"), ("7", "GND", "power_in")],
        "right": [("3", "LX1", "passive"), ("2", "LX2", "passive"), ("1", "VOUT", "power_out"), ("8", "FB", "input")],
    },
    "Wio-SX1262": {
        "prefix": "U",
        "description": "Seeed Wio-SX1262 LoRa module, castellated, antenna on pad 9",
        "left": [
            ("8", "VCC", "power_in"), ("7", "GND", "power_in"), ("10", "GND", "power_in"), ("4", "SCK", "input"),
            ("3", "MOSI", "input"), ("2", "MISO", "output"), ("6", "NSS", "input"), ("5", "NRST", "input"),
        ],
        "right": [("9", "ANT", "passive"), ("1", "RF_SW", "input"), ("11", "BUSY", "output"), ("12", "DIO1", "output")],
    },
    "TLV803S": {
        "prefix": "U",
        "description": "TLV803S reset supervisor, 2.93 V, open-drain output, SOT-23",
        "left": [("3", "VDD", "power_in"), ("1", "GND", "power_in")],
        "right": [("2", "~{RESET}", "open_collector")],
    },
    "TPS259531": {
        "prefix": "U",
        "description": "TPS259531 protection switch: 20 V input, output held to 5.7 V, adjustable current limit and output slew rate, WSON-8",
        "left": [("3", "IN", "power_in"), ("4", "IN", "power_in"), ("2", "EN/UVLO", "input"), ("1", "dVdt", "passive")],
        "right": [("5", "OUT", "power_out"), ("6", "~{FLT}", "open_collector"), ("7", "ILM", "passive"),
                  ("8", "GND", "power_in"), ("9", "GND", "power_in")],
    },
    "USB_C_Plug_24P": {
        "prefix": "J",
        "description": "USB Type-C plug on one face of the board edge, 24 contacts, shell on two legs and two pads",
        "left": [
            ("A1", "GND", "passive"), ("A2", "TX1+", "passive"), ("A3", "TX1-", "passive"), ("A4", "VBUS", "passive"),
            ("A5", "CC", "passive"), ("A6", "D+", "passive"), ("A7", "D-", "passive"), ("A8", "SBU1", "passive"),
            ("A9", "VBUS", "passive"), ("A10", "RX2-", "passive"), ("A11", "RX2+", "passive"), ("A12", "GND", "passive"),
            ("25", "SHELL", "passive"), ("27", "SHELL", "passive"),
        ],
        "right": [
            ("B1", "GND", "passive"), ("B2", "TX2+", "passive"), ("B3", "TX2-", "passive"), ("B4", "VBUS", "passive"),
            ("B5", "VCONN", "passive"), ("B6", "B6", "passive"), ("B7", "B7", "passive"), ("B8", "SBU2", "passive"),
            ("B9", "VBUS", "passive"), ("B10", "RX1-", "passive"), ("B11", "RX1+", "passive"), ("B12", "GND", "passive"),
            ("26", "SHELL", "passive"), ("28", "SHELL", "passive"),
        ],
    },
    "I2C_Sensor_JST_PH4": {
        "prefix": "J",
        "description": "JST PH 4-way side-entry header for the I2C sensor cable",
        "left": [],
        "right": [("1", "SCL", "passive"), ("2", "SDA", "passive"), ("3", "3V3", "passive"), ("4", "GND", "passive"),
                  ("5", "MP", "passive"), ("6", "MP", "passive")],
    },
    "Battery_JST_PH2": {
        "prefix": "J",
        "description": "JST PH 2-way side-entry header for the battery",
        "left": [],
        "right": [("1", "BAT+", "passive"), ("2", "BAT-", "passive"), ("3", "MP", "passive"), ("4", "MP", "passive")],
    },
    "Printed_Line": {
        "prefix": "TL",
        "description": "A line printed in copper: part of the circuit, nothing to fit",
        "left": [("1", "LINE", "passive")],
        "right": [],
    },
}

# Nets that reach a supply pin only through passive parts need a flag to say they are driven.
POWER_FLAGS = ["GND", "VBUS_F", "BAT_AON"]

# The sheet: blocks of (title, origin, symbols at offsets, a column of two-pin parts, notes).
BLOCKS = [
    {
        "title": "USB-C plug and input protection",
        "at": (15, 25),
        "symbols": {"J1": (40, 62), "U14": (40, 122)},
        "rows": (100, 14, ["L3", "C7", "R38", "R39", "C37", "R40", "D3", "D1", "D2", "R1", "R2", "R4", "R10", "C25"]),
        "notes": ["J1 is a plug: only A5 carries CC, and B5 (VCONN) stays open.",
                  "U14 takes the ring of a hot plug on its input, which is rated",
                  "for 20 V, then raises VBUS at 1.3 V/ms and never lets it over",
                  "5.9 V. It passes USB power above 3.75 V and limits it to 1.37 A."],
    },
    {
        "title": "Battery input and power mux",
        "at": (160, 25),
        "symbols": {"CN1": (22, 24), "Q1": (72, 30), "U4": (45, 82)},
        "rows": (105, 14, ["R21", "C32", "C31", "R9", "C33", "C38", "C39", "TP1"]),
        "notes": ["Q1 blocks a reversed battery.", "U4 passes the higher of USB and the battery: its select and",
                  "mode pins are on ground. C38 and C39, with C1, feed the",
                  "converter while it changes over. R9 empties VBUS when USB goes."],
        "flags": (15, 128),
    },
    {
        "title": "Wake timer and DONE stage",
        "at": (305, 25),
        "symbols": {"U10": (42, 38), "Q2": (45, 95)},
        "rows": (105, 14, ["R20", "SW3", "C34", "R24", "R22", "R23", "TP2", "TP3"]),
        "notes": ["Power off: drive IO4 high, then low.", "DONE rises when Q2 lets go.",
                  "TP2 is on IO4, ahead of R22."],
    },
    {
        "title": "3.3 V buck-boost converter",
        "at": (450, 25),
        "symbols": {"U5": (40, 38)},
        "rows": (105, 14, ["C1", "L2", "C26", "R15", "R16", "R32", "D4", "D5", "R13", "R37"]),
        "notes": ["EN is high while the timer drives DRVN", "or while USB power is present.",
                  "R37 keeps it high on battery, for firmware that", "never signals DONE. The timed order leaves it out.",
                  "D5 is silicon: a Schottky leaks when warm."],
    },
    {
        "title": "ESP32-S3 module",
        "at": (15, 200),
        "symbols": {"U1": (45, 80), "U13": (45, 165)},
        "rows": (110, 14, ["C27", "C4", "C2", "C13", "C12", "R5", "C3", "SW2", "R36", "C35", "R6", "C5", "SW1", "R11", "R12", "LED1", "R7"]),
        "notes": ["IO35 to IO37 belong to the module's", "PSRAM and are never used.",
                  "U13 holds EN low while +3V3 is under 2.93 V.",
                  "R36 keeps its output under 5 mA as C3 discharges."],
    },
    {
        "title": "LoRa module",
        "at": (160, 200),
        "symbols": {"U11": (40, 45)},
        "rows": (105, 14, ["C9", "C28", "R25", "R26", "R27", "R28", "R29"]),
        "notes": ["U11 is Seeed's 113991436, the Wio-SX1262 without", "the antenna connector. It is sent to the assembler."],
    },
    {
        "title": "868 MHz feed and antenna",
        "at": (305, 200),
        "symbols": {"J3": (105, 30), "ANT1": (105, 75), "TL1": (105, 112)},
        "rows": (42, 14, ["R30", "R31", "L5", "L6", "L7"]),
        "notes": ["Production fits R30 only.", "The antenna-test order fits R31 and J3 instead.", "L5, L6 and L7 are tuned on the VNA.",
                  "TL1 is the antenna's printed tuning line."],
    },
    {
        "title": "I2C sensor connector",
        "at": (450, 200),
        "symbols": {"J2": (22, 28), "U12": (45, 85)},
        "rows": (105, 14, ["C29", "C30", "R18", "R19", "R33", "R34"]),
        "notes": ["R18 and R19 are footprints only: the", "sensor board carries the pull-ups.",
                  "R33 and R34 slow the edges on the cable."],
    },
]


def uid(*names):
    return Q(str(uuid.uuid5(NAMESPACE, "/".join(names))))


def snap(value):
    return round(round(value / GRID) * GRID, 4)


def effects(justify=None, size=1.27, bold=False):
    font = ["font", ["size", size, size]]
    if bold:
        font.append(["bold", "yes"])
    node = ["effects", font]
    if justify:
        node.append(["justify", *justify.split()])
    return node


def prop(name, value, at, angle=0, hide=False, fx=None):
    node = ["property", Q(name), Q(value), ["at", at[0], at[1], angle]]
    if hide:
        node.append(["hide", "yes"])
    node += [["show_name", "no"], ["do_not_autoplace", "no"], fx or effects()]
    return node


def box_symbol(name, spec):
    """A rectangle with pins on its left and right sides, 2.54 mm apart."""
    rows = max(len(spec["left"]), len(spec["right"]))
    chars = max((len(p[1]) for p in spec["left"]), default=0) + max((len(p[1]) for p in spec["right"]), default=0)
    half = max(2, round((chars * 1.2 + 6.0) / (2 * GRID))) * GRID
    top = (rows // 2) * GRID
    bottom = top - (rows - 1) * GRID
    body = ["symbol", Q(f"{name}_0_1"),
            ["rectangle", ["start", -half, top + GRID], ["end", half, bottom - GRID],
             ["stroke", ["width", 0.254], ["type", "default"]], ["fill", ["type", "background"]]]]
    unit = ["symbol", Q(f"{name}_1_1")]
    for side, x, angle in (("left", -half - PIN_LENGTH, 0), ("right", half + PIN_LENGTH, 180)):
        for row, (number, pin_name, kind) in enumerate(spec[side]):
            unit.append(["pin", kind, "line", ["at", x, top - row * GRID, angle], ["length", PIN_LENGTH],
                         ["name", Q(pin_name), effects()], ["number", Q(number), effects()]])
    return ["symbol", Q(name), ["pin_names", ["offset", 1.016]], ["exclude_from_sim", "no"], ["in_bom", "yes"],
            ["on_board", "yes"], ["in_pos_files", "yes"], ["duplicate_pin_numbers_are_jumpers", "no"],
            prop("Reference", spec["prefix"], (-half, top + 2 * GRID), fx=effects("left")),
            prop("Value", name, (-half, bottom - 2 * GRID), fx=effects("left")),
            prop("Footprint", "", (0, 0), hide=True),
            prop("Datasheet", "", (0, 0), hide=True),
            prop("Description", spec["description"], (0, 0), hide=True),
            body, unit, ["embedded_fonts", "no"]]


class Library:
    def __init__(self, symbols_dir):
        self.symbols_dir = symbols_dir
        self.trees = {}

    def get(self, lib, name):
        key = f"{lib}:{name}"
        if key not in self.trees:
            self.trees[key] = box_symbol(name, BOXES[name]) if lib == OWN_LIB else load_symbol(self.symbols_dir, lib, name)
        return self.trees[key]

    def embedded(self):
        """The symbols as the schematic stores them: named with their library."""
        out = ["lib_symbols"]
        for key in sorted(self.trees):
            tree = copy.deepcopy(self.trees[key])
            tree[1] = Q(key)
            out.append(tree)
        return out

    def own(self):
        out = ["kicad_symbol_lib", ["version", "20251024"], ["generator", Q(GENERATOR)], ["generator_version", Q("10.0")]]
        out += [self.trees[key] for key in sorted(self.trees) if key.startswith(OWN_LIB + ":")]
        return out


def symbol_for(ref):
    if ref in BY_REF:
        return BY_REF[ref]
    return BY_PREFIX[ref.rstrip("0123456789")]


def pin_point(at, angle, pin):
    lx, ly = pin["at"]
    dx, dy = (lx, -ly) if angle == 0 else (-ly, -lx)
    return (round(at[0] + dx, 4), round(at[1] + dy, 4))


def lib_field(tree, name):
    node = next(p for p in find_all(tree, "property") if p[1] == name)
    at = find(node, "at")
    return (float(at[1]), float(at[2])), find(node, "effects")


def ic_fields(tree, at):
    """Where an IC's reference and value go so they miss the labels on its top and bottom pins.

    Returns {field name: (position, justification)}: the reference above the
    top-left corner, the value below the body.
    """
    symbol_pins = pins(tree)
    inner = {0: lambda p: p["at"][0] + p["length"], 180: lambda p: p["at"][0] - p["length"],
             90: lambda p: p["at"][1] + p["length"], 270: lambda p: p["at"][1] - p["length"]}
    side_ys = [p["at"][1] for p in symbol_pins if p["angle"] in (0, 180)]
    left = min(inner[0](p) for p in symbol_pins if p["angle"] == 0)
    tops = [p for p in symbol_pins if p["angle"] == 270]
    bottoms = [p for p in symbol_pins if p["angle"] == 90]
    top = max(inner[270](p) for p in tops) if tops else max(side_ys) + GRID
    bottom = min(inner[90](p) for p in bottoms) if bottoms else min(side_ys) - GRID
    reference = (at[0] + left, at[1] - top - 1.9), "left"
    if tops:
        reference = (at[0] + min(p["at"][0] for p in tops) - 2.0, at[1] - top - 1.9), "right"
    value_x = max(p["at"][0] for p in bottoms) + 2.0 if bottoms else left
    return {"Reference": reference, "Value": ((at[0] + value_x, at[1] - bottom + 1.9), "left")}


def placed_symbol(ref, lib_id, tree, at, angle, fields, flags, row_part):
    """One symbol on the sheet. `fields` are (name, value, hidden); `flags` are in_bom, in_pos, dnp."""
    in_bom, in_pos, dnp = flags
    node = ["symbol", ["lib_id", Q(lib_id)], ["at", at[0], at[1], angle], ["unit", 1], ["body_style", 1],
            ["exclude_from_sim", "no"], ["in_bom", "yes" if in_bom else "no"], ["on_board", "yes"],
            ["in_pos_files", "yes" if in_pos else "no"], ["dnp", "yes" if dnp else "no"], ["uuid", uid(ref, "symbol")]]
    is_ic = ref.startswith("U") and not lib_id.startswith(OWN_LIB + ":")
    for name, value, hidden in fields:
        if name in ("Reference", "Value") and row_part:
            above = -4.8 if ref.startswith("SW") else -3.3       # a push-button's actuator sticks up
            where = (at[0], at[1] + (above if name == "Reference" else 3.3))
            node.append(prop(name, value, where, angle))
        elif name in ("Reference", "Value") and is_ic:
            where, justify = ic_fields(tree, at)[name]
            node.append(prop(name, value, (round(where[0], 4), round(where[1], 4)), 0, fx=effects(justify)))
        elif name in ("Reference", "Value"):
            (fx, fy), lib_fx = lib_field(tree, name)
            node.append(prop(name, value, (round(at[0] + fx, 4), round(at[1] - fy, 4)), 0, hide=hidden, fx=copy.deepcopy(lib_fx)))
        else:
            node.append(prop(name, value, at, 0, hide=hidden))
    for pin in pins(tree):
        node.append(["pin", Q(pin["number"]), ["uuid", uid(ref, "pin", pin["number"])]])
    node.append(["instances", ["project", Q(PROJECT), ["path", Q(f"/{ROOT_ID}"), ["reference", Q(ref)], ["unit", 1]]]])
    return node


def global_label(net, at, angle, owner):
    justify = "left" if angle in (0, 90) else "right"
    return ["global_label", Q(net), ["shape", "passive"], ["at", at[0], at[1], angle], effects(justify), ["uuid", uid(owner, "label")],
            ["property", Q("Intersheetrefs"), Q("${INTERSHEET_REFS}"), ["at", at[0], at[1], 0], ["hide", "yes"],
             ["show_name", "no"], ["do_not_autoplace", "no"], effects(justify)]]


def note(text, at, name, size=1.27, bold=False):
    return ["text", Q(text), ["exclude_from_sim", "no"], ["at", at[0], at[1], 0], effects("left bottom", size, bold), ["uuid", uid(name, "text")]]


ROOT_ID = str(uuid.uuid5(NAMESPACE, "root"))


def main():
    model_path, project_dir, symbols_dir = sys.argv[1:4]
    with open(model_path) as fh:
        all_parts = parts_module.resolve(json.load(fh))
    library = Library(symbols_dir)
    items = []
    labelled = set()
    placed = set()
    open_pins = 0

    def place(ref, at, row_part):
        nonlocal open_pins
        part = all_parts[ref]
        lib, name, angle = symbol_for(ref)
        tree = library.get(lib, name)
        symbol_pins = pins(tree)
        numbers = {p["number"] for p in symbol_pins}
        if numbers != set(part["nets"]):
            raise SystemExit(f"{ref}: symbol {lib}:{name} has pins {sorted(numbers ^ set(part['nets']))} that the footprint does not, or the reverse")
        at = (snap(at[0]), snap(at[1]))
        fields = [("Reference", ref, False), ("Value", part["value"], False), ("Footprint", part["fp_id"], True),
                  ("Datasheet", "", True), ("Description", "", True)]
        fields += [(name, value, True) for name, value in parts_module.assembly_fields(part)]
        flags = (not part["no_bom"], not part["no_bom"], part["dnp"])
        items.append(placed_symbol(ref, f"{lib}:{name}", tree, at, angle, fields, flags, row_part))
        for pin in symbol_pins:
            point = pin_point(at, angle, pin)
            net = part["nets"][pin["number"]]
            if not net:
                if ("nc", point) not in labelled:
                    labelled.add(("nc", point))
                    items.append(["no_connect", ["at", *point], ["uuid", uid(ref, "nc", pin["number"])]])
                    open_pins += 1
                continue
            if (net, point) in labelled:            # pins stacked on one point share a label
                continue
            labelled.add((net, point))
            items.append(global_label(net, point, (pin["angle"] + angle + 180) % 360, f"{ref}.{pin['number']}"))
        placed.add(ref)

    for block in BLOCKS:
        x0, y0 = block["at"]
        items.append(note(block["title"], (x0, y0), block["title"], 2.54, True))
        for ref, (dx, dy) in block["symbols"].items():
            place(ref, (x0 + dx, y0 + dy), False)
        notes = block.get("notes", [])
        col_x, first_y, refs = block["rows"]
        first_y = max(first_y, 5 + len(notes) * 2.4 + 8)          # the first row starts below the notes
        for row, ref in enumerate(refs):
            place(ref, (x0 + col_x, y0 + first_y + row * ROW_PITCH), True)
        for line, text in enumerate(notes):
            items.append(note(text, (x0, y0 + 5 + line * 2.4), f"{block['title']}/{line}"))
        if "flags" in block:
            fx, fy = block["flags"]
            flag = library.get("power", "PWR_FLAG")
            for index, net in enumerate(POWER_FLAGS):
                at = (snap(x0 + fx + index * 25.4), snap(y0 + fy))
                ref = f"#FLG{index + 1:02d}"
                fields = [("Reference", ref, True), ("Value", "PWR_FLAG", False), ("Footprint", "", True),
                          ("Datasheet", "", True), ("Description", "", True)]
                items.append(placed_symbol(ref, "power:PWR_FLAG", flag, at, 0, fields, (True, True, False), False))
                items.append(global_label(net, at, 270, ref))

    missing = set(all_parts) - placed
    if missing:
        raise SystemExit(f"parts with no place on the sheet: {sorted(missing)}")

    sheet = ["kicad_sch", ["version", "20260306"], ["generator", Q(GENERATOR)], ["generator_version", Q("10.0")],
             ["uuid", Q(ROOT_ID)], ["paper", Q("A2")],
             ["title_block", ["title", Q(design.TITLE)], ["date", Q(design.DATE)], ["rev", Q(design.REVISION)],
              ["comment", 1, Q("Rebuilt in KiCad from the PCB_V3 fabrication data with the review changes applied")],
              ["comment", 2, Q("Generated by tools/build.py from tools/design.py: change that and rebuild, do not edit by hand")]],
             library.embedded(), *items,
             ["sheet_instances", ["path", Q("/"), ["page", Q("1")]]], ["embedded_fonts", "no"]]
    with open(os.path.join(project_dir, f"{PROJECT}.kicad_sch"), "w") as fh:
        fh.write(dump(sheet) + "\n")
    with open(os.path.join(project_dir, f"{OWN_LIB}.kicad_sym"), "w") as fh:
        fh.write(dump(library.own()) + "\n")
    with open(os.path.join(project_dir, "sym-lib-table"), "w") as fh:
        fh.write('(sym_lib_table\n  (version 7)\n  (lib (name "' + OWN_LIB + '")(type "KiCad")(uri "${KIPRJMOD}/' + OWN_LIB
                 + '.kicad_sym")(options "")(descr "Symbols drawn for this board"))\n)\n')
    nets = {net for part in all_parts.values() for net in part["nets"].values() if net}
    print(f"schematic: {len(placed)} parts, {len(nets)} nets, {open_pins} pins marked not connected, {len(library.trees)} different symbols")


if __name__ == "__main__":
    main()
