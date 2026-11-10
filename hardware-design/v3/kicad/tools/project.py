"""Names and tool locations shared by the build scripts."""
import os

# KiCad project name. Its own symbol and footprint libraries carry the same name.
PROJECT = "lora-sensor"

# The scripts need the KiCad whose Python bindings they import. Set these if yours is elsewhere.
KICAD_CLI = os.environ.get("KICAD_CLI", "/usr/bin/kicad-cli")
KICAD_FOOTPRINTS = os.environ.get("KICAD_FOOTPRINTS", "/usr/share/kicad/footprints")
KICAD_SYMBOLS = os.environ.get("KICAD_SYMBOLS", "/usr/share/kicad/symbols")
