import sys
import os
import re
import urllib.request
import traceback
from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
							   QPushButton, QLineEdit, QLabel, QListWidget, QListWidgetItem,
							   QCheckBox, QComboBox, QFileDialog, QProgressBar, QMessageBox,
							   QTabWidget, QGroupBox, QFormLayout, QProgressDialog, QSplitter, QSizePolicy)
from PySide6.QtCore import Qt, QTimer, QEventLoop, QLocale
from PySide6.QtGui import QPixmap, QImage, QCloseEvent, QIcon

from utilita import registra_log, percorso_log, pulisci_nome_file, ottieni_percorso_base, VERSIONE
from config import carica_configurazione, salva_configurazione, ottieni_percorso_config
from lingue import elenca_lingue, rileva_lingua_sistema, unisci_testi, cartelle_locales
from ffmpeg_manager import (verifica_ffmpeg, scaricamento_supportato, piattaforma_ffmpeg,
							ScaricatoreFfmpeg, ControllaAggiornamentoFfmpeg, TIMEOUT_RETE, STATO_OK, STATO_NON_ESEGUIBILE)
from deno_manager import verifica_deno, scaricamento_deno_supportato, nome_eseguibile_deno, ScaricatoreDeno, ControllaAggiornamentoDeno
from workers import Analizzatore, Scaricatore
from tracce import raggruppa_audio, raggruppa_altre, tipo_formato, TIPO_FORMATO_VIDEO, CATEGORIA_ORIGINALE, CATEGORIA_SINTETICA
from sottotitoli import SceltaSottotitolo, TIPO_MANUALE, TIPO_AUTOMATICO, ATTESA_INIZIALE_S, INCREMENTO_ATTESA_S, voci_per_origine
from nomi_tracce import SceltaTraccia, TRACCIA_VIDEO, TRACCIA_AUDIO, TRACCIA_ALTRO, parte_nome_audio, parte_nome_video, parte_nome_altro

MSG_NESSUNA_LINGUA = "No language file found in the folder:\n{cartella}\n\nThe program does not include language files: copy the 'locales' folder next to the executable and restart the program. Until then, interface texts appear as keys."

_finestra = None

# Icona della finestra (barra del titolo e barra delle applicazioni): il PNG della cartella ico. Nell' eseguibile e' incorporato (PyInstaller --add-data);
# l' icona del file .exe / .app e' invece quella indicata con --icon nel workflow.
NOME_ICONA = "Papirus-Team-Papirus-Apps-Youtube-dl.512.png"

# Barra di stato: colori (sfondo, testo) per ogni stato. Il significato e' sempre scritto anche a parole: il colore non e' l' unico indicatore.
STATI_BARRA = {
	"lavoro": ("#e3f2fd", "#0d47a1"),  # operazione in corso: azzurro
	"attesa": ("#fff3e0", "#8a4b00"),  # attesa, errore temporaneo (429) o completato con avvisi: arancione
	"ok": ("#e8f5e9", "#1b5e20"),  # completato: verde
	"errore": ("#ffebee", "#b71c1c"),  # operazione non riuscita: rosso
}

# Pulsante di salvataggio delle impostazioni permanenti quando ci sono modifiche non salvate: grigio scuro con testo bianco (contrasto circa 5:1)
STILE_SALVA_NON_SALVATE = ("QPushButton { background-color: #6e6e6e; color: #ffffff; border: 1px solid #4a4a4a; border-radius: 3px; padding: 4px 12px; } "
						   "QPushButton:hover { background-color: #5f5f5f; } QPushButton:pressed { background-color: #4f4f4f; }")
# Fase evidenziata del lampeggio
STILE_SALVA_LAMPEGGIO = "QPushButton { background-color: #ffd54f; color: #000000; border: 1px solid #b28704; border-radius: 3px; padding: 4px 12px; }"
# Sequenza del lampeggio (due lampi) e durata di ogni fase in millisecondi
FASI_LAMPEGGIO_SALVA = (STILE_SALVA_LAMPEGGIO, STILE_SALVA_NON_SALVATE, STILE_SALVA_LAMPEGGIO, STILE_SALVA_NON_SALVATE)
DURATA_FASE_LAMPEGGIO_MS = 150

# Stile azzurro ad alto contrasto per il pulsante Analizza
STILE_BTN_ANALIZZA = ("QPushButton { background-color: #0277bd; color: #ffffff; font-weight: bold; border: 1px solid #01579b; border-radius: 3px; padding: 4px 12px; } "
					  "QPushButton:hover { background-color: #01579b; } "
					  "QPushButton:pressed { background-color: #002f6c; } "
					  "QPushButton:disabled { background-color: #81d4fa; color: #000000; border: 1px solid #4fc3f7; }")

# Stile verde ad alto contrasto per il pulsante Scarica quando viene attivato
STILE_BTN_SCARICA = ("QPushButton { background-color: #2e7d32; color: #ffffff; font-weight: bold; border: 1px solid #1b5e20; border-radius: 3px; padding: 4px 12px; } "
					 "QPushButton:hover { background-color: #1b5e20; } "
					 "QPushButton:pressed { background-color: #0f3811; } "
					 "QPushButton:disabled { background-color: #a5d6a7; color: #000000; border: 1px solid #81c784; }")

def gestore_eccezioni(tipo, valore, tb) -> None:
	"""Nessuna eccezione non gestita (es. dentro uno slot Qt) resta nascosta nella console."""
	testo = "".join(traceback.format_exception(tipo, valore, tb))
	print(testo, file=sys.stderr)
	registra_log(testo)
	if QApplication.instance() is None:
		return
	box = QMessageBox(_finestra)
	box.setIcon(QMessageBox.Icon.Critical)
	box.setWindowTitle(_finestra.traduci("error") if _finestra else "Error")
	box.setText(f"{tipo.__name__}: {valore}"[:500])
	box.setDetailedText(testo)
	box.setInformativeText(f"{_finestra.traduci('log_saved_in') if _finestra else 'Log:'} {percorso_log()}")
	box.exec()

