import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'station'))
from desktop.labels import prepare_label_batch, render_labels


def label(slot, count=1):
    return {'id': f'job-{slot}', 'session_id': 'session-a', 'slot': slot,
            'payload': {'session': 'session-a', 'slot': slot, 'count': count,
                        'mode': 'collaudo', 'client': 'Demo', 'site': 'Sede',
                        'archive': 'ospiti', 'subject': {'name': 'Persona demo'},
                        'garments': [{'tag': f'TAG-{i}'} for i in range(count)],
                        'station': 'Armadio demo', 'closed_at': '2026-11-11'}}


class LabelBatchTests(unittest.TestCase):
    def test_one_label_per_slot_sorted_numerically_without_mutating_payloads(self):
        jobs = [label(10, 3), label(2, 2), label(1)]
        before = copy.deepcopy(jobs)
        batch = prepare_label_batch(jobs)
        self.assertEqual([j['slot'] for j in batch], [1, 2, 10])
        self.assertEqual(jobs, before)
        html = render_labels(jobs)
        self.assertEqual(html.count('<section>'), 3)
        self.assertLess(html.index('Casella 2'), html.index('Casella 10'))
        self.assertIn('una copia per casella', html)
        self.assertNotIn('<script', html)

    def test_mixed_sessions_duplicate_slots_and_ids_are_blocked(self):
        for field in ('session', 'slot', 'id'):
            with self.subTest(field=field):
                jobs = [label(1), label(2)]
                if field == 'session':
                    jobs[1]['session_id'] = jobs[1]['payload']['session'] = 'session-b'
                elif field == 'slot':
                    jobs[1]['slot'] = jobs[1]['payload']['slot'] = 1
                else:
                    jobs[1]['id'] = jobs[0]['id']
                with self.assertRaises(ValueError):
                    prepare_label_batch(jobs)

    def test_invalid_counts_slot_or_payload_session_are_blocked(self):
        for field, value in [('count', 2), ('count', 0), ('slot', '1'), ('slot', True), ('session', 'other'), ('closed_at', '')]:
            with self.subTest(field=field, value=value):
                job = label(1)
                job['payload'][field] = value
                with self.assertRaises(ValueError):
                    prepare_label_batch([job])
        with self.assertRaises(ValueError):
            prepare_label_batch([])


if __name__ == '__main__':
    unittest.main()
