"""Bounded input-only probe for a configured standalone ASCII RFID reader.

Reads whitelisted hardware settings only. It never sends reader commands,
imports proprietary libraries, changes firmware, drives LEDs, or records moves.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET

try:
    import serial
except ImportError:
    serial = None

SERIAL_ERRORS = (OSError,) if serial is None else (OSError, serial.SerialException)


class ProbeError(Exception):
    pass


@dataclass(frozen=True)
class StandaloneProfile:
    port: str
    baudrate: int
    packet_length: int
    field_offset: int
    field_length: int

    def __post_init__(self):
        if not re.fullmatch(r'COM[1-9][0-9]{0,3}', self.port):
            raise ProbeError('La porta del lettore non è una porta COM valida.')
        if self.baudrate not in (9600, 19200, 38400, 57600, 115200):
            raise ProbeError('La velocità configurata richiede una verifica prima del collaudo.')
        if not (8 <= self.field_length <= 64 and 0 <= self.field_offset
                and self.field_offset + self.field_length <= self.packet_length <= 256):
            raise ProbeError('Il formato configurato per la lettura non è valido.')

    def public_settings(self):
        return asdict(self)


def profile_from_settings(path):
    path = Path(path)
    if path.stat().st_size > 1024 * 1024:
        raise ProbeError('Il file delle impostazioni è troppo grande.')
    raw = path.read_bytes()
    # Only attributes of the reader node are used; never expose DB credentials.
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper() or b'\x00' in raw:
        raise ProbeError('Formato del file impostazioni non supportato.')
    try:
        root = ET.fromstring(raw)
        main, node = root.find('MAIN'), root.find('StandAloneReader')
        if main is None or node is None or main.get('RfidReaderType', '').lower() != 'standalone':
            raise ProbeError('Questa prova richiede un lettore configurato in modalità StandAlone.')
        if node.get('DataBits') != '8' or node.get('Parity', '').lower() != 'no' or node.get('StopBit') != '1' or node.get('RTS', '').lower() != 'no':
            raise ProbeError('Questa prova supporta il profilo 8N1 senza RTS.')
        if node.get('PacketContain', ''):
            raise ProbeError('Il lettore usa un filtro di pacchetto che richiede una verifica.')
        profile = StandaloneProfile(
            node.attrib['Port'].upper().strip(), int(node.attrib['Bps']),
            int(node.attrib['PacketLength']), int(node.attrib['StartOffset']),
            int(node.attrib['FieldLength']),
        )
        declared = main.get('RfidReaderCOMport', '').upper().strip()
        if declared and ('COM' + declared if declared.isdigit() else declared) != profile.port:
            raise ProbeError('Le due impostazioni della porta RFID non coincidono.')
        # Never open a port configured as the cabinet LED controller.
        sorter = root.find('EasySorter')
        if sorter is not None:
            sorter_port = sorter.get('SorterCOM', '').upper().strip()
            led_com = 'COM' + sorter_port if sorter_port.isdigit() else sorter_port
            if led_com == profile.port:
                raise ProbeError('La porta del lettore coincide con quella dei LED: nessun accesso eseguito.')
        return profile
    except (ET.ParseError, KeyError, ValueError):
        raise ProbeError('Il file non contiene un profilo di lettura valido.') from None


def serial_available():
    return serial is not None


def probe_reader(profile, seconds=10, factory=None, cancelled=lambda: False, clock=time.monotonic):
    if factory is None:
        if serial is None:
            raise ProbeError('Il collegamento seriale non è incluso in questa versione.')
        factory = serial.Serial
    if not 0 < seconds <= 15:
        raise ProbeError('Durata della prova non valida.')
    if cancelled():
        return {'status': 'annullata', 'port': profile.port}
    port = factory()
    # Configure both modem signals before opening, rather than pulsing defaults.
    port.port = profile.port
    port.baudrate = profile.baudrate
    port.bytesize, port.parity, port.stopbits = 8, 'N', 1
    port.timeout = 0.05
    port.xonxoff = port.rtscts = port.dsrdtr = False
    port.dtr = port.rts = False
    sample, pending = bytearray(), bytearray()
    try:
        port.open()
        port.reset_input_buffer()
        deadline = clock() + seconds
        while not cancelled() and clock() < deadline and len(sample) < 4096:
            block = port.read(256)
            sample.extend(block)
            pending.extend(block)
            # The configured packet length is a byte count; CR/LF may separate
            # frames. Never strip other bytes or infer UIDs by reversing bytes.
            while pending and pending[0] in (10, 13):
                del pending[0]
            while len(pending) >= profile.packet_length:
                frame = bytes(pending[:profile.packet_length])
                del pending[:profile.packet_length]
                field = frame[profile.field_offset:profile.field_offset + profile.field_length]
                if re.fullmatch(rb'[0-9A-Fa-f]{8,64}', field):
                    return {'status': 'ricevuto', 'port': profile.port,
                            'tag_candidate': field.decode('ascii').upper(),
                            'raw_frame_hex': frame.hex().upper(),
                            'bytes_received': len(sample), 'movements_created': 0}
                # Stop on an unexpected frame. A guessed boundary must never
                # turn unrecognized bytes into a garment identification.
                return {'status': 'formato_da_verificare', 'port': profile.port,
                        'raw_sample_hex': bytes(sample[:256]).hex().upper(),
                        'bytes_received': len(sample), 'movements_created': 0}
        return {'status': 'annullata' if cancelled() else 'nessun_codice_completo',
                'port': profile.port, 'raw_sample_hex': bytes(sample[:256]).hex().upper(),
                'bytes_received': len(sample), 'movements_created': 0}
    except SERIAL_ERRORS:
        raise ProbeError('Impossibile leggere ' + profile.port + '. Verifica che Sort Pulito sia chiuso e il lettore collegato.') from None
    finally:
        port.close()
