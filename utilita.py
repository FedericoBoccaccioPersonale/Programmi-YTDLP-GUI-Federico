import os
import re
import sys
from datetime import datetime

try:
	from versione import VERSIONE  # file creato dal workflow durante la compilazione: contiene "<ultimo tag>_<data yyyy-mm-dd>"
except ImportError:
	VERSIONE = ""  # avviato dai sorgenti (il file non esiste): il programma mostra "sviluppo"

def ottieni_percorso_base() -> str:
	if getattr(sys, 'frozen', False):
		percorso = os.path.dirname(sys.executable)
		# Su macOS l' eseguibile sta dentro NomeApp.app/Contents/MacOS: la cartella utile (config, locales, FFmpeg) è quella che contiene il .app
		if sys.platform == "darwin" and percorso.endswith(os.path.join(".app", "Contents", "MacOS")):
			return os.path.dirname(os.path.dirname(os.path.dirname(percorso)))
		return percorso
	return os.path.dirname(os.path.abspath(__file__))

def percorso_log() -> str:
	return os.path.join(ottieni_percorso_base(), "errori.log")

def registra_log(testo: str) -> None:
	try:
		with open(percorso_log(), "a", encoding="utf-8") as f:
			f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{VERSIONE or 'dev'}]\n{testo}\n\n")
	except Exception as e:
		print(f"Impossibile scrivere il log {percorso_log()}: {e}", file=sys.stderr)

def pulisci_nome_file(nome: str) -> str:
	return re.sub(r'[\\/*?\"<>|]', '_', nome)