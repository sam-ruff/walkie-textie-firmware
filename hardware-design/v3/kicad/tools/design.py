"""The corrected board, as data.

Board coordinates are millimetres from the lower-left corner, Y up, the same
frame as the PCB_V3 Gerbers. Rotations are KiCad footprint orientations in
degrees. Parts that are unchanged from the PCB_V3 drop are listed with
`kept()`: their footprint and position come from the import model and only
their nets are restated here, so the builder can check them against the copper
that was delivered.
"""
from project import PROJECT

# Printed on the board and the schematic, and written into the fabrication files as their date.
TITLE = "LoRa sensor node"
REVISION = "3.1"
DATE = "2026-11-10"

BOARD_W = 45.085
BOARD_H = 53.721          # the two areas beside the ESP32 antenna are gone (review M3)

OUTLINE = [(0.0, 0.0), (BOARD_W, 0.0), (BOARD_W, BOARD_H), (0.0, BOARD_H)]

# USB-C plug: HRO TYPE-C-31-G-07. It sits on the top face against the left edge, which stays straight,
# and its shell hangs 10.7 mm over that edge. Its drawing's "Recommended P.C.B. Layout" measures from the
# back face of the shell: the row of pads nearer it is centred 0.85 mm in and the other 2.40 mm, and the
# slots for the shell's two legs are 2.30 mm in and 8.50 mm apart. The footprint's origin is midway
# between the rows.
#
# The shell's back face stops against the board edge, and a 1.50 mm leg in a 1.80 mm slot has 0.15 mm
# of play. JLCPCB cuts an outline to within 0.2 mm, so an edge drawn at the face could stand 0.2 mm
# proud and keep the legs out of their slots. The edge is therefore drawn 0.10 mm back from the face.
PLUG_Y = 29.972
PLUG_SET_BACK = 0.10
PLUG_ROWS = {"B": 0.85, "A": 2.40}                                              # centre of each row of pads
PLUG_LEGS = {"in": 2.30, "apart": 8.50, "slot": (0.50, 1.80), "leg": 1.50}      # slot: across the leg, along it
OUTLINE_TOLERANCE = 0.2


def plug_x(inward):
    """Board x of a point the plug's drawing puts `inward` mm from the back face of its shell."""
    return round(inward - PLUG_SET_BACK, 4)


PLUG_AT = (plug_x(sum(PLUG_ROWS.values()) / 2), PLUG_Y)

# 868 MHz antenna: copper-free area on every layer, sized as in the Pulse W3000
# datasheet's 868 MHz reference (9.5 mm deep, 20 mm along the board edge).
ANT_CLEAR = (BOARD_W - 20.0, 0.0, BOARD_W, 9.5)          # x1, y1, x2, y2

LIB_V3 = "PCB_V3"          # land patterns as delivered
LIB_NEW = PROJECT          # footprints drawn for this revision
KICAD = "kicad"            # KiCad's own library; name is "Library:Footprint"

R0402 = (LIB_V3, "R0402")
C0402 = (LIB_V3, "C0402")
L0603 = (LIB_V3, "L0603")
SOT23 = (KICAD, "Package_TO_SOT_SMD:SOT-23")
C0805 = (KICAD, "Capacitor_SMD:C_0805_2012Metric")
C0603 = (KICAD, "Capacitor_SMD:C_0603_1608Metric")
TESTPAD = (KICAD, "TestPoint:TestPoint_Pad_D1.0mm")
# Solder mask opening beyond each pad of a part with 0.5 mm between its pins. The board's 0.051 mm leaves
# under the 0.1 mm of mask that JLCPCB keeps between two openings.
FINE_PITCH_MASK = 0.025

PARTS = {}


def kept(ref, was, nets, **over):
    """A part carried over from the drop. `was` is its designator there."""
    PARTS[ref] = {"ref": ref, "was": was, "nets": nets, **over}


def part(ref, value, footprint, at, rot, nets, **extra):
    PARTS[ref] = {"ref": ref, "was": None, "value": value, "footprint": footprint, "at": at, "rot": rot, "nets": nets, **extra}


# ---------------------------------------------------------------- ESP32 and its support parts
ESP = {str(n): "" for n in range(1, 42)}
ESP.update(
    {
        "1": "GND", "40": "GND", "41": "GND", "2": "+3V3", "3": "EN",
        "4": "IO4_DONE",                 # to the DONE transistor, not straight to the timer (B5)
        "7": "SCK", "12": "MISO", "17": "MOSI", "34": "NSS", "35": "RST", "33": "BUSY", "32": "DIO1",
        "31": "RF_SW",
        "13": "USB_DN", "14": "USB_DP",
        "16": "IO46", "26": "IO45", "25": "USER_LED", "27": "BOOT",
        "38": "SDA_MCU", "39": "SCL_MCU",   # through R33 and R34 to the connector's SDA and SCL
        # pad 30 (IO37) is left open: it belongs to the module's PSRAM (B2)
    }
)
kept("U1", "U1", ESP)
kept("C4", "C4", {"1": "GND", "2": "+3V3"})
# One value, one part: the drop's 1 uF, 10k, 1k and 5.1k are each on the part number the rest of the
# board uses for that value, from JLCPCB's basic range.
ONE_UF = {"lcsc": "C52923", "mpn": "CL05A105KA5NQNC", "manufacturer": "SAMSUNG"}
TEN_K = {"lcsc": "C25744", "mpn": "0402WGF1002TCE", "manufacturer": "UNI-ROYAL"}
ONE_K = {"lcsc": "C11702", "mpn": "0402WGF1001TCE", "manufacturer": "UNI-ROYAL"}
kept("C2", "U2", {"1": "GND", "2": "+3V3"}, **ONE_UF)
# Every 100 nF on the board is this one 50 V part from JLCPCB's basic range.
kept("C13", "C13", {"1": "GND", "2": "+3V3"}, lcsc="C307331", mpn="CL05B104KB54PNC", manufacturer="SAMSUNG")
kept("C12", "C12", {"1": "GND", "2": "+3V3"}, lcsc="C307331", mpn="CL05B104KB54PNC", manufacturer="SAMSUNG")
part("C27", "22uF", C0805, (6.6, 51.7), 90, {"1": "GND", "2": "+3V3"}, lcsc="C45783", mpn="CL21A226MAQNNNE", manufacturer="SAMSUNG")
kept("R5", "R5", {"1": "+3V3", "2": "EN"}, **TEN_K)
kept("C3", "C3", {"1": "GND", "2": "EN"}, value="1uF", **ONE_UF)
kept("SW2", "SW2", {"1": "EN", "2": "GND"})
# Holds EN low while the 3.3 V rail is under 2.93 V and for 200 ms after. The rail is switched by design
# and can dip without reaching zero; Espressif's guidelines ask for a supervisor then, as R5 and C3
# alone do not reset the chip.
part("U13", "TLV803S", SOT23, (9.8, 47.9), 180, {"1": "GND", "2": "U13_RST", "3": "+3V3"},
     lcsc="C132016", mpn="TLV803SDBZR", manufacturer="Texas Instruments")
# U13's output is rated for 5 mA and has C3's 1 uF to discharge at every reset: R36 keeps it under that.
part("R36", "1k", R0402, (12.2, 49.483), 90, {"1": "U13_RST", "2": "EN"}, **ONE_K)
# Its datasheet asks for 100 nF at the supply pin, to keep the threshold steady.
part("C35", "100nF", C0402, (7.3, 46.984), 270, {"1": "GND", "2": "+3V3"}, lcsc="C307331", mpn="CL05B104KB54PNC", manufacturer="SAMSUNG")
kept("R6", "R6", {"1": "+3V3", "2": "BOOT"}, **TEN_K)
kept("C5", "C5", {"1": "GND", "2": "BOOT"}, dnp=True)
kept("SW1", "SW1", {"1": "BOOT", "2": "GND"})
kept("R11", "R11", {"1": "GND", "2": "IO46"}, **TEN_K)
kept("R12", "R12", {"1": "GND", "2": "IO45"}, **TEN_K)
kept("LED1", "LED1", {"1": "USER_LED", "2": "LED_A"})
kept("R7", "R7", {"1": "LED_A", "2": "+3V3"}, **ONE_K)

