import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

STATION=Path(__file__).resolve().parents[1]/'station'
sys.path.insert(0,str(STATION))
from desktop.cloud import CloudAPI,CloudError
from desktop.config import Preferences,backend_config
from desktop.credentials import TokenStore
from desktop.startup import application_name
from desktop.app import self_test
from desktop.labels import render_labels

class DesktopTests(unittest.TestCase):
    def test_login_and_refresh_never_send_password_to_data_api(self):
        sent=[]
        def transport(request):
            sent.append(request)
            if '/auth/v1/token' in request.full_url:return {'access_token':'fixture-access','refresh_token':'fixture-refresh','expires_in':3600}
            return []
        client=CloudAPI({'url':'https://fixture.supabase.co','publishableKey':'sb_publishable_fixture'},transport)
        client.login('fixture@example.invalid','fixture-password')
        self.assertIsNone(sent[0].get_header('Authorization'))
        self.assertEqual(json.loads(sent[0].data)['password'],'fixture-password')
        client.rpc('rf_snapshot',p_session='fixture')
        self.assertEqual(sent[-1].get_header('Authorization'),'Bearer fixture-access')
        self.assertNotIn('password',sent[-1].data.decode())
        client.expires=time.time()-1
        client.rpc('rf_snapshot',p_session='fixture')
        self.assertIn('grant_type=refresh_token',sent[-2].full_url)
        self.assertEqual(json.loads(sent[-2].data),{'refresh_token':'fixture-refresh'})
        with self.assertRaises(ValueError):client.rpc('arbitrary_database_command')

    def test_unauthenticated_data_access_is_blocked_without_a_request(self):
        client=CloudAPI({'url':'https://fixture.supabase.co','publishableKey':'sb_publishable_fixture'},lambda _:self.fail('Network called'))
        with self.assertRaises(CloudError):client.snapshot('fixture')

    def test_pending_open_survives_restart_with_same_identifier(self):
        with tempfile.TemporaryDirectory() as folder:
            prefs=Preferences(folder);arguments={'p_station':'station-a','p_client':'client-a','p_archive':'tutti','p_mode':'collaudo'}
            first=prefs.open_command(arguments)
            self.assertEqual(Preferences(folder).open_command(arguments),first)
            with self.assertRaises(ValueError):prefs.open_command({**arguments,'p_client':'other-client'})
            self.assertNotIn('password',prefs.path.read_text())
            prefs.save(pending_open=None)
            self.assertNotEqual(prefs.open_command(arguments)['id'],first['id'])

    def test_no_plaintext_token_fallback_on_other_platforms(self):
        import os
        if os.name=='nt':self.skipTest('Windows encryption is covered by packaged executable self-test')
        with tempfile.TemporaryDirectory() as folder:
            store=TokenStore(folder)
            with self.assertRaises(RuntimeError):store.save('fixture-refresh')
            self.assertFalse(store.path.exists())

    def test_label_preview_escapes_imported_text_and_marks_test_data(self):
        text=render_labels([{'id':'fixture-job','payload':{'mode':'collaudo','client':'Demo','site':'Sede','archive':'ospiti','slot':1,'subject':{'name':'<script>bad()</script>','department':'Piano'},'count':2,'garments':[{'article':'<img src=x>'}],'station':'Armadio test','closed_at':'2026-11-05'}}])
        self.assertNotIn('<script>',text);self.assertNotIn('<img src=x>',text)
        self.assertIn('&lt;script&gt;',text);self.assertIn('COLLAUDO',text)
        self.assertIn('default-src',text)

    def test_both_entrypoints_have_valid_public_config_and_durable_queue(self):
        self.assertTrue(backend_config()['publishableKey'].startswith('sb_publishable_'))
        for kind in ['sporco','pulito']:
            report=self_test(kind)
            self.assertEqual(report['kind'],kind);self.assertEqual(report['queue'],'ok')
            self.assertFalse(report['hardware_connected']);self.assertEqual(report['mode'],'collaudo')
        self.assertEqual(application_name('sporco'),'Sporco')
        self.assertEqual(application_name('pulito'),'Pulito')
        with self.assertRaises(ValueError):application_name('unknown')

if __name__=='__main__':unittest.main()
