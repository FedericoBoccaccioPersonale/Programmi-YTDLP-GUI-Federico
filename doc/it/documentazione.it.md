# Interfaccia grafica per yt-dlp (Nome in codice: YTDLP-GUI-Federico)

*(Nota: Questo file in lingua italiana è il documento di riferimento ufficiale per il progetto. Le traduzioni in altre lingue sono subordinate a questo documento).*

YTDLP-GUI-Federico è un' interfaccia grafica multipiattaforma gratuita (Windows, macOS, Linux) per lo strumento a riga di comando `yt-dlp`, notoriamente ostico. È progettata per essere semplice da usare pur mantenendo il controllo granulare sulle tracce audio, video e sottotitoli, e per fare ciò che le altre interfacce non fanno.

> ## 🔊 Audio multilingua
> **Scarica le tracce audio in tutte le lingue disponibili.**
> Se un video offre più lingue audio (doppiaggio dell' autore o traduzione automatica), il programma le elenca tutte e ti lascia scegliere quali scaricare, anche più di una. Puoi salvarle come file separati oppure unirle in un unico file MKV/MKA, senza ricompressione.

## Guida rapida
Al primo avvio farà scaricare le librerie necessarie, agli avvi successivi controllerà la presenza di aggiornamenti.
Inserisci l' url YouTube nel campo in alto, quindi premi Analizza (in azzurro).
Quando la barra di stato indica la fine dell' analisi seleziona le tracce dalle shcede a destra.
Se vuoi puoi modificare la cartella di destinazione.
Premi il pulsante (verde) di download in basso.

### Note di sviluppo
Non richiede l' installazione di Python, FFmpeg né Deno sul sistema host: il programma è un unico file eseguibile scaricabile dalle release; FFmpeg e Deno vengono scaricati dal programma stesso, chiedendo conferma, e li posiziona accanto all' eseguibile. È quindi necessario posizionare il programma in una cartella con permessi di scrittura. Quindi su windows evita `Programmi`.
* Il programma è compilato quindi python non è necessario (evvai! 🎉🎉🎉🎉)
* La presenza di FFmpeg viene controllata dal programma all' avvio. Se non è presente o è presente una versione superata chiede di scaricarlo e quindi lo aggiorna
* yt-dlp viene integrato, insieme ai componenti JavaScript necessari a YouTube.
* Anche Deno (l' interprete JavaScript che yt-dlp usa per mostrare tutti i formati di YouTube) viene controllato all' avvio: se manca chiede di scaricarlo, e se esiste una versione più recente chiede di aggiornarlo. Senza Deno alcuni formati possono mancare.
* i file di lingua sono in una cartella a parte così da poter essere scaricati o creati singolarmente

Nota su Deno: non ne avevo mai sentito parlare.

## Specifiche attuali

- **Estrazione dati:** Analizza URL supportati da yt-dlp e mostra l' anteprima della copertina.
- **Selezione tracce disponibili:**
  - Risoluzioni e framerate ordinati dal più alto al più basso tra quelle disponibili da YouTube. Le tracce video sono raggruppate per risoluzione e framerate: su ogni riga c' è la risoluzione (es. 1080p60) seguita da una casella per ogni formato disponibile (codec, bitrate).
  - Elenco completo e accurato di tutte le tracce audio effettivamente presenti, rese disponibili da YouTube, consentendo di selezionarle e scaricarle singolarmente o in combinazione. Le tracce sono raggruppate per lingua: su ogni riga c' è il nome della lingua seguito da una casella per ogni formato disponibile per quella lingua.
  - Ogni traccia che YouTube espone è elencata, di qualsiasi tipo (video, audio, sottotitoli e altre); quelle che YouTube non espone non sono elencate. Se l' utente ne seleziona una, il programma trova il modo per scaricarla. I sottotitoli hanno una riga per lingua con, per ogni variante (come Italiano generico, Italiano-Italia, Italiano-Svizzera), una casella per ogni tipo (manuale, automatico): ogni casella è indipendente e rappresenta una traccia.
  - Le tracce che non sono né video né audio (per esempio gli storyboard di YouTube) sono nella scheda "Altre tracce", visibile solo se il sito ne espone, e si scaricano come file separati nomeFile.tipo.dimensione.ext. Sono elencati anche gli audio senza codec noto (HLS di YouTube).
  - Lingue audio e sottotitoli ordinate in base alle lingue preferite specificate (es. tutte le varianti `it-*` se impostato `it`), seguite dalle altre lingue in ordine alfabetico.
  - Distinzione chiara tra tracce (video/audio/sottotitoli) manuali (caricate dall' autore) e tracce generate/tradotte automaticamente. Questa distinzione viene memorizzata anche nel nome della traccia.
  - Il programma cerca un campo fornito da YouTube per sapere per ogni traccia se è automatica o manuale.
  
  - L' utente selezionerà quali tracce scaricare (anche multiple).
- **Controlli di sessione vs Impostazioni permanenti:**
  - Le opzioni di sessione (modalità di salvataggio tracce, gestione sottotitoli, formato sottotitoli e SponsorBlock) sono posizionate visivamente sotto l' anteprima video per una configurazione rapida e immediata.
  - I valori predefiniti per i controlli di sessione sono configurabili e salvati in modo permanente insieme alle preferenze globali (lingua dell' interfaccia, lingue preferite, cartella di salvataggio predefinita) nel file `config.json`.
  - Quando modifichi un' impostazione il pulsante cambia ad indicare che non sono salvate.
- **Modalità di salvataggio e unificazione tracce:** L' utente sceglie se unificare le tracce selezionate in un unico file o scaricarle come file separati. Il programma deciderà automaticamente il contenitore (**MKV** per video o **MKA** per solo audio nel caso di file unificato) e salverà i flussi nativi senza alcuna ricompressione. Eventuali ricompressioni o conversioni per adattarsi ad altri formati o dispositivi esulano dallo scopo di questo programma.
- **Capitoli e SponsorBlock:** Estrazione e inclusione automatica dei capitoli originali del video, con contrassegno `[SponsorBlock]` aggiunto ai capitoli corrispondenti a sezioni sponsorizzate quando è attiva la marcatura dei segmenti.
- **Avanzamento del download:** Monitoraggio costante e lineare dell' avanzamento globale (0-100%), eliminando blocchi o fluttuazioni al 99%.
- **Barra di stato:** In fondo alla finestra una barra colorata dice cosa sta facendo il programma e quando ha finito: azzurro per «Analisi in corso...» e «Scaricamento in corso...», verde per «Analisi completata» e «Download completato», arancione quando c' è un' attesa (ad esempio per l' errore 429 dei sottotitoli tradotti) o quando l' operazione è finita con avvisi, rosso quando non è riuscita. Il significato è sempre scritto a parole: il colore non è l' unico indicatore. Se il video non ha sottotitoli, la scheda dei sottotitoli mostra «Nessuno».
- **Numero di versione:** Il numero di versione è l' ultimo tag del repository GitHub (escluso `anteprima`) al momento della compilazione, seguito dalla data di compilazione (UTC) nel formato yyyy-mm-dd, ad esempio `V1.2_2026-10-21`. Compare nel titolo della finestra, in ogni voce di `errori.log` e nel nome dello zip (`YTDLP-GUI-Federico-V1.2_2026-10-21-Windows-x64.zip`). Se il programma è avviato dai sorgenti, al posto del numero compare «sviluppo». Compilare senza che esista alcun tag è un errore.
- **Sottotitoli esterni:** Quando l' utente sceglie di salvare i sottotitoli in file esterni, questi vengono nominati con la struttura `nomeFile.lingua.ext`, riconosciuta da VLC. I sottotitoli automatici hanno aggiunta la dicitura "auto", ottenendo così la forma `nomeFile.auto.lingua.ext`; le traduzioni indicano anche la lingua da cui sono tradotte: nomeFile.auto.lingua.da-origine.ext (es. nomeFile.auto.it.da-en.ext).
- **Sottotitoli interni (embed):** Sono memorizzati con l' indicazione della lingua e con il nome completo della traccia come titolo (es. Italiano (Svizzera) - Automatico).
- Tracce audio e video seguono le stesse regole dei sottotitoli.\
  Segue spiegazione a prova di IA (spero):\
  **Tracce audio, video e altre:** Ogni traccia ha un nome completo. Nel file unito è il titolo del flusso (es. `Italiano (Italia) - Sintetica / Tradotta - mp4a 129k`, `1080p60 - avc1 5686k`). Se le tracce sono salvate separatamente, i file si chiamano `nomeFile.lingua.ext` per le originali, `nomeFile.auto.lingua.ext` per le sintetiche o tradotte, `nomeFile.1080p60.ext` per il video e `nomeFile.storyboard.160x90.ext` per le altre; se più tracce avrebbero lo stesso nome, a tutte si aggiunge l' ID del formato.
- **Solo sottotitoli:** Se l' utente seleziona solo sottotitoli (nessuna traccia video o audio), il programma non scarica il video. Con i sottotitoli esterni salva un file per sottotitolo. Con i sottotitoli integrati in un unico file chiede conferma, avvisando che è meglio salvarli come tracce esterne, e crea un unico file Matroska con i soli sottotitoli (nomeFile.mks), con lingua e nome completo di ogni traccia; se l' unione non riesce, i sottotitoli restano file esterni.
- **Sottotitoli automatici tradotti:** YouTube limita le richieste dei sottotitoli tradotti automaticamente in un' altra lingua (errore 429 🤬). Il programma aspetta 20 s dall' estrazione prima di scaricarli e, a ogni errore, aumenta l' attesa di ulteriori 30 s e riprova (fino a 4 volte, quindi aspetta prima 20, poi altri 50, poi altri 80, poi altri 110). La barra di stato in fondo alla finestra mostra l' attesa e l' errore, così l' utente sa che il download non è terminato. Per ogni lingua YouTube espone la traccia nella lingua stessa (se esiste) e una traduzione per ogni altra traccia del video da cui la traduce: ogni traccia ha la sua casella ("Automatico", "Tradotto da en", "Tradotto da de-DE"...) e l' utente sceglie. Se un sottotitolo non si riesce a scaricare, il resto del download prosegue e un avviso elenca le tracce mancanti.
- **Pannello impostazioni permanenti:** Consente di definire la lingua dell' interfaccia (predefinito: rilevamento automatico della lingua di sistema o inglese se non disponibile), la lista ordinata delle lingue preferite e la cartella di salvataggio predefinita. Include anche tre caselle di spunta (abilitate per impostazione predefinita) per ricevere un avviso di conferma prima del download se non è stata selezionata alcuna traccia video, audio o sottotitolo. Un secondo gruppo contiene i valori predefiniti dei controlli di sessione: modalità di salvataggio delle tracce (file unico MKV/MKA o file separati), gestione dei sottotitoli (integrati o esterni), formato dei sottotitoli (srt, vtt, ass, lrc) e SponsorBlock (disattivato, rimozione o marcatura). L' inclusione embed dei sottotitoli è subordinata alla creazione di un file unico.
- **Metadati testuali e comando equivalente:** Al termine del download, il programma salva un file `.txt` avente lo stesso nome base del file principale (nella forma `nomeFile.txt`) contenente l' URL sorgente, il comando CLI equivalente di `yt-dlp` (ovvero il comando che l' utente dovrebbe lanciare da terminale per ottenere lo stesso risultato | NOTA: a causa di una cattiva implementazione in `yt-dlp`, usa la sigla della lingua come chiave, o questo è quello che giura l' IA, quindi il comando equivalente può dividersi in più righe), titolo completo, autore (uploader), nome del canale (channel), tag e descrizione; i campi che YouTube non fornisce non vengono scritti (il titolo mancante è "Sconosciuto"). Viene creato anche un secondo file  `nomeFile_metadata.txt` che contiene tutti i metadati documentati da yt-dlp che siano convertibili in testo (quindi non le immagini); a titolo di esempio ma non esaustivo: id, webpage_url_basename, extractor_key, _type, media_type, ext, uploader_id, channel_follower_count, creators, upload_date, duration, description, tags, categories, cast, location, age_limit, subtitles (lista di quelli disponibili), format_id, width, height, aspect_ratio, resolution, dynamic_range, fps, series, series_id, season, season_number, season_id, track, track_number, track_id, artists, composers, genres, album, album_type, album_artists, disc_number, entries, playlist_count. Dopo i campi, contiene l' elenco di tutte le tracce disponibili (video, audio, sottotitoli e altre tracce), una riga per traccia con nome completo e dettagli tecnici.
- **Multilingua:** Interfaccia nativamente in Italiano e Inglese, estendibile con file JSON.
- **Integrazione SponsorBlock:** Possibilità di attivare lo skip o la marcatura dei segmenti sponsorizzati direttamente dall' interfaccia. Ciò è gestito direttamente da una funzione esposta da yt-dlp.
- **Nessun errore silenzioso:** Tutte le eccezioni vengono catturate e mostrate visivamente all' utente tramite finestre di dialogo native.
- **Architettura multithreading:** Classi QThread distinte (analisi dei dati, download, e download e controllo degli aggiornamenti di FFmpeg e di Deno) in modo che l' interfaccia grafica non si blocchi mai durante le operazioni di rete o di elaborazione di FFmpeg.
- **Pulsanti principali dell' interfaccia:**
  - Il pulsante **Analizza** è evidenziato in colore azzurro ad alto contrasto sin dal caricamento del programma.
  - Il pulsante **Scarica** diventa di colore verde ad alto contrasto non appena viene abilitato (dopo il completamento dell' analisi) e mantiene la colorazione verde anche quando disabilitato per renderlo chiaramente visibile.
- **Avvisi sulle tracce selezionate:**
  - Se l' utente non ha selezionato **alcuna traccia** (0 video, 0 audio, 0 sottotitoli, 0 altre), il download viene bloccato con un avviso.
  - Se l' utente ha dimenticato di selezionare almeno una traccia di ogni tipo (video, audio o sottotitolo), e le relative caselle nelle impostazioni permanenti sono attive, compaiono sequenzialmente fino a 3 finestre di dialogo di conferma (in ordine: prima Video, poi Audio, poi Sottotitoli) che chiedono all' utente se intende procedere comunque, evidenziando il tipo di traccia mancante in colore rosso. Se l' utente seleziona "No" a uno qualsiasi degli avvisi, il download viene annullato con un messaggio di conferma. Questa impostazione è stata preferita rispetto a un messaggio unico perchè si suppone che al primo avvio del programma non si abbia letto la documentazione nè esplorato il programma e quindi si preme download senza aver selezionato niente; mentre dalla volta successiva, al massimo ci si dimentica di una singola traccia.
- **Avviare il download:** In fondo al form è presente un campo per selezionare il nome del file di destinazione, predefinito il titolo del video stesso. Accanto il pulsante per iniziare il download. A questo punto il programma si occuperà di scaricare le tracce e unirle (se impostato), ottenendo i/il file richiesto.
- **Pannelli ridimensionabili:** tra il pannello con l' anteprima e le opzioni di sessione e le schede c' è un divisore: si trascina con il mouse per allargare l' uno o l' altro. Allargando la finestra, lo spazio in più va alle schede.

## Nota
Python è il male supremo. L' ho usato solo per coerenza con yt-dlp, così da avere maggiori possibilità di ottenere un programma compatibile per le stesse piattaforme. Pertanto non lo conosco granchè e l' implementazione è generata da IA.
Per tua informazione (cosa che credo di aver già scritto altrove) odio python almeno per le seguenti ragioni:
- Per definire i blocchi usa l' indentazione
- e questo è un problema perchè visualmente tab o 4 spazi sono la stessa cosa, ma dal punto di vista dell' interprete mescolare tab e spazi è un disastro, e copiando il codice dal web si rischia di fare confusione
- quando rientri da un lungo if dentro a un altro if e magari un ciclo ti ritrovi con numerosi spazi e incolonnarli correttamente (sono 5 o 6?) diventa complicato
- per di più i programmatori python sembrano prediligere lo spazio (che aumenta il numero di caratteri) e questo dimostra che questo linguaggio non fa per me

OK, in effetti è più un argomentazione unica. Quello che dovrebbe interessarti se intendi aiutarmi nello sviluppo del programma, è che qui uso i tab.

Buona parte della dimensione dell' eseguibile, che supera i 50MB (su Windows) e i 100 (su Linux), è dovuto alla libreria grafica e a curl_cffi, la libreria che permette a yt-dlp di scaricare i sottotitoli di YouTube (nella compilazione per Linux ne aggiunge circa 18MB).\
FFmpeg pesa circa 160MB, altri 160 per FFprobe, Deno circa 100 MB.\
Spazio totale stimato circa 500MB.

## Avviso
Ho potuto testare solo la versione per Windows.

## Istallazione (o megli estrazione)
1. Vai nella scheda Releases (linkata nel readme) e scarica lo zip per il tuo sistema operativo.
2. Estrailo in una cartella in cui hai il permesso di scrittura, senza separare l' eseguibile dalla cartella `locales`. Nessuna installazione richiesta (almeno su Windows).
3. Avvia il programma. Ad ogni avvio verifica la presenza di FFmpeg e Deno e chiede conferma per scaricarli se mancano o non sono aggiornati.

yt-dlp è integrato nel programma e si aggiorna con le nuove versioni compilate su GitHub Actions. FFmpeg e Deno invece li aggiorna il programma stesso.

### Requisiti
* Windows x64 (testato), Linux x64 e macOS con processore Apple Silicon (arm64) (compilati ma non testati). I Mac con processore Intel non sono attualmente supportati.
* Linux: serve la libreria `libxcb-cursor0` (su Fedora e Arch si chiama `xcb-util-cursor`), senza la quale Qt non riesce ad avviare l' interfaccia. Esempio su Ubuntu: `sudo apt install libxcb-cursor0`.
* Connessione a Internet: altrimenti non arrivi a YB!
* Posiziona il programma in una cartella in cui possa scrivere: accanto all' eseguibile verranno salvati config.json, errori.log, ffmpeg, ffprobe e deno.
* La cartella locales accanto all' eseguibile, con i file di lingua. È presente nel download.

Senza FFmpeg non è possibile avviare i download. Senza Deno l' analisi funziona, ma alcuni formati di YouTube possono mancare.

## Limitazioni di YT-DLP
yt-dlp può scaricare una qualsiasi delle tracce: gli manca solo un modo per sceglierla dalla riga di comando.

**Come funziona**
1. yt-dlp, quando estrae un video, restituisce per ogni lingua automatica (per esempio `it`) una lista di voci. Possono ad esempio esserci tracce `it` in 56 versioni: 8 tracce, ciascuna in 7 formati. Ogni voce ha il proprio indirizzo, con `lang=<sorgente>` e, se è una traduzione, `tlang=it`.
2. Dalla riga di comando si può dire solo `--sub-langs it`. yt-dlp sceglie da solo una di quelle voci, per formato, e scarica quella.
3. Il programma usa yt-dlp come libreria, non come comando. Nel modulo `sottotitoli.py` c'è una sottoclasse di `YoutubeDL` che sostituisce il passaggio in cui yt-dlp sceglie la voce. Per ogni casella spuntata:
   - tiene solo le voci della traccia scelta (la lingua stessa, oppure «tradotto da de-DE»);
   - chiede al metodo di scelta di yt-dlp di prendere da quelle il formato giusto;
   - consegna il risultato a yt-dlp con un nome diverso per ogni traccia.
4. A quel punto yt-dlp scarica l'indirizzo che gli abbiamo consegnato, come fa sempre.

**Limiti**
- Il comando CLI equivalente non può ripetere la scelta della sorgente, per questo termina con la riga di commento.
- La sottoclasse usa un metodo interno di yt-dlp (`process_subtitles`), non documentato come interfaccia pubblica. Il workflow installa sempre l' ultima versione di yt-dlp: se in una versione futura il metodo cambia, la scelta delle tracce smette di funzionare. Dovrai scaricare a mano una versione precedente.

E con questo il mio programma è appena diventato migliore della libreria che cercavo semplicemente di rendere più facile da usare.

Il funzionamento è stato verificato il 22 ottobre 2026 con yt-dlp 2026.10.21, la versione disponibile in quel momento. Il programma dipende dai **capricci** non solo di YouTube ma anche di yt-dlp: per scegliere da quale traccia è tradotto un sottotitolo, per riparare le unioni dei flussi senza timestamp e per mostrare gli errori di ffmpeg usa parti interne di yt-dlp che il README di yt-dlp non documenta (ad esempio il metodo process_subtitles) e che i suoi autori possono cambiare o togliere senza avviso. Se yt-dlp o YouTube cambiano e il programma smette di funzionare, tu dovrai provare a scaricare manualmente, dalla scheda Releases, una versione precedente del programma, che contiene una versione precedente di yt-dlp; anche questo potrebbe non funzionare, a causa dei capricci di Google. Non ho potuto chiedere al progetto yt-dlp di documentare queste parti né di aggiungere l' opzione alla riga di comando: il progetto vieta l' uso dell' IA per qualsiasi contributo (questo programma è scritto con l' IA) e accetta solo issue tramite moduli predefiniti, non issue libere.

## Roadmap

Consulta il file [ROADMAP.md](ROADMAP.it.md) per conoscere le funzionalità in arrivo.

## Contribuire e codice di condotta

Sei interessato ad aggiungere una lingua o a migliorare il codice? Leggi [CONTRIBUTING.md](Contribuire.it.md) per le istruzioni e [Codice di condotta.md](Codice_di_condotta.it.md) per le regole della community.
