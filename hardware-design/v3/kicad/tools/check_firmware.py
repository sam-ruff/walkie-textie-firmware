"""Check that the board gives the firmware in this repo every connection it uses.

Usage: check_firmware.py model.json firmware_src_dir kicad_symbols_dir

The pin numbers are read from the firmware source (src/main.rs) and the radio
settings from src/config.rs, so the check follows the code rather than a copy
of it. Each pin is followed through the schematic's nets to the part it has to
reach. The board-side conditions the firmware relies on without driving a pin
(pull-ups, strapping, the module's switch enable) are checked as well.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design
import parts as parts_module
from firmware_config import radio_settings
from sym_pins import load_symbol, pins

MCU = "U1"
RADIO = "U11"
# What each firmware pin must reach: (name in main.rs, purpose, series part or None, destination pin).
SIGNALS = [
    ("sclk", "SPI clock", "R28", (RADIO, "SCK")),
    ("miso", "SPI data in", "R26", (RADIO, "MISO")),
    ("mosi", "SPI data out", "R27", (RADIO, "MOSI")),
    ("nss", "radio chip select", "R29", (RADIO, "NSS")),
    ("dio1", "radio interrupt", None, (RADIO, "DIO1")),
    ("nrst", "radio reset", None, (RADIO, "NRST")),
    ("busy", "radio busy", None, (RADIO, "BUSY")),
    ("usb d+", "USB D+", "R2", ("J1", "D+")),
    ("usb d-", "USB D-", "R1", ("J1", "D-")),
]
# From the Wio-SX1262 datasheet: frequency range, most output power, and what DIO2 and DIO3 do inside the module.
MODULE = {"mhz": (862.0, 930.0), "dbm": 22, "tcxo_volts": (1.7, 3.3)}
TCXO_VOLTS = {0x00: 1.6, 0x01: 1.7, 0x02: 1.8, 0x03: 2.2, 0x04: 2.4, 0x05: 2.7, 0x06: 3.0, 0x07: 3.3}     # SX1262 SetDIO3AsTcxoCtrl


def firmware_pins(source):
    """{role: GPIO number} and the LED's on level, from main.rs."""
    found = {}
    for role, gpio in re.findall(r"let (sclk|miso|mosi) = peripherals\.GPIO(\d+)", source):
        found[role] = int(gpio)
    for role, gpio in re.findall(r"let (nss|nrst) = Output::new\(\s*peripherals\.GPIO(\d+)", source):
        found[role] = int(gpio)
    for role, gpio in re.findall(r"let (dio1|busy) = Input::new\(\s*peripherals\.GPIO(\d+)", source):
        found[role] = int(gpio)
    usb = re.search(r"Usb::new\(\s*peripherals\.USB0,\s*peripherals\.GPIO(\d+),\s*peripherals\.GPIO(\d+)", source)
    if usb:
        found["usb d+"], found["usb d-"] = int(usb.group(1)), int(usb.group(2))
    led = re.search(r"let led = Output::new\(\s*peripherals\.GPIO(\d+),\s*Level::(\w+)", source)
    if led:
        found["led"] = int(led.group(1))
    missing = [name for name, *_ in SIGNALS if name not in found] + ([] if led else ["led"])
    if missing:
        raise SystemExit(f"could not find these pins in main.rs, so this check needs updating: {missing}")
    return found, led.group(2)


def gpio_pads(symbols_dir):
    """{GPIO number: module pad} for the ESP32-S3-WROOM-1, from KiCad's symbol."""
    special = {"USB_D-": 19, "USB_D+": 20, "TXD0": 43, "RXD0": 44}
    table = {}
    for pin in pins(load_symbol(symbols_dir, "RF_Module", "ESP32-S3-WROOM-1")):
        name = pin["name"]
        if name in special:
            table[special[name]] = pin["number"]
        elif re.fullmatch(r"IO\d+", name):
            table[int(name[2:])] = pin["number"]
    return table


class Board:
    def __init__(self, all_parts):
        self.parts = all_parts
        self.on_net = {}
        for ref, part in all_parts.items():
            for pad, net in part["nets"].items():
                if net:
                    self.on_net.setdefault(net, set()).add((ref, pad))

    def net(self, ref, pad):
        return self.parts[ref]["nets"][pad]

    def across(self, ref, net):
        """The net on the other pad of a two-pad part, given the net on one pad."""
        nets = list(self.parts[ref]["nets"].values())
        if len(nets) != 2 or net not in nets:
            return None
        return nets[1] if nets[0] == net else nets[0]

    def joins(self, ref, net_a, net_b):
        return self.across(ref, net_a) == net_b

    def fitted(self, ref):
        return not self.parts[ref]["dnp"]


