"""Escaped local print preview; opening a preview is never a print acknowledgement."""
from html import escape


def prepare_label_batch(jobs):
    """Validate one immutable backend label per occupied slot, in numeric order.

    This prepares data only; it has no printer transport or print acknowledgement.
    Refuse mixed sessions and duplicates instead of silently dropping labels.
    """
    jobs = list(jobs)
    if not jobs:
        raise ValueError('Nessuna etichetta disponibile.')
    sessions, slots, identifiers = set(), set(), set()
    for job in jobs:
        payload = job['payload']
        slot, count = payload['slot'], payload['count']
        if type(slot) is not int or not 1 <= slot <= 500 or job['slot'] != slot:
            raise ValueError('Casella etichetta non valida.')
        if type(count) is not int or count < 1 or count != len(payload['garments']):
            raise ValueError('Conteggio capi dell’etichetta non valido.')
        if slot in slots or job['id'] in identifiers:
            raise ValueError('Etichette duplicate: verifica il batch prima della stampa.')
        if job['session_id'] != payload['session'] or not payload['closed_at']:
            raise ValueError('Sessione etichetta non valida.')
        slots.add(slot)
        identifiers.add(job['id'])
        sessions.add(job['session_id'])
    if len(sessions) != 1:
        raise ValueError('Il batch contiene etichette di armadi diversi.')
    return sorted(jobs, key=lambda job: job['payload']['slot'])


def render_labels(jobs):
    jobs=prepare_label_batch(jobs)
    def safe(value):return escape(str(value if value is not None else ''))
    sections=[]
    for job in jobs:
        payload=job['payload'];subject=payload['subject']
        items=' · '.join(safe(item.get('article') or item.get('tag')) for item in payload['garments'])
        sections.append('<section><small>'+('COLLAUDO — NON USARE IN PRODUZIONE' if payload['mode']=='collaudo' else 'ETICHETTA BUSTA')+'</small><p>'+safe(payload['client'])+' · '+safe(payload['site'])+' · '+safe(payload['archive'])+'</p><h1>Casella '+safe(payload['slot'])+'</h1><h2>'+safe(subject['name'])+'</h2><p>'+safe(subject.get('department'))+' · Piano '+safe(subject.get('floor'))+'</p><strong>'+safe(payload['count'])+' capi</strong><p>'+items+'</p><footer>'+safe(payload['station'])+' · '+safe(payload['closed_at'])+' · '+safe(job['id'])+'</footer></section>')
    return '<!doctype html><html lang="it"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'"><title>Etichette delle buste</title><style>body{font:15px Segoe UI,sans-serif;color:#142b48;background:#f3f6fb;margin:25px}section{padding:24px;margin-bottom:24px;border:1px solid #bac6cf;border-radius:12px;background:white;break-inside:avoid}h1{font-size:32px;margin:12px 0}h2{font-size:24px;margin:12px 0}footer,small{font-size:11px}small{font-weight:bold}footer{margin-top:20px}@media print{body{background:white;margin:0}.summary{display:none}section{break-after:page}section:last-child{break-after:auto}}</style><p class="summary">Batch di '+str(len(jobs))+' etichette · una copia per casella · ordine numerico. Facsimile HTML: layout Zebra da verificare. Usa il comando Stampa del browser; l’apertura non conferma una stampa fisica.</p>'+''.join(sections)+'</html>'
