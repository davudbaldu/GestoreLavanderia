import importlib.util
import tempfile
import unittest
import uuid
from pathlib import Path

spec=importlib.util.spec_from_file_location('outbox', Path(__file__).resolve().parents[1]/'station'/'outbox.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class OutboxTests(unittest.TestCase):
    def test_network_loss_restart_and_idempotent_resend_keep_same_ids(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'readings.sqlite3';outbox=module.ReadOutbox(path)
            event=outbox.enqueue(str(uuid.uuid4()),'sporco','0000ABCD12345678',metadata={'reader_id':'fixture-reader','antenna_port':1,'rssi':-51});seen=[]
            def interrupted(session, events):
                seen.append(events[0]);raise ConnectionError('Response lost after server commit')
            with self.assertRaises(ConnectionError):outbox.sync_once(interrupted)
            outbox=module.ReadOutbox(path)
            self.assertEqual(outbox.pending(),1)
            def retry(session,events):
                self.assertEqual(events[0],seen[0]);self.assertEqual(events[0]['metadata']['antenna_port'],1);return [{'id':event,'outcome':'accettata'}]
            self.assertEqual(outbox.sync_once(retry),1);self.assertEqual(outbox.pending(),0)

    def test_partial_ack_never_drops_reads_and_clean_is_single_item(self):
        with tempfile.TemporaryDirectory() as folder:
            outbox=module.ReadOutbox(Path(folder)/'readings.sqlite3');session=str(uuid.uuid4())
            one=outbox.enqueue(session,'sporco','ABCD123456780001');two=outbox.enqueue(session,'sporco','ABCD123456780002')
            with self.assertRaises(ValueError):outbox.sync_once(lambda s,e:[{'id':one,'outcome':'accettata'}])
            self.assertEqual(outbox.pending(),2)
            outbox.sync_once(lambda s,e:[{'id':r['id'],'outcome':'tag_sconosciuto'} for r in e])
            clean=str(uuid.uuid4());outbox.enqueue(clean,'pulito','ABCD123456780003');outbox.enqueue(clean,'pulito','ABCD123456780004')
            def single(s,events):
                self.assertEqual(len(events),1);return [{'id':events[0]['id'],'outcome':'accettata'}]
            self.assertEqual(outbox.sync_once(single),1);self.assertEqual(outbox.pending(),1)

if __name__=='__main__':unittest.main()
