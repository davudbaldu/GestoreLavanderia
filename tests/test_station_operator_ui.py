"""Real Tk operator-view regression tests with synthetic backend responses."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'station'))
from desktop.app import StationApp, tk
from desktop.operator_messages import blocked_read_message


class OperatorMessageTests(unittest.TestCase):
    def test_missing_ownership_is_not_invented(self):
        title, detail = blocked_read_message('tag_sconosciuto')
        self.assertEqual(title, 'TAG NON PRESENTE\nNEGLI ARCHIVI')
        self.assertIn('proprietario non identificabile', detail)
        self.assertIn('ARCHIVIO NON DISPONIBILE', blocked_read_message('archivio_diverso', {})[1])


@unittest.skipUnless(os.name == 'nt' and tk is not None, 'Native Tk rendering requires Windows')
class OperatorUITests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = StationApp('pulito', self.root, directory=self.folder.name)
        self.station = {'id': 'station-demo', 'kind': 'pulito', 'name': 'Armadio demo'}
        self.client = {'id': 'client-demo', 'name': 'Emmaus demo', 'site': 'Sede demo'}
        self.app.show_station(([self.station], [self.client], []))
        self.session = {'id': 'session-demo', 'station_id': 'station-demo', 'client_id': 'client-demo',
                        'archive': 'ospiti', 'status': 'aperta', 'slot_count': 90}

    def tearDown(self):
        self.app.shutdown()
        self.folder.cleanup()

    def display_read(self, outcome, slot=None, snapshot=None):
        self.app.display({'session': self.session, 'station': self.station, 'client': self.client,
                          'counts': {'accepted': 1, 'reads': 2, 'duplicates': 0, 'blocked': 1, 'movements': 0, 'labels': 0},
                          'slots': [{'slot': 1, 'count': 1}],
                          'reads': [{'tag': 'E004000000000001', 'outcome': outcome, 'slot': slot, 'snapshot': snapshot or {}}]})

    def test_red_errors_clear_previous_guidance_and_keep_ownership_visible(self):
        for outcome, text in [('tag_sconosciuto', 'TAG NON PRESENTE\nNEGLI ARCHIVI'),
                              ('cliente_diverso', 'CLIENTE ERRATO'), ('archivio_diverso', 'ARCHIVIO ERRATO')]:
            with self.subTest(outcome=outcome):
                self.display_read('accettata', 1)
                self.assertEqual(self.app.active_slot, 1)
                self.display_read(outcome, snapshot={'name': 'Operatore demo', 'client': 'Altra struttura demo', 'site': 'Altra sede', 'archive': 'divise'})
                self.assertIn(text, self.app.instruction.get())
                self.assertIsNone(self.app.active_slot)
                self.assertEqual(self.app.slot_banner.cget('bg'), '#a61f2b')
                self.assertEqual(self.app.slot_banner.cget('fg'), 'white')
                self.assertEqual(self.app.slot_widgets[1].cget('bg'), '#cbefe7')
                if outcome != 'tag_sconosciuto':
                    self.assertIn('Altra struttura demo', self.app.scan_detail.get())
                    self.assertIn('DIVISE OPERATORI', self.app.scan_detail.get())

    def test_explicit_unknown_message_fits_minimum_window_banner(self):
        from tkinter.font import Font
        self.display_read('tag_sconosciuto')
        self.app.fit_instruction(840)
        font = Font(self.root, font=self.app.slot_banner.cget('font'))
        self.assertGreaterEqual(abs(font.cget('size')), 30)
        for line in self.app.instruction.get().splitlines():
            self.assertLessEqual(font.measure(line), 808)

    def test_multiline_error_and_all_slots_remain_inside_operator_view(self):
        self.display_read('tag_sconosciuto')
        self.root.deiconify()
        self.root.update()
        self.assertGreaterEqual(self.app.hero.content.winfo_height(),self.app.hero_stack.winfo_reqheight())
        bottom=self.app.operator_area.winfo_rooty()+self.app.operator_area.winfo_height()
        for widget in [self.app.slot_widgets[90],self.app.operator_warning]:
            self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),bottom)
        self.assertFalse(self.app.admin_area.winfo_manager())


if __name__ == '__main__':
    unittest.main()