class FinestraPrincipale(QMainWindow):
	def __init__(self) -> None:
		super().__init__()
		self.avvisi_avvio: List[Tuple[str, dict]] = []
		self.config, errore_config = carica_configurazione()
		self.lingue_disponibili, errori_lingue = elenca_lingue()
		if errore_config:
			self.avvisi_avvio.append(("config_load_error", {"details": errore_config}))
		for e in errori_lingue:
			self.avvisi_avvio.append(("lang_load_error", {"details": e}))

		self.lingua_corrente = self.config.get("lingua_interfaccia", "system")
		if self.lingua_corrente == "system":
			self.lingua_corrente = rileva_lingua_sistema(self.lingue_disponibili)

		self.testi = {}
		self.info_video = {}
		self.elenco_tracce: Dict[str, List[str]] = {"video": [], "audio": [], "subtitles": [], "other": []}
		self._download_in_corso = False
		self._avvisi_operazione = False  # True se l' analisi o il download in corso hanno prodotto avvisi
		self._impostazioni_non_salvate = False
		self._fase_lampeggio = 0
		self.timer_lampeggio = QTimer(self)
		self.timer_lampeggio.timeout.connect(self.passo_lampeggio_salvataggio)
		self.cartella_ffmpeg = ""
		self.versione_ffmpeg = ""
		self.thread_aggiornamento_ffmpeg = None
		self.percorso_deno = ""
		self.versione_deno = ""
		self.thread_aggiornamento_deno = None
		self._esito_ffmpeg: Dict[str, str] = {}
		self._controllo_ffmpeg_attivo = False

		self.carica_lingua()
		self.inizializza_ui()
		QTimer.singleShot(0, self.controlli_avvio)

	def carica_lingua(self) -> None:
		disp = self.lingue_disponibili
		if self.lingua_corrente not in disp:
			originale = self.lingua_corrente
			if "en" in disp:
				fallback = "en"
			elif disp:
				fallback = sorted(disp)[0]
			else:
				self.testi = {}
				self.avvisi_avvio.append(("lang_none", {}))
				return
			self.avvisi_avvio.append(("lang_fallback", {"lang": originale, "fallback": fallback}))
			self.lingua_corrente = fallback
		self.testi, mancanti = unisci_testi(disp, self.lingua_corrente)
		if mancanti:
			registra_log(f"File di lingua '{self.lingua_corrente}': chiavi mancanti: {', '.join(mancanti)}")
			elenco = ", ".join(mancanti[:10]) + (f" ... (+{len(mancanti) - 10})" if len(mancanti) > 10 else "")
			self.avvisi_avvio.append(("lang_missing_keys", {"lang": self.lingua_corrente, "keys": elenco}))

	def traduci(self, chiave: str, **kw) -> str:
		testo = self.testi.get(chiave, chiave)
		if kw:
			try:
				return testo.format(**kw)
			except (KeyError, IndexError, ValueError):
				return testo
		return testo

	def mostra_avvisi_avvio(self) -> None:
		if not self.avvisi_avvio:
			return
		if self.testi:
			testi = [self.traduci(k, **p) for k, p in self.avvisi_avvio]
		else:
			testi = [MSG_NESSUNA_LINGUA.format(cartella=cartelle_locales()[0]) if k == "lang_none" else f"{k}: {p.get('details', p)}" for k, p in self.avvisi_avvio]
		self.avvisi_avvio = []
		registra_log("\n".join(testi))
		QMessageBox.warning(self, self.traduci("warning"), "\n\n".join(testi))

	def mostra_dialogo(self, icona, chiave_titolo: str, breve: str, dettagli: str = "") -> None:
		box = QMessageBox(self)
		box.setIcon(icona)
		box.setWindowTitle(self.traduci(chiave_titolo))
		box.setText(breve)
		if dettagli:
			box.setDetailedText(dettagli)
		box.setInformativeText(f"{self.traduci('log_saved_in')} {percorso_log()}")
		box.exec()

	def chiedi_conferma(self, testo: str, chiave_titolo: str = "ffmpeg_title") -> bool:
		box = QMessageBox(self)
		box.setIcon(QMessageBox.Icon.Question)
		box.setWindowTitle(self.traduci(chiave_titolo))
		box.setText(testo)
		pulsante_si = box.addButton(self.traduci("yes_btn"), QMessageBox.ButtonRole.YesRole)
		box.addButton(self.traduci("no_btn"), QMessageBox.ButtonRole.NoRole)
		box.exec()
		return box.clickedButton() == pulsante_si

	def controlli_avvio(self) -> None:
		# Un solo slot per tenere in sequenza gli avvisi e i controlli di FFmpeg e Deno: timer separati aprirebbero i dialoghi sovrapposti
		self.mostra_avvisi_avvio()
		if self.assicura_ffmpeg(): self.avvia_controllo_aggiornamento_ffmpeg()
		if self.assicura_deno(): self.avvia_controllo_aggiornamento_deno()

	def assicura_ffmpeg(self) -> bool:
		"""True se FFmpeg e' utilizzabile (self.cartella_ffmpeg impostata). Altrimenti propone il download e restituisce l' esito.
		Non e' rientrante: durante il download l' event loop annidato potrebbe far scattare un altro controllo e due thread userebbero lo stesso attributo."""
		if self._controllo_ffmpeg_attivo: return False
		self._controllo_ffmpeg_attivo = True
		try:
			return self.verifica_e_scarica_ffmpeg()
		finally:
			self._controllo_ffmpeg_attivo = False

	def verifica_e_scarica_ffmpeg(self) -> bool:
		try:
			stato = verifica_ffmpeg()
			if stato.codice == STATO_OK:
				self.cartella_ffmpeg = stato.cartella
				self.versione_ffmpeg = stato.versione
				return True
			if not scaricamento_supportato():
				QMessageBox.warning(self, self.traduci("warning"), self.traduci("ffmpeg_manual", system=" ".join(piattaforma_ffmpeg())))
				return False
			destinazione = ottieni_percorso_base()
		except Exception as e:
			registra_log(traceback.format_exc())
			self.mostra_dialogo(QMessageBox.Icon.Critical, "error", self.traduci("ffmpeg_check_error", details=str(e)), traceback.format_exc())
			return False
		if stato.codice == STATO_NON_ESEGUIBILE:
			testo = self.traduci("ffmpeg_unusable", details=stato.dettagli, destination=destinazione)
		else:
			testo = self.traduci("ffmpeg_missing", path=destinazione)
		if not self.chiedi_conferma(testo): return False
		return self.scarica_ffmpeg(destinazione)

	def scarica_ffmpeg(self, destinazione: str) -> bool:
		esito = self.scarica_componente(ScaricatoreFfmpeg(destinazione), "ffmpeg_download_title", "ffmpeg_downloading")
		if esito["esito"] == "ok":
			self.cartella_ffmpeg = esito["cartella"]
			self.versione_ffmpeg = esito["dettagli"]
			QMessageBox.information(self, self.traduci("success"), self.traduci("ffmpeg_download_ok", version=esito["dettagli"], path=esito["cartella"]))
			return True
		if esito["esito"] == "errore":
			self.mostra_dialogo(QMessageBox.Icon.Critical, "error", self.traduci("ffmpeg_download_error", details=esito["dettagli"][:300]), esito["dettagli"])
		return False

	def scarica_componente(self, thread, chiave_titolo: str, chiave_testo: str) -> Dict[str, str]:
		"""Esegue il thread di download di un componente esterno (FFmpeg, Deno) con una barra di avanzamento modale e ne restituisce l' esito."""
		self._esito_ffmpeg = {"esito": "", "cartella": "", "dettagli": ""}
		self._ciclo_ffmpeg = QEventLoop()
		self._dialogo_ffmpeg = QProgressDialog(self.traduci(chiave_testo), self.traduci("cancel_btn"), 0, 100, self)
		self._dialogo_ffmpeg.setWindowTitle(self.traduci(chiave_titolo))
		self._dialogo_ffmpeg.setWindowModality(Qt.WindowModality.WindowModal)
		self._dialogo_ffmpeg.setMinimumDuration(0)
		self._dialogo_ffmpeg.setAutoClose(False)
		self._dialogo_ffmpeg.setAutoReset(False)
		self._dialogo_ffmpeg.setValue(0)

		self.thread_ffmpeg = thread
		self.thread_ffmpeg.progresso.connect(self._dialogo_ffmpeg.setValue)
		self.thread_ffmpeg.fase.connect(self.ffmpeg_fase)
		self.thread_ffmpeg.completato.connect(self.ffmpeg_completato)
		self.thread_ffmpeg.errore.connect(self.ffmpeg_errore)
		self.thread_ffmpeg.annullato.connect(self.ffmpeg_annullato)
		self._dialogo_ffmpeg.canceled.connect(self.thread_ffmpeg.annulla)
		self.thread_ffmpeg.start()
		self._dialogo_ffmpeg.show()
		self._ciclo_ffmpeg.exec()
		self.thread_ffmpeg.wait()
		self._dialogo_ffmpeg.close()
		return self._esito_ffmpeg

	def avvia_controllo_aggiornamento_ffmpeg(self) -> None:
		self.thread_aggiornamento_ffmpeg = ControllaAggiornamentoFfmpeg(self.versione_ffmpeg)
		self.thread_aggiornamento_ffmpeg.trovato.connect(self.ffmpeg_aggiornamento_disponibile)
		self.thread_aggiornamento_ffmpeg.errore.connect(self.ffmpeg_controllo_errore)
		self.thread_aggiornamento_ffmpeg.start()

	def ffmpeg_aggiornamento_disponibile(self, versione_locale: str, versione_remota: str) -> None:
		if self._controllo_ffmpeg_attivo:
			QTimer.singleShot(1000, lambda: self.ffmpeg_aggiornamento_disponibile(versione_locale, versione_remota))
			return
		self._controllo_ffmpeg_attivo = True
		try:
			destinazione = ottieni_percorso_base()
			testo = self.traduci("ffmpeg_update_available", version=versione_locale, latest=versione_remota, path=self.cartella_ffmpeg, destination=destinazione)
			if self.chiedi_conferma(testo): self.scarica_ffmpeg(destinazione)
		except Exception as e:
			registra_log(traceback.format_exc())
			self.mostra_dialogo(QMessageBox.Icon.Critical, "error", self.traduci("ffmpeg_check_error", details=str(e)), traceback.format_exc())
		finally:
			self._controllo_ffmpeg_attivo = False

	def ffmpeg_controllo_errore(self, messaggio: str) -> None:
		# Senza rete il controllo degli aggiornamenti non e' possibile: non e' un errore da mostrare a ogni avvio, ma resta nel log
		registra_log(f"Controllo aggiornamenti FFmpeg non riuscito: {messaggio}")

	def assicura_deno(self) -> bool:
		"""True se Deno accanto al programma e' utilizzabile (self.percorso_deno impostato). Deno non e' indispensabile: se manca o l' utente rifiuta,
		yt-dlp prosegue senza e mostra il proprio avviso. Condivide il blocco di rientranza con FFmpeg per non aprire due download insieme."""
		if self._controllo_ffmpeg_attivo: return False
		self._controllo_ffmpeg_attivo = True
		try:
			return self.verifica_e_scarica_deno()
		finally:
			self._controllo_ffmpeg_attivo = False

	def verifica_e_scarica_deno(self) -> bool:
		try:
			stato = verifica_deno()
			if stato.codice == STATO_OK:
				self.percorso_deno = stato.percorso
				self.versione_deno = stato.versione
				return True
			if not scaricamento_deno_supportato():
				QMessageBox.warning(self, self.traduci("warning"), self.traduci("deno_manual", system=" ".join(piattaforma_ffmpeg())))
				return False
			destinazione = ottieni_percorso_base()
		except Exception as e:
			registra_log(traceback.format_exc())
			self.mostra_dialogo(QMessageBox.Icon.Critical, "error", self.traduci("deno_check_error", details=str(e)), traceback.format_exc())
			return False
		if stato.codice == STATO_NON_ESEGUIBILE:
			testo = self.traduci("deno_unusable", details=stato.dettagli, destination=destinazione)
		else:
			testo = self.traduci("deno_missing", path=destinazione)
		if not self.chiedi_conferma(testo, "deno_title"): return False
		return self.scarica_deno(destinazione)

	def scarica_deno(self, destinazione: str) -> bool:
		esito = self.scarica_componente(ScaricatoreDeno(destinazione), "deno_download_title", "deno_downloading")
		if esito["esito"] == "ok":
			self.percorso_deno = os.path.join(esito["cartella"], nome_eseguibile_deno())
			self.versione_deno = esito["dettagli"]
			QMessageBox.information(self, self.traduci("success"), self.traduci("deno_download_ok", version=esito["dettagli"], path=esito["cartella"]))
			return True
		if esito["esito"] == "errore":
			self.mostra_dialogo(QMessageBox.Icon.Critical, "error", self.traduci("deno_download_error", details=esito["dettagli"][:300]), esito["dettagli"])
		return False

	def avvia_controllo_aggiornamento_deno(self) -> None:
		self.thread_aggiornamento_deno = ControllaAggiornamentoDeno(self.versione_deno)
		self.thread_aggiornamento_deno.trovato.connect(self.deno_aggiornamento_disponibile)
		self.thread_aggiornamento_deno.errore.connect(self.deno_controllo_errore)
		self.thread_aggiornamento_deno.start()

	def deno_aggiornamento_disponibile(self, versione_locale: str, versione_remota: str) -> None:
		if self._controllo_ffmpeg_attivo:
			QTimer.singleShot(1000, lambda: self.deno_aggiornamento_disponibile(versione_locale, versione_remota))
			return
		self._controllo_ffmpeg_attivo = True
		try:
			destinazione = ottieni_percorso_base()
			testo = self.traduci("deno_update_available", version=versione_locale, latest=versione_remota, path=self.percorso_deno, destination=destinazione)
			if self.chiedi_conferma(testo, "deno_title"): self.scarica_deno(destinazione)
		except Exception as e:
			registra_log(traceback.format_exc())
			self.mostra_dialogo(QMessageBox.Icon.Critical, "error", self.traduci("deno_check_error", details=str(e)), traceback.format_exc())
		finally:
			self._controllo_ffmpeg_attivo = False

	def deno_controllo_errore(self, messaggio: str) -> None:
		# Come per FFmpeg: senza rete il controllo non e' possibile, il motivo resta nel log
		registra_log(f"Controllo aggiornamenti Deno non riuscito: {messaggio}")

	def opzioni_js_runtimes(self) -> dict:
		"""Runtime JavaScript per yt-dlp: il Deno scaricato dal programma; se manca, vale il comportamento predefinito di yt-dlp."""
		if self.percorso_deno: return {'deno': {'path': self.percorso_deno}}
		return {}

	def closeEvent(self, evento: QCloseEvent) -> None:
		# Un QThread distrutto mentre e' in esecuzione fa terminare il processo con un errore: si attende la fine del controllo (ha un timeout di rete)
		for thread in (self.thread_aggiornamento_ffmpeg, self.thread_aggiornamento_deno):
			if thread is not None: thread.wait(TIMEOUT_RETE * 1000 + 2000)
		super().closeEvent(evento)

	def ffmpeg_fase(self, chiave: str) -> None:
		self._dialogo_ffmpeg.setLabelText(self.traduci(chiave))

	def ffmpeg_completato(self, cartella: str, versione: str) -> None:
		self._esito_ffmpeg = {"esito": "ok", "cartella": cartella, "dettagli": versione}
		self._ciclo_ffmpeg.quit()

	def ffmpeg_errore(self, messaggio: str) -> None:
		self._esito_ffmpeg = {"esito": "errore", "cartella": "", "dettagli": messaggio}
		self._ciclo_ffmpeg.quit()

	def ffmpeg_annullato(self) -> None:
		self._esito_ffmpeg = {"esito": "annullato", "cartella": "", "dettagli": ""}
		self._ciclo_ffmpeg.quit()

	def cambia_lingua_interfaccia(self, idx: int) -> None:
		codice = self.combo_lingua_interfaccia.itemData(idx)
		if codice == "system":
			nuova = rileva_lingua_sistema(self.lingue_disponibili)
		else:
			nuova = codice
		if nuova != self.lingua_corrente:
			self.lingua_corrente = nuova
			self.carica_lingua()
			self.aggiorna_testi_ui()
			self.mostra_avvisi_avvio()

	def titolo_finestra(self) -> str:
		"""Nome del programma e numero di versione (ultimo tag e data di compilazione; 'sviluppo' se avviato dai sorgenti)."""
		return f"{self.traduci('app_name')} - {VERSIONE or self.traduci('version_dev')}"

	def imposta_stato(self, testo: str, stato: str = "") -> None:
		"""Mostra un messaggio nella barra di stato con il colore dello stato (vedi STATI_BARRA); senza testo o stato la barra si svuota."""
		if not testo or stato not in STATI_BARRA:
			self.etichetta_stato.setText("")
			self.etichetta_stato.setStyleSheet("")
			return
		sfondo, colore = STATI_BARRA[stato]
		self.etichetta_stato.setStyleSheet(f"background-color: {sfondo}; color: {colore}; font-weight: bold; padding: 2px 8px;")
		self.etichetta_stato.setText(testo)

	def aggiorna_testi_ui(self) -> None:
		self.setWindowTitle(self.titolo_finestra())
		self.etichetta_url.setText(self.traduci("url_label"))
		self.combo_lingua_interfaccia.setItemText(0, self.traduci("system_lang"))
		self.btn_analizza.setText(self.traduci("analyze_btn"))
		self.etichetta_lingua_interfaccia.setText(self.traduci("interface_lang"))
		self.etichetta_pref.setText(self.traduci("pref_langs"))
		self.etichetta_default_save_path.setText(self.traduci("default_save_path"))
		self.chk_avviso_no_video.setText(self.traduci("warn_no_video"))
		self.chk_avviso_no_audio.setText(self.traduci("warn_no_audio"))
		self.chk_avviso_no_subs.setText(self.traduci("warn_no_subs"))
		self.btn_sfoglia_perm.setText(self.traduci("browse_btn"))
		self.aggiorna_testo_pulsante_salvataggio()

		self.grp_session_controls.setTitle(self.traduci("session_controls_group"))
		self.grp_session_defaults.setTitle(self.traduci("session_defaults_group"))

		self.etichetta_modalita_unione.setText(self.traduci("merge_mode_label"))
		self.etichetta_sottotitoli.setText(self.traduci("subs_mode"))
		self.etichetta_formato_sub.setText(self.traduci("subs_format"))
		self.etichetta_sponsor.setText(self.traduci("sponsorblock_label"))

		self.etichetta_modalita_unione_def.setText(self.traduci("merge_mode_label"))
		self.etichetta_sottotitoli_def.setText(self.traduci("subs_mode"))
		self.etichetta_formato_sub_def.setText(self.traduci("subs_format"))
		self.etichetta_sponsor_def.setText(self.traduci("sponsorblock_label"))

		self.etichetta_percorso.setText(self.traduci("save_path"))
		self.btn_sfoglia.setText(self.traduci("browse_btn"))
		self.etichetta_nome_file.setText(self.traduci("filename_label"))
		self.btn_scarica.setText(self.traduci("download_btn"))

		self.schede.setTabText(0, self.traduci("video_tab"))
		self.schede.setTabText(1, self.traduci("audio_tab"))
		self.schede.setTabText(2, self.traduci("subs_tab"))
		self.schede.setTabText(3, self.traduci("other_tab"))
		self.schede.setTabText(4, self.traduci("settings_tab"))

		for combo in [self.combo_modalita_unione, self.combo_modalita_unione_def]:
			combo.setItemText(0, self.traduci("merge_mode_mkv"))
			combo.setItemText(1, self.traduci("merge_mode_separate"))

		for combo in [self.combo_sottotitoli, self.combo_sottotitoli_def]:
			combo.setItemText(0, self.traduci("subs_embedded"))
			combo.setItemText(1, self.traduci("subs_external"))

		for combo in [self.combo_sponsor, self.combo_sponsor_def]:
			combo.setItemText(0, self.traduci("sponsor_none"))
			combo.setItemText(1, self.traduci("sponsor_remove"))
			combo.setItemText(2, self.traduci("sponsor_mark"))

	def inizializza_ui(self) -> None:
		self.setWindowTitle(self.titolo_finestra())
		self.resize(1000, 700)
		# Barra di stato: un' etichetta che occupa tutta la larghezza, colorata in base allo stato (vedi imposta_stato)
		self.etichetta_stato = QLabel("")
		self.etichetta_stato.setObjectName("etichetta_stato")
		self.statusBar().addWidget(self.etichetta_stato, 1)

		widget_centrale = QWidget()
		layout_principale = QVBoxLayout(widget_centrale)

		layout_url = QHBoxLayout()
		self.etichetta_url = QLabel(self.traduci("url_label"))
		self.campo_url = QLineEdit()
		self.btn_analizza = QPushButton(self.traduci("analyze_btn"))
		self.btn_analizza.setStyleSheet(STILE_BTN_ANALIZZA)
		self.btn_analizza.clicked.connect(self.avvia_analisi)
		layout_url.addWidget(self.etichetta_url)
		layout_url.addWidget(self.campo_url)
		layout_url.addWidget(self.btn_analizza)
		layout_principale.addLayout(layout_url)

		layout_centrale = QHBoxLayout()

		layout_sinistra_anteprima = QVBoxLayout()
		self.etichetta_immagine = QLabel()
		self.etichetta_immagine.setFixedSize(320, 180)
		self.etichetta_immagine.setStyleSheet("background-color: black; color: white;")
		self.etichetta_immagine.setWordWrap(True)
		self.etichetta_immagine.setAlignment(Qt.AlignCenter)

		layout_immagine_centrata = QHBoxLayout()
		layout_immagine_centrata.addStretch()
		layout_immagine_centrata.addWidget(self.etichetta_immagine)
		layout_immagine_centrata.addStretch()
		layout_sinistra_anteprima.addLayout(layout_immagine_centrata)

		self.grp_session_controls = QGroupBox(self.traduci("session_controls_group"))
		layout_session = QFormLayout(self.grp_session_controls)

		self.etichetta_modalita_unione = QLabel(self.traduci("merge_mode_label"))
		self.combo_modalita_unione = QComboBox()
		self.combo_modalita_unione.addItem(self.traduci("merge_mode_mkv"), "merge")
		self.combo_modalita_unione.addItem(self.traduci("merge_mode_separate"), "separate")
		idx_unione = 0 if self.config.get("modalita_unione_default", "merge") == "merge" else 1
		self.combo_modalita_unione.setCurrentIndex(idx_unione)

		self.etichetta_sottotitoli = QLabel(self.traduci("subs_mode"))
		self.combo_sottotitoli = QComboBox()
		self.combo_sottotitoli.addItems([self.traduci("subs_embedded"), self.traduci("subs_external")])
		idx_sub_def = min(self.config.get("sottotitoli_default", 0), 1)
		self.combo_sottotitoli.setCurrentIndex(idx_sub_def)

		self.etichetta_formato_sub = QLabel(self.traduci("subs_format"))
		self.combo_formato_sub = QComboBox()
		self.combo_formato_sub.addItems(["srt", "vtt", "ass", "lrc"])
		idx_fmt = self.combo_formato_sub.findText(self.config.get("formato_sub_default", "srt"))
		if idx_fmt >= 0:
			self.combo_formato_sub.setCurrentIndex(idx_fmt)

		self.etichetta_sponsor = QLabel(self.traduci("sponsorblock_label"))
		self.combo_sponsor = QComboBox()
		self.combo_sponsor.addItems([self.traduci("sponsor_none"), self.traduci("sponsor_remove"), self.traduci("sponsor_mark")])
		self.combo_sponsor.setCurrentIndex(self.config.get("sponsorblock_default", 0))

		layout_session.addRow(self.etichetta_modalita_unione, self.combo_modalita_unione)
		layout_session.addRow(self.etichetta_sottotitoli, self.combo_sottotitoli)
		layout_session.addRow(self.etichetta_formato_sub, self.combo_formato_sub)
		layout_session.addRow(self.etichetta_sponsor, self.combo_sponsor)

		layout_sinistra_anteprima.addWidget(self.grp_session_controls)
		layout_sinistra_anteprima.addStretch()

		self.schede = QTabWidget()

		self.lista_video = QListWidget()
		self.schede.addTab(self.lista_video, self.traduci("video_tab"))

		self.lista_audio = QListWidget()
		self.schede.addTab(self.lista_audio, self.traduci("audio_tab"))

		self.lista_sottotitoli = QListWidget()
		self.schede.addTab(self.lista_sottotitoli, self.traduci("subs_tab"))

		# Tracce che non sono ne' video ne' audio (es. storyboard): la scheda si mostra solo se il sito ne espone
		self.lista_altre = QListWidget()
		self.schede.addTab(self.lista_altre, self.traduci("other_tab"))
		self.schede.setTabVisible(3, False)

		scheda_impostazioni = QWidget()
		layout_impostazioni = QVBoxLayout(scheda_impostazioni)

		layout_form_perm = QFormLayout()

		self.etichetta_lingua_interfaccia = QLabel(self.traduci("interface_lang"))
		self.combo_lingua_interfaccia = QComboBox()
		self.combo_lingua_interfaccia.addItem(self.traduci("system_lang"), "system")
		for codice, (nome, _) in sorted(self.lingue_disponibili.items(), key=lambda kv: kv[1][0].lower()):
			self.combo_lingua_interfaccia.addItem(nome, codice)
		idx_lang = self.combo_lingua_interfaccia.findData(self.config.get("lingua_interfaccia", "system"))
		if idx_lang >= 0:
			self.combo_lingua_interfaccia.setCurrentIndex(idx_lang)
		self.combo_lingua_interfaccia.currentIndexChanged.connect(self.cambia_lingua_interfaccia)

		self.etichetta_pref = QLabel(self.traduci("pref_langs"))
		self.campo_pref = QLineEdit(self.config.get("lingue_preferite", "it,en"))

		layout_cartella_perm = QHBoxLayout()
		self.etichetta_default_save_path = QLabel(self.traduci("default_save_path"))
		self.campo_default_save_path = QLineEdit(self.config.get("cartella_salvataggio", os.path.join(os.path.expanduser("~"), "Downloads")))
		self.btn_sfoglia_perm = QPushButton(self.traduci("browse_btn"))
		self.btn_sfoglia_perm.clicked.connect(self.sfoglia_cartella_perm)
		layout_cartella_perm.addWidget(self.campo_default_save_path)
		layout_cartella_perm.addWidget(self.btn_sfoglia_perm)

		layout_form_perm.addRow(self.etichetta_lingua_interfaccia, self.combo_lingua_interfaccia)
		layout_form_perm.addRow(self.etichetta_pref, self.campo_pref)
		layout_form_perm.addRow(self.etichetta_default_save_path, layout_cartella_perm)

		self.chk_avviso_no_video = QCheckBox(self.traduci("warn_no_video"))
		self.chk_avviso_no_video.setChecked(self.config.get("avviso_mancanza_video", True))
		self.chk_avviso_no_audio = QCheckBox(self.traduci("warn_no_audio"))
		self.chk_avviso_no_audio.setChecked(self.config.get("avviso_mancanza_audio", True))
		self.chk_avviso_no_subs = QCheckBox(self.traduci("warn_no_subs"))
		self.chk_avviso_no_subs.setChecked(self.config.get("avviso_mancanza_sottotitoli", True))

		layout_form_perm.addRow(self.chk_avviso_no_video)
		layout_form_perm.addRow(self.chk_avviso_no_audio)
		layout_form_perm.addRow(self.chk_avviso_no_subs)

		layout_impostazioni.addLayout(layout_form_perm)

		self.grp_session_defaults = QGroupBox(self.traduci("session_defaults_group"))
		layout_form_defs = QFormLayout(self.grp_session_defaults)

		self.etichetta_modalita_unione_def = QLabel(self.traduci("merge_mode_label"))
		self.combo_modalita_unione_def = QComboBox()
		self.combo_modalita_unione_def.addItem(self.traduci("merge_mode_mkv"), "merge")
		self.combo_modalita_unione_def.addItem(self.traduci("merge_mode_separate"), "separate")
		self.combo_modalita_unione_def.setCurrentIndex(idx_unione)

		self.etichetta_sottotitoli_def = QLabel(self.traduci("subs_mode"))
		self.combo_sottotitoli_def = QComboBox()
		self.combo_sottotitoli_def.addItems([self.traduci("subs_embedded"), self.traduci("subs_external")])
		self.combo_sottotitoli_def.setCurrentIndex(idx_sub_def)

		self.etichetta_formato_sub_def = QLabel(self.traduci("subs_format"))
		self.combo_formato_sub_def = QComboBox()
		self.combo_formato_sub_def.addItems(["srt", "vtt", "ass", "lrc"])
		if idx_fmt >= 0:
			self.combo_formato_sub_def.setCurrentIndex(idx_fmt)

		self.etichetta_sponsor_def = QLabel(self.traduci("sponsorblock_label"))
		self.combo_sponsor_def = QComboBox()
		self.combo_sponsor_def.addItems([self.traduci("sponsor_none"), self.traduci("sponsor_remove"), self.traduci("sponsor_mark")])
		self.combo_sponsor_def.setCurrentIndex(self.config.get("sponsorblock_default", 0))

		layout_form_defs.addRow(self.etichetta_modalita_unione_def, self.combo_modalita_unione_def)
		layout_form_defs.addRow(self.etichetta_sottotitoli_def, self.combo_sottotitoli_def)
		layout_form_defs.addRow(self.etichetta_formato_sub_def, self.combo_formato_sub_def)
		layout_form_defs.addRow(self.etichetta_sponsor_def, self.combo_sponsor_def)

		layout_impostazioni.addWidget(self.grp_session_defaults)

		self.btn_salva_impostazioni = QPushButton(self.traduci("save_settings_btn"))
		self.btn_salva_impostazioni.clicked.connect(self.salva_impostazioni_permanenti)

		# Ogni modifica di un' impostazione permanente segna le impostazioni come non salvate (collegamento dopo la creazione: i valori iniziali non contano)
		for combo in (self.combo_lingua_interfaccia, self.combo_modalita_unione_def, self.combo_sottotitoli_def, self.combo_formato_sub_def, self.combo_sponsor_def):
			combo.currentIndexChanged.connect(self.segna_impostazioni_modificate)
		for campo in (self.campo_pref, self.campo_default_save_path):
			campo.textChanged.connect(self.segna_impostazioni_modificate)
		for chk in (self.chk_avviso_no_video, self.chk_avviso_no_audio, self.chk_avviso_no_subs):
			chk.stateChanged.connect(self.segna_impostazioni_modificate)
		layout_impostazioni.addWidget(self.btn_salva_impostazioni)
		layout_impostazioni.addStretch()

		self.schede.addTab(scheda_impostazioni, self.traduci("settings_tab"))
		# Divisore trascinabile tra il pannello a sinistra (anteprima e opzioni) e le schede a destra: l' utente decide con il mouse quale dei due allargare.
		# Quando si allarga la finestra lo spazio in piu' va alle schede.
		pannello_sinistro = QWidget()
		layout_sinistra_anteprima.setContentsMargins(0, 0, 6, 0)
		pannello_sinistro.setLayout(layout_sinistra_anteprima)
		pannello_sinistro.setMinimumWidth(340)
		self.divisore = QSplitter(Qt.Orientation.Horizontal)
		self.divisore.setObjectName("divisore")
		self.divisore.setChildrenCollapsible(False)
		self.divisore.setHandleWidth(8)
		self.divisore.setStyleSheet("QSplitter::handle { background-color: #c8c8c8; } QSplitter::handle:hover { background-color: #8c8c8c; }")
		self.divisore.addWidget(pannello_sinistro)
		self.divisore.addWidget(self.schede)
		self.divisore.setStretchFactor(0, 0)
		self.divisore.setStretchFactor(1, 1)
		self.divisore.setSizes([490, 510])
		layout_centrale.addWidget(self.divisore)

		layout_principale.addLayout(layout_centrale)

		layout_salvataggio = QHBoxLayout()
		self.etichetta_percorso = QLabel(self.traduci("save_path"))
		self.campo_percorso = QLineEdit(self.config.get("cartella_salvataggio", os.path.join(os.path.expanduser("~"), "Downloads")))
		self.btn_sfoglia = QPushButton(self.traduci("browse_btn"))
		self.btn_sfoglia.clicked.connect(self.sfoglia_cartella)
		layout_salvataggio.addWidget(self.etichetta_percorso)
		layout_salvataggio.addWidget(self.campo_percorso)
		layout_salvataggio.addWidget(self.btn_sfoglia)
		layout_principale.addLayout(layout_salvataggio)

		self.barra_progresso = QProgressBar()
		self.barra_progresso.setValue(0)
		layout_principale.addWidget(self.barra_progresso)

		layout_download = QHBoxLayout()
		self.etichetta_nome_file = QLabel(self.traduci("filename_label"))
		self.campo_nome_file = QLineEdit()
		self.btn_scarica = QPushButton(self.traduci("download_btn"))
		self.btn_scarica.clicked.connect(self.avvia_download)
		self.btn_scarica.setEnabled(False)
		layout_download.addWidget(self.etichetta_nome_file)
		layout_download.addWidget(self.campo_nome_file)
		layout_download.addWidget(self.btn_scarica)
		layout_principale.addLayout(layout_download)

		self.setCentralWidget(widget_centrale)

	def sfoglia_cartella_perm(self) -> None:
		cartella = QFileDialog.getExistingDirectory(self, self.traduci("select_dir"))
		if cartella: self.campo_default_save_path.setText(cartella)

	def aggiorna_testo_pulsante_salvataggio(self) -> None:
		testo = self.traduci("save_settings_btn")
		if self._impostazioni_non_salvate: testo += " " + self.traduci("unsaved_suffix")
		self.btn_salva_impostazioni.setText(testo)

	def segna_impostazioni_modificate(self, *_: object) -> None:
		"""Alla prima modifica dopo un salvataggio: testo con '(non salvate)', grigio scuro e un lampeggio. Le modifiche successive non lampeggiano di nuovo."""
		if self._impostazioni_non_salvate: return
		self._impostazioni_non_salvate = True
		self.aggiorna_testo_pulsante_salvataggio()
		self._fase_lampeggio = 0
		self.passo_lampeggio_salvataggio()
		self.timer_lampeggio.start(DURATA_FASE_LAMPEGGIO_MS)

	def passo_lampeggio_salvataggio(self) -> None:
		self.btn_salva_impostazioni.setStyleSheet(FASI_LAMPEGGIO_SALVA[self._fase_lampeggio])
		self._fase_lampeggio += 1
		if self._fase_lampeggio >= len(FASI_LAMPEGGIO_SALVA): self.timer_lampeggio.stop()

	def ripristina_pulsante_salvataggio(self) -> None:
		self.timer_lampeggio.stop()
		self._impostazioni_non_salvate = False
		self.btn_salva_impostazioni.setStyleSheet("")
		self.aggiorna_testo_pulsante_salvataggio()

	def salva_impostazioni_permanenti(self) -> None:
		self.config["lingua_interfaccia"] = self.combo_lingua_interfaccia.currentData()
		self.config["lingue_preferite"] = self.campo_pref.text().strip()
		self.config["cartella_salvataggio"] = self.campo_default_save_path.text().strip()
		self.config["modalita_unione_default"] = self.combo_modalita_unione_def.currentData()
		self.config["sottotitoli_default"] = self.combo_sottotitoli_def.currentIndex()
		self.config["formato_sub_default"] = self.combo_formato_sub_def.currentText()
		self.config["sponsorblock_default"] = self.combo_sponsor_def.currentIndex()
		self.config["avviso_mancanza_video"] = self.chk_avviso_no_video.isChecked()
		self.config["avviso_mancanza_audio"] = self.chk_avviso_no_audio.isChecked()
		self.config["avviso_mancanza_sottotitoli"] = self.chk_avviso_no_subs.isChecked()

		try:
			salva_configurazione(self.config)
		except Exception as e:
			registra_log(traceback.format_exc())
			QMessageBox.critical(self, self.traduci("error"),
								 self.traduci("config_save_error", details=f"{ottieni_percorso_config()}: {e}"))
			return
		self.campo_percorso.setText(self.config["cartella_salvataggio"])
		self.ripristina_pulsante_salvataggio()
		QMessageBox.information(self, self.traduci("success"), self.traduci("settings_saved"))

	def sfoglia_cartella(self) -> None:
		cartella = QFileDialog.getExistingDirectory(self, self.traduci("select_dir"))
		if cartella: self.campo_percorso.setText(cartella)

	def nome_lingua(self, codice: str) -> str:
		"""Nome della lingua nella lingua stessa (es. 'de-DE' -> 'Deutsch'); stringa vuota se Qt non conosce il codice."""
		locale = QLocale(codice.replace("-", "_"))
		if locale.language() == QLocale.Language.C: return ""
		nome = locale.nativeLanguageName()
		return nome[:1].upper() + nome[1:]

	def crea_riga_audio(self, gruppo: dict) -> QWidget:
		"""Una riga per lingua: nome della lingua e, sulla stessa riga, una casella per ogni formato disponibile."""
		lingua = gruppo['lingua'] or self.traduci("lang_undefined")
		if gruppo['categoria'] == CATEGORIA_ORIGINALE: tipo_str = self.traduci("original")
		elif gruppo['categoria'] == CATEGORIA_SINTETICA: tipo_str = self.traduci("synthetic")
		else: tipo_str = self.traduci("audio_standard")
		nome = self.nome_lingua(gruppo['lingua']) if gruppo['lingua'] else ""
		titolo = f"[{lingua}] {nome} ({tipo_str})" if nome else f"[{lingua}] ({tipo_str})"

		riga = QWidget()
		riga.setAccessibleName(titolo)
		layout = QHBoxLayout(riga)
		layout.setContentsMargins(4, 2, 4, 2)
		etichetta = QLabel(titolo)
		layout.addWidget(etichetta)
		for f in gruppo['formati']:
			abr = f.get('abr')
			codec = (f.get('acodec') or self.traduci("codec_unknown")).split(".")[0]
			if abr: descrizione = f"{codec} {int(abr)}k"
			else: descrizione = f"{codec} {(f.get('protocol') or '').split('_')[0]} #{f.get('format_id')}".replace("  ", " ")  # senza bitrate noto l' ID distingue le tracce
			casella = QCheckBox(descrizione)
			casella.setProperty("format_id", f.get('format_id'))
			nome_lingua_completo = self.nome_lingua_variante(gruppo['lingua']) if gruppo['lingua'] else lingua
			casella.setProperty("nome", f"{nome_lingua_completo} - {tipo_str} - {descrizione}")
			casella.setProperty("parte_nome", parte_nome_audio(gruppo['lingua'], gruppo['categoria'] == CATEGORIA_SINTETICA))
			self.elenco_tracce["audio"].append(f"{casella.property('nome')} | " + self.descrizione_tecnica(f, ("format_id", "ext", "protocol", "language", "acodec", "abr", "audio_channels", "asr", "filesize", "filesize_approx", "format_note")))
			casella.setToolTip(f"ID: {f.get('format_id')}\n{f.get('acodec') or ''} - {f.get('ext') or ''} - {f.get('protocol') or ''}\n{f.get('format_note') or ''}".strip())
			casella.setAccessibleName(f"{titolo} - {descrizione}")
			layout.addWidget(casella)
		layout.addStretch()
		return riga

	def descrizione_variante(self, codice: str, nome_provider: str) -> str:
		"""Parte del nome che distingue una variante dalla lingua base: 'it-CH' -> 'Svizzera', 'it-orig' -> 'Originale', 'fr-FR-orig' -> 'Francia, Originale'.
		Stringa vuota per la variante generica (es. 'it')."""
		base = codice.split("-")[0]
		qualificatori = []
		for parte in codice.split("-")[1:]:
			if parte.lower() == "orig": qualificatori.append(self.traduci("original"))
			elif (len(parte) == 2 and parte.isalpha()) or (len(parte) == 3 and parte.isdigit()):
				qualificatori.append(QLocale(f"{base}_{parte}").nativeTerritoryName() or parte)
			elif len(parte) == 4 and parte.isalpha():
				# Scrittura (es. Hans, Hant): Qt non ha un nome nella lingua stessa, si usa quello di YouTube tra parentesi (es. 'Chinese (Simplified)')
				trovato = re.search(r"\(([^)]*)\)", nome_provider)
				qualificatori.append(trovato.group(1) if trovato else parte)
			else: qualificatori.append(parte)
		return ", ".join(qualificatori)

	def nome_lingua_variante(self, codice: str, nome_provider: str = "") -> str:
		"""Lingua e variante: 'it-CH' -> 'Italiano (Svizzera)', 'it' -> 'Italiano'."""
		nome = self.nome_lingua(codice.split("-")[0]) or nome_provider.split(" (")[0] or codice
		variante = self.descrizione_variante(codice, nome_provider)
		return f"{nome} ({variante})" if variante else nome

	def nome_completo_sottotitolo(self, codice: str, nome_provider: str, tipo: str, origine: str = "") -> str:
		"""Nome completo della traccia: lingua, variante, tipo e, per una traduzione, la lingua da cui e' tradotta.
		Es. 'Italiano (Svizzera) - Automatico', 'Italiano - Automatico (tradotto da Deutsch (Deutschland))'."""
		nome = f"{self.nome_lingua_variante(codice, nome_provider)} - {self.traduci(tipo)}"
		if origine: nome += f" ({self.traduci('translated_from', source=self.nome_lingua_variante(origine))})"
		return nome

	def descrizione_tecnica(self, formato: dict, campi: Tuple[str, ...]) -> str:
		"""'campo=valore' per i campi presenti (nomi di yt-dlp, uguali in ogni lingua): vanno nell' elenco delle tracce del file dei metadati."""
		return " ".join(f"{campo}={formato[campo]}" for campo in campi if formato.get(campo) not in (None, ""))

	def crea_riga_video(self, altezza: int, fps: int, formati: List[dict]) -> QWidget:
		"""Una riga per risoluzione e framerate (es. 1080p60) con, sulla stessa riga, una casella per ogni formato disponibile."""
		titolo = parte_nome_video(altezza, fps)
		riga = QWidget()
		riga.setAccessibleName(titolo)
		layout = QHBoxLayout(riga)
		layout.setContentsMargins(4, 2, 4, 2)
		etichetta = QLabel(titolo)
		etichetta.setObjectName("etichetta_riga")
		layout.addWidget(etichetta)
		for f in formati:
			traccia = self.nome_traccia_video(f)
			codec = (f.get('vcodec') or self.traduci("codec_unknown")).split(".")[0]
			bitrate = f.get('vbr') or f.get('tbr')
			bitrate_str = f"{int(bitrate)}k" if bitrate else self.traduci("bitrate_auto")
			descrizione = f"{codec} {bitrate_str} {f.get('ext', '')} #{f.get('format_id')}"
			casella = QCheckBox(descrizione)
			casella.setProperty("format_id", f.get('format_id'))
			casella.setProperty("nome", traccia.nome)
			casella.setProperty("parte_nome", traccia.parte_nome)
			casella.setToolTip(f"ID: {f.get('format_id')}\n{traccia.nome}\n{f.get('vcodec') or ''} - {f.get('ext') or ''} - {f.get('protocol') or ''}\n{f.get('format_note') or ''}".strip())
			casella.setAccessibleName(f"{traccia.nome} - {f.get('ext') or ''} #{f.get('format_id')}")
			layout.addWidget(casella)
			self.elenco_tracce["video"].append(f"{traccia.nome} | " + self.descrizione_tecnica(f, ("format_id", "ext", "protocol", "width", "height", "fps", "vcodec", "vbr", "tbr", "dynamic_range", "filesize", "filesize_approx", "format_note")))
		layout.addStretch()
		return riga

	def crea_riga_altre(self, gruppo: dict) -> QWidget:
		"""Una riga per tipo di traccia diversa da video e audio (es. storyboard) con una casella per ogni formato disponibile."""
		titolo = gruppo['nome']
		riga = QWidget()
		riga.setAccessibleName(titolo)
		layout = QHBoxLayout(riga)
		layout.setContentsMargins(4, 2, 4, 2)
		etichetta = QLabel(titolo)
		etichetta.setObjectName("etichetta_riga")
		layout.addWidget(etichetta)
		for f in gruppo['formati']:
			larghezza = f.get('width') or 0
			altezza = f.get('height') or 0
			misura = f"{larghezza}x{altezza}" if larghezza and altezza else ""
			casella = QCheckBox(f"{misura} {f.get('ext', '')} #{f.get('format_id')}".strip())
			casella.setProperty("format_id", f.get('format_id'))
			casella.setProperty("nome", f"{titolo} - {misura} {f.get('ext', '')}".replace("  ", " ").strip(" -"))
			casella.setProperty("parte_nome", parte_nome_altro(titolo, larghezza, altezza))
			casella.setToolTip(f"ID: {f.get('format_id')}\n{f.get('ext') or ''} - {f.get('protocol') or ''}\n{f.get('format_note') or ''}".strip())
			casella.setAccessibleName(f"{casella.property('nome')} #{f.get('format_id')}")
			layout.addWidget(casella)
			self.elenco_tracce["other"].append(f"{casella.property('nome')} | " + self.descrizione_tecnica(f, ("format_id", "ext", "protocol", "width", "height", "fps", "format_note", "filesize", "filesize_approx")))
		layout.addStretch()
		return riga

	def nome_traccia_video(self, formato: dict) -> SceltaTraccia:
		"""Traccia video con il suo nome completo: risoluzione, framerate e codec. Es. '1080p60 - avc1 5686k'."""
		parte = parte_nome_video(formato.get('height') or 0, formato.get('fps') or 0)
		codec = (formato.get('vcodec') or self.traduci("codec_unknown")).split(".")[0]
		bitrate = formato.get('vbr') or formato.get('tbr')
		nome = f"{parte} - {codec}" + (f" {int(bitrate)}k" if bitrate else "")
		return SceltaTraccia(str(formato.get('format_id')), TRACCIA_VIDEO, nome, parte)

	def crea_riga_sottotitoli(self, base: str, varianti: Dict[str, Dict[str, object]]) -> QWidget:
		"""Una riga per lingua base: nome della lingua e, sulla stessa riga, una colonna per ogni variante (sottolingua). Ogni colonna ha l' etichetta e, subito dopo, una casella
		per ogni traccia che YouTube espone: manuale, automatico nella lingua stessa e un automatico tradotto per ogni traccia del video da cui YouTube lo traduce.
		Ogni casella e' indipendente. Ordine delle colonne: generica (it), originale (it-orig), poi le altre in ordine di codice.
		Ogni colonna e' larga esattamente quanto il suo contenuto (politica di dimensione fissa): lo spazio che avanza nella riga va in fondo, mai tra le colonne."""
		nome = self.nome_lingua(base)
		titolo = f"[{base}] {nome}" if nome else f"[{base}]"

		riga = QWidget()
		riga.setAccessibleName(titolo)
		layout = QHBoxLayout(riga)
		layout.setContentsMargins(4, 2, 4, 2)
		layout.setSpacing(14)
		etichetta = QLabel(titolo)
		etichetta.setObjectName("etichetta_lingua")
		etichetta.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
		layout.addWidget(etichetta)
		riga.base = base
		riga.etichette_varianti = {}  # codice -> etichetta della variante
		originale = (self.info_video.get('language') or '').split("-")[0]
		for codice in sorted(varianti, key=lambda c: (c != base, c != f"{base}-orig", c)):
			voce = varianti[codice]
			nome_provider = str(voce["nome"])
			colonna = QWidget()
			colonna.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
			layout_colonna = QHBoxLayout(colonna)
			layout_colonna.setContentsMargins(0, 0, 0, 0)
			variante = self.descrizione_variante(codice, nome_provider) or self.traduci("lang_generic")
			etichetta_variante = QLabel(f"[{codice}] {variante}")
			etichetta_variante.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
			riga.etichette_varianti[codice] = etichetta_variante
			layout_colonna.addWidget(etichetta_variante)
			for tipo in (TIPO_MANUALE, TIPO_AUTOMATICO):
				if tipo in voce: self.aggiungi_casella_sottotitolo(layout_colonna, codice, nome_provider, tipo, "", self.traduci(tipo), list(voce[tipo]))
			# Una casella per ogni traccia del video da cui YouTube traduce questo sottotitolo; prima quella della lingua originale del video
			for origine in sorted(voce.get("tradotti", {}), key=lambda o: (o.split("-")[0] != originale, o)):
				testo = self.traduci("translated_from", source=origine)
				self.aggiungi_casella_sottotitolo(layout_colonna, codice, nome_provider, TIPO_AUTOMATICO, origine, testo[:1].upper() + testo[1:], list(voce["tradotti"][origine]))
			layout.addWidget(colonna)
		layout.addStretch()
		return riga

	def aggiungi_casella_sottotitolo(self, layout: QHBoxLayout, codice: str, nome_provider: str, tipo: str, origine: str, testo: str, formati: List[str]) -> None:
		nome_completo = self.nome_completo_sottotitolo(codice, nome_provider, tipo, origine)
		casella = QCheckBox(testo)
		casella.setProperty("lingua", codice)
		casella.setProperty("tipo", tipo)
		casella.setProperty("origine", origine)
		casella.setProperty("nome", nome_completo)
		casella.setToolTip(f"[{codice}] {nome_completo}\n" + self.traduci("subs_available_formats", formats=", ".join(formati) or "-")
						   + (f"\n{self.traduci('subs_translated_note', seconds=ATTESA_INIZIALE_S, increment=INCREMENTO_ATTESA_S)}" if origine else ""))
		casella.setAccessibleName(f"[{codice}] {nome_completo}")
		layout.addWidget(casella)
		sorgente = f" source={origine}" if origine else ""
		traduzione = f" translated={'true' if origine else 'false'}" if tipo == TIPO_AUTOMATICO else ""
		self.elenco_tracce["subtitles"].append(f"{nome_completo} | language={codice} type={tipo}{sorgente}{traduzione} formats={','.join(formati)}")

	def avvia_analisi(self) -> None:
		url = self.campo_url.text().strip()
		if not url: return

		self.btn_analizza.setEnabled(False)
		self.btn_scarica.setEnabled(False)
		self._avvisi_operazione = False
		self.imposta_stato(self.traduci("analyzing"), "lavoro")
		self.lista_video.clear()
		self.lista_audio.clear()
		self.lista_sottotitoli.clear()
		self.lista_altre.clear()
		self.schede.setTabVisible(3, False)
		self.etichetta_immagine.clear()

		self.thread_analisi = Analizzatore(url, self.opzioni_js_runtimes())
		self.thread_analisi.completato.connect(self.analisi_completata)
		self.thread_analisi.errore.connect(lambda messaggio: self.mostra_errore(messaggio, "status_analysis_failed"))
		self.thread_analisi.avvisi.connect(self.mostra_avvisi_ytdlp)
		self.thread_analisi.start()

	def calcola_peso_lingua(self, lingua: str, preferite: List[str]) -> Tuple[int, int, str]:
		lingua_clean = (lingua or 'indefinito').lower().strip()
		for i, pref in enumerate(preferite):
			if lingua_clean == pref or lingua_clean.startswith(f"{pref}-"):
				return (0, i, lingua_clean)
		return (1, 0, lingua_clean)

	def analisi_completata(self, info: dict) -> None:
		self.info_video = info
		self.elenco_tracce = {"video": [], "audio": [], "subtitles": [], "other": []}

		titolo_video = info.get("title", "")
		if titolo_video:
			self.campo_nome_file.setText(titolo_video)

		miniatura_url = info.get("thumbnail")
		if miniatura_url:
			try:
				with urllib.request.urlopen(miniatura_url, timeout=10) as risposta:
					dati = risposta.read()
				immagine = QImage()
				if not immagine.loadFromData(dati):
					raise ValueError("dati immagine non validi")
				pixmap = QPixmap(immagine).scaled(self.etichetta_immagine.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
				self.etichetta_immagine.setPixmap(pixmap)
			except Exception as e:
				registra_log(f"Errore caricamento miniatura {miniatura_url}: {e}")
				self.etichetta_immagine.setText(self.traduci("thumb_error", details=str(e)))

		preferite = [l.strip().lower() for l in self.campo_pref.text().split(",") if l.strip()]

		formati_video = [f for f in info.get('formats', []) if tipo_formato(f) == TIPO_FORMATO_VIDEO]
		formati_video.sort(key=lambda x: (x.get('height') or 0, x.get('fps') or 0), reverse=True)

		# Una riga per risoluzione e framerate; sulla stessa riga una casella per ogni formato disponibile (codec, bitrate), dal bitrate piu' alto
		gruppi_video: Dict[Tuple[int, int], List[dict]] = {}
		for f in formati_video: gruppi_video.setdefault((f.get('height') or 0, int(f.get('fps') or 0)), []).append(f)
		righe_video = [self.crea_riga_video(altezza, fps, sorted(formati, key=lambda f: -(f.get('vbr') or f.get('tbr') or 0))) for (altezza, fps), formati in gruppi_video.items()]
		larghezza_etichetta_video = max((r.findChild(QLabel, "etichetta_riga").sizeHint().width() for r in righe_video), default=0)
		for riga in righe_video:
			riga.findChild(QLabel, "etichetta_riga").setMinimumWidth(larghezza_etichetta_video)
			item = QListWidgetItem()
			item.setSizeHint(riga.sizeHint())
			self.lista_video.addItem(item)
			self.lista_video.setItemWidget(item, riga)

		righe_altre = [self.crea_riga_altre(g) for g in raggruppa_altre(info.get('formats', []))]
		larghezza_etichetta_altre = max((r.findChild(QLabel, "etichetta_riga").sizeHint().width() for r in righe_altre), default=0)
		for riga in righe_altre:
			riga.findChild(QLabel, "etichetta_riga").setMinimumWidth(larghezza_etichetta_altre)
			item = QListWidgetItem()
			item.setSizeHint(riga.sizeHint())
			self.lista_altre.addItem(item)
			self.lista_altre.setItemWidget(item, riga)
		self.schede.setTabVisible(3, bool(righe_altre))

		righe_audio = [self.crea_riga_audio(g) for g in raggruppa_audio(info.get('formats', []), lambda lingua: self.calcola_peso_lingua(lingua, preferite))]
		# Stessa larghezza per tutte le etichette, cosi' le caselle restano allineate tra le righe
		larghezza_etichetta = max((r.findChild(QLabel).sizeHint().width() for r in righe_audio), default=0)
		for riga in righe_audio:
			riga.findChild(QLabel).setMinimumWidth(larghezza_etichetta)
			item = QListWidgetItem()
			item.setSizeHint(riga.sizeHint())
			self.lista_audio.addItem(item)
			self.lista_audio.setItemWidget(item, riga)

		# Una riga per lingua base (it); sulla stessa riga le sue varianti (it, it-CH, it-orig...), ognuna con le caselle dei tipi disponibili (manuale, automatico)
		sottotitoli: Dict[str, Dict[str, Dict[str, object]]] = {}
		for tipo, chiave in ((TIPO_MANUALE, 'subtitles'), (TIPO_AUTOMATICO, 'automatic_captions')):
			for codice, subs in info.get(chiave, {}).items():
				voce = sottotitoli.setdefault(codice.split("-")[0], {}).setdefault(codice, {"nome": ""})
				if tipo == TIPO_MANUALE:
					voce[tipo] = list(dict.fromkeys(f.get('ext', '') for f in subs))
				else:
					# La lista di una lingua automatica contiene piu' tracce: quella nella lingua stessa e le traduzioni dalle altre tracce del video
					per_origine = voci_per_origine(subs)
					if "" in per_origine: voce[tipo] = list(dict.fromkeys(f.get('ext', '') for f in per_origine[""]))
					voce["tradotti"] = {origine: list(dict.fromkeys(f.get('ext', '') for f in voci)) for origine, voci in per_origine.items() if origine}
				if not voce["nome"]: voce["nome"] = next((f.get('name') for f in subs if f.get('name')), "")
		lingue_ordinate = sorted(sottotitoli, key=lambda lang: (self.calcola_peso_lingua(lang, preferite), lang))
		righe_sub = [self.crea_riga_sottotitoli(lang, sottotitoli[lang]) for lang in lingue_ordinate]
		larghezza_etichetta_sub = max((r.findChild(QLabel, "etichetta_lingua").sizeHint().width() for r in righe_sub), default=0)
		# Colonne di larghezza minima: ogni colonna ha la larghezza del proprio contenuto. L' unica allineata tra le righe e' la prima (nome della lingua) e, subito dopo,
		# l' etichetta della variante generica ("[it] generico"), che ha la larghezza della piu' larga fra le generiche: cosi' le caselle iniziano alla stessa altezza
		# nelle righe semplici, senza che le etichette lunghe di poche altre righe (es. "[zh-Hans] (Simplified)") allarghino le altre.
		larghezza_generici = max((r.etichette_varianti[c].sizeHint().width() for r in righe_sub for c in r.etichette_varianti if c == r.base), default=0)
		for r in righe_sub:
			if r.base in r.etichette_varianti: r.etichette_varianti[r.base].setFixedWidth(larghezza_generici)
		for riga in righe_sub:
			riga.findChild(QLabel, "etichetta_lingua").setFixedWidth(larghezza_etichetta_sub)
			item = QListWidgetItem()
			item.setSizeHint(riga.sizeHint())
			self.lista_sottotitoli.addItem(item)
			self.lista_sottotitoli.setItemWidget(item, riga)

		if not righe_sub:
			# Nessun sottotitolo esposto dal sito: una voce spenta lo dice, invece di una scheda vuota
			voce_vuota = QListWidgetItem(self.traduci("subs_none"))
			voce_vuota.setFlags(Qt.ItemFlag.NoItemFlags)
			self.lista_sottotitoli.addItem(voce_vuota)

		self.btn_analizza.setEnabled(True)
		if not self.btn_scarica.styleSheet():
			self.btn_scarica.setStyleSheet(STILE_BTN_SCARICA)
		self.btn_scarica.setEnabled(True)
		if self._avvisi_operazione: self.imposta_stato(self.traduci("status_analysis_done_warnings"), "attesa")
		else: self.imposta_stato(self.traduci("status_analysis_done"), "ok")

	def mostra_errore(self, messaggio: str, chiave_stato: str = "status_download_failed") -> None:
		self._download_in_corso = False
		self.imposta_stato(self.traduci(chiave_stato), "errore")
		self.btn_analizza.setEnabled(True)
		self.btn_scarica.setEnabled(True)
		righe = [r for r in messaggio.strip().splitlines() if r.strip()]
		breve = righe[0][:500] if righe else messaggio[:500]
		dettagli = messaggio if (len(righe) > 1 or len(breve) < len(messaggio.strip())) else ""
		self.mostra_dialogo(QMessageBox.Icon.Critical, "error", breve, dettagli)

	def mostra_avvisi_ytdlp(self, testo: str) -> None:
		self._avvisi_operazione = True
		registra_log(testo)
		self.mostra_dialogo(QMessageBox.Icon.Warning, "warning", self.traduci("yt_warnings"), testo)

	def avvia_download(self) -> None:
		if not self.assicura_ffmpeg():
			QMessageBox.warning(self, self.traduci("warning"), self.traduci("ffmpeg_required"))
			return
		url = self.campo_url.text().strip()
		cartella_out = self.campo_percorso.text().strip()
		nome_file_out = self.campo_nome_file.text().strip()
		if not nome_file_out:
			nome_file_out = "%(title)s"

		nome_base_pulito = pulisci_nome_file(nome_file_out)
		modalita_unione = self.combo_modalita_unione.currentData()

		id_video_selezionati = []
		tracce = []
		for i in range(self.lista_video.count()):
			for casella in self.lista_video.itemWidget(self.lista_video.item(i)).findChildren(QCheckBox):
				if not casella.isChecked(): continue
				id_video_selezionati.append(casella.property("format_id"))
				tracce.append(SceltaTraccia(str(casella.property("format_id")), TRACCIA_VIDEO, casella.property("nome"), casella.property("parte_nome")))

		id_audio_selezionati = []
		for i in range(self.lista_audio.count()):
			for casella in self.lista_audio.itemWidget(self.lista_audio.item(i)).findChildren(QCheckBox):
				if casella.isChecked(): id_audio_selezionati.append(casella.property("format_id"))

		scelte_sottotitoli = []
		for i in range(self.lista_sottotitoli.count()):
			for casella in self.lista_sottotitoli.itemWidget(self.lista_sottotitoli.item(i)).findChildren(QCheckBox):
				if casella.isChecked(): scelte_sottotitoli.append(SceltaSottotitolo(casella.property("lingua"), casella.property("tipo"), casella.property("nome"), casella.property("origine") or ""))

		altre = []
		for i in range(self.lista_altre.count()):
			for casella in self.lista_altre.itemWidget(self.lista_altre.item(i)).findChildren(QCheckBox):
				if casella.isChecked(): altre.append(SceltaTraccia(str(casella.property("format_id")), TRACCIA_ALTRO, casella.property("nome"), casella.property("parte_nome")))

		# Controlli sulle tracce selezionate dall' utente prima di procedere al download
		totale_selezionate = len(id_video_selezionati) + len(id_audio_selezionati) + len(scelte_sottotitoli) + len(altre)
		if totale_selezionate == 0:
			QMessageBox.warning(self, self.traduci("warning"), self.traduci("no_tracks_selected"))
			return

		# Avvisi sequenziali per mancanza di specifiche tracce (Video -> Audio -> Sottotitoli)
		if len(id_video_selezionati) == 0 and self.config.get("avviso_mancanza_video", True):
			if not self.chiedi_conferma(self.traduci("confirm_no_video"), "warning"):
				QMessageBox.information(self, self.traduci("warning"), self.traduci("download_cancelled"))
				return

		if len(id_audio_selezionati) == 0 and self.config.get("avviso_mancanza_audio", True):
			if not self.chiedi_conferma(self.traduci("confirm_no_audio"), "warning"):
				QMessageBox.information(self, self.traduci("warning"), self.traduci("download_cancelled"))
				return

		if len(scelte_sottotitoli) == 0 and self.config.get("avviso_mancanza_sottotitoli", True):
			if not self.chiedi_conferma(self.traduci("confirm_no_subs"), "warning"):
				QMessageBox.information(self, self.traduci("warning"), self.traduci("download_cancelled"))
				return

		# Le tracce audio spuntate si aggiungono a quelle video, ognuna con il suo nome completo
		for i in range(self.lista_audio.count()):
			for casella in self.lista_audio.itemWidget(self.lista_audio.item(i)).findChildren(QCheckBox):
				if casella.isChecked(): tracce.append(SceltaTraccia(str(casella.property("format_id")), TRACCIA_AUDIO, casella.property("nome"), casella.property("parte_nome")))

		selezionati = id_video_selezionati + id_audio_selezionati
		stringa_formato = ",".join(selezionati) if modalita_unione == "separate" else "+".join(selezionati)
		num_flussi = len(selezionati)

		# Tracce separate: yt-dlp le salva come nomeFile.ID.ext, perche' senza l' ID due tracce dello stesso tipo si sovrascriverebbero; poi il programma le rinomina con il nome completo
		tracce_separate = bool(selezionati) and modalita_unione == "separate"
		template_finale = f"{nome_base_pulito}.%(format_id)s.%(ext)s" if tracce_separate else f"{nome_base_pulito}.%(ext)s"
		formato_sub = self.combo_formato_sub.currentText()

		opzioni = {
			'format': stringa_formato,
			'outtmpl': {
				'default': os.path.join(cartella_out, template_finale),
				# Stesso nome base per tutte le tracce: i sottotitoli si chiamano nomeFile.lingua.ext e non si duplicano
				'subtitle': os.path.join(cartella_out, f"{nome_base_pulito}.%(ext)s")
			},
			'subtitlesformat': formato_sub,
			'addmetadata': True,
			'embedchapters': True,
			'quiet': True,
			'postprocessors': [{'key': 'FFmpegMetadata'}],
			'ffmpeg_location': self.cartella_ffmpeg
		}
		js_runtimes = self.opzioni_js_runtimes()
		if js_runtimes: opzioni['js_runtimes'] = js_runtimes

		if modalita_unione == "merge":
			# Senza queste opzioni yt-dlp unisce solo la prima traccia audio e la prima traccia video scelte
			opzioni['allow_multiple_audio_streams'] = True
			opzioni['allow_multiple_video_streams'] = True
			if id_video_selezionati or not id_audio_selezionati:
				opzioni['merge_output_format'] = 'mkv'
			else:
				opzioni['merge_output_format'] = 'mka'

		stato_sub = self.combo_sottotitoli.currentIndex()  # 0: embedded, 1: external
		if scelte_sottotitoli:
			# I due flag servono a yt-dlp per scrivere i file; quali sottotitoli scaricare lo decide YoutubeDLConSottotitoli in base alle caselle spuntate
			opzioni['writesubtitles'] = True
			opzioni['writeautomaticsub'] = True

			if stato_sub == 0 and modalita_unione == "merge":
				opzioni['postprocessors'].append({'key': 'FFmpegEmbedSubtitle'})

		stato_sponsor = self.combo_sponsor.currentText()
		categorie_sponsor = {'sponsor', 'intro', 'outro', 'selfpromo', 'interaction'}
		if stato_sponsor == self.traduci("sponsor_remove"):
			opzioni['sponsorblock_remove'] = categorie_sponsor
		elif stato_sponsor == self.traduci("sponsor_mark"):
			opzioni['sponsorblock_mark'] = categorie_sponsor

		# Solo sottotitoli (niente video ne' audio): non si scarica il video. Con i sottotitoli integrati e un unico file si crea un file Matroska con i soli sottotitoli (.mks)
		unisci_sottotitoli = False
		if not selezionati and scelte_sottotitoli:
			opzioni['skip_download'] = True
			opzioni['format'] = 'bv*+ba/b'  # con skip_download non si scarica, ma yt-dlp sceglie comunque un formato: quello vuoto dava errore
			opzioni['ignore_no_formats_error'] = True
			opzioni['postprocessors'] = [pp for pp in opzioni['postprocessors'] if pp.get('key') != 'FFmpegEmbedSubtitle']  # senza video non c' e' niente in cui incorporarli
			num_flussi = 1
			if stato_sub == 0 and modalita_unione == "merge":
				if not self.chiedi_conferma(self.traduci("confirm_subs_single_file"), "warning"):
					QMessageBox.information(self, self.traduci("warning"), self.traduci("download_cancelled"))
					return
				unisci_sottotitoli = True

		self.btn_scarica.setEnabled(False)
		self.btn_analizza.setEnabled(False)
		self.barra_progresso.setValue(0)
		self._download_in_corso = True
		self._avvisi_operazione = False
		self.imposta_stato(self.traduci("downloading"), "lavoro")

		# Il passaggio principale (video, audio, sottotitoli) manca solo se l' utente ha spuntato soltanto altre tracce
		principale = bool(selezionati) or bool(scelte_sottotitoli) or not altre
		chiavi_meta = ("meta_url", "meta_command", "meta_title", "meta_author", "meta_channel", "meta_tags", "meta_description", "meta_unknown_title", "meta_cli_note", "meta_cli_note_sources", "subs_wait_status", "subs_retry_status", "subs_download_failed", "subs_not_available", "merge_repaired", "subs_merge_failed", "meta_cli_note_mks")
		etichette_meta = {chiave: self.traduci(chiave) for chiave in chiavi_meta}
		self.thread_download = Scaricatore(opzioni, url, self.info_video, nome_base_pulito, num_flussi, etichette_meta, scelte_sottotitoli, tracce, tracce_separate, self.elenco_tracce, altre, principale, unisci_sottotitoli)
		self.thread_download.progresso.connect(self.barra_progresso.setValue)
		self.thread_download.stato.connect(self.mostra_stato_download)
		self.thread_download.completato.connect(self.download_completato)
		self.thread_download.errore.connect(self.mostra_errore)
		self.thread_download.avvisi.connect(self.mostra_avvisi_ytdlp)
		self.thread_download.start()

	def mostra_stato_download(self, testo: str) -> None:
		"""Barra di stato: messaggi che spiegano perche' il download non e' ancora finito (attesa, errore 429 e nuovo tentativo), in arancione.
		Testo vuoto = l' attesa e' finita: si torna al messaggio di download in corso."""
		if testo: self.imposta_stato(testo, "attesa")
		elif self._download_in_corso: self.imposta_stato(self.traduci("downloading"), "lavoro")
		else: self.imposta_stato("")

	def download_completato(self) -> None:
		self._download_in_corso = False
		if self._avvisi_operazione: self.imposta_stato(self.traduci("status_download_done_warnings"), "attesa")
		else: self.imposta_stato(self.traduci("status_download_done"), "ok")
		self.btn_scarica.setEnabled(True)
		self.btn_analizza.setEnabled(True)
		QMessageBox.information(self, self.traduci("success"), self.traduci("download_complete"))

def percorso_icona() -> Optional[str]:
	"""Cerca il PNG dell' icona nella cartella ico incorporata nell' eseguibile e, in sviluppo, in quella del progetto."""
	cartelle = [os.path.join(ottieni_percorso_base(), "ico")]
	if hasattr(sys, '_MEIPASS'): cartelle.insert(0, os.path.join(sys._MEIPASS, "ico"))
	for cartella in cartelle:
		percorso = os.path.join(cartella, NOME_ICONA)
		if os.path.isfile(percorso): return percorso
	return None

if __name__ == "__main__":
	app = QApplication(sys.argv)
	sys.excepthook = gestore_eccezioni
	percorso_png = percorso_icona()
	if percorso_png: app.setWindowIcon(QIcon(percorso_png))
	else: registra_log(f"Icona della finestra non trovata ({NOME_ICONA} nella cartella ico): la finestra usa l' icona predefinita.")
	finestra = FinestraPrincipale()
	_finestra = finestra
	finestra.show()
	sys.exit(app.exec())