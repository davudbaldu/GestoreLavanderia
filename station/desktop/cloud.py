"""HTTPS client for the same authenticated backend used by the web management app."""
import json
import time
import urllib.error
import urllib.request


class CloudError(Exception):
    pass


class CloudAPI:
    def __init__(self, config, transport=None):
        self.url = config['url']
        self.key = config['publishableKey']
        self.token = None
        self.refresh_token = None
        self.expires = 0
        self.transport = transport or self._transport

    @staticmethod
    def _transport(request):
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response) if response.status != 204 else None

    def _request(self, path, body=None, auth=True):
        if auth:
            if not self.token:
                raise CloudError('Accedi con il tuo account abilitato.')
            if time.time() > self.expires - 30 and self.refresh_token:
                self.refresh()
        headers = {'apikey': self.key, 'Content-Type': 'application/json', 'Cache-Control': 'no-store'}
        if auth:
            headers['Authorization'] = 'Bearer ' + self.token
        request = urllib.request.Request(self.url + path,
            data=None if body is None else json.dumps(body).encode(), headers=headers,
            method='GET' if body is None else 'POST')
        try:
            return self.transport(request)
        except urllib.error.HTTPError as error:
            try:
                data = json.loads(error.read())
                detail = data.get('message') or data.get('msg') or data.get('error_description')
            except (ValueError, AttributeError):
                detail = None
            if error.code==404 and path.startswith('/rest/v1/rf_'):
                detail='Il modulo delle postazioni non è ancora attivato sul gestionale. Puoi intanto rilevare i dispositivi.'
            raise CloudError(detail or 'Richiesta non completata: HTTP ' + str(error.code)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise CloudError('Collegamento al server non disponibile. Le letture già accodate restano sul PC.') from None

    def _session(self, response):
        if not response.get('access_token'):
            raise CloudError('Accesso non completato.')
        self.token = response['access_token']
        self.refresh_token = response.get('refresh_token')
        self.expires = time.time() + response.get('expires_in', 3600)
        return response

    def login(self, email, password):
        return self._session(self._request('/auth/v1/token?grant_type=password', {'email': email, 'password': password}, False))

    def refresh(self, token=None):
        value = token or self.refresh_token
        if not value:
            raise CloudError('Accedi nuovamente al gestionale.')
        return self._session(self._request('/auth/v1/token?grant_type=refresh_token', {'refresh_token': value}, False))

    def rpc(self, name, **arguments):
        allowed = {'rf_start_session', 'rf_read_batch', 'rf_close_session', 'rf_snapshot', 'rf_configure_slots', 'rf_print_attempt'}
        if name not in allowed:
            raise ValueError('Comando di postazione non valido')
        return self._request('/rest/v1/rpc/' + name, arguments)

    def lists(self):
        members = self._request('/rest/v1/app_members?select=user_id&active=eq.true')
        if not members:
            raise CloudError('Account registrato ma non abilitato al gestionale.')
        return (self._request('/rest/v1/rf_stations?select=*&order=code.asc'),
                self._request('/rest/v1/rf_clients?select=*&order=name.asc'),
                self._request('/rest/v1/rf_session_list?select=*&status=eq.aperta&order=opened_at.desc'))

    def read_batch(self, session_id, events):
        return self.rpc('rf_read_batch', p_session=session_id, p_events=events)

    def snapshot(self, session_id, before=None):
        return self.rpc('rf_snapshot', p_session=session_id, p_before=before)

    def labels(self, session_id):
        import uuid
        session_id=str(uuid.UUID(session_id))
        return self._request('/rest/v1/rf_label_status?select=*&session_id=eq.'+session_id+'&order=slot.asc')
