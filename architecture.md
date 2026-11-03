# Architettura del pilota

## Distribuzione

GitHub conserva il codice. La demo in docs è statica e portabile su un hosting web. Il database operativo e i report reali rimangono privati e separati dal repository.

Il dominio e il fornitore del servizio applicativo saranno scelti dopo aver verificato le risorse disponibili, l'autenticazione e i collegamenti con la lavanderia. Nessuna dipendenza da GitHub Pages per il futuro database.

## Identità e provenienza

Ogni importazione ha un hash del contenuto, archivio di provenienza e tipo di report. La chiave esterna della persona è archivio + CLIEID, quando disponibile. Lo stesso CLIEID può rappresentare persone diverse in due archivi.

Nei report anagrafici e dei tag che non espongono CLIEID, il nominativo e il reparto sono candidati per la riconciliazione, non chiavi definitive. Omonimi e varianti devono essere verificati. I dati originali restano disponibili.

Scorte, dotazioni e persone sono entità distinte. Tag, capo fisico e assegnazione devono avere identità e storici separati.

## Movimenti

Il report di movimento associa un ingresso e/o un'uscita al tag. L'acquisizione conserva la riga originale. Le registrazioni normalizzate mantengono la precisione disponibile: una data priva di ora resta una data, senza generare un orario fittizio.

Le letture iniziali sono ingresso sporco e uscita pulito alla ricomposizione. Non equivalgono a ritiro presso il cliente, fine lavaggio o consegna. Eventuali punti futuri all'ingresso e all'uscita di un tunnel diventano nuovi tipi di evento verificati.

Tag assenti dall'elenco attivo possono appartenere allo storico. Un'assegnazione diversa nei movimenti non deve sovrascrivere quella attuale.

## Consegne

Il modello distingue cliente, sede, servizio, soggetto che esegue la lavorazione, punto di ritiro e trasportatore. Partite di origini diverse possono appartenere alla stessa consegna prevista.

Ogni partita mantiene preparazione e documento indipendenti, con visibilità riunita per destinazione. Quantità in pezzi, roll e kg mantengono unità distinte e non vengono sommate fra loro.

Una lettura pulito non cambia automaticamente lo stato in consegnato. Emissione documentale, ritiro e consegna sono operazioni esplicite e tracciate.

## Sequenza operativa prevista

1. Verifica e acquisizione privata dei CSV.
2. Riconciliazione delle identità e dei capi.
3. Database condiviso e accessi distinti per ufficio, produzione, autisti, terzisti e clienti.
4. Distinte operative, numerazione documenti, versioni e stampa.
5. Portale clienti, etichette QR e conferme dei trasporti.
6. Integrazione RFID e contabilità sulla base delle interfacce effettivamente disponibili.

La demo navigabile e l'importatore di acquisizione sono implementati. Le altre parti sono requisiti di sviluppo, non funzionalità già attive.
