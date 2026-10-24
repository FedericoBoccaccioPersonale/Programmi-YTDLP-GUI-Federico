import os
import re
import sys
from typing import Dict, List, Optional

from yt_dlp.postprocessor.ffmpeg import FFmpegMergerPP, FFmpegPostProcessorError

# Messaggi con cui ffmpeg segnala che in un flusso alcuni pacchetti non hanno timestamp (tipico di certi flussi HLS di YouTube): il muxer Matroska li rifiuta
CAUSA_SENZA_TIMESTAMP = ("Can't write packet with unknown timestamp", "Timestamps are unset in a packet")


class FFmpegMergerRobusto(FFmpegMergerPP):
	"""L' unione dei flussi di yt-dlp, con un secondo tentativo per i flussi senza timestamp.
	Se ffmpeg rifiuta l' unione perche' un flusso ha pacchetti senza timestamp (errore finale 'Conversion failed!', causa 'Can't write packet with unknown timestamp'),
	quel flusso viene prima ricopiato in un MP4 senza ricompressione, che ne ricostruisce i timestamp, e poi l' unione si ripete con la copia.
	Gli altri errori di ffmpeg non vengono nascosti: l' eccezione originale resta cosi' com'e'."""

	def _flussi_senza_timestamp(self, info: dict) -> Optional[List[int]]:
		"""Indici (nell' elenco dei file da unire) dei flussi senza timestamp, ricavati dall' errore di ffmpeg; None se la causa dell' errore e' un' altra."""
		dettagli = getattr(self._downloader, "ultimo_errore_ffmpeg", None)
		if dettagli is None: return None
		testo = "\n".join(dettagli(400)[1])
		if not any(causa in testo for causa in CAUSA_SENZA_TIMESTAMP): return None
		# Nell' ordine dei -map di FFmpegMergerPP: per ogni file prima l' audio e poi il video; il numero nel messaggio e' l' indice del flusso in uscita
		uscite = []
		for i, formato in enumerate(info['requested_formats']):
			if formato.get('acodec') != 'none': uscite.append(i)
			if formato.get('vcodec') != 'none': uscite.append(i)
		indici = sorted({uscite[int(n)] for n in re.findall(r"Timestamps are unset in a packet for stream (\d+)", testo) if int(n) < len(uscite)})
		# Se ffmpeg non dice quale flusso, si ricopiano tutti i file con video
		return indici or [i for i, formato in enumerate(info['requested_formats']) if formato.get('vcodec') != 'none']

	def run(self, info):
		try:
			return super().run(info)
		except FFmpegPostProcessorError:
			indici = self._flussi_senza_timestamp(info)
			if not indici: raise
			originali = list(info['__files_to_merge'])
			riparati: Dict[int, str] = {}
			try:
				for i in indici:
					copia = os.path.splitext(originali[i])[0] + ".fix.mp4"
					self.to_screen(f'Rewriting "{originali[i]}" as MP4 to rebuild its timestamps')
					self.run_ffmpeg(originali[i], copia, ['-c', 'copy'])
					riparati[i] = copia
			except FFmpegPostProcessorError:
				for copia in riparati.values(): self._elimina(copia)
				raise
			self._elimina(self._percorso_temporaneo(info['filepath']))  # resto del primo tentativo fallito
			info['__files_to_merge'] = [riparati.get(i, percorso) for i, percorso in enumerate(originali)]
			try:
				super().run(info)
			except FFmpegPostProcessorError:
				for copia in riparati.values(): self._elimina(copia)
				raise
			finally:
				info['__files_to_merge'] = originali
			segnala = getattr(self._downloader, "flussi_riparati", None)
			if segnala is not None: segnala.extend(str(info['requested_formats'][i].get('format_id')) for i in riparati)
			# Da eliminare dopo l' unione: i file scaricati e le loro copie
			return originali + list(riparati.values()), info

	@staticmethod
	def _percorso_temporaneo(percorso: str) -> str:
		base, estensione = os.path.splitext(percorso)
		return f"{base}.temp{estensione}"

	@staticmethod
	def _elimina(percorso: str) -> None:
		try: os.remove(percorso)
		except OSError: pass


def attiva() -> None:
	"""yt-dlp crea il passo di unione con il nome FFmpegMergerPP del proprio modulo YoutubeDL: lo sostituiamo con la versione robusta (vale per tutto il programma)."""
	sys.modules["yt_dlp.YoutubeDL"].FFmpegMergerPP = FFmpegMergerRobusto