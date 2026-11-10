import sys
import time
import unittest
from pathlib import Path
from threading import Event

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "station"))
from desktop.hardware import StandaloneProfile, ProbeError
from desktop.live_reader import UIDFrameDecoder, LiveSerialReader

PROFILE = StandaloneProfile("COM6", 115200, 16, 0, 16)


class FrameTests(unittest.TestCase):
    def test_fragmented_frames_and_separators(self):
        decoder = UIDFrameDecoder(PROFILE)
        self.assertEqual(decoder.feed(b"00000000"), [])
        self.assertEqual(decoder.feed(b"12345678\r\nE00403502B1BB749"), ["0000000012345678", "E00403502B1BB749"])

    def test_invalid_frame_is_rejected(self):
        with self.assertRaises(ProbeError):
            UIDFrameDecoder(PROFILE).feed(b"!00403502B1BB749")


class FakePort:
    def __init__(self):
        self.closed = False
        self.reads = [b"E00403502B1BB749\r\nE00403502B1BB749"]
        self.writes = []
        self.read_count = 0

    def open(self):
        self.settings_on_open = (self.port, self.baudrate, self.dtr, self.rts, self.rtscts)

    def reset_input_buffer(self):
        pass

    def read(self, count):
        self.read_count += 1
        if self.reads:
            return self.reads.pop(0)
        time.sleep(0.005)
        return b""

    def write(self, data):
        self.writes.append(data)
        raise AssertionError("Serial writing is forbidden")

    def close(self):
        self.closed = True


class LiveReaderTests(unittest.TestCase):
    def test_continuous_reader_emits_uid_once_and_never_transmits(self):
        port = FakePort()
        events = []
        seen = Event()
        def emit(item):
            events.append(item)
            if item[0] == "tag":
                seen.set()
        worker = LiveSerialReader(PROFILE, emit, serial_factory=lambda: port)
        worker.start()
        self.assertTrue(seen.wait(2), events)
        worker.stop()
        self.assertTrue(port.closed)
        self.assertEqual(port.writes, [])
        self.assertEqual(port.settings_on_open, ("COM6", 115200, False, False, False))
        self.assertEqual([e[1] for e in events if e[0] == "tag"], ["E00403502B1BB749"])

    def test_malformed_uid_never_emitted(self):
        port = FakePort()
        port.reads = [b"invalid:12345678"]
        events = []
        worker = LiveSerialReader(PROFILE, events.append, serial_factory=lambda: port)
        worker.start()
        for _ in range(100):
            if any(e[0] == "state" and e[1] == "stopped" for e in events):
                break
            time.sleep(0.01)
        worker.stop()
        self.assertFalse(any(e[0] == "tag" for e in events))


if __name__ == "__main__":
    unittest.main()
