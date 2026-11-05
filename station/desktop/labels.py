"""Escaped local print preview; opening a preview is never a print acknowledgement."""
from html import escape


def render_labels(jobs):
    def safe(value):return escape(str(value if value is not None else ''))
    sections=[]
    for job in jobs:
        payload=job['payload'];subject=payload['subject']
        items=' · '.join(safe(item.get('article') or item.get('tag')) for item in payload['garments'])
        sections.append('<section><small>'+('COLLAUDO — NON USARE IN PRODUZIONE' if payload['mode']=='collaudo' else 'ETICHETTA BUSTA')+'</small><p>'+safe(payload['client'])+' · '+safe(payload['site'])+' · '+safe(payload['archive'])+'</p><h1>Casella '+safe(payload['slot'])+'</h1><h2>'+safe(subject['name'])+'</h2><p>'+safe(subject.get('department'))+' · Piano '+safe(subject.get('floor'))+'</p><strong>'+safe(payload['count'])+' capi</strong><p>'+items+'</p><footer>'+safe(payload['station'])+' · '+safe(payload['closed_at'])+' · '+safe(job['id'])+'</footer></section>')
    return '<!doctype html><html lang="it"><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'"><title>Etichette delle buste</title><style>body{font:15px Segoe UI,sans-serif;color:#142b48;background:#f3f6fb;margin:25px}section{padding:24px;margin-bottom:24px;border:1px solid #bac6cf;border-radius:12px;background:white;break-inside:avoid}h1{font-size:32px;margin:12px 0}h2{font-size:24px;margin:12px 0}footer,small{font-size:11px}small{font-weight:bold}footer{margin-top:20px}@media print{body{background:white;margin:0}section{break-after:page}}</style><p>Anteprima: usa il comando Stampa del browser. L’apertura non conferma una stampa fisica.</p>'+''.join(sections)+'</html>'
