import serial
import time

# Konfiguration aus config.h
PORT = '/dev/ttyAMA4'  # Serielle Port-Konfiguration
BAUDRATE = 19200
TIMEOUT = 1

# Konfigurationswerte aus config.h
BUFFSIZE = 32  # Puffergröße
VALUE_BYTES = 33  # Größe der Werte in Bytes
LABEL_BYTES = 9  # Größe der Labels in Bytes
NUM_KEYWORDS = 18  # Anzahl der Schlüsselwörter für MPPT 75 | 10

# Definition der Schlüsselwörter für MPPT 75 | 10
keywords = [
    "PID", "FW", "SER#", "V", "I", "VPV", "PPV", "CS", "ERR", "LOAD", 
    "IL", "H19", "H20", "H21", "H22", "H23", "HSDS", "Checksum"
]

# Umschlüsselungstabelle
key_mapping = {
    "PID": {"name": "Produkt-ID", "unit": None, "icon": "mdi:identifier", "update_interval": 3600},
    "FW": {"name": "Firmware-Version", "unit": None, "icon": "mdi:chip", "update_interval": 3600},
    "SER#": {"name": "Seriennummer", "unit": None, "icon": "mdi:barcode", "update_interval": 3600},
    "V": {"name": "Batteriespannung", "unit": "V", "icon": "mdi:flash", "update_interval": 30},
    "I": {"name": "Batteriestrom", "unit": "A", "icon": "mdi:current-dc", "update_interval": 30},
    "VPV": {"name": "PV-Spannung", "unit": "V", "icon": "mdi:solar-power", "update_interval": 30},
    "PPV": {"name": "PV-Leistung", "unit": "W", "icon": "mdi:solar-power", "update_interval": 30},
    "CS": {"name": "Ladestatus", "unit": None, "icon": "mdi:power-settings", "update_interval": 30},
    "MPPT": {"name": "MPPT-Modus", "unit": None, "icon": "mdi:solar-power", "update_interval": 30},
    "OR": {"name": "Betriebsstatus", "unit": None, "icon": "mdi:information", "update_interval": 3600},
    "ERR": {"name": "Fehlercode", "unit": None, "icon": "mdi:alert", "update_interval": 30},
    "LOAD": {"name": "Lastausgang", "unit": None, "icon": "mdi:power", "update_interval": 30},
    "IL": {"name": "Laststrom", "unit": "A", "icon": "mdi:current-dc", "update_interval": 30},
    "H19": {"name": "Gesamtertrag", "unit": "kWh", "icon": "mdi:calendar", "update_interval": 3600},
    "H20": {"name": "Ertrag heute", "unit": "kWh", "icon": "mdi:calendar-today", "update_interval": 3600},
    "H21": {"name": "Ertrag gestern", "unit": "kWh", "icon": "mdi:calendar-yesterday", "update_interval": 3600},
    "H22": {"name": "Ertrag letzte 30 Tage", "unit": "kWh", "icon": "mdi:calendar-month", "update_interval": 3600},
    "H23": {"name": "Tagesmaximum PV-Spannung", "unit": "V", "icon": "mdi:flash", "update_interval": 3600},
    "HSDS": {"name": "Tageszählstand", "unit": None, "icon": "mdi:counter", "update_interval": 3600}
}

# Verbindung zur seriellen Schnittstelle herstellen
try:
    ser = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
    print(f"Verbindung zu {PORT} hergestellt.")
except serial.SerialException as e:
    print(f"Fehler beim Öffnen der seriellen Schnittstelle: {e}")
    exit(1)

# Letzter bekannter Zustand der Daten
last_data = {}

def parse_line(line):
    """
    Parst eine Zeile des VE.Direct-Protokolls und gibt ein Tupel aus (Schlüssel, Wert) zurück.
    """
    try:
        key, value = line.split('\t')
        return key, value
    except ValueError:
        return None, None

def read_victron_data():
    """
    Liest Daten vom Victron-Gerät und gibt sie als umgeschlüsseltes Dictionary zurück.
    """
    data = {}
    while True:
        line = ser.readline().decode('ascii').strip()
        if not line:
            continue
        key, value = parse_line(line)
        if key and value and key in key_mapping:
            # Umschlüsseln der Daten
            mapped_key = key_mapping[key]["name"]
            data[mapped_key] = {
                "value": value,
                "unit": key_mapping[key]["unit"],
                "icon": key_mapping[key]["icon"],
                "update_interval": key_mapping[key]["update_interval"]
            }
        if key == "Checksum":
            break
    
    return data

def has_data_changed(new_data, old_data):
    """
    Überprüft, ob sich die neuen Daten von den alten unterscheiden.
    """
    for key, details in new_data.items():
        if key not in old_data or old_data[key]["value"] != details["value"]:
            return True
    return False

try:
    while True:
        victron_data = read_victron_data()
        if victron_data and has_data_changed(victron_data, last_data):
            print("Empfangene und geänderte Daten:")
            for key, details in victron_data.items():
                print(f"{key}: {details['value']} {details['unit'] if details['unit'] else ''}")
            last_data = victron_data.copy()  # Aktualisiere den letzten Zustand der Daten
        
        # 5-Sekunden-Pause nach jedem Lesevorgang
        time.sleep(5)
except KeyboardInterrupt:
    print("Programm beendet.")
finally:
    ser.close()
    print("Serielle Verbindung geschlossen.")
