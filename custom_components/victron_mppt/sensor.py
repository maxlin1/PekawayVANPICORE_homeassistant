import serial
import asyncio
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from queue import Queue
import logging

# Logger für die Komponente konfigurieren
_LOGGER = logging.getLogger(__name__)

# Lade Konfiguration aus der config.py
from .config import key_mapping

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required("port"): cv.string,
    vol.Optional("baudrate", default=19200): cv.positive_int,
    vol.Optional("sleeptime", default=5): cv.positive_int,
})

# Warteschlange für die Datenübergabe zwischen Thread und Home Assistant
data_queue = Queue()

def isnumber(number):
    number = number[1:] if number[0] == "-" else number
    return number.isnumeric()


async def serial_reader_async(port, baudrate):
    """Asynchrone Funktion, um Daten von der seriellen Schnittstelle zu lesen und in der Queue zu speichern."""
    try:
        ser = serial.Serial(port, baudrate)
        current_data = {}
        while True:
            # Verwende 'utf-8' statt 'ascii' mit errors='ignore', um problematische Zeichen zu vermeiden
            line = await asyncio.to_thread(ser.readline)  # Nicht blockierendes Lesen
            line = line.decode('utf-8', errors='ignore').strip()
            if line:
                key, value = parse_line(line)
                #_LOGGER.debug(f"New incoming data: {key} = {value}")
                if key and value and key in key_mapping:
                    mapped_key = key_mapping[key]["name"]
                    if isnumber(value):
                        scalefactore = key_mapping[key].get("scale", 1)
                        value = int(value) * scalefactore
                        roundby = key_mapping[key].get("round", None)
                        value = round(value, roundby) if roundby else value
                    current_data[mapped_key] = value

                if key == "Checksum":  # Annahme, dass dies das Ende eines Datensatzes ist
                    if current_data:  # Überprüfen, ob Daten vorliegen
                        data_queue.queue.clear()
                        for key, value in current_data.items():
                            _LOGGER.debug(f"Safe new data to data_queue: {key} = {value}")
                        data_queue.put(current_data.copy())
                        current_data.clear()  # Leere den aktuellen Datensatz für den nächsten Zyklus
                    else:
                        _LOGGER.debug("Checksum, but no new data")
            await asyncio.sleep(0.01)  # Geringe Pause für Event-Loop
    except Exception as e:
        _LOGGER.error(f"Fehler beim Lesen der seriellen Daten: {e}", )

def parse_line(line):
    """Parst eine Zeile des VE.Direct-Protokolls."""
    try:
        key, value = line.split('\t')
        return key, value
    except ValueError:
        return None, None

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup der Victron-Sensoren asynchron."""
    port = config["port"]
    baudrate = config["baudrate"]
    sleeptime = config["sleeptime"]

    # Starte die asynchrone serielle Lesefunktion
    hass.loop.create_task(serial_reader_async(port, baudrate))
    _LOGGER.info("Asynchrone serielle Leser-Schleife gestartet.")

    # Initialisiere alle Entitäten für jede Konfiguration in key_mapping
    sensors = [VictronSensor(key, details) for key, details in key_mapping.items()]
    async_add_entities(sensors)
    _LOGGER.info("Victron-Sensoren wurden initialisiert und hinzugefügt.")

    # Starte die wiederholte Queue-Überwachung nur, wenn Daten verfügbar sind
    hass.loop.create_task(check_queue_and_update_sensors(sensors, sleeptime))

async def check_queue_and_update_sensors(sensors, sleeptime):
    """Wiederholte Aufgabe, um die Queue zu überprüfen und Sensoren zu aktualisieren."""
    while True:
        if not data_queue.empty():
            _LOGGER.debug("New data to HA")
            data = data_queue.get()
            for sensor in sensors:
                if sensor.name in data:
                    _LOGGER.debug(f"Save to ha: {sensor.name}={data[sensor.name]}")
                    sensor.update_state(data[sensor.name])
                else:
                    _LOGGER.debug(f"Not saved, as not found in data: {sensor.name}")

                    
        await asyncio.sleep(sleeptime)  # Pausiert für mehr Effizienz

class VictronSensor(Entity):
    """Repräsentiert einen Victron-Sensor."""

    def __init__(self, key, details):
        """Initialisiert den Sensor."""
        self._key = key
        self._name = details["name"]
        self._unit = details["unit"]
        self._icon = details["icon"]
        self._state = None
        self._attr_should_poll = False  # Schaltet Polling ab, da die Queue überwacht wird
        self._attr_available = True
        self._attr_unique_id = f"victron_{self._key}"

    @property
    def unique_id(self):
        """Gibt die eindeutige ID der Entität zurück."""
        return self._attr_unique_id

    @property
    def name(self):
        """Gibt den Namen des Sensors zurück."""
        return self._name

    @property
    def state(self):
        """Gibt den aktuellen Zustand des Sensors zurück."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Gibt die Maßeinheit des Sensors zurück."""
        return self._unit

    @property
    def icon(self):
        """Gibt das Icon des Sensors zurück."""
        return self._icon

    def update_state(self, value):
        """Aktualisiert den Zustand des Sensors nur, wenn sich der Wert geändert hat."""
        if value != self._state:  # Nur aktualisieren, wenn sich der Wert geändert hat
            self._state = value
            _LOGGER.debug(f"{self._name} Zustand aktualisiert: Neuer Wert = {self._state}")
            self.async_write_ha_state()  # Asynchrones Schreiben in Home Assistant
