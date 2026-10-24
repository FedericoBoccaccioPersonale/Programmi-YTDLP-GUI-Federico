# Come contribuire

Sono felice di accettare contributi. L' intero processo di compilazione è automatizzato tramite GitHub Actions, quindi non dovrai preoccuparti di fornire eseguibili, ma solo codice sorgente pulito.

## Traduzioni (aggiungere una nuova lingua o migliorare quelle esistenti)
1. Fai un fork del repository.
2. Copia il file `locales/it.json` (o di una lingua che conosci meglio) e rinominalo con il codice ISO della lingua (es. `es.json`, `fr.json`).
3. Traduci i valori a destra mantenendo invariate le chiavi a sinistra.
4. Traduci possibilmente anche i vari file di documentazione e modifica il readme per includere riferimenti ai nuovi file tradotti.
5. Apri una Pull Request.

Le traduzioni sono responsabilità degli autori e revisionatori.

## Sviluppo del codice
- Il progetto rifiuta l' uso di Python dal lato utente, ma il motore è scritto in Python tramite `PySide6`.
- PySide6 è stato scelto in quanto libreria GUI multipiattaforma.
- Usa l' indentazione con tab.
- Fine riga: i file del progetto usano il fine riga LF (quello di GitHub e di Linux), non CRLF. Se modifichi i file con un editor locale su Windows, impostalo su LF (in Visual Studio Code: clicca «CRLF» nella barra in basso a destra e scegli «LF») e dai a Git il comando `git config core.autocrlf input`; altrimenti un confronto tra due versioni mostra tutte le righe come modificate. L' editor online di GitHub usa già LF.
- Testa sempre la compilazione avviando un branch personale con GitHub Actions prima di inviare una Pull Request al ramo principale.
- Qualsiasi modifica alla logica di yt-dlp deve essere validata assicurandosi che non rompa l' etichettatura dei metadati di FFmpeg.
- Se conosci python meglio di me, sentiti libero di migliorare l' architettura del progetto... senza rompere nulla e rispettando le specifiche.

## Specifiche di GitHub Actions
- Appaiono una lista di pulsanti che permettono di compilare per le specifiche piattaforme, e un pulsante che genera output per tutte le piattaforme.
- Ad ogni compilazione, il sistema scaricherà automaticamente l' ultima versione di yt-dlp (con i componenti JavaScript e `curl-cffi`, necessaria per scaricare i sottotitoli di YouTube), PySide6, PyInstaller e certifi tramite il gestore di pacchetti pip. Questi strumenti sono incorporati nel programma.
- Poichè anche mettere in cache FFmpeg occupa troppa banda, e anzi credo abbia aumentato il consumo, FFmpeg non è incorporato nell' eseguibile unico: è il programma stesso a scaricare le build statiche precompilate (FFmpeg e FFprobe, e anche Deno) e a posizionarle accanto all' eseguibile compilato. Le fonti sono BtbN per Windows e Linux, Martin Riedl per macOS Apple Silicon ed evermeet.cx per macOS Intel (non compilato dai workflow); Deno si scarica dalle release ufficiali su GitHub.
- Siccome le lingue sono in file separati, anche queste verranno incluse nello zip.
- Nomenclatura ZIP: L' archivio finale segue il formato: YTDLP-GUI-Federico-[Versione]-[SistemaOperativo].zip. La versione è l' ultimo tag del repository (escluso `anteprima`) seguito dalla data di compilazione nel formato yyyy-mm-dd, ad esempio `V1.2_2026-10-21`; il sistema operativo è `Windows-x64`, `Linux-x64` o `macOS-arm64`. Prima di compilare deve quindi esistere almeno un tag (su GitHub: Releases > Draft a new release > Choose a tag > Create new tag), altrimenti la compilazione si ferma con un errore.
- Ci sono due workflow, che differiscono solo per la destinazione: `build (crea artefatto).yml` salva gli zip come artefatti (conservati un giorno), `build (crea release).yml` li allega alla pre-release `anteprima`.
- Il file `versione.py` non è nel repository (è ignorato da Git): lo crea il workflow durante la compilazione, con il numero di versione. Avviando il programma dai sorgenti non esiste e compare «sviluppo». Senza questo file sembra che il programma non possa conoscere il proprio numero di versione.
- La cartella `ico` contiene l' icona: il workflow applica il `.ico` (Windows) o il `.icns` (macOS) all' eseguibile con `--icon` e incorpora il `.png` per l' icona della finestra.
- Leggi anche la guida per [pubblicare](pubblicare.md).

#### Questa è la teoria. La pratica è che ci sono delle limitazioni irrisolvibili.
* Si ostina a compilare con componenti deprecati

Escono questi orrori (hai letto bene: con la "o")
> **Annotations**
> 
> 4 notices
> 
> |   |
> |---|
> |**Configurazione matrice**<br><br>"The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026. For more information, see [https://github.com/actions/runner-images/issues/14748](https://github.com/actions/runner-images/issues/14748)"|
> |**Preparazione Release di anteprima**<br><br>"The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026. For more information, see [https://github.com/actions/runner-images/issues/14748](https://github.com/actions/runner-images/issues/14748)"|
> |**macOS arm64**<br><br>Due to capacity constraints, jobs targeting macOS arm64 runners may experience longer queue times.|
> |**Linux x64**<br><br>"The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026. For more information, see [https://github.com/actions/runner-images/issues/14748](https://github.com/actions/runner-images/issues/14748)"|

* Sarebbero dovuti essere 3 pulsanti invece è uscita una combo
