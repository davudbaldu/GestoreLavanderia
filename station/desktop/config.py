"""Public backend configuration and per-user, non-secret station preferences."""
import json
import os
import sys
import uuid
from threading import RLock
from pathlib import Path
from urllib.parse import urlsplit


def backend_config():
    bundled = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2])) / 'station-backend.json'
    if bundled.is_file():
        data = json.loads(bundled.read_text(encoding='utf-8'))
    else:
        source = Path(__file__).resolve().parents[2] / 'docs' / 'backend-config.js'
        text = source.read_text(encoding='utf-8')
        data = json.loads(text[text.index('{'):text.rindex('}') + 1])
    url = urlsplit(data['url'])
    if url.scheme != 'https' or not url.hostname or not url.hostname.endswith('.supabase.co') or url.path not in ('', '/') or url.username or url.password:
        raise ValueError('Configurazione del server non valida.')
    if not str(data['publishableKey']).startswith('sb_publishable_'):
        raise ValueError('Serve una chiave pubblicabile, non una chiave amministrativa.')
    return {'url': data['url'].rstrip('/'), 'publishableKey': data['publishableKey']}


def data_directory(kind):
    if kind not in ('sporco', 'pulito'):
        raise ValueError('Postazione non valida')
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local' / 'share')
    directory = base / 'GestoreLavanderia' / kind
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class Preferences:
    def __init__(self, directory):
        self.lock = RLock()
        self.path = Path(directory) / 'station.json'
        self.data = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}

    def save(self, **values):
        with self.lock:
            self.data.update(values)
            temporary = self.path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.data, indent=2), encoding='utf-8')
            temporary.replace(self.path)

    def open_command(self, arguments):
        with self.lock:
            pending = self.data.get('pending_open')
            if pending and pending['arguments'] != arguments:
                raise ValueError('Un’apertura è ancora da verificare. Riprendi la sessione prima di cambiare struttura.')
            if not pending:
                pending = {'id': str(uuid.uuid4()), 'arguments': arguments}
                self.save(pending_open=pending, station_id=arguments['p_station'])
            return pending
