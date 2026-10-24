import os
import re
import ssl
import json
import shutil
import platform
import subprocess
import tarfile
import tempfile
import traceback
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QThread, Signal

from utilita import ottieni_percorso_base, registra_log

STATO_OK = "ok"
STATO_ASSENTE = "assente"
STATO_NON_ESEGUIBILE = "non_eseguibile"

TIMEOUT_RETE = 10

URL_BTBN = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
URL_EVERMEET = "https://evermeet.cx/ffmpeg/getrelease/"
URL_INFO_EVERMEET = "https://evermeet.cx/ffmpeg/info/ffmpeg/release"
URL_RIEDL = "https://ffmpeg.martin-riedl.de/"

# (sistema, architettura) -> (fonte, nome piattaforma nei file della fonte, tipo archivio).
# BtbN pubblica nel suo elenco (checksums.sha256) un archivio per ogni release di FFmpeg; evermeet.cx (solo Intel) e il server di Martin Riedl (anche Apple Silicon)
# pubblicano l' ultima release: macOS su Apple Silicon (arm64, lo standard attuale) usa il secondo, perche' evermeet.cx non fa build native per arm64.
SORGENTI_FFMPEG: Dict[Tuple[str, str], Tuple[str, str, str]] = {
	("windows", "x64"): ("btbn", "win64", "zip"),
	("windows", "arm64"): ("btbn", "winarm64", "zip"),
	("linux", "x64"): ("btbn", "linux64", "tar.xz"),
	("linux", "arm64"): ("btbn", "linuxarm64", "tar.xz"),
	("darwin", "x64"): ("evermeet", "", "zip"),
	("darwin", "arm64"): ("riedl", "macos/arm64", "zip")
}

@dataclass
class StatoFfmpeg:
	codice: str
	cartella: str = ""
	versione: str = ""
	dettagli: str = ""

class _Annullato(Exception):
	pass

def nomi_eseguibili() -> Tuple[str, str]:
	if os.name == "nt": return ("ffmpeg.exe", "ffprobe.exe")
	return ("ffmpeg", "ffprobe")

def piattaforma_ffmpeg() -> Tuple[str, str]:
	sistema = platform.system().lower()
	macchina = platform.machine().lower()
	if macchina in ("x86_64", "amd64"): arch = "x64"
	elif macchina in ("arm64", "aarch64"): arch = "arm64"
	else: arch = macchina
	return (sistema, arch)

def scaricamento_supportato() -> bool:
	return piattaforma_ffmpeg() in SORGENTI_FFMPEG

def percorso_coppia(cartella: str) -> Optional[Tuple[str, str]]:
	"""Restituisce (ffmpeg, ffprobe) se entrambi sono nella cartella, altrimenti None."""
	nome_ffmpeg, nome_ffprobe = nomi_eseguibili()
	p_ffmpeg = os.path.join(cartella, nome_ffmpeg)
	p_ffprobe = os.path.join(cartella, nome_ffprobe)
	if os.path.isfile(p_ffmpeg) and os.path.isfile(p_ffprobe): return (p_ffmpeg, p_ffprobe)
	return None

def leggi_versione(percorso_ffmpeg: str) -> str:
	"""Restituisce il testo della versione (es. '7.1.1' oppure 'N-127222-g151814650f-20261006').
	Solleva RuntimeError se FFmpeg non e' eseguibile o l' output non e' riconoscibile."""
	opzioni: Dict[str, int] = {}
	if os.name == "nt": opzioni["creationflags"] = subprocess.CREATE_NO_WINDOW
	try:
		esito = subprocess.run([percorso_ffmpeg, "-version"], capture_output=True, text=True, errors="replace", timeout=20, **opzioni)
	except (OSError, subprocess.TimeoutExpired) as e:
		raise RuntimeError(f"{percorso_ffmpeg}: {e}") from e
	if esito.returncode != 0:
		raise RuntimeError(f"{percorso_ffmpeg}: codice di uscita {esito.returncode}\n{esito.stderr.strip()}")
	corrispondenza = re.search(r"^ffmpeg version (\S+)", esito.stdout, re.MULTILINE)
	if not corrispondenza:
		raise RuntimeError(f"{percorso_ffmpeg}: output di -version non riconosciuto\n{esito.stdout[:300]}")
	return corrispondenza.group(1)

