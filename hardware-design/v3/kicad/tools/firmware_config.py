"""Read the radio settings the firmware is built with, from the text of src/config.rs."""
import re

SETTINGS = {
    "hertz": r"FREQUENCY_HZ: u32 = ([\d_]+)",
    "spreading_factor": r"SPREADING_FACTOR: u8 = (\d+)",
    "bandwidth_khz": r"BANDWIDTH_KHZ: u32 = ([\d_]+)",
    "power_dbm": r"TX_POWER_DBM: i8 = (-?\d+)",
    "tcxo_code": r"VOLTAGE_CODE: u8 = (0x[0-9A-Fa-f]+|\d+)",
}


def radio_settings(config):
    """{setting: number} for every radio setting the board checks use."""
    found = {}
    for name, pattern in SETTINGS.items():
        match = re.search(pattern, config)
        if not match:
            raise SystemExit(f"could not find {name} in config.rs, so this check needs updating")
        found[name] = int(match.group(1).replace("_", ""), 0)
    return found


def selectable_spreading_factors(handler):
    """(lowest, highest) spreading factor a host may select, from the text of src/dispatcher/handler.rs."""
    match = re.search(r"\((\d+)\.\.=(\d+)\)\.contains\(&spreading_factor\)", handler)
    if not match:
        raise SystemExit("could not find the spreading factor range in handler.rs, so this check needs updating")
    return int(match.group(1)), int(match.group(2))
