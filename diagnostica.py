from collections import deque
from typing import Deque, List, Optional, Tuple

import yt_dlp


class YoutubeDLConDiagnostica(yt_dlp.YoutubeDL):
	"""yt-dlp che ricorda gli ultimi messaggi di debug senza attivare la modalita' dettagliata (verbose).
	Quando ffmpeg fallisce yt-dlp mostra all' utente solo l' ultima riga dell' errore (di solito 'Conversion failed!'): la causa vera e la riga di comando
	di ffmpeg li passa a write_debug, che di norma scarta tutto se non si e' in verbose. Qui invece li conserviamo, per scriverli nel log e nella finestra di errore."""

	def __init__(self, params: Optional[dict] = None, auto_init: bool = True) -> None:
		self.flussi_riparati: List[str] = []  # flussi ricopiati in MP4 prima dell' unione perche' senza timestamp (vedi unione.py)
		self.coda_debug: Deque[str] = deque(maxlen=80)  # creata prima di super().__init__: write_debug puo' essere chiamato gia' durante l' inizializzazione
		super().__init__(params, auto_init)

	def write_debug(self, message, only_once: bool = False):
		self.coda_debug.append(str(message))
		return super().write_debug(message, only_once)

	def ultimo_errore_ffmpeg(self, massimo_righe: int = 12) -> Tuple[str, List[str]]:
		"""(riga di comando, ultime righe dell' errore) dell' ultima esecuzione di ffmpeg registrata; vuoti se ffmpeg non e' stato eseguito."""
		messaggi = list(self.coda_debug)
		for i in range(len(messaggi) - 1, -1, -1):
			if messaggi[i].startswith("ffmpeg command line:"):
				righe = [r for r in (messaggi[i + 1].splitlines() if i + 1 < len(messaggi) else []) if r.strip()]
				return messaggi[i][len("ffmpeg command line:"):].strip(), righe[-massimo_righe:]
		return "", []