# ---------------------------------------------------------------- USB-C plug
PLUG = {f"{row}{n}": "" for row in "AB" for n in range(1, 13)}
PLUG.update(
    {
        "A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND",
        "A4": "VBUS_IN", "A9": "VBUS_IN", "B4": "VBUS_IN", "B9": "VBUS_IN",
        "A5": "CC1",                      # a plug's only CC contact; B5 is VCONN and stays open (B1)
        "A6": "D+", "A7": "D-",           # a plug carries the data pair on A6 and A7 only
        "25": "CHS", "26": "CHS", "27": "CHS", "28": "CHS",
    }
)
# JLCPCB places this plug with a fixture. It takes the place of the drop's plug, which clamped the board
# edge between two rows of tails and could only be soldered by hand.
part("J1", "TYPE-C-31-G-07", (LIB_NEW, "USB-C_Plug_HRO_TYPE-C-31-G-07"), PLUG_AT, 270, PLUG,
     lcsc="C530607", mpn="TYPE-C-31-G-07", manufacturer="Korean Hroparts Elec")
kept("R4", "R4", {"1": "GND", "2": "CC1"}, lcsc="C25905", mpn="0402WGF5101TCE", manufacturer="UNI-ROYAL")
kept("D1", "D1", {"1": "D+", "2": "GND"})
kept("D2", "D2", {"1": "D-", "2": "GND"})
kept("D3", "D3", {"1": "VBUS_IN", "2": "GND"})
kept("R1", "R1", {"1": "D-", "2": "USB_DN"})
kept("R2", "R2", {"1": "D+", "2": "USB_DP"})
kept("R10", "R10", {"1": "CHS", "2": "GND"}, at=(0.76, 23.96))
# 100 nF holds the shell under this part's 50 V in a 15 kV discharge; the drop's 1 nF would reach 520 V at 4 kV.
kept("C25", "C25", {"1": "CHS", "2": "GND"}, at=(2.03, 23.96), value="100nF", lcsc="C307331", mpn="CL05B104KB54PNC", manufacturer="SAMSUNG")
part("L3", "120R 3A", (KICAD, "Inductor_SMD:L_0603_1608Metric"), (5.84, 32.51), 90, {"1": "VBUS_IN", "2": "VBUS_F"},
     lcsc="C85831", mpn="BLM18KG121TN1D", manufacturer="Murata")

# ---------------------------------------------------------------- USB input protection
# Plugged into a supply that is already on, the lead's inductance rings with whatever capacitance sits on
# the input, and the mux, the converter and the timer allow 6 V on a supply that may be 5.5 V. U14 is rated
# for 20 V and takes the ring on its input, where only C7 is. It then raises its output at the rate C37
# sets, so nothing behind it sees a step, and it limits the current to what R40 sets.
#
# The TPS259531 is the version that also holds its output to 5.7 V at the most while its input is higher.
# That covers a plug that loses contact and makes it again while U14 is on, when the ring would otherwise
# pass straight through. The TPS259571 (C471038) has the same pads and no clamp.
part("U14", "TPS259531", (KICAD, "Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm"), (7.8, 36.0), 0,
     {"1": "DVDT", "2": "UVLO", "3": "VBUS_F", "4": "VBUS_F", "5": "VBUS", "6": "", "7": "ILM", "8": "GND", "9": "GND"},
     lcsc="C2155674", mpn="TPS259531DSGR", manufacturer="Texas Instruments", mask_margin=FINE_PITCH_MASK)
kept("C7", "C7", {"1": "GND", "2": "VBUS_F"}, at=(5.42, 34.85), rot=0, lcsc="C307331", mpn="CL05B104KB54PNC", manufacturer="SAMSUNG")
# U14 passes USB power once its input is over 3.75 V and stops under 3.44 V. The divider also keeps the
# ring off its enable pin, which allows 6 V.
part("R38", "100k", R0402, (5.4, 36.25), 0, {"1": "VBUS_F", "2": "UVLO"}, lcsc="C25741", mpn="0402WGF1003TCE", manufacturer="UNI-ROYAL")
part("R39", "47k", R0402, (5.837, 37.55), 90, {"1": "UVLO", "2": "GND"}, lcsc="C25792", mpn="0402WGF4702TCE", manufacturer="UNI-ROYAL")
# 33 nF: the output rises 1.3 V a millisecond, which charges everything behind it at under 0.1 A,
# the most a USB port owes a device that has not yet asked for more.
part("C37", "33nF", C0402, (6.85, 38.1), 90, {"1": "DVDT", "2": "GND"}, lcsc="C106862", mpn="CC0402KRX7R9BB333", manufacturer="YAGEO")
# 1.5k: a limit of 1.37 A. The most the board takes from USB is at the moment the mux hands a flat
# battery's load over, with VBUS still at the battery's voltage: just under 1 A.
part("R40", "1.5k", R0402, (8.75, 38.15), 90, {"1": "ILM", "2": "GND"}, lcsc="C25867", mpn="0402WGF1501TCE", manufacturer="UNI-ROYAL")

# ---------------------------------------------------------------- battery input and power mux
kept("CN1", "CN1", {"1": "BAT_RAW", "2": "GND", "3": "", "4": ""})     # pin order as the brief (B4)
# The brief names Vishay's Si2367DS, which JLCPCB does not stock. The Si2333DS is the same maker's
# 12 V part with the same pinout, and it is specified at the gate drive two tired AA cells give:
# 59 milliohms at 1.8 V, with 100 nA gate leakage.
part("Q1", "Si2333DS", SOT23, (4.97, 12.3), 270, {"1": "Q1_G", "2": "BAT_AON", "3": "BAT_RAW"},
     lcsc="C727544", mpn="SI2333DS-T1-GE3", manufacturer="VISHAY")
part("R21", "1M", R0402, (7.62, 11.6), 0, {"1": "Q1_G", "2": "GND"}, lcsc="C26083", mpn="0402WGF1004TCE", manufacturer="UNI-ROYAL")
# The mux passes whichever of its two inputs is the higher: its mode pin (5) and its select pin (4) are
# both on ground, the last row of the truth table in its datasheet. The drop chose USB by a threshold on
# VBUS instead. Above the battery's voltage that threshold joins USB to a lower output, which pulls VBUS
# back under it, and the mux can switch back and forth. Below the battery's voltage it drags the output
# down to the threshold at every unplug, however good the cells are. Taking the higher input hands over
# where the two are equal, in both directions. An LM66200 (C3235556) fits these pads and does the same.
kept("U4", "U4", {"1": "GND", "2": "SYS_OUT", "3": "VBUS", "4": "GND", "5": "GND", "6": "BAT_AON", "7": "SYS_OUT", "8": "ST"},
     track_only=("4", "5"))
# 10k empties C31 once USB is gone, so that a charge left on VBUS cannot pass for a supply.
kept("R9", "R9", {"1": "GND", "2": "VBUS"}, at=(9.5, 16.0), rot=90, value="10k", track_only=("1",), **TEN_K)
part("C31", "1uF", C0402, (7.4, 15.9), 0, {"1": "GND", "2": "VBUS"}, **ONE_UF)
part("C32", "1uF", C0402, (6.2, 15.0), 180, {"1": "BAT_AON", "2": "GND"}, **ONE_UF)
part("C33", "1uF", C0402, (10.6, 13.4), 90, {"1": "GND", "2": "SYS_OUT"}, **ONE_UF)
part("TP1", "ST", TESTPAD, (9.56, 11.65), 0, {"1": "ST"}, no_bom=True)

