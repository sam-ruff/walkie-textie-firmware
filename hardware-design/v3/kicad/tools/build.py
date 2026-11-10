"""Build the KiCad project and the fabrication files from design.py.

Usage: build.py [--upto place|copper|zones|board] [--fetch]

Run it with a Python that has KiCad's pcbnew module and the packages in
requirements.txt. The project folder and the fab folder beside this one are
rewritten from scratch. Each stage is a script in this directory and the build
stops at the first one that fails. The stages named verify and check_*
generate nothing: they are the gates. --fetch lets the last of them download
JLCPCB's library entry for a part that is new to the BOM.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design
from project import KICAD_FOOTPRINTS, KICAD_SYMBOLS, PROJECT

ROOT = os.path.dirname(HERE)
PROJECT_DIR = os.path.join(ROOT, PROJECT)
FAB_DIR = os.path.join(ROOT, "fab")
MODEL = os.path.join(HERE, "data", "v3_model.json")
AVATAR = os.path.join(HERE, "assets", "goblin.png")
# JLCPCB's library entry for each part in the BOM, fetched once and kept so the check is repeatable.
JLC_LIBRARY = os.path.join(HERE, "data", "jlc")
# The firmware this board has to run: the repo's own src directory, four levels up from here.
FIRMWARE = os.path.normpath(os.path.join(ROOT, "..", "..", "..", "src"))
# Footprints drawn by hand for this board; the scripts make the rest.
HAND_DRAWN = os.path.join(HERE, "footprints")

# A rule KiCad's stock checks do not have: it looks at a via and a pad of the same net too.
DESIGN_RULES = f"""(version 1)

# A via's hole stays clear of every pad, same net or not, so solder is not drawn
# down the hole. The ESP32 module's ground paddle is the exception: its vias are wanted.
(rule "via hole clear of pads"
	(condition "A.Type == 'Via' && B.Type == 'Pad' && !(B.memberOfFootprint('{design.VIA_IN_PAD_OK[0]}') && B.Pad_Number == '{design.VIA_IN_PAD_OK[1]}')")
	(constraint physical_hole_clearance (min {design.VIA_TO_PAD}mm)))

# The plug's legs stand in plated slots that pass through both planes with no land of their own there.
# JLCPCB asks for 0.3 mm between a plated hole and inner-layer copper.
(rule "plug slots clear of the planes"
	(condition "A.Type == 'Pad' && A.Pad_Type == 'Through-hole' && A.memberOfFootprint('{design.PLUG_REF}')")
	(constraint hole_clearance (min {design.SLOT_TO_PLANE}mm)))
"""
LIB_TABLE = f"""(fp_lib_table
  (version 7)
  (lib (name "{design.LIB_V3}")(type "KiCad")(uri "${{KIPRJMOD}}/{design.LIB_V3}.pretty")(options "")(descr "Land patterns as delivered in the PCB_V3 drop"))
  (lib (name "{design.LIB_NEW}")(type "KiCad")(uri "${{KIPRJMOD}}/{design.LIB_NEW}.pretty")(options "")(descr "Footprints drawn for the corrected board"))
)
"""
GENERATED = [f"{PROJECT}.kicad_pcb", f"{PROJECT}.kicad_sch", f"{PROJECT}.kicad_pro", f"{PROJECT}.kicad_prl",
             f"{PROJECT}.kicad_sym", f"{PROJECT}.kicad_dru", "fp-lib-table", "sym-lib-table"]
STAGES = ["place", "copper", "zones", "board", "fab"]


def run(script, *args):
    # A fixed hash seed makes set order, and so the stitcher's choices, the same every run.
    env = {**os.environ, "PYTHONHASHSEED": "0"}
    res = subprocess.run([sys.executable, "-P", "-s", os.path.join(HERE, script), *args], capture_output=True, text=True, env=env)
    noise = ("Debug:", "Gtk", "wxWidgets")
    print("\n".join(line for line in (res.stdout + res.stderr).splitlines() if not any(word in line for word in noise)))
    if res.returncode:
        raise SystemExit(f"{script} failed")


def start_clean(v3_lib, new_lib):
    os.makedirs(PROJECT_DIR, exist_ok=True)
    for name in GENERATED:
        path = os.path.join(PROJECT_DIR, name)
        if os.path.exists(path):
            os.remove(path)
    for lib in (v3_lib, new_lib):
        shutil.rmtree(lib, ignore_errors=True)
    os.makedirs(new_lib)
    for name in sorted(os.listdir(HAND_DRAWN)):
        shutil.copyfile(os.path.join(HAND_DRAWN, name), os.path.join(new_lib, name))
    with open(os.path.join(PROJECT_DIR, "fp-lib-table"), "w") as fh:
        fh.write(LIB_TABLE)
    with open(os.path.join(PROJECT_DIR, f"{PROJECT}.kicad_dru"), "w") as fh:
        fh.write(DESIGN_RULES)


def main():
    upto = sys.argv[sys.argv.index("--upto") + 1] if "--upto" in sys.argv else STAGES[-1]
    if upto not in STAGES:
        raise SystemExit(f"--upto takes one of: {' '.join(STAGES)}")
    last = STAGES.index(upto)
    v3_lib = os.path.join(PROJECT_DIR, f"{design.LIB_V3}.pretty")
    new_lib = os.path.join(PROJECT_DIR, f"{design.LIB_NEW}.pretty")
    board = os.path.join(PROJECT_DIR, f"{PROJECT}.kicad_pcb")
    schematic = os.path.join(PROJECT_DIR, f"{PROJECT}.kicad_sch")

    start_clean(v3_lib, new_lib)
    run("make_lib.py", MODEL, v3_lib)
    run("make_footprints.py", new_lib, KICAD_FOOTPRINTS)
    with tempfile.TemporaryDirectory() as tmp:
        run("logo_trace.py", AVATAR, new_lib, os.path.join(tmp, "logo.png"),
            "--width-mm", str(design.LOGO["width"]), "--style", design.LOGO["style"])
    run("check_firmware.py", MODEL, FIRMWARE, KICAD_SYMBOLS)
    run("check_rf.py", MODEL, HAND_DRAWN, JLC_LIBRARY, FIRMWARE)
    run("check_values.py", MODEL)
    run("make_schematic.py", MODEL, PROJECT_DIR, KICAD_SYMBOLS)
    run("build_board.py", MODEL, board, v3_lib, new_lib, KICAD_FOOTPRINTS)
    run("set_stackup.py", board)
    # the board step starts the project file, without which KiCad does not see the project's own libraries
    run("verify.py", PROJECT_DIR, "--schematic-only")
    run("sync_nets.py", board, schematic)
    if last >= STAGES.index("copper"):
        run("add_copper.py", board)
        run("check_routes.py", board)
    if last >= STAGES.index("zones"):
        run("add_zones.py", board)
    if last >= STAGES.index("board"):
        run("stitch_edges.py", board)
        run("add_zones.py", board)
        run("tidy_ground.py", board)
        run("silk.py", board)
        run("add_zones.py", board)
        run("verify.py", PROJECT_DIR)
        run("check_emc.py", board, MODEL)
        run("check_connectors.py", board, KICAD_FOOTPRINTS)
    if last >= STAGES.index("fab"):
        fetch = ["--fetch"] if "--fetch" in sys.argv else []
        run("fab_outputs.py", PROJECT_DIR, FAB_DIR, JLC_LIBRARY, MODEL, *fetch)
        run("check_fab.py", FAB_DIR, MODEL)
        run("check_jlc.py", FAB_DIR, board, JLC_LIBRARY, MODEL, *fetch)


if __name__ == "__main__":
    main()
