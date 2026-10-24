# Roadmap del progetto

Questo documento elenca le funzionalità ipotetiche per le future versioni. Non ci sono tempistiche ma puoi collaborare.

- [ ] **Pulsante annulla:** Per bloccare il download e chiedere se conservare o cancellare i file già creati.
- [ ] Avvisare quando l' analisi non ha trovato alcun video.
- [ ] Analisi anche degli url che contengono anche la playlist
- [ ] **Code di download:** Possibilità di incollare più URL e metterli in coda, impostando parametri globali o specifici per ogni elemento.
- [ ] **Template nome file:** Inserimento di una stringa personalizzabile nelle impostazioni per definire il nome del file generato (es. `%(title)s - %(uploader)s [%(resolution)s].%(ext)s`).
- [ ] **Aggiornamento In-App:** Pulsante per forzare l' aggiornamento interno del motore `yt-dlp` senza dover riscaricare l' intera interfaccia da GitHub.
- [ ] **Aggiornamento programma** Pulsante per controllare (magari in automatico) la disponibilità di aggiornamenti del programma e non solo delle librerie.
- [ ] **Supporto profili:** Salvataggio di preset (es. "Musica", "Video alta qualità") per richiamare rapidamente impostazioni complesse. Questo prevederà la gestione di eccezioni quando la traccia richiesta è assente.
- [ ] **Supporto ad account:** Per consentire di scaricare video privati.
- [ ] **Ricerca Playlist:** Ricerca, almeno sullo stesso canale, delle playlist che contengono questo video.
- [ ] **Navigatore contenuti:** YB ha la cattiva abitudine di elencare male playlist e video, quindi intendo realizzare un modulo che le elenca tutte, senza caricamento allo scorrimento e indicando il nome per esteso.
- [ ] **Download asincrono della miniatura:** Al momento la miniatura del video viene scaricata nel thread principale, in caso di rete lenta blocca la finestra.
