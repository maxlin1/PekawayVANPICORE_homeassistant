"""Konstanten der Board-Module (Relais/Eingänge, Tanks, 1-Wire, Victron)."""

from __future__ import annotations

# Subentry-Typen (je Typ ein eigener "Hinzufügen"-Knopf in der Integration)
SUBENTRY_IO = "io"
SUBENTRY_TANK = "tank"
SUBENTRY_ONEWIRE = "onewire"
SUBENTRY_VICTRON = "victron"
SUBENTRY_TANK_INPUTS = "tank_inputs"

CONF_I2C_BUS = "i2c_bus"
CONF_ADDRESS = "address"
CONF_NAME = "name"

# MCP23017 (Relais und Eingänge)
CONF_INVERT_INPUTS = "invert_inputs"
CONF_INVERT_RELAYS = "invert_relays"
CONF_KEEP_STATE = "keep_state"
MCP_DEFAULT_ADDRESS = 0x20
# Belegung auf dem VAN PI CORE: GPA0-7 = Eingänge 1-8, GPB0-7 = Relais 1-8
VANPI_INPUT_PINS = list(range(0, 8))
VANPI_RELAY_PINS = list(range(8, 16))
IO_POLL_INTERVAL = 0.1  # s

# ADS1115 (Tanks)
CONF_CHANNEL = "channel"
CONF_MODE = "mode"
MODE_VOLTAGE = "voltage"
MODE_RESISTIVE = "resistive"
CONF_CURVE = "curve"
CONF_UNIT = "unit"
UNIT_LITERS = "L"
UNIT_PERCENT = "%"
CONF_DIVIDER = "divider_ratio"
CONF_PULLUP = "r_pullup_ohm"  # nur noch Altbestand, Board-Wert ist fest
CONF_PAIR_12 = "pair_12"  # Sensortyp Tankeingang 1+2
CONF_PAIR_34 = "pair_34"  # Sensortyp Tankeingang 3+4
BOARD_PULLUP_OHM = 47000
BOARD_VREF = 3.3
CONF_VREF = "v_ref"
CONF_SCAN_INTERVAL = "scan_interval"
ADS_DEFAULT_ADDRESS = 0x48
TANK_DEFAULT_CURVE = "0:0, 3.3:100"
TANK_DEFAULT_INTERVAL = 5

# 1-Wire
CONF_MOUNT_DIR = "mount_dir"
ONEWIRE_DEFAULT_DIR = "/sys/bus/w1/devices"
ONEWIRE_DEFAULT_INTERVAL = 30
ONEWIRE_FAMILIES = {"10", "22", "28", "3B", "42"}

# Victron VE.Direct
CONF_PORT = "port"
CONF_DEVICE_TYPE = "device_type"
CONF_BAUDRATE = "baudrate"
DEVICE_MPPT = "mppt"
DEVICE_SHUNT = "shunt"
VICTRON_DEFAULT_BAUD = 19200
VICTRON_DEFAULT_INTERVAL = 5
VICTRON_STALE_AFTER = 30  # s ohne gültigen Datenblock -> nicht verfügbar