def analizza_versione(testo: str) -> Optional[Tuple[int, int, int]]:
	"""Estrae la versione numerica (es. '7.1.1' -> (7, 1, 1), 'n9.0.2-22-g46d8f462ee-20261006' -> (9, 0, 2)).
	Restituisce None se il formato non e' numerico (build 'git' tipo N-127222-g151814650f-20261006): in tal caso non si puo' confrontare."""
	corrispondenza = re.match(r"[nN]?(\d+)\.(\d+)(?:\.(\d+))?", testo)
	if not corrispondenza: return None
	return (int(corrispondenza.group(1)), int(corrispondenza.group(2)), int(corrispondenza.group(3) or 0))

def verifica_ffmpeg() -> StatoFfmpeg:
	"""Controllo locale (senza rete) della sola copia accanto al programma: FFmpeg installato in sistema o nel PATH viene ignorato."""
	cartella = ottieni_percorso_base()
	coppia = percorso_coppia(cartella)
	if coppia is None: return StatoFfmpeg(STATO_ASSENTE, cartella)
	try:
		versione = leggi_versione(coppia[0])
	except RuntimeError as e:
		return StatoFfmpeg(STATO_NON_ESEGUIBILE, cartella, "", str(e))
	return StatoFfmpeg(STATO_OK, cartella, versione)

def contesto_ssl() -> ssl.SSLContext:
	"""Certificati di sistema piu' quelli di certifi (se disponibile). I soli certifi escluderebbero le CA aggiunte dal sistema (reti aziendali, antivirus);
	i soli certificati di sistema possono mancare negli eseguibili PyInstaller, soprattutto su macOS."""
	contesto = ssl.create_default_context()
	try:
		import certifi
	except ImportError:
		return contesto
	contesto.load_verify_locations(cafile=certifi.where())
	return contesto

def scarica_testo(url: str) -> str:
	richiesta = urllib.request.Request(url, headers={"User-Agent": "YTDLP-GUI-Federico"})
	with urllib.request.urlopen(richiesta, timeout=TIMEOUT_RETE, context=contesto_ssl()) as risposta:
		return risposta.read().decode("utf-8")

def ultima_release_ffmpeg() -> Tuple[Tuple[int, int, int], List[Tuple[str, str]]]:
	"""Interroga la fonte della piattaforma. Restituisce (versione dell' ultima release, [(url, tipo archivio)]).
	Solleva un' eccezione se la rete non e' raggiungibile o la risposta non e' riconosciuta."""
	sorgente = SORGENTI_FFMPEG.get(piattaforma_ffmpeg())
	if sorgente is None:
		raise RuntimeError(f"Sistema non supportato per il download automatico: {piattaforma_ffmpeg()}")
	nome, piattaforma, tipo = sorgente
	if nome == "btbn":
		elenco = scarica_testo(URL_BTBN + "checksums.sha256")
		schema = re.compile(rf"ffmpeg-n(\d+(?:\.\d+)*)-latest-{piattaforma}-gpl-\d+(?:\.\d+)*\.{re.escape(tipo)}\b")
		trovate = [(analizza_versione(m.group(1)), m.group(0)) for m in schema.finditer(elenco)]
		if not trovate:
			raise RuntimeError(f"Nessuna release per {piattaforma} nell' elenco di {URL_BTBN}")
		versione, archivio = max(trovate, key=lambda t: t[0])
		return (versione, [(URL_BTBN + archivio, tipo)])
	if nome == "riedl":
		# /redirect/latest/... reindirizza a /download/<sistema>/<arch>/<numero>_<versione>/ffmpeg.zip: la versione si legge dall' indirizzo finale
		richiesta = urllib.request.Request(f"{URL_RIEDL}redirect/latest/{piattaforma}/release/ffmpeg.zip", headers={"User-Agent": "YTDLP-GUI-Federico"})
		with urllib.request.urlopen(richiesta, timeout=TIMEOUT_RETE, context=contesto_ssl()) as risposta:
			indirizzo = risposta.geturl()
		trovato = re.match(r"^(.*/\d+_(\d+(?:\.\d+)+)/)ffmpeg\.zip$", indirizzo)
		versione = analizza_versione(trovato.group(2)) if trovato else None
		if trovato is None or versione is None:
			raise RuntimeError(f"Indirizzo della release di FFmpeg non riconosciuto: {indirizzo}")
		return (versione, [(trovato.group(1) + "ffmpeg.zip", "zip"), (trovato.group(1) + "ffprobe.zip", "zip")])
	dati = json.loads(scarica_testo(URL_INFO_EVERMEET))
	versione = analizza_versione(str(dati.get("version", "")))
	if versione is None:
		raise RuntimeError(f"Risposta di {URL_INFO_EVERMEET} non riconosciuta: {str(dati)[:200]}")
	return (versione, [(URL_EVERMEET + "zip", "zip"), (URL_EVERMEET + "ffprobe/zip", "zip")])

