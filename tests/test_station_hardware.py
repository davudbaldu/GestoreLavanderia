import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'station'))
from desktop.hardware import StandaloneProfile, ProbeError, profile_from_settings, probe_reader


SETTINGS = '''<Settings><MAIN RfidReaderType="StandAlone" RfidReaderCOMport="6"
 DBPassword="fixture-private-value" DBUser="fixture-user" />
 <StandAloneReader Port="COM6" Bps="115200" DataBits="8" Parity="No" StopBit="1"
 RTS="No" PacketLength="16" StartOffset="0" FieldLength="16" PacketContain="" /></Settings>'''


class FakePort:
    def __init__(self, chunks=(), busy=False):
        self.chunks = iter(chunks)
        self.busy = busy
        self.closed = False
        self.opened = False
        self.before_open = None

    def open(self):
        self.before_open = (self.port, self.baudrate, self.dtr, self.rts, self.rtscts)
        if self.busy:
            raise OSError('Fixture: busy serial port')
        self.opened = True

    def reset_input_buffer(self):
        pass

    def read(self, count):
        return next(self.chunks, b'')

    def write(self, value):
        raise AssertionError('A reader probe must never transmit bytes')

    def close(self):
        self.closed = True


class HardwareProbeTests(unittest.TestCase):
    def profile(self):
        return StandaloneProfile('COM6', 115200, 16, 0, 16)

    def parse(self, text):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Settings.config'
            path.write_text(text, encoding='utf-8')
            return profile_from_settings(path)

    def test_config_import_retains_only_validated_reader_settings(self):
        profile = self.parse(SETTINGS)
        self.assertEqual(profile, self.profile())
        saved = json.dumps(profile.public_settings())
        self.assertNotIn('fixture-private-value', saved)
        self.assertNotIn('DBPassword', saved)
        self.assertNotIn('fixture-user', saved)

    def test_conflicting_port_or_nonstandalone_profile_is_refused(self):
        with self.assertRaises(ProbeError):
            self.parse(SETTINGS.replace('RfidReaderCOMport="6"', 'RfidReaderCOMport="5"'))
        with self.assertRaises(ProbeError):
            self.parse(SETTINGS.replace('RfidReaderType="StandAlone"', 'RfidReaderType="VendorSDK"'))
        with self.assertRaises(ProbeError):
            self.parse(SETTINGS.replace('RTS="No"', 'RTS="Yes"'))

    def test_xml_entities_and_unbounded_packet_settings_are_refused(self):
        with self.assertRaises(ProbeError):
            self.parse('<!DOCTYPE Settings [<!ENTITY a "fixture">]>' + SETTINGS)
        with self.assertRaises(ProbeError):
            self.parse(SETTINGS.replace('PacketLength="16"', 'PacketLength="99999"'))
        with self.assertRaises(ProbeError):
            self.parse(SETTINGS.replace('Port="COM6"', 'Port="file://fixture"'))

    def test_fragmented_uid_preserves_zeroes_and_never_transmits(self):
        port = FakePort([b'\r\n', b'0000ab', b'cd12345678'])
        result = probe_reader(self.profile(), factory=lambda: port, clock=lambda: 0)
        self.assertEqual(result['status'], 'ricevuto')
        self.assertEqual(result['tag_candidate'], '0000ABCD12345678')
        self.assertEqual(result['movements_created'], 0)
        self.assertEqual(port.before_open, ('COM6', 115200, False, False, False))
        self.assertTrue(port.closed)

    def test_unexpected_frame_is_returned_for_review_without_guessing(self):
        port = FakePort([b'!0000ABCD12345678'])
        result = probe_reader(self.profile(), factory=lambda: port, clock=lambda: 0)
        self.assertEqual(result['status'], 'formato_da_verificare')
        self.assertNotIn('tag_candidate', result)
        self.assertTrue(port.closed)

    def test_timeout_releases_port_and_reports_incomplete_input(self):
        ticks = iter([0, .1, 2])
        port = FakePort([b'0000'])
        result = probe_reader(self.profile(), seconds=1, factory=lambda: port, clock=lambda: next(ticks))
        self.assertEqual(result['status'], 'nessun_codice_completo')
        self.assertEqual(result['bytes_received'], 4)
        self.assertTrue(port.closed)

    def test_cancelled_probe_does_not_open_any_port(self):
        result = probe_reader(self.profile(), factory=lambda: self.fail('Port created'), cancelled=lambda: True)
        self.assertEqual(result['status'], 'annullata')

    def test_busy_port_fails_without_falling_back_to_another_device(self):
        port = FakePort(busy=True)
        with self.assertRaises(ProbeError):
            probe_reader(self.profile(), factory=lambda: port)
        self.assertTrue(port.closed)


if __name__ == '__main__':
    unittest.main()
