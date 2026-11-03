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

La demo non include ancora autenticazione applicativa, database condiviso, emissione DDT definitiva, QR code o connessione ai lettori RFID. Le modifiche demo alle consegne sono salvate soltanto nel browser. I risultati delle analisi CSV restano in memoria.

Prima di attivare dati reali per più utenti servono accessi e permessi verificati, database privato, backup, ripristino e collegamento alle postazioni di lettura. GitHub Pages serve la demo statica; il servizio applicativo richiede hosting separato.

Vedi [architettura del pilota](architecture.md).

## Database privato

È predisposto lo [schema PostgreSQL/Supabase](database/README.md) con accesso riservato, versioni dei report e controlli automatici dei permessi. L'attivazione del progetto e il caricamento richiedono il collegamento al servizio; nessun dato operativo è presente nel repository.

## Area riservata

L'interfaccia di consultazione è in `docs/riservato.html`. Usa Supabase Auth e le policy del database per leggere report, anagrafiche, tag e movimenti. La configurazione frontend contiene solo l'URL del progetto e la chiave pubblicabile. Le sessioni restano in memoria e nessuna chiave segreta è inclusa.

Il proprietario abilita il primo account con un codice personale, valido una sola volta e con scadenza. La verifica dell'email è obbligatoria. Il codice non è nel repository; nel database è conservato solo il suo hash. La sola registrazione non concede accesso ai dati.

Gli originali importati e le segnalazioni risiedono nel database privato e non vengono distribuiti con il sito. La demo in `docs/index.html` rimane separata dai dati operativi.
