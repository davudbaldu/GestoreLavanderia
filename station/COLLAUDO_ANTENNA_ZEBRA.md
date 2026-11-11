# Pulito: verifica antenna e stampa Zebra

Stato rilevato l'11 novembre 2026. Ramo `codex/pulito-rapido-senza-led`, PR #2.
Questo documento distingue il codice disponibile dalle prove sull'impianto.

## Antenna HF TAGSYS

Sul PC accessibile in questa sessione l'inventario Windows in sola lettura
(Win32_SerialPort, dispositivi PnP/FTDI e candidati USB RFID) ha restituito:

- Nessuna porta seriale o dispositivo seriale rilevato.
- Nessun candidato USB TAGSYS/FTDI/RFID e nessun processo di lettura riconosciuto.
- Nessuna Zebra installata; solo OneNote e Microsoft Print to PDF.
- Nessun errore di acquisizione dell'inventario completo.

**Connessione fisica HF TAGSYS non verificata.** Questi risultati valgono per il
PC accessibile, senza prova che coincida con il PC sostitutivo dell'armadio.
Non dimostrano che un dispositivo su un altro PC o una connessione diversa
sia scollegato. Nessuna COM è stata aperta e nessun UID reale è stato acquisito.

`desktop/live_reader.py` è predisposto per leggere frame ASCII dal profilo
StandAlone di Sort Pulito: worker separato dalla UI, nessuna `write` seriale,
DTR/RTS richiesti disattivati, nessun comando LED. L'evento `active` significa
che l'apertura COM è riuscita, non che un tag sia stato riconosciuto o che
l'antenna sia collaudata. I test con porte simulate non provano l'hardware.

È presente un'installazione **LaundryClever**, non una configurazione Sort
Pulito identificata e validata. Il suo file dichiara un lettore StandAlone su
COM22 a 115200, campo/pacchetto 19 byte: è una configurazione su disco, non una
COM rilevata e non un profilo da attribuire automaticamente all'HF TAGSYS.
Non usare COM6 o COM22 per supposizione; non provare altre porte a caso.
Il file completo non è stato copiato perché può contenere credenziali.

## Stampa disponibile oggi

La chiusura lato backend prepara `rf_label_jobs`, uno per `(session_id, slot)`.
Il payload contiene cliente/sede/archivio, casella, destinatario, capi e data di
chiusura. La UI Windows legge le etichette della sessione chiusa e apre un HTML
locale. La demo browser usa soltanto dati fittizi e `window.print()` su richiesta.
**Nessuna stampa automatica diretta Zebra è attiva.** Aprire l'HTML, aprire la
finestra di stampa o accodare un lavoro non prova l'uscita fisica dell'etichetta.

Il batch locale ora rifiuta caselle/job duplicati, sessioni mescolate, caselle o
conteggi incoerenti; ordina numericamente e presenta una sola etichetta per
casella occupata, anche con più capi. Riaprire l'anteprima non chiama la chiusura
e non crea movimenti. Il facsimile HTML non è il layout Zebra recuperato.

La migrazione `database/ricomposizione_distinta_uscita.sql` contiene la chiusura
con movimento `ricomposizione`; non è stata interrogata né modificata l'istanza
operativa in questa sessione. Prima della produzione verificarne l'applicazione:
il vecchio schema base usa `uscita_pulito`. La ristampa non deve richiamare la
chiusura né registrare una nuova ricomposizione/uscita.

## Formati recuperati senza modificare NewPod

Letti da `NewPOD/LaundryClever/Reports`, copiati solo nell'area privata locale
`Collaudo locale/Formati Zebra recuperati` esterna al checkout pubblico:

| File | Linguaggio rilevato | Byte | SHA-256 |
| --- | --- | ---: | --- |
| BARCODE.txt | ZPL | 250 | aaac68e8e822459ac650e7f910152cae0abc5e9cefb71aa8b4fc5f9fc1a9c3f0 |
| BARCODE_Zebra_TLP2844.txt | EPL | 153 | 962d1a380b2ffea171b3294e7a5281ca32aeab9ec811e5d8118382eebdbb3ef6 |
| BARCODE_Zebra_ZT230.txt | ZPL | 214 | ba41a9798e97474218bf0e555ed75bbfb78340ff8fce1c7bd2d86c61eba136be |

I segnaposto comprendono struttura, persona, posizione e barcode/tag: sembrano
formati del singolo capo. Non è stato identificato il formato busta usato da
Sort Pulito. Il `LabelPrinter` di LaundryClever dichiara `doPDF v7`, che non
compare tra le stampanti installate. Nessuna di queste impostazioni prova il
modello o la coda della Zebra dell'armadio.

Conservare gli originali e mantenere inizialmente l'aspetto del layout busta
esistente, una volta identificato. Non sostituirlo con il facsimile HTML e non
inventare il significato dei segnaposto. I file ZPL includono anche comandi di
configurazione: non inviarli alla cieca alla stampante condivisa.

