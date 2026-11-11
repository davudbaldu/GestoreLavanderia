"""Operator stop messages: explicit cause, known ownership and no slot guidance."""


def blocked_read_message(outcome, snapshot=None):
    snapshot = snapshot or {}
    titles = {
        'tag_sconosciuto': 'TAG NON PRESENTE\nNEGLI ARCHIVI',
        'cliente_diverso': 'CLIENTE ERRATO\nFERMA IL CAPO',
        'archivio_diverso': 'ARCHIVIO ERRATO\nFERMA IL CAPO',
        'tag_ambiguo': 'TAG DA VERIFICARE',
        'tag_non_valido': 'CODICE NON VALIDO',
        'identita_da_verificare': 'DESTINATARIO\nDA VERIFICARE',
        'altro_armadio': 'CAPO GIÀ IN\nUN ALTRO ARMADIO',
        'armadio_pieno': 'ARMADIO PIENO',
        'sessione_chiusa': 'SESSIONE CHIUSA',
    }
    detail = 'Nessuna casella assegnata. Metti il capo da parte per la verifica.'
    if outcome == 'tag_sconosciuto':
        detail += ' Assente dagli archivi importati disponibili; proprietario non identificabile.'
    elif outcome in ('cliente_diverso', 'archivio_diverso'):
        archive = {'ospiti': 'OSPITI', 'divise': 'DIVISE OPERATORI'}.get(
            snapshot.get('archive'), 'ARCHIVIO NON DISPONIBILE')
        owner = ' · '.join(filter(None, [snapshot.get('name'), snapshot.get('client'), snapshot.get('site'), archive]))
        detail = 'Appartiene a: ' + owner + '. ' + detail
    elif outcome == 'tag_ambiguo':
        detail += ' Il tag risulta associato a più record: proprietario da verificare.'
    return titles.get(outcome, 'FERMA IL CAPO'), detail
