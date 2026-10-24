import re
import time
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from yt_dlp.networking.exceptions import HTTPError, RequestError
from yt_dlp.utils import DownloadError, ExtractorError

from diagnostica import YoutubeDLConDiagnostica

TIPO_MANUALE = "manual"
TIPO_AUTOMATICO = "auto"

# Suffisso della chiave dei sottotitoli automatici: yt-dlp usa la chiave nel nome del file (nomeFile.chiave.ext), quindi il manuale si chiama
# nomeFile.it-CH.vtt e l' automatico nomeFile.it-CH.auto.vtt. Cosi' i due si distinguono anche quando esistono per la stessa lingua.
SUFFISSO_AUTOMATICO = "auto"

# YouTube risponde 429 (Too Many Requests) ai sottotitoli automatici tradotti in un' altra lingua, non ai manuali ne' agli automatici nella lingua originale (-orig).
# Si aspetta ATTESA_INIZIALE_S secondi dall' estrazione prima di scaricare un sottotitolo tradotto; a ogni errore 429 l' attesa aumenta di INCREMENTO_ATTESA_S secondi
# e si riprova, fino a TENTATIVI_DOPO_429 volte.
MOTIVO_NON_DISPONIBILE = "not available"  # marcatore: chi mostra l' elenco dei falliti lo sostituisce con il testo nella lingua dell' interfaccia

ATTESA_INIZIALE_S = 20
INCREMENTO_ATTESA_S = 30
TENTATIVI_DOPO_429 = 3  # nuovi tentativi: con l' attesa iniziale sono 4 tentativi in tutto, dopo 20, 50, 80 e 110 secondi

class SceltaSottotitolo(NamedTuple):
	"""Una casella spuntata dall' utente: codice lingua completo (es. 'it-CH'), tipo (manuale/automatico), nome completo della traccia e,
	per un automatico tradotto, la lingua della traccia da cui e' tradotto (origine); vuota per manuali e automatici nella lingua stessa."""
	lingua: str
	tipo: str
	nome: str
	origine: str = ""

class AttesaSottotitolo(NamedTuple):
	"""Stato di un' attesa in corso, per informare l' utente che il download non e' finito."""
	secondi: int  # secondi che mancano
	nome: str  # nome completo della traccia che si sta aspettando di scaricare
	tentativo: int  # 0 = attesa iniziale; k = k-esimo nuovo tentativo dopo un errore
	tentativi_max: int
	per_errore: bool  # True se l' attesa e' dovuta a un errore 429

def radice_sottotitolo(lingua: str, origine: str) -> str:
	"""Parte del nome che identifica la traccia: 'it-CH' oppure, per una traduzione, 'it.da-en'."""
	if origine: return f"{lingua}.da-{origine}"
	return lingua

def chiave_sottotitolo(lingua: str, tipo: str, origine: str = "") -> str:
	if tipo == TIPO_AUTOMATICO: return f"{radice_sottotitolo(lingua, origine)}.{SUFFISSO_AUTOMATICO}"
	return lingua

def origine_voce(voce: dict) -> Tuple[str, bool]:
	"""(lingua della traccia sorgente, e' una traduzione). L' indirizzo di YouTube ha lang=<sorgente> e, se tradotto, tlang=<destinazione>."""
	parametri = parse_qs(urlparse(voce.get('url') or '').query)
	return (parametri.get('lang', [''])[0], 'tlang' in parametri)

def voci_per_origine(formati: List[dict]) -> Dict[str, List[dict]]:
	"""La lista di una lingua automatica contiene piu' tracce: quella nella lingua stessa (chiave '') e le traduzioni dalle altre tracce del video (chiave = lingua sorgente).
	Ogni traccia ha i suoi formati."""
	gruppi: Dict[str, List[dict]] = {}
	for voce in formati:
		sorgente, tradotta = origine_voce(voce)
		gruppi.setdefault((sorgente or "?") if tradotta else "", []).append(voce)
	return gruppi

