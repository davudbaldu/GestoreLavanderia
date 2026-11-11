# Gestore Lavanderia

Prima versione del gestionale, utilizzabile da PC e smartphone. Questo repository pubblico contiene solo codice e dati fittizi.

## Cosa è già disponibile

- Panoramica operativa e navigazione responsive.
- Anagrafiche demo distinte fra ospiti, personale, scorte e dotazioni.
- Ricerca capi/tag e scheda del capo.
- Movimenti con precisione della data esplicita.
- Distinte dimostrative per laboratorio interno e terzista, con passaggi preparazione → pronto → ritirato → consegnato.
- Stampa delle distinte o salvataggio PDF dal browser. Le distinte demo non sono DDT validi.
- Analisi CSV NewPod sul dispositivo: nessuna richiesta di rete, nessun caricamento dei report, dati mantenuti in memoria.
- Importatore Python che conserva i file acquisiti per versione in un database SQLite privato, senza modificare gli originali.

## Aprire la demo online

In **Settings → Pages → Build and deployment**, scegliere:

- Source: **Deploy from a branch**
- Branch: **main**
- Folder: **/docs**
- **Save**

GitHub mostrerà il link della demo quando la pubblicazione sarà completata. L'attivazione di Pages non può essere eseguita dalle normali azioni di scrittura del codice.

## Prova locale

La demo non richiede installazioni o compilazione. Aprire \`docs/index.html\` nel browser oppure servire la cartella con:

\`\`\`text
python -m http.server 8000 --directory docs
\`\`\`

Aprire http://localhost:8000.

## Verificare i CSV dal browser

Aprire **Importazioni CSV**, scegliere i report e indicare l'archivio Ospiti o Divise per ciascuno. Premere **Analizza i report**. Gli originali non vengono modificati e i report non vengono inviati a GitHub o ad altri server.

Sono supportati i report con intestazioni NewPod di tag attivi, anagrafiche e movimenti. Il controllo individua date non valide, incongruenze delle date con gli indicatori, tag storici assenti dall'elenco attivo e differenze di assegnazione. Non ricostruisce passaggi di produzione non registrati. Le righe prive di uscita non costituiscono una giacenza.

## Acquisizione privata per versione

Richiede Python 3.11 o successivo, senza librerie esterne. Il database deve trovarsi fuori dal repository.

\`\`\`text
python tools/newpod_import.py --csv "C:\percorso-privato\movimenti.csv" --archive ospiti --audit-only
python tools/newpod_import.py --csv "C:\percorso-privato\movimenti.csv" --archive ospiti --db "C:\percorso-privato\pilota.sqlite3"
\`\`\`

Ripetere lo stesso file non duplica l'acquisizione. Una nuova versione conserva quella precedente. Le righe ambigue e anomale vengono conservate e segnalate, senza deduplicazione distruttiva e senza unire persone per semplice corrispondenza del nome.

Il database SQLite è un'area di acquisizione, non il database condiviso dell'applicazione.

## Controlli

\`\`\`text
node --test tests/core.test.cjs
python -m unittest discover -s tests -p "test_*.py" -v
python tools/check_project.py
\`\`\`

Il workflow GitHub Actions esegue questi controlli a ogni aggiornamento di main.

## Perimetro e prossimi passi

La pagina dimostrativa rimane separata dall’area autenticata, che dispone di un database privato condiviso e del modulo di preparazione. Emissione DDT definitiva, QR code e connessione ai lettori RFID restano da realizzare. Le modifiche demo alle consegne sono salvate soltanto nel browser. I risultati delle analisi CSV restano in memoria.

Prima dell’uso operativo da parte di più ruoli servono permessi dedicati verificati, backup e ripristino collaudati e collegamento alle postazioni di lettura. GitHub Pages serve la demo statica; il servizio applicativo richiede hosting separato.

Vedi [architettura del pilota](architecture.md).

## Database privato

È predisposto lo [schema PostgreSQL/Supabase](database/README.md) con accesso riservato, versioni dei report e controlli automatici dei permessi. L'attivazione del progetto e il caricamento richiedono il collegamento al servizio; nessun dato operativo è presente nel repository.

## Area riservata

L'interfaccia di consultazione è in `docs/riservato.html`. Usa Supabase Auth e le policy del database per leggere report, anagrafiche, tag e movimenti. La configurazione frontend contiene solo l'URL del progetto e la chiave pubblicabile. Le sessioni restano in memoria e nessuna chiave segreta è inclusa.

Il proprietario abilita il primo account con un codice personale, valido una sola volta e con scadenza. La verifica dell'email è obbligatoria. Il codice non è nel repository; nel database è conservato solo il suo hash. La sola registrazione non concede accesso ai dati.

Gli originali importati e le segnalazioni risiedono nel database privato e non vengono distribuiti con il sito. La demo in `docs/index.html` rimane separata dai dati operativi. Le distinte reali si trovano esclusivamente nell’area riservata.

## Preparazione condivisa e installazione

L'area riservata comprende **Consegne e preparazione**: articoli, contenitori,
revisioni e conferme di pronto/ritiro/consegna sono salvati nel database privato.
L'accesso iniziale è limitato al proprietario abilitato. Le distinte operative
non sono ancora DDT emessi e non sono collegate alle letture RFID.

Il manifest permette di installare il gestionale dai browser compatibili quando
servito in HTTPS o su localhost. Se disponibile compare **Installa app**; è
possibile usare anche il comando di installazione del browser. Su iPhone/iPad si
usa il menu Condividi → Aggiungi alla schermata Home. Questa prima versione
richiede connessione per i dati condivisi e non conserva operazioni offline.

Il software installato alle antenne e agli armadi sarà un componente separato,
con protocolli hardware e continuità operativa da collaudare sull'impianto.

## Programmi Windows delle postazioni

Sono presenti due entry point nativi: `station/sporco.py` e `station/pulito.py`.
Il workflow **Build Windows stations** genera `Sporco.exe` e `Pulito.exe` su
Windows, esegue il collaudo del pacchetto e conserva i download come artefatti.
Le istruzioni sono in `station/INSTALLAZIONE.txt`.

Questa prima versione è di collaudo: può collegarsi al backend autenticato,
conservare osservazioni e provare i flussi. Pulito ha un adattatore seriale
StandAlone RX-only predisposto, da collaudare sull'antenna reale. Non invia
comandi LED né stampa direttamente su Zebra. L'avvio automatico configurabile è all'accesso
Windows. Il funzionamento prima del login e il sorting offline completo
richiedono componenti successivi.

La demo [Pulito nel browser](docs/pulito-demo.html) usa dati fittizi e un menu
nascosto. Gli errori hanno testo grande esplicito e cancellano la casella attiva.
Per stato effettivo, formati Zebra recuperati e prove ancora necessarie, leggere
[collaudo antenna e stampa](station/COLLAUDO_ANTENNA_ZEBRA.md).