def main():
    model_path, firmware_dir, symbols_dir = sys.argv[1:4]
    with open(model_path) as fh:
        board = Board(parts_module.resolve(json.load(fh)))
    with open(os.path.join(firmware_dir, "main.rs")) as fh:
        source = fh.read()
    used, led_on = firmware_pins(source)
    with open(os.path.join(firmware_dir, "config.rs")) as fh:
        config = fh.read()
    pad_of = gpio_pads(symbols_dir)
    radio_pin = {name: number for number, name, _ in RADIO_PINS}
    plug_pin = {"D+": "A6", "D-": "A7"}
    problems = []

    print(f"{'firmware pin':13} {'GPIO':>4} {'pad':>4}  {'net':10} reaches")
    for role, purpose, series, (ref, pin_name) in SIGNALS:
        gpio = used[role]
        pad = pad_of[gpio]
        net = board.net(MCU, pad)
        target_pad = radio_pin[pin_name] if ref == RADIO else plug_pin[pin_name]
        target_net = board.net(ref, target_pad)
        if series:
            ok = bool(net) and board.joins(series, net, target_net) and board.fitted(series)
            path = f"{series} then {ref} {pin_name} (pad {target_pad})"
        else:
            ok = bool(net) and net == target_net
            path = f"{ref} {pin_name} (pad {target_pad})"
        print(f"{role:13} {gpio:>4} {pad:>4}  {net or 'nothing':10} {path}{'' if ok else '   <-- NOT CONNECTED'}")
        if not ok:
            problems.append(f"{purpose}: GPIO{gpio} does not reach {ref} {pin_name}")

    # LED: the firmware drives the pin low to light it, so the cathode is on the pin and the anode goes to 3.3 V
    led_net = board.net(MCU, pad_of[used["led"]])
    anode = board.across("LED1", led_net)
    lit_low = board.net("LED1", "1") == led_net and anode is not None and board.joins("R7", anode, "+3V3")
    print(f"{'led':13} {used['led']:>4} {pad_of[used['led']]:>4}  {led_net or 'nothing':10} LED1 cathode, anode through R7 to +3V3{'' if lit_low else '   <-- WRONG'}")
    if not lit_low or led_on != "Low":
        problems.append(f"LED: firmware lights it with Level::{led_on}, board lights it when the pin is {'low' if lit_low else 'not low'}")

    def need(ok, text):
        print(f"  {'ok ' if ok else 'BAD'} {text}")
        if not ok:
            problems.append(text)

    print("what the firmware relies on without driving a pin:")
    switch_net = board.net(RADIO, radio_pin["RF_SW"])
    switch_gpio = [gpio for gpio, pad in pad_of.items() if board.net(MCU, pad) == switch_net]
    driven = any(re.search(rf"peripherals\.GPIO{gpio}\b", source) for gpio in switch_gpio)
    need(board.joins("R25", switch_net, "+3V3") and board.fitted("R25") and len(switch_gpio) == 1,
         f"the radio module's RF_SW pin is pulled up to +3V3 by R25 and reaches GPIO{switch_gpio[0] if switch_gpio else '?'}")
    if driven:
        print("      the firmware uses that pin, so what it drives there decides the module's antenna switch")
    else:
        # Seeed's datasheet for the module has RF_SW high to receive and low at other times. Its staff
        # describe the pin as the /CTRL input of the module's antenna switch, with DIO2 on CTRL; on a
        # switch of that kind a high level there leaves DIO2 alone in control. Neither is measured here.
        print("      the firmware never drives that pin, so RF_SW is high all the time: the module's receive path is enabled,")
        print("      and it stays high in transmit, where Seeed's datasheet has it low. See the README: this needs a")
        print("      measurement of transmit power on the first board")
    need(board.net(RADIO, radio_pin["VCC"]) == "+3V3", "radio module is supplied from +3V3")
    boot = board.net(MCU, pad_of[0])
    need(board.joins("R6", boot, "+3V3") and board.joins("SW1", boot, "GND"), "GPIO0 (boot) has a pull-up and a button to ground")
    enable = board.net(MCU, "3")
    need(board.joins("R5", enable, "+3V3") and board.joins("C3", enable, "GND") and board.joins("SW2", enable, "GND"),
         "EN has a pull-up, a capacitor and a reset button to ground")
    need(all(board.joins(ref, board.net(MCU, pad_of[gpio]), "GND") for gpio, ref in ((45, "R12"), (46, "R11"))),
         "strapping pins GPIO45 and GPIO46 are pulled down")
    need(not any(board.net(MCU, pad_of[gpio]) for gpio in (35, 36, 37)), "GPIO35 to GPIO37 (the module's PSRAM) are not connected")
    always_on = design.ORDERS[design.DEFAULT_ORDER]
    need(board.across("R37", "SYS_OUT") == "PWR_EN" and board.fitted("R37") and "R37" not in always_on.get("leave_out", []),
         "R37 holds the converter on in the default order, for running this firmware from a battery (it never signals the timer)")

    print("radio settings in config.rs against the module's datasheet:")
    radio = radio_settings(config)
    hertz, power, code = radio["hertz"], radio["power_dbm"], radio["tcxo_code"]
    need(MODULE["mhz"][0] <= hertz / 1e6 <= MODULE["mhz"][1], f"{hertz / 1e6:.3f} MHz is inside the module's {MODULE['mhz'][0]:.0f} to {MODULE['mhz'][1]:.0f} MHz")
    need(power <= MODULE["dbm"], f"+{power} dBm is within the module's +{MODULE['dbm']} dBm")
    need(MODULE["tcxo_volts"][0] <= TCXO_VOLTS[code] <= MODULE["tcxo_volts"][1],
         f"TCXO supply {TCXO_VOLTS[code]} V from DIO3 is inside the module's {MODULE['tcxo_volts'][0]} to {MODULE['tcxo_volts'][1]} V")

    if problems:
        raise SystemExit(f"{len(problems)} problems between the firmware and the board")
    print("firmware and board agree")


# Wio-SX1262 pads: (number, name, direction), from its datasheet.
RADIO_PINS = [("1", "RF_SW", "in"), ("2", "MISO", "out"), ("3", "MOSI", "in"), ("4", "SCK", "in"), ("5", "NRST", "in"), ("6", "NSS", "in"),
              ("7", "GND", "power"), ("8", "VCC", "power"), ("9", "ANT", "rf"), ("10", "GND", "power"), ("11", "BUSY", "out"), ("12", "DIO1", "out")]


if __name__ == "__main__":
    main()
