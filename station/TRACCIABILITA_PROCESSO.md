# Tracciabilità capi: dal ritiro alla spedizione (proposta di sviluppo)

## Obiettivo
Seguire il percorso reale di un singolo capo, preservando la differenza tra una
lettura RFID **osservata** e una fase **dedotta** dal passaggio di un lotto.

La vista operatore Pulito resta semplice: capo -> identificazione -> CASELLA N,
nessuna conferma per capo e nessun comando LED. Alla chiusura, movimenti di
**ricomposizione** e un'etichetta per ogni casella usata; la **spedizione** è un
evento diverso.

## Stato attuale (10 novembre 2026)
- Tunnel sporco e antenna HF TAGSYS Medio P200u del pulito già identificati.
- Il lettore HF in prova ha restituito un tag reale di 16 caratteri; la lettura
  automatica è una funzione di **collaudo** non ancora autorizzata in produzione.
- Il database dispone di rf_reads, rf_allocations, rf_sessions, rf_label_jobs,
  rf_print_attempts e rf_movements.
- La migrazione `ricomposizione_distinta_uscita` corregge l'evento di chiusura
  armadio da `uscita_pulito` a `ricomposizione` nel database ospitato.
  `uscita_pulito` resta riservato alla spedizione effettiva, ancora da collegare
  ai DDT; nessuna riga storica viene riscritta.
- La preview attuale delle etichette non garantisce l'avvenuta stampa sulla Zebra.
- Le stazioni hardware_ready=false devono restare non abilitate alla produzione
  fino al collaudo.
- L'installazione di USBPcap/Wireshark sul precedente PC armadio è stata
  seguita da problemi gravi di avvio; non serve né viene richiesta in questo pilota.

## Modello eventi proposto
| Fase | Evidenza iniziale | Evento conservato |
|---|---|---|
| Ingresso sporco | Tunnel RFID, lettura capo | `ingresso_sporco` |
| Lettura | Ogni antenna o palmare | `lettura_rfid` (osservazione, non cambio fase) |
| Cernita | Lettura puntuale o lotto assegnato | `cernita` |
| Lavaggio | Lotto + lavatrice + inizio/fine ciclo | `lavaggio_inizio`, `lavaggio_fine` |
| Asciugatura | Lotto + macchina + ciclo | `asciugatura_inizio`, `asciugatura_fine` |
| Stiratura | Lettura capo a uscita stiro o lotto | `stiratura` |
| Ricomposizione | Tag letto + assegnazione casella confermata a chiusura | `ricomposizione` |
| Uscita | DDT / carico autista / spedizione confermata | `uscita` |

Alcuni capi saltano fasi (ad esempio stiro o asciugatrice) e altri sono
lavorati da terzisti: il modello non deve inventare passaggi. Ogni fase deve
supportare `non_applicabile` e `non_rilevata`, senza spacciarle per osservate.

### Schema minimo per la futura tabella append-only
- `event_id` UUID: idempotenza ed evita duplicazioni, incluse ristampe.
- `source_record_id`, `tag`, `client_id`, `session_id` dove disponibili.
- `stage` e `event_kind` (inserimento, inizio, fine, lettura, eccezione).
- `occurred_at` e `recorded_at`: non inventare l'ora del processo.
- `source_method`: `rfid_singolo`, `lettura_lotto`, `macchina`,
  `manuale`, `ddt`; `confidence`: osservato, associato_a_lotto,
  stimato (in quest'ultimo caso non presentarlo come certezza).
- `reader_id`, `machine_id`, `batch_id`, `actor_id`, `slot`, `ddt_id`.
- Contesto `metadata` con schema validato, nessuna credenziale o dato eccedente.

La transizione per capi singoli tramite lotto può essere descritta con una
associazione evento-lotto e capo-lotto: `il lotto ha fatto il ciclo` non è la
stessa evidenza di `ogni capo è stato letto all'uscita`.

## Proposta di rollout in sicurezza
1. **Pulito senza LED, in collaudo:** lettura continua COM del lettore esistente,
   casella grande su schermo soltanto dopo esito autorevole; seconda lettura
   dello stesso capo senza movimento extra; chiusura + etichette.
2. **Separazione semantica:** migrazione versionata con `ricomposizione` distinta
   da `uscita`. Audit, permessi e verifiche su replay/chiusure.
3. **Spedizione confermata:** carico tramite DDT digitale, altro evento di uscita.
4. **Cernita/stiro:** nuove antenne solo dove i test dimostrano letture puntuali
   e assenza di interferenze; prima pilotare un punto ad alta resa.
5. **Lavaggio/asciugatura:** identificare carrelli/lotti, associare macchine e
   cicli; non è obbligatorio che la singola antenna legga tessuti bagnati
   all'interno di una macchina.
6. **Dashboard:** posizione nota e ultima fase osservata, tempo per fase,
   code, ritardi, eccezioni, scarti e rinvii a ricomposizione.

## Gate prima della produzione
- Test di 100+ capi con più letture consecutive, omonimi, tag mancanti e
  duplicati, riconnessione COM e problemi di rete.
- Misurare ritardo reale scansione -> assegnazione, nessuna casella errata
  mostrata, nessuna perdita silenziosa di eventi.
- Distinguere conclusione sessione, movimento di ricomposizione, preparazione
  etichette, effettiva stampa e reale uscita dal laboratorio.
- Verifica su un PC di prova / finestra di manutenzione; mantenere NewPod
  disponibile e un backup degli originali.

## Demo pubblica interattiva (solo dati fittizi)

Aprire https://dggunlnrkpqescejogro.supabase.co/functions/v1/pulito-demo
per usare un simulatore browser di 90 caselle, lettura di singoli capi o pila
rapida, gestione ripetizioni e tag sconosciuti, chiusura, movimenti di
ricomposizione ed etichette demo. La funzione è pubblica e NON accede al DB.
Non è un software collegato al lettore; non usare per produzione.
