import os
import subprocess
import sys
import traceback
from typing import Dict, List, Optional, Set

import yt_dlp
from PySide6.QtCore import QThread, Signal

from utilita import registra_log
from diagnostica import YoutubeDLConDiagnostica
import unione
from solo_sottotitoli import unisci_in_mks
from metadati import costruisci_testo_metadati
from sottotitoli import YoutubeDLConSottotitoli, SceltaSottotitolo, AttesaSottotitolo, TIPO_MANUALE, TIPO_AUTOMATICO, MOTIVO_NON_DISPONIBILE
from nomi_tracce import SceltaTraccia, ImpostaTitoliTracce, ridenomina_file, PREFISSO_AUTOMATICO


# Avanzamento: il download dei flussi occupa fino all' 85%; il 100% si emette solo alla fine di tutto il lavoro (prima il tetto e' il 99%)
QUOTA_DOWNLOAD = 85.0
LIMITE_PRIMA_DEL_TERMINE = 99.0

unione.attiva()  # l' unione dei flussi di yt-dlp ripara i flussi senza timestamp (vedi unione.py)

class RegistroYtdlp:
	"""Logger per yt-dlp: raccoglie gli avvisi invece di scartarli (quiet=True li nasconde)."""
	def __init__(self) -> None:
		self.avvisi: List[str] = []
	def debug(self, msg: str) -> None: pass
	def info(self, msg: str) -> None: pass
	def warning(self, msg: str) -> None: self.avvisi.append(msg)
	def error(self, msg: str) -> None: pass  # l'errore arriva comunque come eccezione
	def testo(self) -> str: return "\n".join(self.avvisi)

def costruisci_comando_cli(opzioni: dict, url: str, scelte_sottotitoli: List[SceltaSottotitolo], lingue_con_manuale: Set[str], nota_incorporati: str, nota_traduzioni: str,
						   altre: List[SceltaTraccia], principale: bool, nome_base: str, nota_mks: str = "") -> str:
	"""Comando di yt-dlp equivalente alle scelte fatte. Se un solo comando non basta restituisce piu' comandi, uno per riga:
	i sottotitoli manuali e automatici si scaricano con comandi separati, perche' da riga di comando i secondi si distinguono solo cosi' (nome nomeFile.auto.lingua.ext)
	e perche' con i due flag insieme yt-dlp preferisce il manuale quando per una lingua esistono entrambi."""
	manuali = [s.lingua for s in scelte_sottotitoli if s.tipo == TIPO_MANUALE]
	automatici = [s.lingua for s in scelte_sottotitoli if s.tipo == TIPO_AUTOMATICO]
	incorporati = any(pp.get('key') == 'FFmpegEmbedSubtitle' for pp in opzioni.get('postprocessors', []))
	sub_fmt = opzioni.get('subtitlesformat')
	modello_sub = opzioni.get('outtmpl', {}).get('subtitle') or opzioni.get('outtmpl', {}).get('default') or ""
	modello_sub_auto = modello_sub.replace(".%(ext)s", f".{PREFISSO_AUTOMATICO}.%(ext)s")
	in_conflitto = bool(manuali) and any(lingua in lingue_con_manuale for lingua in automatici)
	automatici_a_parte = bool(manuali) and bool(automatici) and (not incorporati or in_conflitto)

	parti = ["yt-dlp"]
	parti.append(f'"{url}"')

	fmt = opzioni.get('format')
	if opzioni.get('skip_download'): parti.append("--skip-download")  # solo sottotitoli: il formato non si usa
	elif fmt:
		parti.append(f'-f "{fmt}"')

	outtmpl = opzioni.get('outtmpl', {}).get('default')
	if outtmpl:
		parti.append(f'-o "{outtmpl}"')

	if opzioni.get('addmetadata'):
		parti.append("--add-metadata")

	if opzioni.get('embedchapters'):
		parti.append("--embed-chapters")

	merge_fmt = opzioni.get('merge_output_format')
	if merge_fmt:
		parti.append(f'--merge-output-format {merge_fmt}')

	if opzioni.get('allow_multiple_audio_streams'):
		parti.append("--audio-multistreams")
	if opzioni.get('allow_multiple_video_streams'):
		parti.append("--video-multistreams")

	lingue_comando = manuali if automatici_a_parte else list(dict.fromkeys(manuali + automatici))
	if manuali:
		parti.append("--write-subs")
	if automatici and not automatici_a_parte:
		parti.append("--write-auto-subs")
	if lingue_comando:
		parti.append(f'--sub-langs "{",".join(lingue_comando)}"')
	if automatici and not manuali and not incorporati and modello_sub_auto:
		parti.append(f'-o "subtitle:{modello_sub_auto}"')

	if sub_fmt:
		parti.append(f'--sub-format "{sub_fmt}"')

	if incorporati:
		parti.append("--embed-subs")

	if 'sponsorblock_remove' in opzioni:
		cats = ",".join(opzioni['sponsorblock_remove'])
		parti.append(f'--sponsorblock-remove "{cats}"')
	elif 'sponsorblock_mark' in opzioni:
		cats = ",".join(opzioni['sponsorblock_mark'])
		parti.append(f'--sponsorblock-mark "{cats}"')
		if 'sponsorblock_chapter_title' in opzioni:
			parti.append(f'--sponsorblock-chapter-title "{opzioni["sponsorblock_chapter_title"]}"')

	righe = [" ".join(parti)] if principale else []
	if automatici_a_parte:
		secondo = ["yt-dlp", f'"{url}"', "--skip-download", "--write-auto-subs", f'--sub-langs "{",".join(dict.fromkeys(automatici))}"']
		if sub_fmt: secondo.append(f'--sub-format "{sub_fmt}"')
		if modello_sub_auto: secondo.append(f'-o "subtitle:{modello_sub_auto}"')
		righe.append(" ".join(secondo))
		if incorporati and in_conflitto: righe.append(f"# {nota_incorporati}")
	if nota_mks: righe.append(f"# {nota_mks}")
	# Da riga di comando yt-dlp non puo' scegliere da quale traccia e' tradotto un sottotitolo
	if any(scelta.origine for scelta in scelte_sottotitoli): righe.append(f"# {nota_traduzioni}")
	if altre:
		# Le altre tracce (es. storyboard) si scaricano a parte, ognuna come nomeFile.ID.ext
		cartella = os.path.dirname(opzioni.get('outtmpl', {}).get('default') or "") or "."
		modello = os.path.join(cartella, f"{nome_base}.%(format_id)s.%(ext)s").replace("\\", "/")
		righe.append(f'yt-dlp "{url}" -f "{",".join(t.format_id for t in altre)}" -o "{modello}"')
	return "\n".join(righe)