# ---------------------------------------------------------------- timer and its DONE stage
kept("U10", "U10", {"1": "SYS_OUT", "2": "GND", "3": "DELAY", "4": "DONE", "5": "DRVN", "6": "SYS_OUT"}, at=(3.3, 18.9), rot=0)
kept("R20", "R20", {"1": "GND", "2": "DELAY"}, at=(5.75, 17.7), rot=180)
part("C34", "100nF", C0402, (2.35, 21.85), 270, {"1": "GND", "2": "SYS_OUT"}, lcsc="C307331", mpn="CL05B104KB54PNC", manufacturer="SAMSUNG")
part("SW3", "B3U-1000P", (LIB_V3, "KEY-SMD_B3U-1000PM"), (2.6, 15.6), 0, {"1": "SYS_OUT", "2": "DELAY"},
     lcsc="C231329", mpn="B3U-1000P", manufacturer="OMRON")
part("Q2", "MMBT3904", SOT23, (6.8, 20.1), 180, {"1": "Q2_B", "2": "GND", "3": "DONE"}, lcsc="C81464", mpn="MMBT3904LT1G", manufacturer="onsemi")
part("R22", "47k", R0402, (9.8, 19.15), 0, {"1": "Q2_B", "2": "IO4_DONE"}, lcsc="C25792", mpn="0402WGF4702TCE", manufacturer="UNI-ROYAL")
part("R23", "1M", R0402, (9.8, 18.0), 0, {"1": "Q2_B", "2": "GND"}, lcsc="C26083", mpn="0402WGF1004TCE", manufacturer="UNI-ROYAL")
part("R24", "100k", R0402, (4.25, 21.9), 90, {"1": "DONE", "2": "SYS_OUT"}, lcsc="C25741", mpn="0402WGF1003TCE", manufacturer="UNI-ROYAL")
# On IO4, ahead of R22, so that touching it to 3.3 V drives the base through 47k.
part("TP2", "IO4", TESTPAD, (10.0, 21.0), 0, {"1": "IO4_DONE"}, no_bom=True)
part("TP3", "DONE", TESTPAD, (6.2, 22.95), 0, {"1": "DONE"}, no_bom=True)

# ---------------------------------------------------------------- buck-boost converter, laid out as TI's example
kept("U5", "U5", {"1": "+3V3", "2": "LX2", "3": "LX1", "4": "SYS_OUT", "5": "PWR_EN", "6": "GND", "7": "GND", "8": "FB"},
     at=(16.2, 15.0), rot=180)                                           # MODE (6) to GND: power-save mode (B3)
part("L2", "1uH 4.3A", (KICAD, "Inductor_SMD:L_1008_2520Metric"), (16.2, 18.2), 0, {"1": "LX1", "2": "LX2"},
     lcsc="C882955", mpn="DFE252012P-1R0M=P2", manufacturer="Murata")
part("C1", "22uF", C0805, (13.9, 15.0), 90, {"1": "GND", "2": "SYS_OUT"}, lcsc="C45783", mpn="CL21A226MAQNNNE", manufacturer="SAMSUNG")
# The mux disconnects both supplies for some microseconds whenever it changes from one to the other, and
# what is on its output then feeds the converter alone. C38 and C39 treble what C1 holds for that.
part("C38", "22uF", C0805, (12.5, 17.7), 0, {"1": "GND", "2": "SYS_OUT"}, lcsc="C45783", mpn="CL21A226MAQNNNE", manufacturer="SAMSUNG")
part("C39", "22uF", C0805, (12.9, 20.65), 0, {"1": "GND", "2": "SYS_OUT"}, lcsc="C45783", mpn="CL21A226MAQNNNE", manufacturer="SAMSUNG")
part("C26", "47uF", C0805, (18.4, 15.0), 90, {"1": "GND", "2": "+3V3"}, lcsc="C16780", mpn="CL21A476MQYNNNE", manufacturer="SAMSUNG")
kept("R15", "R15", {"1": "FB", "2": "+3V3"}, at=(18.5, 12.8), rot=0)
kept("R16", "R16", {"1": "FB", "2": "GND"}, at=(16.95, 11.9), rot=270)
kept("R13", "R13", {"1": "PWR_EN", "2": "GND"}, at=(17.1, 10.3), rot=0)
# The drop's B5819W came from a maker JLCPCB holds a few hundred of. This is the same diode from its basic range.
# D4 has to be a Schottky: on two tired cells a silicon diode would leave EN under its 1.2 V turn-on.
B5819W = {"value": "B5819W", "lcsc": "C8598", "mpn": "B5819W SL", "manufacturer": "CJ"}
kept("D4", "U7", {"1": "PWR_EN", "2": "DRVN"}, at=(13.8, 10.45), rot=180, **B5819W)
# D5 is a silicon diode. A Schottky here leaks from PWR_EN into the USB input's capacitors when warm,
# and their charge then holds the converter on after the timer has let go.
kept("D5", "U9", {"1": "PWR_EN", "2": "VBUS"}, at=(13.8, 12.2), rot=180,
     value="1N4148W", lcsc="C81598", mpn="1N4148W", manufacturer="Semtech Electronics")
part("R32", "10k", R0402, (21.6, 14.6), 90, {"1": "GND", "2": "+3V3"}, lcsc="C25744", mpn="0402WGF1002TCE", manufacturer="UNI-ROYAL")
# Fitted, R37 holds the converter on whenever a battery is in. That is for firmware that never signals
# DONE, such as the radio firmware in this repo: without it the timer cuts the rail for 50 ms at the end
# of every period. Left out, the timer is in charge. ORDERS says which order fits it.
part("R37", "0R", R0402, (15.4, 8.0), 0, {"1": "SYS_OUT", "2": "PWR_EN"}, lcsc="C17168", mpn="0402WGF0000TCE", manufacturer="UNI-ROYAL")

# ---------------------------------------------------------------- LoRa module and its support parts
# JLCPCB does not stock this module: it places it from modules sent to it, under the number its library
# gives Seeed's part 113991436, the Wio-SX1262 without the antenna connector. That entry has no footprint
# of its own, so the placement check uses JLCPCB's entry for the module with the connector (C55348741,
# none in stock), which has the same pads.
part("U11", "Wio-SX1262-N", (LIB_NEW, "Seeed_Wio-SX1262"), (32.61, 21.0), 180,
     {"1": "RF_SW", "2": "LORA_MISO", "3": "LORA_MOSI", "4": "LORA_SCK", "5": "RST", "6": "LORA_NSS", "7": "GND", "8": "+3V3",
      "9": "RF_ANT", "10": "GND", "11": "BUSY", "12": "DIO1"},
     lcsc="C9900285183", mpn="113991436", manufacturer="Seeed Studio", supplied=True, footprint_as="C55348741")
part("C9", "10uF", C0603, (26.3, 28.75), 0, {"1": "GND", "2": "+3V3"}, lcsc="C19702", mpn="CL10A106KP8NNNC", manufacturer="SAMSUNG")
part("C28", "100nF", C0402, (28.83, 28.5), 0, {"1": "+3V3", "2": "GND"}, lcsc="C307331", mpn="CL05B104KB54PNC", manufacturer="SAMSUNG")
part("R25", "10k", R0402, (39.3, 28.0), 90, {"1": "RF_SW", "2": "+3V3"}, lcsc="C25744", mpn="0402WGF1002TCE", manufacturer="UNI-ROYAL")
part("R26", "22R", R0402, (35.81, 28.9), 90, {"1": "LORA_MISO", "2": "MISO"}, lcsc="C25092", mpn="0402WGF220JTCE", manufacturer="UNI-ROYAL")
part("R27", "22R", R0402, (34.54, 28.9), 90, {"1": "LORA_MOSI", "2": "MOSI"}, lcsc="C25092", mpn="0402WGF220JTCE", manufacturer="UNI-ROYAL")
part("R28", "22R", R0402, (33.27, 28.9), 90, {"1": "LORA_SCK", "2": "SCK"}, lcsc="C25092", mpn="0402WGF220JTCE", manufacturer="UNI-ROYAL")
part("R29", "22R", R0402, (30.73, 28.9), 90, {"1": "LORA_NSS", "2": "NSS"}, lcsc="C25092", mpn="0402WGF220JTCE", manufacturer="UNI-ROYAL")

