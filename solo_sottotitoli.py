import os
import re
import subprocess
import sys
from typing import List, Optional, Tuple

from yt_dlp.utils import ISO639Utils

from sottotitoli import SceltaSottotitolo, TIPO_AUTOMATICO, radice_sottotitolo
from nomi_tracce import PREFISSO_AUTOMATICO


def file_sottotitolo(cartella: str, nome_base: str, scelta: SceltaSottotitolo) -> Optional[str]:
	"""Percorso del file scaricato per una scelta: nomeFile.lingua.ext (manuale) oppure nomeFile.auto.lingua.ext (automatico; per le traduzioni nomeFile.auto.lingua.da-origine.ext).
	L' estensione e' quella del formato scelto o, se non c' era, quella che yt-dlp ha usato al suo posto."""
	prefisso = f"{nome_base}.{PREFISSO_AUTOMATICO}.{radice_sottotitolo(scelta.lingua, scelta.origine)}" if scelta.tipo == TIPO_AUTOMATICO else f"{nome_base}.{scelta.lingua}"
	modello = re.compile(rf"^{re.escape(prefisso)}\.([^.]+)$")
	for nome in sorted(os.listdir(cartella)):
		if modello.match(nome): return os.path.join(cartella, nome)
	return None


def codice_lingua_iso(lingua: str) -> str:
	"""Codice a tre lettere per Matroska (es. 'it-CH' -> 'ita'); 'und' (indefinita) se non si riconosce."""
	base = lingua.split("-")[0]
	return ISO639Utils.short2long(base) or (base if len(base) == 3 and base.isalpha() else "und")


def percorso_ffmpeg(cartella_ffmpeg: str) -> str:
	return os.path.join(cartella_ffmpeg or "", "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")


def unisci_in_mks(cartella: str, nome_base: str, scelte: List[SceltaSottotitolo], cartella_ffmpeg: str) -> Tuple[Optional[str], List[str], str]:
	"""Unisce i sottotitoli scaricati in un unico file Matroska con i soli sottotitoli (nomeFile.mks), senza ricompressione del video (non c' e'):
	ogni sottotitolo e' un flusso con lingua e nome completo come titolo. Restituisce (file creato, file di origine usati, errore); in caso di errore il file non c' e' e gli originali restano."""
	elenco = [(scelta, file_sottotitolo(cartella, nome_base, scelta)) for scelta in scelte]
	trovati = [(scelta, percorso) for scelta, percorso in elenco if percorso]
	if not trovati: return None, [], "no subtitle file found"
	uscita = os.path.join(cartella, f"{nome_base}.mks")
	codec = "ass" if all(percorso.lower().endswith(".ass") for _, percorso in trovati) else "srt"
	comando = [percorso_ffmpeg(cartella_ffmpeg), "-y", "-loglevel", "error"]
	for _, percorso in trovati: comando += ["-i", percorso]
	for i in range(len(trovati)): comando += ["-map", str(i)]
	comando += ["-c:s", codec]
	for i, (scelta, _) in enumerate(trovati):
		comando += [f"-metadata:s:s:{i}", f"language={codice_lingua_iso(scelta.lingua)}", f"-metadata:s:s:{i}", f"title={scelta.nome}"]
	comando += ["-f", "matroska", uscita]
	opzioni = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace", "timeout": 120}
	if sys.platform == "win32": opzioni["creationflags"] = subprocess.CREATE_NO_WINDOW
	try:
		esito = subprocess.run(comando, **opzioni)
	except (OSError, subprocess.SubprocessError) as errore:
		return None, [], str(errore)
	if esito.returncode != 0:
		try: os.remove(uscita)
		except OSError: pass
		return None, [], (esito.stderr or "").strip() or f"ffmpeg exit code {esito.returncode}"
	return uscita, [percorso for _, percorso in trovati], ""