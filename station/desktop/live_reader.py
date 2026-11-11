"""Continuous, input-only HF RFID scanner for the Pulito station.

Runs on a worker thread; callbacks must NOT touch Tk directly.
Opens only the reader COM port described by a verified Settings.config.
It never writes serial bytes, controls COM5/LEDs or sends observations online.
"""
from __future__ import annotations

import re
import threading
import time

from .hardware import ProbeError, StandaloneProfile, serial


class UIDFrameDecoder:
    """Incrementally decode configured fixed-width ASCII hexadecimal frames."""

    def __init__(self, profile: StandaloneProfile):
        self.profile = profile
        self.pending = bytearray()

    def feed(self, chunk: bytes) -> list[str]:
        if not isinstance(chunk, bytes) or len(chunk) > 4096:
            raise ProbeError("Blocco seriale non valido.")
        self.pending.extend(chunk)
        if len(self.pending) > 4096:
            raise ProbeError("Buffer RFID troppo grande: verifica il formato.")
        tags = []
        length = self.profile.packet_length
        while self.pending:
            while self.pending and self.pending[0] in (10, 13):
                del self.pending[0]
            if len(self.pending) < length:
                break
            frame = bytes(self.pending[:length])
            del self.pending[:length]
            field = frame[self.profile.field_offset:self.profile.field_offset+self.profile.field_length]
            if not re.fullmatch(rb"[0-9a-fA-F]{8,64}", field):
                raise ProbeError("Formato RFID inatteso. Nessuna casella assegnata: verifica il lettore.")
            tags.append(field.decode("ascii").upper())
        return tags


class LiveSerialReader:
    """Serial RX-only thread. Emits ('tag', uid) and ('state', status) events."""

    def __init__(self, profile: StandaloneProfile, emit, serial_factory=None,
                 clock=time.monotonic, holdoff_seconds=0.9):
        if not callable(emit):
            raise ValueError("Missing event callback")
        self.profile = profile
        self.emit = emit
        self.factory = serial_factory
        self.clock = clock
        self.holdoff_seconds = holdoff_seconds
        self._stop = threading.Event()
        self._thread = None

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive() and not self._stop.is_set()

    def start(self):
        if self.running:
            raise ProbeError("Lettura continua già attiva.")
        if self._thread is not None and self._thread.is_alive():
            raise ProbeError("La precedente lettura non è ancora terminata.")
        if self.factory is None and serial is None:
            raise ProbeError("La libreria seriale non è disponibile.")
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="pulito-rfid-reader", daemon=True)
        self._thread.start()

    def stop(self, timeout=1.0):
        self._stop.set()
        if self._thread is not None and threading.current_thread() != self._thread:
            self._thread.join(timeout=timeout)

    def _run(self):
        port = None
        decoder = UIDFrameDecoder(self.profile)
        last_tag, last_time = None, None
        try:
            factory = self.factory or serial.Serial
            port = factory()
            port.port = self.profile.port
            port.baudrate = self.profile.baudrate
            port.bytesize, port.parity, port.stopbits = 8, "N", 1
            port.timeout = 0.05
            port.xonxoff = port.rtscts = port.dsrdtr = False
            port.dtr = port.rts = False
            port.open()
            port.reset_input_buffer()
            self.emit(("state", "active", self.profile.port))
            while not self._stop.is_set():
                block = port.read(256)
                if not block:
                    continue
                for tag in decoder.feed(block):
                    now = self.clock()
                    if tag == last_tag and last_time is not None and now - last_time < self.holdoff_seconds:
                        last_time = now
                        continue
                    last_tag, last_time = tag, now
                    self.emit(("tag", tag, self.profile.port))
        except (Exception,) as exc:
            if not self._stop.is_set():
                # Do not leak OS paths or hardware metadata from exception details.
                self.emit(("state", "error", "Lettore non disponibile o formato RFID inatteso; verifica che Sort Pulito sia chiuso e la porta corretta."))
        finally:
            if port is not None:
                try:
                    port.close()
                except Exception:
                    pass
            self.emit(("state", "stopped", self.profile.port))