class Analizzatore(QThread):
	completato = Signal(dict)
	errore = Signal(str)
	avvisi = Signal(str)

	def __init__(self, url: str, js_runtimes: dict) -> None:
		super().__init__()
		self.url = url
		self.js_runtimes = js_runtimes

	def run(self) -> None:
		registro = RegistroYtdlp()
		try:
			opzioni = {'quiet': True, 'skip_download': True, 'logger': registro}
			if self.js_runtimes: opzioni['js_runtimes'] = self.js_runtimes
			with yt_dlp.YoutubeDL(opzioni) as ydl:
				info = ydl.extract_info(self.url, download=False)
			self.completato.emit(info)
			if registro.avvisi:
				self.avvisi.emit(registro.testo())
		except Exception as e:
			registra_log(traceback.format_exc())
			self.errore.emit(str(e) + (f"\n\n{registro.testo()}" if registro.avvisi else ""))

class Scaricatore(QThread):
	progresso = Signal(float)
	stato = Signal(str)  # testo da mostrare nella barra di avanzamento (vuoto = nessun testo)
	completato = Signal()
	errore = Signal(str)
	avvisi = Signal(str)

	def __init__(self, opzioni: dict, url: str, info: dict, nome_base_out: str, num_flussi: int, etichette_meta: Dict[str, str], scelte_sottotitoli: List[SceltaSottotitolo], tracce: List[SceltaTraccia], separato: bool, elenco_tracce: Dict[str, List[str]], altre: List[SceltaTraccia], principale: bool, unisci_sottotitoli: bool = False) -> None:
		super().__init__()
		self.unisci_sottotitoli = unisci_sottotitoli  # solo sottotitoli, integrati: si uniscono in un unico file Matroska (.mks)
		self.altre = altre
		self.principale = principale
		self.elenco_tracce = elenco_tracce
		self.etichette_meta = etichette_meta
		self.scelte_sottotitoli = scelte_sottotitoli
		self.tracce = tracce
		self.separato = separato
		self.opzioni = opzioni
		self.url = url
		self.info = info
		self.nome_base_out = nome_base_out
		self.num_flussi = max(1, num_flussi)
		self._flussi_completati = 0
		self._ultimo_progresso = 0.0

	def _su_stato(self, attesa: Optional[AttesaSottotitolo]) -> None:
		"""Testo per la barra di stato: attesa iniziale oppure errore 429 con il nuovo tentativo; vuoto quando l' attesa e' finita."""
		if attesa is None: self.stato.emit("")
		elif attesa.per_errore: self.stato.emit(self.etichette_meta['subs_retry_status'].format(name=attesa.nome, seconds=attesa.secondi, attempt=attesa.tentativo + 1, total=attesa.tentativi_max + 1))
		else: self.stato.emit(self.etichette_meta['subs_wait_status'].format(name=attesa.nome, seconds=attesa.secondi))

	def _emetti_progresso(self, valore: float) -> None:
		"""Il progresso non torna mai indietro e non arriva a 100% finche' tutto il lavoro non e' finito (download, unione, metadati): il 100% si emette solo alla fine."""
		valore = min(valore, LIMITE_PRIMA_DEL_TERMINE)
		if valore > self._ultimo_progresso:
			self._ultimo_progresso = valore
			self.progresso.emit(valore)

	def _hook_progresso(self, d: dict) -> None:
		# Fanno avanzare il progresso solo i flussi audio e video (hanno un format_id): gli eventi dei sottotitoli e di altri file non sono flussi
		# e, contati come tali, portavano il totale oltre il 100%
		if not (d.get('info_dict') or {}).get('format_id'): return
		if d['status'] == 'downloading':
			totale = d.get('total_bytes') or d.get('total_bytes_estimate')
			scaricati = d.get('downloaded_bytes', 0)
			if totale and totale > 0:
				progresso_flusso = min(1.0, scaricati / totale)
				quota_flusso = QUOTA_DOWNLOAD / self.num_flussi
				self._emetti_progresso(min(QUOTA_DOWNLOAD, (self._flussi_completati * quota_flusso) + (progresso_flusso * quota_flusso)))
		elif d['status'] == 'finished':
			self._flussi_completati += 1
			quota_flusso = QUOTA_DOWNLOAD / self.num_flussi
			self._emetti_progresso(min(QUOTA_DOWNLOAD, self._flussi_completati * quota_flusso))

	def _hook_postprocessor(self, d: dict) -> None:
		if d['status'] == 'started': self._emetti_progresso(88.0)
		elif d['status'] == 'finished': self._emetti_progresso(95.0)

	def contesto_errore(self, ydl: Optional[YoutubeDLConDiagnostica]) -> str:
		"""Testo per il log quando il download fallisce: le scelte fatte, le versioni e, se ffmpeg e' stato eseguito, la sua riga di comando e il suo errore completo."""
		righe = ["Contesto del download:", f"  URL: {self.url}", f"  formato richiesto: {self.opzioni.get('format')}",
				 f"  unione: {self.opzioni.get('merge_output_format') or 'file separati'}",
				 f"  tracce scelte: {', '.join(f'{t.format_id} ({t.nome})' for t in self.tracce + self.altre) or 'nessuna'}",
				 f"  sottotitoli scelti: {', '.join(s.nome for s in self.scelte_sottotitoli) or 'nessuno'}",
				 f"  yt-dlp: {yt_dlp.version.__version__}"]
		ffmpeg = os.path.join(self.opzioni.get('ffmpeg_location') or "", "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
		try:
			versione = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True, timeout=10).stdout.splitlines()
			righe.append(f"  ffmpeg: {versione[0] if versione else '?'}")
		except Exception as errore:
			righe.append(f"  ffmpeg: non eseguibile ({errore})")
		comando, errore_ffmpeg = ydl.ultimo_errore_ffmpeg(40) if ydl is not None else ("", [])
		if comando: righe += ["Comando di ffmpeg:", f"  {comando}"]
		if errore_ffmpeg: righe += ["Messaggi di ffmpeg:"] + [f"  {r}" for r in errore_ffmpeg]
		return "\n".join(righe)

	def run(self) -> None:
		registro = RegistroYtdlp()
		ydl_corrente: Optional[YoutubeDLConDiagnostica] = None  # per il log degli errori (vedi contesto_errore)
		try:
			self.opzioni['progress_hooks'] = [self._hook_progresso]
			self.opzioni['postprocessor_hooks'] = [self._hook_postprocessor]
			opzioni_ydl = dict(self.opzioni)
			opzioni_ydl['logger'] = registro
			opzioni_ydl['postprocessors'] = list(self.opzioni.get('postprocessors', []))
			rimuovi = list(opzioni_ydl.pop('sponsorblock_remove', []) or [])
			marca = list(opzioni_ydl.pop('sponsorblock_mark', []) or [])
			titolo_cap = opzioni_ydl.pop('sponsorblock_chapter_title', '[SponsorBlock]: %(category_names)l')
			opzioni_ydl.pop('addmetadata', None)
			opzioni_ydl.pop('embedchapters', None)
			if rimuovi or marca:
				opzioni_ydl['postprocessors'] = [
					{'key': 'SponsorBlock', 'categories': sorted(set(rimuovi) | set(marca)), 'when': 'after_filter'},
					{'key': 'ModifyChapters', 'remove_sponsor_segments': sorted(rimuovi),
					 'sponsorblock_chapter_title': titolo_cap, 'force_keyframes': False},
				] + opzioni_ydl['postprocessors']
			for pp in opzioni_ydl['postprocessors']:
				if pp.get('key') == 'FFmpegMetadata':
					pp['add_chapters'] = True
					pp['add_metadata'] = True
			sottotitoli_falliti: List[tuple] = []
			flussi_riparati: List[str] = []
			unione_sottotitoli_fallita = ""
			cartella_output = os.path.dirname(self.opzioni['outtmpl']['default']) or "."
			if self.principale:
				# Con sottotitoli scelti si usa la classe che scarica esattamente le coppie (lingua, tipo) spuntate
				with (YoutubeDLConSottotitoli(opzioni_ydl, self.scelte_sottotitoli, self._su_stato) if self.scelte_sottotitoli else YoutubeDLConDiagnostica(opzioni_ydl)) as ydl:
					ydl_corrente = ydl
					# Nel file unito ogni flusso audio e video prende come titolo il nome completo della traccia
					if not self.separato and self.tracce:
						ydl.add_post_processor(ImpostaTitoliTracce(ydl, {t.format_id: t.nome for t in self.tracce}), when='post_process')
					ydl.download([self.url])
					sottotitoli_falliti = list(getattr(ydl, 'sottotitoli_falliti', []))
					flussi_riparati = list(getattr(ydl, 'flussi_riparati', []))
				ridenominati = ridenomina_file(cartella_output, self.nome_base_out, self.tracce, self.scelte_sottotitoli, self.separato)
				for vecchio, nuovo in ridenominati: registra_log(f"Rinominato {vecchio} -> {nuovo}")
				if self.unisci_sottotitoli:
					# Solo sottotitoli, integrati: un unico file Matroska (.mks); gli originali si tolgono solo se l' unione riesce
					file_mks, originali, errore_unione = unisci_in_mks(cartella_output, self.nome_base_out, self.scelte_sottotitoli, self.opzioni.get('ffmpeg_location') or "")
					if errore_unione:
						registra_log(f"Unione dei sottotitoli in un unico file non riuscita:\n{errore_unione}")
						unione_sottotitoli_fallita = errore_unione
					else:
						registra_log(f"Sottotitoli uniti in {file_mks}")
						for originale in originali:
							try: os.remove(originale)
							except OSError as errore_file: registra_log(f"Impossibile eliminare {originale}: {errore_file}")
			if self.altre:
				# Altre tracce (es. storyboard): secondo passaggio, ognuna come nomeFile.ID.ext e poi rinominata con il suo nome completo
				opzioni_altre = {chiave: valore for chiave, valore in opzioni_ydl.items() if chiave in ('logger', 'ffmpeg_location', 'js_runtimes')}
				opzioni_altre['format'] = ",".join(t.format_id for t in self.altre)
				opzioni_altre['outtmpl'] = {'default': os.path.join(cartella_output, f"{self.nome_base_out}.%(format_id)s.%(ext)s")}
				with YoutubeDLConDiagnostica(opzioni_altre) as ydl_altre:
					ydl_corrente = ydl_altre
					ydl_altre.download([self.url])
				for vecchio, nuovo in ridenomina_file(cartella_output, self.nome_base_out, self.altre, [], True): registra_log(f"Rinominato {vecchio} -> {nuovo}")

			self._emetti_progresso(98.0)

			percorso_out = self.opzioni.get('outtmpl', {}).get('default', 'output')
			if isinstance(percorso_out, str):
				cartella = os.path.dirname(percorso_out)
				if not cartella:
					cartella = "."
				comando_cli = costruisci_comando_cli(self.opzioni, self.url, self.scelte_sottotitoli, set(self.info.get('subtitles') or {}), self.etichette_meta['meta_cli_note'], self.etichette_meta['meta_cli_note_sources'], self.altre, self.principale, self.nome_base_out,
															 self.etichette_meta['meta_cli_note_mks'] if self.unisci_sottotitoli else "")

				# Ogni campo si scrive solo se yt-dlp lo ha restituito: nessun valore di ripiego. L' elenco completo e' in nomeFile_metadata.txt
				et = self.etichette_meta
				etichetta_comando = f"{et['meta_command']}:\n{comando_cli}" if "\n" in comando_cli else f"{et['meta_command']}: {comando_cli}"
				righe_base = [f"{et['meta_url']}: {self.url}", etichetta_comando]
				titolo = self.info.get('title', et['meta_unknown_title'])
				campi = [("meta_author", self.info.get('uploader')), ("meta_channel", self.info.get('channel')),
						 ("meta_tags", ", ".join(self.info.get('tags') or []))]
				righe_dati = [f"{et['meta_title']}: {titolo}"] + [f"{et[chiave]}: {valore}" for chiave, valore in campi if valore]
				blocchi = ["\n".join(righe_base)]
				if righe_dati: blocchi.append("\n".join(righe_dati))
				if self.info.get('description'): blocchi.append(f"{et['meta_description']}:\n{self.info['description']}")

				nome_file_txt = f"{self.nome_base_out}.txt"
				file_meta = os.path.join(cartella, nome_file_txt).replace("\\", "/")
				with open(file_meta, "w", encoding="utf-8") as f:
					f.write("\n\n".join(blocchi) + "\n")

				file_metadata = os.path.join(cartella, f"{self.nome_base_out}_metadata.txt").replace("\\", "/")
				with open(file_metadata, "w", encoding="utf-8") as f:
					f.write(costruisci_testo_metadati(self.info, self.elenco_tracce))

			# Tutto il lavoro e' finito: solo adesso il 100%
			self.progresso.emit(100.0)
			# Avvisi di yt-dlp e sottotitoli non scaricati (il resto del download e' completato): un solo messaggio
			testo_avvisi = registro.testo() if registro.avvisi else ""
			if sottotitoli_falliti:
				elenco = "\n".join(f"- {nome}: {self.etichette_meta['subs_not_available'] if motivo == MOTIVO_NON_DISPONIBILE else ' '.join(motivo.split())}" for nome, motivo in sottotitoli_falliti)
				testo_avvisi = (testo_avvisi + "\n\n" if testo_avvisi else "") + self.etichette_meta['subs_download_failed'].format(names=elenco)
			if unione_sottotitoli_fallita:
				testo_avvisi = (testo_avvisi + "\n\n" if testo_avvisi else "") + self.etichette_meta['subs_merge_failed'].format(reason=' '.join(unione_sottotitoli_fallita.split()))
			if flussi_riparati:
				nomi = {t.format_id: t.nome for t in self.tracce}
				elenco = "\n".join(f"- {nomi.get(id_formato, id_formato)}" for id_formato in flussi_riparati)
				testo_avvisi = (testo_avvisi + "\n\n" if testo_avvisi else "") + self.etichette_meta['merge_repaired'].format(names=elenco)
			if testo_avvisi: self.avvisi.emit(testo_avvisi)
			self.completato.emit()
		except Exception as e:
			registra_log(traceback.format_exc() + "\n" + self.contesto_errore(ydl_corrente))
			# Se ffmpeg e' fallito, nella finestra di errore compaiono anche le sue ultime righe: contengono la causa (yt-dlp mostra solo l' ultima, es. "Conversion failed!")
			errore_ffmpeg = ydl_corrente.ultimo_errore_ffmpeg()[1] if ydl_corrente is not None else []
			self.errore.emit(str(e) + ("\n\nffmpeg:\n" + "\n".join(errore_ffmpeg) if errore_ffmpeg else "") + (f"\n\n{registro.testo()}" if registro.avvisi else ""))