## Integrazione proposta, ancora da implementare e collaudare

1. Identificare modello, DPI, driver, linguaggio effettivo (EPL/ZPL), connessione,
   dimensioni/gap/supporto e il layout busta reale. Conservare una copia privata
   con hash e un campione stampato da NewPod; mappare i campi al payload chiuso.
2. Usare uno spooler Windows locale con **coda scelta esplicitamente**, senza
   cambiare stampante predefinita, driver, preferenze NewPod o parametri globali.
   Una seconda coda sullo stesso dispositivo non isola i comandi di configurazione.
   Nessun accesso diretto a COM/USB/TCP 9100 e nessun servizio web di stampa.
3. Dopo verifica del formato, scegliere rendering tramite driver oppure RAW
   EPL/ZPL compatibile. RAW richiede dati già pronti per quel linguaggio: la
   scelta non è automatica dal marchio Zebra. Separare i comandi di setup dal
   layout, sanificare i dati variabili contro comandi/iniezioni, verificare
   accenti, testi lunghi e barcode senza cambiare inizialmente l'aspetto.
4. Worker fuori dal thread UI. Un batch congelato dalla sessione chiusa,
   in ordine di casella, quantità **1 per casella**. Manifest locale con ID
   sessione/job, hash payload/layout, coda, ID spooler ed esiti per etichetta.
   Per esempio 67 caselle occupate producono 67 etichette, non una per capo.
5. Registrare la richiesta separatamente dall'invio allo spooler e dalla verifica
   fisica. `StartDocPrinter`/`WritePrinter` possono bloccare: eseguirli sul worker.
   Un timeout o riavvio dopo invio produce esito **da verificare**, senza retry
   automatico dell'intero batch. Ristampa esplicita delle sole caselle selezionate,
   dopo confronto con etichette già uscite; nessun nuovo movimento.
6. Non fermare/riavviare lo spooler, cancellare code NewPod, ricalibrare la Zebra,
   installare driver o attivare autostart durante la produzione. Collaudare in
   pausa concordata e preservare il ritorno al programma attuale.

Riferimenti: [Microsoft WritePrinter](https://learn.microsoft.com/en-us/windows/win32/printdocs/writeprinter),
[stati dei lavori Windows](https://learn.microsoft.com/en-us/windows/win32/printdocs/job-info-2),
[formati memorizzati Zebra](https://docs.zebra.com/us/en/printers/software/zpl-pg/c-zpl-adv-techn-advanced-techniques/t-zpl-adv-techn-stored-formats.html).
L'accettazione da parte dello spooler non va trattata come verifica fisica.

## Prove fisiche ancora necessarie

- Sul PC sostitutivo: ripetere inventario, riconoscere antenna/adattatore/cavo,
  identificare COM reale e Settings.config di **Sort Pulito**, confrontare il
  lettore e la porta LED. Durante una pausa chiudere soltanto il programma che
  occupa quella COM, senza forzarlo durante le lavorazioni.
- Eseguire la prova RX-only con un capo noto; confrontare UID esatto, zeri e
  formato. Poi provare letture consecutive, ripetizioni, tag assente, altra
  struttura e divise mentre si lavorano gli ospiti; verificare nessuna casella
  per gli errori, latenza e gestione di disconnessione/riconnessione.
- Su Zebra: recuperare layout busta e campione NewPod, confrontare supporto/DPI,
  orientamento, margini, leggibilità e nomi lunghi/accentati. Una sola etichetta
  di prova prima del batch, senza toccare la configurazione produttiva.
- Batch con più capi nella stessa casella e caselle non consecutive; conteggio
  e ordine delle etichette. Provare carta esaurita/offline/interruzione/restart,
  verificare l'esito incerto e la ristampa selettiva senza doppi movimenti.

## Verifiche software di questa modifica

- Suite Python: 38 test, 37 passati e 1 non applicabile a Windows; include test
  reali Tk dei tre banner e delle dimensioni, più seriale simulata RX-only.
- Ispezione visiva Windows con dati sintetici: avviso sconosciuto su due righe
  grandi, menu nascosto e griglia completa da 90 caselle.
- La UI Windows riprende la grafica della demo: pannelli e caselle arrotondati,
  sfondo chiaro, verde petrolio, testi bianchi nel banner e accesso su scheda.
  L'altezza del banner cresce con il testo per evitare tagli negli avvisi.
- Suite JavaScript: 22 test, inclusi tre test del codice effettivo della demo
  per errori, highlight, chiusura, quantità etichette e riapertura senza duplicati.
- Controllo risorse pubbliche e `git diff --check`.
- Nessun collaudo COM/stampante, test SQL sul database operativo o invio RAW.
- La visualizzazione browser del file locale è stata bloccata dalla policy del
  browser protetto; i test DOM non costituiscono verifica visiva mobile/desktop.

Il report dispositivi e le copie dei formati rimangono solo nell'area locale.