class YoutubeDLConSottotitoli(YoutubeDLConDiagnostica):
	"""Scarica esattamente i sottotitoli scelti dall' utente, uno per ogni coppia (lingua, tipo).
	yt-dlp da solo non lo permette: con i due flag attivi, se per una lingua esiste il manuale scarica sempre quello e mai l' automatico,
	e non puo' scaricarli entrambi. Qui la selezione si fa per tipo, riusando la scelta del formato di yt-dlp (opzione subtitlesformat),
	e a ogni traccia si da' il nome completo: yt-dlp lo scrive come titolo del flusso quando i sottotitoli vengono incorporati."""

	def __init__(self, params: dict, scelte: List[SceltaSottotitolo], su_stato: Optional[Callable[[Optional[AttesaSottotitolo]], None]] = None,
				 attesa_iniziale: float = ATTESA_INIZIALE_S, incremento: float = INCREMENTO_ATTESA_S, tentativi: int = TENTATIVI_DOPO_429) -> None:
		super().__init__(params)
		self.scelte_sottotitoli = scelte
		self.su_stato = su_stato  # chiamata ogni secondo durante un' attesa e con None alla fine
		self.attesa = attesa_iniziale  # attesa corrente: aumenta a ogni errore 429 e non torna indietro
		self.incremento = incremento
		self.tentativi = tentativi
		self.pronto_dopo = time.monotonic() + self.attesa  # istante prima del quale non si scarica un sottotitolo tradotto
		self.esaurito = False  # True dopo che un sottotitolo ha esaurito i tentativi
		self.sottotitoli_falliti: List[Tuple[str, str]] = []  # (nome completo della traccia, motivo)

	def attendi_fino(self, istante: float, nome: str, tentativo: int, per_errore: bool) -> None:
		while True:
			rimanenti = istante - time.monotonic()
			if rimanenti <= 0: break
			if self.su_stato: self.su_stato(AttesaSottotitolo(int(rimanenti) + 1, nome, tentativo, self.tentativi, per_errore))
			time.sleep(min(1.0, rimanenti))
		if self.su_stato: self.su_stato(None)

	def dl(self, name: str, info: dict, subtitle: bool = False, test: bool = False):
		"""Per i sottotitoli: i tradotti automaticamente (l' indirizzo contiene 'tlang=') aspettano l' istante pronto_dopo; a ogni errore 429 l' attesa aumenta
		e si riprova. Dopo che un sottotitolo ha esaurito i tentativi, per i tradotti successivi si fa un solo tentativo. Se un sottotitolo non si riesce a scaricare
		non si blocca tutto il download (yt-dlp, di default, si fermerebbe prima ancora di scaricare video e audio): il fallimento resta in sottotitoli_falliti,
		per mostrarlo all' utente."""
		if not subtitle: return super().dl(name, info, subtitle=subtitle, test=test)
		nome = str(info.get('name') or name)
		tradotto = "tlang=" in (info.get('url') or '')
		if tradotto and not self.esaurito: self.attendi_fino(self.pronto_dopo, nome, 0, False)
		tentativi = 0 if (tradotto and self.esaurito) else self.tentativi
		motivo = ""
		limite_richieste = False
		for tentativo in range(tentativi + 1):
			try:
				return super().dl(name, info, subtitle=subtitle, test=test)
			except (RequestError, DownloadError, ExtractorError, OSError, ValueError) as errore:
				motivo = str(errore)
				limite_richieste = isinstance(errore, HTTPError) and errore.status == 429
				if not limite_richieste or tentativo == tentativi: break
				self.attesa += self.incremento
				self.pronto_dopo = time.monotonic() + self.attesa
				self.attendi_fino(self.pronto_dopo, nome, tentativo + 1, True)
		if limite_richieste: self.esaurito = True
		self.sottotitoli_falliti.append((nome, motivo))
		return (False, False)

	def seleziona_sottotitoli(self, video_id: str, lingue: List[str], manuali: dict, automatici: dict) -> Dict[str, dict]:
		"""Una sola chiamata a process_subtitles di yt-dlp per tipo, con i flag e le lingue impostati solo per la durata della chiamata.
		Le lingue sono espressioni regolari per yt-dlp: si proteggono i caratteri speciali."""
		originali = {chiave: self.params.get(chiave) for chiave in ("writesubtitles", "writeautomaticsub", "subtitleslangs")}
		self.params.update(writesubtitles=bool(manuali), writeautomaticsub=bool(automatici), subtitleslangs=[re.escape(lingua) for lingua in lingue])
		try:
			return super().process_subtitles(video_id, manuali, automatici) or {}
		finally:
			self.params.update(originali)

	def process_subtitles(self, video_id: str, normal_subtitles: Optional[dict], automatic_captions: Optional[dict]) -> Optional[Dict[str, dict]]:
		self.pronto_dopo = max(self.pronto_dopo, time.monotonic() + self.attesa)  # chiamata subito dopo l' estrazione dei dati del video
		scelti: Dict[str, dict] = {}
		for scelta in self.scelte_sottotitoli:
			if scelta.tipo == TIPO_MANUALE:
				formati = (normal_subtitles or {}).get(scelta.lingua) or []
				trovati = self.seleziona_sottotitoli(video_id, [scelta.lingua], {scelta.lingua: formati}, {}) if formati else {}
			else:
				formati = voci_per_origine((automatic_captions or {}).get(scelta.lingua) or []).get(scelta.origine) or []
				trovati = self.seleziona_sottotitoli(video_id, [scelta.lingua], {}, {scelta.lingua: formati}) if formati else {}
			if not trovati:
				self.sottotitoli_falliti.append((scelta.nome, MOTIVO_NON_DISPONIBILE))
				continue
			scelti[chiave_sottotitolo(scelta.lingua, scelta.tipo, scelta.origine)] = dict(trovati[scelta.lingua], name=scelta.nome)
		return scelti or None