# ---------------------------------------------------------------- 868 MHz feed: test structure, pi network, antenna
part("R30", "0R", R0402, (32.0, 13.1), 270, {"1": "RF_ANT", "2": "RF_FEED"}, lcsc="C17168", mpn="0402WGF0000TCE", manufacturer="UNI-ROYAL")
part("R31", "0R", R0402, (30.5, 12.66), 0, {"1": "RF_TEST", "2": "RF_FEED"}, lcsc="C17168", mpn="0402WGF0000TCE", manufacturer="UNI-ROYAL", dnp=True)
# JLCPCB's footprint for this connector calls the centre contact pad 2 and the two ground pads 1 and 3.
part("J3", "U.FL", (LIB_NEW, "U.FL_Hirose_U.FL-R-SMT-1_Vertical"), (26.9, 11.5), 180, {"1": "RF_TEST", "2": "GND"},
     lcsc="C88373", mpn="U.FL-R-SMT-1(10)", manufacturer="Hirose", dnp=True, jlc_pads={"1": ["2"], "2": ["1", "3"]})
kept("L5", "L5", {"1": "RF_FEED", "2": "GND"}, at=(34.1, 10.2), rot=0)
# L6 carries the antenna's whole current, so its loss comes straight off the radiated power. It is a
# wire-wound part with 0.26 ohms of resistance; the drop's multilayer 39 nH has 1 ohm, a Q of 12 at
# 100 MHz and a self-resonance that can be as low as 1.4 GHz. L5 only shunts the feed, and JLCPCB holds
# no wire-wound 6.8 nH in numbers, so it stays as the drop had it.
kept("L6", "L6", {"1": "ANT_FEED", "2": "RF_FEED"}, at=(32.0, 9.5), rot=90,
     value="39nH", lcsc="C86134", mpn="LQW18AN39NG00D", manufacturer="Murata")
part("L7", "DNP", L0603, (30.3, 9.5), 90, {"1": "ANT_FEED", "2": "GND"}, dnp=True)
part("ANT1", "W3000", (LIB_NEW, "Pulse_W3000"), (35.3, 1.3), 0, {"1": "ANT_FEED", "2": "ANT_TUNE"},
     lcsc="C515701", mpn="W3000", manufacturer="Pulse")
# Printed line on the antenna's far pad, shaped as in the Pulse 868 MHz reference layout.
# It is copper only, so it is a footprint with one pad and nothing to fit.
TUNING_LINE = [(38.9, 0.55), (43.385, 0.55), (43.385, 5.8), (34.985, 5.8), (34.985, 4.1), (42.185, 4.1), (42.185, 2.05), (38.9, 2.05)]
TUNING_ANCHOR = (39.05, 1.3)
part("TL1", "tuning line", (LIB_NEW, "W3000_Tuning_Line"), TUNING_ANCHOR, 0, {"1": "ANT_TUNE"}, no_bom=True)

# ---------------------------------------------------------------- sensor connector
kept("J2", "U3", {"1": "SCL", "2": "SDA", "3": "+3V3", "4": "GND", "5": "", "6": ""}, at=(40.01, 42.5), rot=270)
part("U12", "USBLC6-2P6", (KICAD, "Package_TO_SOT_SMD:SOT-666"), (33.6, 42.35), 270,
     {"1": "SDA", "6": "SDA", "3": "SCL", "4": "SCL", "2": "GND", "5": "+3V3"},
     lcsc="C15999", mpn="USBLC6-2P6", manufacturer="STMicroelectronics", mask_margin=FINE_PITCH_MASK)
part("C29", "100nF", C0402, (33.6, 45.3), 90, {"1": "GND", "2": "+3V3"}, lcsc="C307331", mpn="CL05B104KB54PNC", manufacturer="SAMSUNG")
part("C30", "1uF", C0402, (34.69, 44.95), 90, {"1": "+3V3", "2": "GND"}, lcsc="C52923", mpn="CL05A105KA5NQNC", manufacturer="SAMSUNG")
kept("R18", "R18", {"1": "+3V3", "2": "SDA_MCU"}, dnp=True)       # footprints only, as the brief asks
kept("R19", "R19", {"1": "+3V3", "2": "SCL_MCU"}, dnp=True)
# The sensor cable is the longest wire on the product. 100 ohms in each I2C line slows the edges it carries.
part("R33", "100R", R0402, (34.137, 47.5), 90, {"1": "SDA", "2": "SDA_MCU"}, lcsc="C25076", mpn="0402WGF1000TCE", manufacturer="UNI-ROYAL")
part("R34", "100R", R0402, (34.2, 51.25), 0, {"1": "SCL_MCU", "2": "SCL"}, lcsc="C25076", mpn="0402WGF1000TCE", manufacturer="UNI-ROYAL")

# Parts of the drop that are not on this revision.
REMOVED = {
    "R3": "second CC resistor, on the plug's VCONN contact (B1)",
    "R8": "pull-up that put VBUS on the status pin and IO37 (B2)",
    "L1": "replaced by ANT1 with the Pulse land pattern",
    "L2": "replaced by the 2.5 x 2.0 mm inductor",
    "L3": "replaced by a ferrite rated for the input current",
    "C1": "replaced by the 22 uF input capacitor",
    "C6": "the USB input's bulk capacitance, which now sits behind the protection switch",
    "C9": "replaced by the 10 uF module capacitor",
    "U6": "lower half of the divider that set the mux's threshold, which now takes the higher of its inputs",
    "U8": "replaced by a plug that sits on one face of the board, which JLCPCB can place",
    "U11": "replaced by the Wio-SX1262-N",
}

# What each order has assembled. The first is the default population: every part not marked dnp. The
# others differ from it by the parts named. All orders use the same Gerbers.
ORDERS = {
    "node": {"about": "always on: for firmware that never signals DONE, such as the radio firmware in this repo"},
    "timed": {"leave_out": ["R37"], "about": "the wake timer is in charge: for firmware that signals DONE"},
    "antenna-test": {"fit": ["J3", "R31"], "leave_out": ["R30"],
                     "about": "the antenna on its test connector with the radio cut off, for the VNA: never power it"},
    "bench-test": {"fit": ["J3", "R31"], "leave_out": ["L5", "L6"],
                   "about": "the radio on its test connector with the antenna cut off, for the conducted compliance tests"},
}
DEFAULT_ORDER = "node"

# Net names in the drop -> names used here, for checking kept parts against the delivered copper.
NET_WAS = {
    "+3V3": "3.3V_RAIL", "BAT_AON": "BAT+", "LX1": "U5_3", "LX2": "U5_2", "PWR_EN": "U5_5", "FB": "U5_8",
    "DELAY": "U10_3", "CC1": "R4_2", "USB_DN": "R1_2", "USB_DP": "R2_2", "IO46": "U1_16",
    "IO45": "U1_26", "LED_A": "LED1_2", "RF_SW": "RXE", "SDA_MCU": "SDA", "SCL_MCU": "SCL",
}

# Net classes: (clearance, track width) in mm. The RF clearance is the gap the
# top-layer ground keeps from the 50 ohm feed.
NET_CLASSES = {
    "Power": (0.15, 0.5, ["+3V3", "SYS_OUT", "VBUS", "VBUS_F", "VBUS_IN", "BAT_RAW", "BAT_AON", "LX1", "LX2"]),
    "RF": (0.22, 0.17, ["RF_ANT", "RF_FEED", "RF_TEST", "ANT_FEED", "ANT_TUNE"]),
}

# JLCPCB JLC04081H-3313 (4 layers, 0.8 mm finished), which the feed width assumes:
# (layer, type, thickness mm, material, relative permittivity).
STACKUP = [
    ("F.Cu", "copper", 0.035, None, None),
    ("dielectric 1", "prepreg", 0.0994, "3313", 4.1),
    ("In1.Cu", "copper", 0.0152, None, None),
    ("dielectric 2", "core", 0.45, "FR4", 4.6),
    ("In2.Cu", "copper", 0.0152, None, None),
    ("dielectric 3", "prepreg", 0.0994, "3313", 4.1),
    ("B.Cu", "copper", 0.035, None, None),
]
COPPER_FINISH = "HAL lead-free"

