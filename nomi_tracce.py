import os
import re
from typing import Dict, List, NamedTuple, Tuple

from yt_dlp.postprocessor import FFmpegPostProcessor
from yt_dlp.utils import prepend_extension

from sottotitoli import SceltaSottotitolo, TIPO_AUTOMATICO, radice_sottotitolo

TRACCIA_VIDEO = "video"
TRACCIA_AUDIO = "audio"
TRACCIA_ALTRO = "other"

# Prefisso delle tracce automatiche nei nomi dei file: nomeFile.auto.lingua.ext (le manuali o originali: nomeFile.lingua.ext)
PREFISSO_AUTOMATICO = "auto"

class SceltaTraccia(NamedTuple):
	"""Una traccia video o audio spuntata dall' utente."""
	format_id: str
	tipo: str  # TRACCIA_VIDEO o TRACCIA_AUDIO
	nome: str  # nome completo: titolo del flusso nel file unito (es. 'Italiano (Italia) - Sintetica / Tradotta - mp4a 129k')
	parte_nome: str  # parte del nome del file in modalita' separata (es. 'auto.it-IT', '1080p60')

def parte_nome_audio(lingua: str, automatica: bool) -> str:
	codice = lingua or "und"
	if automatica: return f"{PREFISSO_AUTOMATICO}.{codice}"
	return codice

def parte_nome_video(altezza: int, fps: float) -> str:
	"""Es. 1080p60; senza altezza nota (alcuni siti non la espongono) 'video'."""
	base = f"{altezza}p" if altezza else "video"
	if fps: return f"{base}{int(fps)}"
	return base

def parte_nome_altro(nota: str, larghezza: int, altezza: int) -> str:
	"""Es. 'storyboard' 160x90 -> 'storyboard.160x90'."""
	nome = re.sub(r"[^\w-]+", "_", nota).strip("_") or "other"
	if larghezza and altezza: return f"{nome}.{larghezza}x{altezza}"
	return nome

def nomi_file_tracce(tracce: List[SceltaTraccia]) -> Dict[str, str]:
	"""format_id -> parte del nome file. Se piu' tracce avrebbero lo stesso nome (es. due formati della stessa lingua) a tutte si aggiunge l' ID del formato:
	altrimenti si sovrascriverebbero."""
	conteggi: Dict[str, int] = {}
	for traccia in tracce: conteggi[traccia.parte_nome] = conteggi.get(traccia.parte_nome, 0) + 1
	return {t.format_id: (f"{t.parte_nome}.{t.format_id}" if conteggi[t.parte_nome] > 1 else t.parte_nome) for t in tracce}

def ridenomina_file(cartella: str, nome_base: str, tracce: List[SceltaTraccia], scelte_sottotitoli: List[SceltaSottotitolo], separato: bool) -> List[Tuple[str, str]]:
	"""Porta i file scaricati ai nomi finali. Restituisce l' elenco (nome vecchio, nome nuovo).
	- modalita' separata: yt-dlp salva ogni traccia come nomeFile.ID.ext (l' ID evita che le tracce si sovrascrivano) e qui diventa nomeFile.[auto.]lingua.ext
	- sottotitoli automatici esterni: yt-dlp li salva come nomeFile.lingua.auto.ext e qui diventano nomeFile.auto.lingua.ext
	(le traduzioni: nomeFile.lingua.da-origine.auto.ext -> nomeFile.auto.lingua.da-origine.ext)"""
	rinominati: List[Tuple[str, str]] = []
	presenti = os.listdir(cartella)

	def sposta(vecchio: str, nuovo: str) -> None:
		os.replace(os.path.join(cartella, vecchio), os.path.join(cartella, nuovo))
		rinominati.append((vecchio, nuovo))

	if separato:
		nomi = nomi_file_tracce(tracce)
		for traccia in tracce:
			modello = re.compile(rf"^{re.escape(nome_base)}\.{re.escape(traccia.format_id)}\.([^.]+)$")
			for nome_file in presenti:
				trovato = modello.match(nome_file)
				if trovato: sposta(nome_file, f"{nome_base}.{nomi[traccia.format_id]}.{trovato.group(1)}")
	for scelta in scelte_sottotitoli:
		if scelta.tipo != TIPO_AUTOMATICO: continue
		radice = radice_sottotitolo(scelta.lingua, scelta.origine)
		modello = re.compile(rf"^{re.escape(nome_base)}\.{re.escape(radice)}\.{PREFISSO_AUTOMATICO}\.([^.]+)$")
		for nome_file in presenti:
			trovato = modello.match(nome_file)
			if trovato: sposta(nome_file, f"{nome_base}.{PREFISSO_AUTOMATICO}.{radice}.{trovato.group(1)}")
	return rinominati

class ImpostaTitoliTracce(FFmpegPostProcessor):
	"""Dopo l' unione scrive come titolo di ogni flusso audio e video il nome completo della traccia.
	L' ordine dei flussi e' quello di yt-dlp (FFmpegMergerPP): per ogni formato richiesto, nell' ordine, un flusso audio e/o uno video."""

	def __init__(self, downloader, titoli: Dict[str, str]) -> None:
		super().__init__(downloader)
		self.titoli = titoli

	def run(self, info: dict):
		formati = info.get('requested_formats')
		if not formati: return [], info
		opzioni = ['-c', 'copy', '-map', '0']
		audio = 0
		video = 0
		for formato in formati:
			titolo = self.titoli.get(str(formato.get('format_id')))
			if formato.get('acodec') != 'none':
				if titolo: opzioni += [f'-metadata:s:a:{audio}', f'title={titolo}']
				audio += 1
			if formato.get('vcodec') != 'none':
				if titolo: opzioni += [f'-metadata:s:v:{video}', f'title={titolo}']
				video += 1
		if len(opzioni) == 4: return [], info
		nome_file = info['filepath']
		temporaneo = prepend_extension(nome_file, 'temp')
		self.to_screen(f'Impostazione dei titoli delle tracce in "{nome_file}"')
		self.run_ffmpeg(nome_file, temporaneo, opzioni)
		os.replace(temporaneo, nome_file)
		return [], info