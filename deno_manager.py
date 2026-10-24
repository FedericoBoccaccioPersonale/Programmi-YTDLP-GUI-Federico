import os
import re
import shutil
import subprocess
import tempfile
import traceback
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Callable, Dict, Tuple

from PySide6.QtCore import QThread, Signal

from utilita import ottieni_percorso_base, registra_log
from ffmpeg_manager import analizza_versione, contesto_ssl, piattaforma_ffmpeg, TIMEOUT_RETE, STATO_OK, STATO_ASSENTE, STATO_NON_ESEGUIBILE

# Deno e' l' interprete JavaScript che yt-dlp usa per risolvere le sfide di YouTube: senza, alcuni formati possono mancare.
URL_DENO = "https://github.com/denoland/deno/releases/"

# (sistema, architettura) -> nome della piattaforma nei file di Deno (ogni archivio contiene il solo eseguibile)
PIATTAFORME_DENO: Dict[Tuple[str, str], str] = {
	("windows", "x64"): "x86_64-pc-windows-msvc",
	("windows", "arm64"): "aarch64-pc-windows-msvc",
	("linux", "x64"): "x86_64-unknown-linux-gnu",
	("linux", "arm64"): "aarch64-unknown-linux-gnu",
	("darwin", "x64"): "x86_64-apple-darwin",
	("darwin", "arm64"): "aarch64-apple-darwin"
}

@dataclass
class StatoDeno:
	codice: str
	percorso: str = ""
	versione: str = ""
	dettagli: str = ""

class _Annullato(Exception):
	pass

def nome_eseguibile_deno() -> str:
	if os.name == "nt": return "deno.exe"
	return "deno"

def percorso_deno() -> str:
	"""Deno si cerca e si installa solo accanto al programma: quello eventualmente presente nel sistema o nel PATH viene ignorato."""
	return os.path.join(ottieni_percorso_base(), nome_eseguibile_deno())

def scaricamento_deno_supportato() -> bool:
	return piattaforma_ffmpeg() in PIATTAFORME_DENO

def leggi_versione_deno(percorso: str) -> str:
	"""Restituisce il testo della versione (es. '2.9.7'). Solleva RuntimeError se Deno non e' eseguibile o l' output non e' riconoscibile."""
	opzioni: Dict[str, int] = {}
	if os.name == "nt": opzioni["creationflags"] = subprocess.CREATE_NO_WINDOW
	try:
		esito = subprocess.run([percorso, "--version"], capture_output=True, text=True, errors="replace", timeout=20, **opzioni)
	except (OSError, subprocess.TimeoutExpired) as e:
		raise RuntimeError(f"{percorso}: {e}") from e
	if esito.returncode != 0:
		raise RuntimeError(f"{percorso}: codice di uscita {esito.returncode}\n{esito.stderr.strip()}")
	corrispondenza = re.search(r"^deno (\S+)", esito.stdout, re.MULTILINE)
	if not corrispondenza:
		raise RuntimeError(f"{percorso}: output di --version non riconosciuto\n{esito.stdout[:300]}")
	return corrispondenza.group(1)

def verifica_deno() -> StatoDeno:
	"""Controllo locale (senza rete) della sola copia accanto al programma."""
	percorso = percorso_deno()
	if not os.path.isfile(percorso): return StatoDeno(STATO_ASSENTE, percorso)
	try:
		versione = leggi_versione_deno(percorso)
	except RuntimeError as e:
		return StatoDeno(STATO_NON_ESEGUIBILE, percorso, "", str(e))
	return StatoDeno(STATO_OK, percorso, versione)

def ultima_release_deno() -> Tuple[Tuple[int, int, int], str]:
	"""Restituisce (versione come tupla, versione come testo) dell' ultima release, letta dall' indirizzo a cui GitHub reindirizza /releases/latest.
	Solleva un' eccezione se la rete non e' raggiungibile o la risposta non e' riconosciuta."""
	richiesta = urllib.request.Request(URL_DENO + "latest", method="HEAD", headers={"User-Agent": "YTDLP-GUI-Federico"})
	with urllib.request.urlopen(richiesta, timeout=TIMEOUT_RETE, context=contesto_ssl()) as risposta:
		indirizzo = risposta.geturl()
	corrispondenza = re.search(r"/tag/v(\d+\.\d+\.\d+)$", indirizzo)
	if not corrispondenza:
		raise RuntimeError(f"Indirizzo della release di Deno non riconosciuto: {indirizzo}")
	versione = analizza_versione(corrispondenza.group(1))
	if versione is None:
		raise RuntimeError(f"Versione di Deno non riconosciuta: {corrispondenza.group(1)}")
	return (versione, corrispondenza.group(1))