# ---------------------------------------------------------------- copper drawn by hand
# Every track and via that is not carried over from the drop is listed here; nothing is autorouted.
# Entries: ("track", net, layer, width, points), ("via", net, (x, y)) and ("poly", net, layer, points).
# check_routes.py holds the routing to these rules:
FEED_KEEP_OUT = (29.6, 9.5, 33.7, 14.3)      # around the 868 MHz feed and its match: only they and ground go here
TOP_CLEAR = [                                 # no top-layer track here: a line that has to pass crosses on the bottom
    ((15.5, 36.1, 29.45, 53.8), "under the ESP32 module, past where a pad's via goes"),
    ((2.65, 18.35, 4.6, 19.45), "between the timer's pin rows, where its ground pin needs the pour"),
]
UNDER_LORA_MODULE = 2.5                       # mm of top-layer track a line may have under the LoRa module, to reach its pad
T, V, POLY = "track", "via", "poly"
# The plug's two rows of pads, the middle of the gap between them, and its legs.
PB, PA, PM, PL = plug_x(PLUG_ROWS["B"]), plug_x(PLUG_ROWS["A"]), PLUG_AT[0], plug_x(PLUG_LEGS["in"])
COPPER = [
    # battery: connector pin 1 -> Q1 drain; Q1 source -> mux VIN2, with its 1 uF on the way
    (T, "BAT_RAW", "top", 0.5, [(4.969, 9.6), (4.97, 11.362)]),
    (T, "BAT_AON", "top", 0.3, [(4.02, 13.237), (4.02, 14.3), (7.0, 14.3), (7.3, 14.22), (7.869, 14.22)]),
    (T, "BAT_AON", "top", 0.3, [(6.624, 14.3), (6.624, 15.0)]),

    # USB-C plug. Each ground and VBUS contact has a twin in the other row at the same height, and a
    # short track joins each pair. The two VBUS pairs are joined in the gap between the rows.
    (T, "GND", "top", 0.25, [(PB, 27.222), (PA, 27.222), (3.3, 27.222), (4.572, 27.317)]),
    (T, "GND", "top", 0.25, [(3.3, 27.222), (3.7, 26.85)]),
    (V, "GND", (3.7, 26.85)),
    (T, "GND", "top", 0.25, [(PB, 32.722), (PA, 32.722), (3.3, 32.722), (3.7, 33.122), (4.2, 33.622), (4.572, 33.857)]),
    (V, "GND", (3.7, 33.122)),
    (T, "VBUS_IN", "top", 0.25, [(PB, 28.722), (PA, 28.722)]),
    (T, "VBUS_IN", "top", 0.2, [(PM, 28.722), (PM, 31.222)]),
    (T, "VBUS_IN", "top", 0.3, [(PB, 31.222), (PA, 31.222), (3.2, 31.222), (4.2, 32.222), (4.572, 32.437)]),
    (T, "VBUS_IN", "top", 0.4, [(4.572, 32.437), (4.916, 32.093), (5.84, 32.093)]),
    # the data pair and CC, each past its protection diode; beyond the diodes the pair runs as the drop had it
    (T, "D+", "top", 0.2, [(PA, 29.722), (3.3, 29.722), (4.205, 28.817), (4.572, 28.817), (9.639, 28.816), (10.033, 29.21),
                           (10.033, 35.56), (10.414, 35.941), (11.251, 35.941)]),
    (T, "D-", "top", 0.2, [(PA, 30.222), (3.6, 30.222), (4.089, 29.733), (4.568, 29.733), (5.093, 29.21), (9.271, 29.21),
                           (9.525, 29.464), (9.525, 35.687), (11.049, 37.211), (11.251, 37.211)]),
    (T, "CC1", "top", 0.2, [(PA, 29.222), (3.05, 29.222), (4.203, 28.069), (6.043, 28.069)]),
    # the shell: its two legs joined on the bottom layer, and the lower one to its resistor and capacitor
    (T, "CHS", "bot", 0.4, [(PL, 25.722), (PL, 34.222)]),
    (T, "CHS", "top", 0.3, [(PL, 25.722), (2.03, 25.3), (2.03, 24.384), (0.761, 24.389)]),

    # USB input protection: bead -> C7 and U14's input pins -> U14 -> VBUS
    (T, "VBUS_F", "top", 0.4, [(5.84, 33.297), (5.84, 35.25), (6.85, 35.25)]),
    (T, "VBUS_F", "top", 0.25, [(6.85, 35.25), (6.85, 35.75)]),                                  # both input pins
    (T, "VBUS_F", "top", 0.2, [(5.84, 35.25), (5.84, 35.55), (4.971, 35.55), (4.971, 36.25)]),   # R38
    (T, "UVLO", "top", 0.2, [(5.837, 36.25), (6.85, 36.25)]),
    (T, "UVLO", "top", 0.2, [(5.837, 36.25), (5.837, 37.121)]),                                  # R39
    (T, "DVDT", "top", 0.2, [(6.85, 36.75), (6.85, 37.676)]),
    # the limit resistor: out to the right of the ground pin above it, then back to the resistor
    (T, "ILM", "top", 0.2, [(8.75, 36.25), (9.35, 36.25), (9.35, 37.4), (9.03, 37.721), (8.75, 37.721)]),
    (T, "GND", "top", 0.25, [(8.75, 36.75), (7.8, 36.75), (7.8, 37.6)]),                         # ground pin and pad to a via
    (V, "GND", (7.8, 37.6)),
    (T, "GND", "top", 0.25, [(6.85, 38.516), (7.8, 38.55), (8.75, 38.587)]),                     # C37 and R40
    (T, "GND", "top", 0.25, [(7.8, 38.55), (7.8, 37.6)]),
    (T, "GND", "top", 0.25, [(4.996, 34.85), (4.2, 34.85)]),                                     # C7
    (V, "GND", (4.2, 34.85)),
    (T, "GND", "top", 0.25, [(5.837, 37.987), (5.837, 38.7)]),                                   # R39
    (V, "GND", (5.837, 38.7)),
    # U14's output to a via below it, then a run on the bottom layer to the mux
    (T, "VBUS", "top", 0.25, [(8.75, 35.25), (8.75, 34.6)]),
    (T, "VBUS", "top", 0.5, [(8.75, 34.6), (8.6, 34.45), (8.6, 33.9)]),
    (V, "VBUS", (8.6, 33.9)),
    (T, "VBUS", "bot", 0.5, [(8.6, 33.9), (8.128, 33.428), (8.128, 18.0), (8.51, 17.6), (8.51, 17.3)]),
    (V, "VBUS", (8.51, 17.3)),
    (T, "VBUS", "top", 0.5, [(8.51, 17.3), (8.51, 15.9)]),
    (T, "VBUS", "top", 0.3, [(7.816, 15.9), (8.51, 15.9)]),                         # C31
    # past R9 and round the outside of the mux to VIN1, which leaves the gap between its pin rows free
    (T, "VBUS", "top", 0.4, [(8.51, 16.437), (9.499, 16.437), (10.2, 16.437), (10.2, 14.75)]),
    (T, "VBUS", "top", 0.25, [(10.2, 14.75), (9.67, 14.22), (9.149, 14.22)]),
    # the mux's select and mode pins: joined across that gap, on to R9's ground pad, and to ground at
    # C31's pad and the via beside it
    (T, "GND", "top", 0.2, [(7.869, 14.72), (9.149, 14.72), (9.499, 15.1), (9.499, 15.571)]),
    (T, "GND", "top", 0.2, [(7.869, 14.72), (7.4, 14.72), (7.2, 14.92), (7.2, 15.5), (6.976, 15.9)]),
    (T, "GND", "top", 0.25, [(6.976, 15.9), (6.3, 15.9)]),
    (V, "GND", (6.3, 15.9)),

    # mux output to the converter input capacitor
    (T, "SYS_OUT", "top", 0.25, [(7.869, 13.72), (9.149, 13.72), (9.7, 13.72)]),
    (T, "SYS_OUT", "top", 0.4, [(9.7, 13.72), (10.6, 13.816)]),
    (T, "SYS_OUT", "top", 0.5, [(10.6, 13.816), (11.9, 13.816), (12.2, 14.1), (12.2, 15.5), (12.65, 15.95), (13.9, 15.95)]),
    (T, "GND", "top", 0.25, [(9.149, 13.22), (9.6, 13.1), (10.6, 12.976)]),
    (T, "GND", "top", 0.3, [(10.6, 12.976), (10.6, 12.2)]),
    (V, "GND", (10.6, 12.2)),
    # the two capacitors that hold the mux's output up while it changes supply, beside the converter's own
    (T, "SYS_OUT", "top", 0.5, [(13.45, 15.95), (13.45, 17.7), (13.45, 19.9), (13.85, 20.3), (13.85, 20.65)]),
    (T, "GND", "top", 0.4, [(11.55, 17.7), (11.55, 16.5)]),
    (V, "GND", (11.55, 16.5)),
    (T, "GND", "top", 0.4, [(11.95, 20.65), (11.95, 19.4)]),
    (V, "GND", (11.95, 19.4)),

    # converter, after TI's layout example: capacitors at the pins, inductor across LX1/LX2
    (POLY, "SYS_OUT", "top", [(14.4, 15.45), (15.593, 15.45), (15.593, 15.981), (14.4, 15.981)]),
    (POLY, "+3V3", "top", [(16.813, 15.45), (17.9, 15.45), (17.9, 15.981), (16.813, 15.981)]),
    (POLY, "LX1", "top", [(15.813, 15.35), (16.093, 15.35), (16.093, 16.35), (15.75, 16.9), (15.75, 17.5), (14.6, 17.5),
                          (14.6, 17.1), (15.3, 16.6), (15.813, 16.2)]),
    (POLY, "LX2", "top", [(16.313, 15.35), (16.593, 15.35), (16.593, 16.2), (17.1, 16.6), (17.8, 17.1), (17.8, 17.5),
                          (16.65, 17.5), (16.65, 16.9), (16.313, 16.35)]),
    (POLY, "+3V3", "top", [(18.6, 15.55), (22.0, 15.55), (22.0, 16.45), (18.6, 16.45)]),   # output to the 3.3 V plane
    (V, "+3V3", (19.9, 16.0)),
    (V, "+3V3", (20.75, 16.0)),
    (V, "+3V3", (21.6, 16.0)),
    (T, "+3V3", "top", 0.3, [(21.599, 15.037), (21.6, 15.7)]),                      # R32
    (POLY, "GND", "top", [(15.813, 13.3), (16.593, 13.3), (16.593, 14.701), (15.813, 14.701)]),   # MODE and GND pins
    (V, "GND", (16.2, 13.25)),
    (T, "GND", "top", 0.4, [(13.5, 13.75), (13.5, 13.1)]),
    (V, "GND", (13.5, 13.1)),
    (T, "GND", "top", 0.4, [(14.3, 13.75), (14.3, 13.1)]),
    (V, "GND", (14.3, 13.1)),
    (POLY, "GND", "top", [(18.4, 13.75), (21.869, 13.75), (21.869, 14.4), (18.4, 14.4)]),
    (V, "GND", (19.75, 14.08)),
    (V, "GND", (20.55, 14.08)),
    (T, "FB", "top", 0.2, [(16.953, 14.361), (16.953, 12.8), (18.071, 12.801)]),
    (T, "FB", "top", 0.2, [(16.953, 12.8), (16.951, 12.329)]),
    (T, "+3V3", "top", 0.25, [(18.937, 12.801), (19.95, 12.8)]),
    (V, "+3V3", (19.95, 12.8)),
    (T, "PWR_EN", "top", 0.2, [(15.453, 14.361), (15.453, 12.2), (15.431, 10.448), (16.671, 10.301)]),

    # timer block
    (T, "SYS_OUT", "top", 0.25, [(2.348, 17.701), (2.348, 20.1), (2.35, 21.43)]),        # VDD, EN and the 100 nF
    (T, "SYS_OUT", "top", 0.25, [(2.348, 17.4), (1.4, 16.9), (1.0, 16.3)]),               # SW3
    (T, "SYS_OUT", "top", 0.25, [(4.249, 22.337), (3.2, 22.337), (2.9, 21.6), (2.35, 21.43)]),   # R24
    (T, "DELAY", "top", 0.25, [(4.248, 17.701), (4.296, 16.2)]),
    (T, "DELAY", "top", 0.25, [(4.248, 17.701), (5.313, 17.699)]),
    (T, "DONE", "top", 0.25, [(4.248, 20.101), (5.862, 20.1)]),
    (T, "DONE", "top", 0.25, [(4.248, 20.101), (4.249, 21.471)]),
    (T, "Q2_B", "top", 0.2, [(7.737, 19.15), (9.371, 19.151), (9.371, 18.001)]),
    (T, "IO4_DONE", "top", 0.2, [(10.237, 19.151), (10.0, 21.0)]),

    # ESP32 supply: the capacitor row and module pin as in the drop, plus the 22 uF and vias to the plane
    (T, "+3V3", "top", 0.5, [(13.729, 51.186), (13.646, 51.2689), (8.382, 51.2689)]),
    (T, "+3V3", "top", 0.5, [(8.382, 51.2689), (7.6, 51.6), (7.2, 52.3), (6.6, 52.65)]),
    (T, "+3V3", "top", 0.3, [(9.015, 51.2689), (9.015, 50.55)]),
    (V, "+3V3", (9.015, 50.55)),
    (T, "+3V3", "top", 0.3, [(10.285, 51.2689), (10.285, 50.55)]),
    (V, "+3V3", (10.285, 50.55)),
    (T, "+3V3", "top", 0.3, [(11.555, 51.2689), (11.555, 50.55)]),
    (V, "+3V3", (11.555, 50.55)),
    (T, "GND", "top", 0.3, [(8.38, 52.114), (8.38, 52.95)]),
    (V, "GND", (8.38, 52.95)),
    (T, "GND", "top", 0.3, [(9.65, 52.114), (9.65, 52.95)]),
    (V, "GND", (9.65, 52.95)),
    (T, "GND", "top", 0.3, [(10.92, 52.114), (10.92, 52.95)]),
    (V, "GND", (10.92, 52.95)),
    (T, "GND", "top", 0.3, [(12.19, 52.114), (12.19, 52.95)]),
    (V, "GND", (12.19, 52.95)),
    (T, "GND", "top", 0.4, [(6.6, 50.75), (5.3, 50.75)]),
    (V, "GND", (5.3, 50.75)),

    # the other 3.3 V loads, each with a via to the plane beside its pad
    (T, "+3V3", "top", 0.25, [(5.289, 46.561), (6.25, 46.56)]),
    (V, "+3V3", (6.25, 46.56)),
    # reset supervisor: supply from that via past its capacitor, output to R36, whose other pad sits on the EN track
    (T, "+3V3", "top", 0.25, [(6.25, 46.56), (7.3, 46.56), (7.5225, 46.56), (8.8625, 47.9)]),
    (T, "U13_RST", "top", 0.22, [(10.7375, 48.85), (11.85, 48.85), (12.05, 49.05), (12.2, 49.05)]),
    (V, "GND", (34.8, 11.3)),       # beside the shunt inductor of the antenna match
    (T, "+3V3", "top", 0.25, [(5.289, 43.011), (6.25, 42.9)]),
    (V, "+3V3", (6.25, 42.9)),
    (T, "+3V3", "top", 0.25, [(44.097, 33.241), (44.1, 34.25)]),
    (V, "+3V3", (44.1, 34.25)),
    (T, "+3V3", "top", 0.25, [(32.889, 49.101), (33.3, 48.2)]),
    (V, "+3V3", (33.3, 48.2)),
    (T, "+3V3", "top", 0.25, [(32.891, 52.119), (33.85, 52.6)]),
    (V, "+3V3", (33.85, 52.6)),
    (T, "+3V3", "top", 0.25, [(39.299, 28.437), (39.3, 29.35)]),
    (V, "+3V3", (39.3, 29.35)),

    # The sensor connector's ESD parts sit beside the module's right-hand pads, so the radio control lines
    # leave through a via just inside the pad row and run on the bottom layer, as the drop did for BOOT.
    (T, "DIO1", "top", 0.2, [(31.229, 42.296), (29.85, 42.296)]),
    (V, "DIO1", (29.85, 42.296)),
    (T, "BUSY", "top", 0.2, [(31.229, 43.566), (29.85, 43.566)]),
    (V, "BUSY", (29.85, 43.566)),
    (T, "NSS", "top", 0.2, [(31.229, 44.836), (29.85, 44.836)]),
    (V, "NSS", (29.85, 44.836)),
    (T, "RST", "top", 0.2, [(31.229, 46.106), (29.85, 46.106)]),
    (V, "RST", (29.85, 46.106)),
    # SPI series resistors: a via above each MCU-side pad, so the lines can arrive on the bottom layer
    (T, "SCK", "top", 0.2, [(33.269, 29.337), (33.269, 30.4)]),
    (V, "SCK", (33.269, 30.4)),
    (T, "MOSI", "top", 0.2, [(34.539, 29.337), (34.539, 30.4)]),
    (V, "MOSI", (34.539, 30.4)),
    (T, "MISO", "top", 0.2, [(35.809, 29.337), (35.809, 30.4)]),
    (V, "MISO", (35.809, 30.4)),
    # ground for the two strapping pull-downs, which the new routes would otherwise cut off from the pour
    (T, "GND", "top", 0.25, [(16.76, 32.34), (16.76, 31.5)]),
    (V, "GND", (16.76, 31.5)),
    (T, "GND", "top", 0.25, [(29.46, 32.34), (29.46, 31.5)]),
    (V, "GND", (29.46, 31.5)),

    # LoRa module supply and ground
    (T, "+3V3", "top", 0.4, [(27.075, 28.75), (28.406, 28.5), (28.19, 27.3)]),
    (T, "+3V3", "top", 0.4, [(27.075, 28.75), (27.1, 29.85)]),
    (V, "+3V3", (27.1, 29.85)),
    (T, "+3V3", "top", 0.3, [(28.406, 28.5), (28.4, 29.6)]),
    (V, "+3V3", (28.4, 29.6)),
    (T, "GND", "top", 0.4, [(29.246, 28.5), (29.46, 27.3)]),
    (T, "GND", "top", 0.3, [(29.246, 28.5), (29.3, 29.6)]),
    (V, "GND", (29.3, 29.6)),
    (T, "GND", "top", 0.4, [(25.525, 28.75), (24.55, 28.75)]),
    (V, "GND", (24.55, 28.75)),
    (T, "GND", "top", 0.4, [(33.27, 14.6), (33.27, 13.85)]),
    (V, "GND", (33.27, 13.85)),

    # sensor connector: ESD part, its 100 nF, and the 1 uF at the connector's supply pin
    (T, "+3V3", "top", 0.25, [(33.6, 45.716), (33.4, 46.6)]),
    (V, "+3V3", (33.4, 46.6)),
    # I2C: module pad -> pull-up footprint -> series resistor -> ESD part -> connector. SCL has to cross SDA
    # once; it does so on the bottom layer between its resistor and the ESD part, so the connector-to-ESD run
    # stays on one layer.
    (T, "SDA_MCU", "top", 0.2, [(31.229, 49.916), (32.889, 49.967), (34.137, 49.967), (34.137, 47.933)]),
    (T, "SDA", "top", 0.2, [(34.137, 47.067), (34.137, 43.2), (34.137, 41.5), (35.6, 41.501)]),
    (T, "SCL_MCU", "top", 0.2, [(31.229, 51.186), (32.891, 51.253), (33.767, 51.25)]),
    (T, "SCL", "top", 0.2, [(34.633, 51.25), (35.45, 51.25)]),
    (V, "SCL", (35.45, 51.25)),
    (T, "SCL", "bot", 0.2, [(35.45, 51.25), (32.75, 48.55), (32.75, 47.3)]),
    (V, "SCL", (32.75, 47.3)),
    (T, "SCL", "top", 0.2, [(32.75, 47.3), (32.75, 43.6), (33.062, 43.288), (33.062, 41.5), (33.062, 39.9), (33.46, 39.5), (35.6, 39.501)]),
    (T, "GND", "top", 0.25, [(33.6, 43.275), (33.45, 44.05), (33.6, 44.876)]),
    (V, "GND", (33.45, 44.05)),
    (T, "+3V3", "top", 0.3, [(34.69, 44.526), (34.85, 43.5), (35.6, 43.5)]),
    (V, "+3V3", (34.85, 43.5)),
    (T, "GND", "top", 0.3, [(34.69, 45.366), (35.6, 45.5)]),
    (T, "+3V3", "top", 0.25, [(33.6, 41.425), (33.6, 41.1), (34.2, 40.5), (35.9, 40.5)]),
    (V, "+3V3", (35.9, 40.5)),

    # 868 MHz path: module -> 0 ohm link -> feed line over ground -> pi network at the ground edge -> antenna
    (T, "RF_ANT", "top", 0.3, [(32.0, 15.5), (32.001, 13.529)]),
    (T, "RF_FEED", "top", 0.17, [(32.001, 12.663), (32.0, 10.203)]),
    (T, "RF_FEED", "top", 0.4, [(32.0, 10.203), (33.403, 10.2)]),
    (T, "RF_FEED", "top", 0.3, [(30.937, 12.661), (32.001, 12.663)]),
    (T, "RF_TEST", "top", 0.3, [(30.071, 12.661), (29.3, 12.661), (28.7, 12.0), (28.425, 11.5)]),
    (T, "ANT_FEED", "top", 0.5, [(32.0, 8.803), (32.0, 1.3)]),
    (T, "ANT_FEED", "top", 0.5, [(30.3, 8.803), (32.0, 8.803)]),
    (V, "GND", (30.9, 11.4)),       # fence either side of the feed line
    (V, "GND", (33.1, 11.4)),

    # ---- signals. The bottom layer carries a line wherever it passes under a module or has to cross
    # another; nothing runs on the top layer under the LoRa module except the last millimetres to a pad.

    # SPI clock: out to the left of the ESP32, down its side on the bottom, then the corridor's southern lane
    (T, "SCK", "top", 0.2, [(13.729, 44.836), (12.6, 44.836)]),
    (V, "SCK", (12.6, 44.836)),
    (T, "SCK", "bot", 0.2, [(12.6, 44.836), (11.65, 43.886), (11.65, 43.0), (13.3, 41.35), (13.3, 33.4), (16.0, 30.7),
                            (32.969, 30.7), (33.269, 30.4)]),
    # MISO: a via just inside the pad row, beside the drop's ground vias, then the northern lane
    (T, "MISO", "top", 0.2, [(13.729, 38.486), (15.24, 38.486)]),
    (V, "MISO", (15.24, 38.486)),
    (T, "MISO", "bot", 0.2, [(15.24, 38.486), (15.94, 37.786), (15.94, 32.9), (16.34, 32.5), (33.709, 32.5), (35.809, 30.4)]),
    # MOSI crosses MISO on the top layer, then takes the lane between the other two
    (T, "MOSI", "top", 0.2, [(18.034, 34.666), (18.034, 33.2), (19.634, 31.6)]),
    (V, "MOSI", (19.634, 31.6)),
    (T, "MOSI", "bot", 0.2, [(19.634, 31.6), (28.2, 31.6), (28.7, 32.1), (32.839, 32.1), (34.539, 30.4)]),
    # series resistors to the module's pads
    (T, "LORA_NSS", "top", 0.2, [(30.729, 28.471), (30.729, 27.0)]),
    (T, "LORA_SCK", "top", 0.2, [(33.269, 28.471), (33.269, 27.0)]),
    (T, "LORA_MOSI", "top", 0.2, [(34.539, 28.471), (34.539, 27.0)]),
    (T, "LORA_MISO", "top", 0.2, [(35.809, 28.471), (35.809, 27.0)]),

    # Chip select and reset come down under the ESP32's right-hand pads on the bottom, then cross the LED's
    # bottom-layer track on the top layer, straight down to the resistor and the module pad.
    (T, "NSS", "bot", 0.2, [(29.85, 44.836), (31.45, 43.236), (31.45, 35.0)]),
    (V, "NSS", (31.45, 35.0)),
    (T, "NSS", "top", 0.2, [(31.45, 35.0), (30.729, 34.279), (30.729, 29.337)]),
    (T, "RST", "bot", 0.2, [(29.85, 46.106), (32.05, 43.906), (32.05, 35.2), (32.25, 35.0)]),
    (V, "RST", (32.25, 35.0)),
    (T, "RST", "top", 0.2, [(32.25, 35.0), (32.0, 34.75), (32.0, 27.0)]),
    # BUSY and DIO1 stay on the bottom: round the end of the LED's track, down outside the LoRa module,
    # and in under its lower edge to a via beside each pad.
    (T, "DIO1", "bot", 0.2, [(29.85, 42.296), (30.45, 41.696), (30.45, 34.1), (30.85, 33.7), (39.6, 33.7), (40.0, 33.3),
                             (40.0, 18.15), (39.6, 17.75), (35.81, 17.75)]),
    (V, "DIO1", (35.81, 17.75)),
    (T, "DIO1", "top", 0.2, [(35.81, 17.75), (35.81, 15.5)]),
    (T, "BUSY", "bot", 0.2, [(29.85, 43.566), (30.85, 42.566), (30.85, 34.7), (31.25, 34.3), (40.2, 34.3), (40.6, 33.9),
                             (40.6, 17.4), (40.2, 17.0), (34.54, 17.0)]),
    (V, "BUSY", (34.54, 17.0)),
    (T, "BUSY", "top", 0.2, [(34.54, 17.0), (34.54, 15.5)]),
    # The antenna switch enable has no line to cross, so it stays on the top layer: down the gap between
    # the ESP32's pads and the sensor parts, then to the module pad and its pull-up.
    (T, "RF_SW", "top", 0.2, [(31.229, 41.026), (32.2, 41.026), (32.4, 40.826), (32.4, 39.0), (33.0, 38.4), (33.0, 34.6),
                              (37.08, 30.52), (37.08, 27.0)]),
    (T, "RF_SW", "top", 0.2, [(37.08, 28.2), (37.709, 27.571), (39.299, 27.571)]),

    # IO4 to the DONE stage: the reset parts and the BOOT track block the top layer on the left, so it
    # goes down the ESP32's side on the bottom, west of the clock, to a via beside its test pad.
    (T, "IO4_DONE", "top", 0.2, [(13.729, 48.646), (12.896, 48.646), (12.45, 48.2)]),
    (V, "IO4_DONE", (12.45, 48.2)),
    (T, "IO4_DONE", "bot", 0.2, [(12.45, 48.2), (11.25, 47.0), (11.25, 42.8), (12.5, 41.55), (12.5, 24.7), (10.0, 22.2)]),
    (V, "IO4_DONE", (10.0, 22.2)),
    (T, "IO4_DONE", "top", 0.2, [(10.0, 22.2), (10.0, 21.0)]),

    # timer: DONE to its test pad; DRVN under everything to the diode; its supply from the mux output
    (T, "DONE", "top", 0.25, [(4.249, 21.471), (4.721, 21.471), (6.2, 22.95)]),
    (T, "DRVN", "top", 0.2, [(3.298, 20.1), (3.298, 21.048), (3.4, 21.15)]),
    (V, "DRVN", (3.4, 21.15)),
    (T, "DRVN", "bot", 0.2, [(3.4, 21.15), (3.4, 20.3), (13.1, 10.6), (13.1, 10.448)]),
    (V, "DRVN", (13.1, 10.448)),
    (T, "DRVN", "top", 0.2, [(13.1, 10.448), (12.161, 10.448)]),
    (T, "SYS_OUT", "top", 0.25, [(2.348, 17.4), (2.348, 16.3)]),
    (V, "SYS_OUT", (2.348, 16.3)),
    (T, "SYS_OUT", "bot", 0.25, [(2.348, 16.3), (4.2, 16.3), (6.95, 13.55)]),
    (V, "SYS_OUT", (6.95, 13.55)),
    (T, "SYS_OUT", "top", 0.25, [(6.95, 13.55), (7.12, 13.72), (7.869, 13.72)]),
    # the enable diodes and the always-on link
    (T, "VBUS", "bot", 0.3, [(8.51, 17.3), (8.51, 16.89), (13.1, 12.3), (13.1, 12.198)]),
    (V, "VBUS", (13.1, 12.198)),
    (T, "VBUS", "top", 0.3, [(13.1, 12.198), (12.161, 12.198)]),
    (T, "SYS_OUT", "top", 0.25, [(14.971, 8.0), (12.4, 8.0), (11.2, 9.2), (11.2, 13.116), (11.9, 13.816)]),
    (T, "PWR_EN", "top", 0.2, [(15.837, 8.0), (16.05, 8.2), (16.05, 9.2), (16.671, 9.821), (16.671, 10.301)]),
    # mux status to its test pad, and the battery MOSFET's gate to its pull-down
    (T, "ST", "top", 0.2, [(7.869, 13.22), (9.319, 11.77), (9.56, 11.65)]),
    (T, "Q1_G", "top", 0.2, [(5.92, 13.237), (5.92, 12.301), (6.62, 11.601), (7.191, 11.601)]),
]