def estrai_eseguibili(percorso_archivio: str, tipo: str, cartella_destinazione: str, nomi_voluti: List[str]) -> List[str]:
	"""Estrae dall' archivio solo i file con i nomi richiesti (ignorando le sottocartelle), salvandoli con estensione .nuovo.
	Restituisce i nomi trovati."""
	trovati: List[str] = []
	if tipo == "zip":
		with zipfile.ZipFile(percorso_archivio) as archivio:
			for voce in archivio.infolist():
				nome = os.path.basename(voce.filename)
				if voce.is_dir() or nome not in nomi_voluti or nome in trovati: continue
				with archivio.open(voce) as sorgente, open(os.path.join(cartella_destinazione, nome + ".nuovo"), "wb") as uscita:
					shutil.copyfileobj(sorgente, uscita)
				trovati.append(nome)
	else:
		with tarfile.open(percorso_archivio, "r:xz") as archivio:
			for voce in archivio:
				nome = os.path.basename(voce.name)
				if not voce.isfile() or nome not in nomi_voluti or nome in trovati: continue
				sorgente = archivio.extractfile(voce)
				if sorgente is None: continue
				with sorgente, open(os.path.join(cartella_destinazione, nome + ".nuovo"), "wb") as uscita:
					shutil.copyfileobj(sorgente, uscita)
				trovati.append(nome)
				if len(trovati) == len(nomi_voluti): break
	return trovati

class ScaricatoreFfmpeg(QThread):
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

	def _scarica(self, url: str, destinazione: str, quota_inizio: float, quota_fine: float) -> None:
		richiesta = urllib.request.Request(url, headers={"User-Agent": "YTDLP-GUI-Federico"})
		with urllib.request.urlopen(richiesta, timeout=TIMEOUT_RETE, context=contesto_ssl()) as risposta, open(destinazione, "wb") as uscita:
			totale = int(risposta.headers.get("Content-Length") or 0)
			letti = 0
			while True:
				if self._annullato: raise _Annullato()
				blocco = risposta.read(256 * 1024)
				if not blocco: break
				uscita.write(blocco)
				letti += len(blocco)
				if totale > 0: self.progresso.emit(int(quota_inizio + (quota_fine - quota_inizio) * letti / totale))

	def run(self) -> None:
		nomi_voluti = list(nomi_eseguibili())
		cartella_temp = tempfile.mkdtemp(prefix="ytdlp_gui_ffmpeg_")
		try:
			self.fase.emit("ffmpeg_downloading")
			versione_remota, fonti = ultima_release_ffmpeg()
			os.makedirs(self.cartella_destinazione, exist_ok=True)
			trovati: List[str] = []
			for indice, (url, tipo) in enumerate(fonti):
				self.fase.emit("ffmpeg_downloading")
				archivio = os.path.join(cartella_temp, f"archivio{indice}")
				self._scarica(url, archivio, 90.0 * indice / len(fonti), 90.0 * (indice + 1) / len(fonti))
				self.fase.emit("ffmpeg_extracting")
				trovati += estrai_eseguibili(archivio, tipo, self.cartella_destinazione, [n for n in nomi_voluti if n not in trovati])
				os.remove(archivio)
			mancanti = [n for n in nomi_voluti if n not in trovati]
			if mancanti:
				raise RuntimeError(f"File non trovati nell' archivio scaricato: {', '.join(mancanti)}")
			for nome in nomi_voluti:
				nuovo = os.path.join(self.cartella_destinazione, nome + ".nuovo")
				if os.name != "nt": os.chmod(nuovo, 0o755)
				os.replace(nuovo, os.path.join(self.cartella_destinazione, nome))
			versione = leggi_versione(os.path.join(self.cartella_destinazione, nomi_voluti[0]))
			self.progresso.emit(100)
			self.completato.emit(self.cartella_destinazione, versione)
		except _Annullato:
			self.annullato.emit()
		except Exception as e:
			registra_log(traceback.format_exc())
			self.errore.emit(str(e))
		finally:
			shutil.rmtree(cartella_temp, ignore_errors=True)
			for nome in nomi_voluti:
				residuo = os.path.join(self.cartella_destinazione, nome + ".nuovo")
				if os.path.exists(residuo):
					try:
						os.remove(residuo)
					except OSError as e:
						registra_log(f"Impossibile rimuovere il file temporaneo {residuo}: {e}")

class ControllaAggiornamentoFfmpeg(QThread):
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
			remota, _ = ultima_release_ffmpeg()
			if remota > locale: self.trovato.emit(self.versione_locale, ".".join(str(n) for n in remota))
		except Exception as e:
			registra_log(traceback.format_exc())
			self.errore.emit(str(e))