def scarica_file(url: str, destinazione: str, annullato: Callable[[], bool], progresso: Callable[[int], None], quota_inizio: float, quota_fine: float) -> None:
	richiesta = urllib.request.Request(url, headers={"User-Agent": "YTDLP-GUI-Federico"})
	with urllib.request.urlopen(richiesta, timeout=TIMEOUT_RETE, context=contesto_ssl()) as risposta, open(destinazione, "wb") as uscita:
		totale = int(risposta.headers.get("Content-Length") or 0)
		letti = 0
		while True:
			if annullato(): raise _Annullato()
			blocco = risposta.read(256 * 1024)
			if not blocco: break
			uscita.write(blocco)
			letti += len(blocco)
			if totale > 0: progresso(int(quota_inizio + (quota_fine - quota_inizio) * letti / totale))

class ScaricatoreDeno(QThread):
	progresso = Signal(int)
	fase = Signal(str)  # chiave del testo localizzato da mostrare
	completato = Signal(str, str)  # (cartella, versione)
	annullato = Signal()
	errore = Signal(str)

	def __init__(self, cartella_destinazione: str) -> None:
		super().__init__()
		self.cartella_destinazione = cartella_destinazione
		self._annullato = False

	def annulla(self) -> None:
		self._annullato = True

	def run(self) -> None:
		nome = nome_eseguibile_deno()
		nuovo = os.path.join(self.cartella_destinazione, nome + ".nuovo")
		cartella_temp = tempfile.mkdtemp(prefix="ytdlp_gui_deno_")
		try:
			self.fase.emit("deno_downloading")
			piattaforma = PIATTAFORME_DENO.get(piattaforma_ffmpeg())
			if piattaforma is None:
				raise RuntimeError(f"Sistema non supportato per il download automatico: {piattaforma_ffmpeg()}")
			_, versione_remota = ultima_release_deno()
			archivio = os.path.join(cartella_temp, "deno.zip")
			scarica_file(f"{URL_DENO}download/v{versione_remota}/deno-{piattaforma}.zip", archivio, lambda: self._annullato, self.progresso.emit, 0.0, 90.0)

			self.fase.emit("deno_extracting")
			os.makedirs(self.cartella_destinazione, exist_ok=True)
			trovato = False
			with zipfile.ZipFile(archivio) as zip_deno:
				for voce in zip_deno.infolist():
					if voce.is_dir() or os.path.basename(voce.filename) != nome: continue
					with zip_deno.open(voce) as sorgente, open(nuovo, "wb") as uscita:
						shutil.copyfileobj(sorgente, uscita)
					trovato = True
					break
			if not trovato:
				raise RuntimeError(f"File non trovato nell' archivio scaricato: {nome}")
			if os.name != "nt": os.chmod(nuovo, 0o755)
			destinazione = os.path.join(self.cartella_destinazione, nome)
			os.replace(nuovo, destinazione)
			versione = leggi_versione_deno(destinazione)
			self.progresso.emit(100)
			self.completato.emit(self.cartella_destinazione, versione)
		except _Annullato:
			self.annullato.emit()
		except Exception as e:
			registra_log(traceback.format_exc())
			self.errore.emit(str(e))
		finally:
			shutil.rmtree(cartella_temp, ignore_errors=True)
			if os.path.exists(nuovo):
				try:
					os.remove(nuovo)
				except OSError as e:
					registra_log(f"Impossibile rimuovere il file temporaneo {nuovo}: {e}")

class ControllaAggiornamentoDeno(QThread):
	"""Confronta la versione installata con l' ultima release disponibile. Emette 'trovato' solo se la release remota e' piu' recente."""
	trovato = Signal(str, str)  # (versione installata, versione disponibile)
	errore = Signal(str)

	def __init__(self, versione_locale: str) -> None:
		super().__init__()
		self.versione_locale = versione_locale

	def run(self) -> None:
		try:
			locale = analizza_versione(self.versione_locale)
			if locale is None: return
			remota, testo_remoto = ultima_release_deno()
			if remota > locale: self.trovato.emit(self.versione_locale, testo_remoto)
		except Exception as e:
			registra_log(traceback.format_exc())
			self.errore.emit(str(e))