# Silkscreen labels: (text, (x, y), rotation, text height in mm).
LABELS = [
    (f"V{REVISION}  {DATE[:7]}", (17.6, 3.6), 0, 1.0),
    ("ALWAYS ON", (15.4, 5.9), 0, 1.0),
    ("BAT+", (2.1, 9.6), 0, 1.0),
    ("BAT-", (9.3, 9.6), 0, 1.0),
    ("3 3V3", (38.6, 52.3), 0, 1.0),
    ("4 GND", (42.6, 52.3), 0, 1.0),
    ("1 SCL", (38.6, 50.6), 0, 1.0),
    ("2 SDA", (42.6, 50.6), 0, 1.0),
]

# Parts the silkscreen names by what they do, in place of their designator. Each name is placed
# beside its part before any designator is.
SILK_NAMES = {"SW1": "BOOT", "SW2": "RST", "SW3": "WAKE"}

# The goblin on the silkscreen: footprint in the board's own library, centre, rotation, width in mm
# and style ("filled" draws the robe solid, "lines" draws outlines only).
LOGO = {"name": "Logo_Goblin", "at": (18.2, 26.4), "rot": 0, "width": 9.0, "style": "filled"}

# Battery polarity in copper, on the bottom layer under the connector's pins (mirrored, read from below).
COPPER_MARKS = [("+", (4.97, 8.1), 1.6), ("-", (6.97, 8.1), 1.6)]

# A via's hole stays this far from every pad, same net or not, so solder is not drawn down
# the hole. The ESP32 module's ground paddle is the exception: the drop's nine vias there are wanted.
VIA_TO_PAD = 0.2
VIA_IN_PAD_OK = ("U1", "41")

# Copper kept from the drop: whole nets, and for ground only what lies in these boxes. Nothing is kept
# around the plug and the USB input, which are laid out afresh.
KEEP_NETS = ["USB_DP", "USB_DN", "EN", "BOOT", "IO46", "IO45", "LED_A", "USER_LED"]
KEEP_BOXES = {
    "GND": [(9.9, 27.5, 12.6, 39.5), (9.9, 33.5, 32.2, 39.5), (0.0, 39.5, 32.2, 53.7), (38.0, 31.5, 45.1, 35.0)],
}
