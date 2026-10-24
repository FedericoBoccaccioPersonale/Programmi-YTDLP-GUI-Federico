import os
import json
from typing import Optional, Tuple

from utilita import ottieni_percorso_base

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
	"lingua_interfaccia": "system",
	"lingue_preferite": "it,en",
	"cartella_salvataggio": os.path.join(os.path.expanduser("~"), "Downloads"),
	"modalita_unione_default": "merge",
	"sottotitoli_default": 0,  # 0: Embedded, 1: External
	"formato_sub_default": "srt",
	"sponsorblock_default": 0, # 0: None, 1: Remove, 2: Mark
	"avviso_mancanza_video": True,
	"avviso_mancanza_audio": True,
	"avviso_mancanza_sottotitoli": True
}

def ottieni_percorso_config() -> str:
	return os.path.join(ottieni_percorso_base(), CONFIG_FILE)

def carica_configurazione() -> Tuple[dict, Optional[str]]:
	"""Restituisce (configurazione, errore). Se il file non esiste non e' un errore."""
	percorso = ottieni_percorso_config()
	if not os.path.exists(percorso):
		return DEFAULT_CONFIG.copy(), None
	try:
		with open(percorso, "r", encoding="utf-8") as f:
			dati = json.load(f)
		if not isinstance(dati, dict):
			raise ValueError("il file non contiene un oggetto JSON")
	except Exception as e:
		return DEFAULT_CONFIG.copy(), f"{percorso}: {e}"
	config = DEFAULT_CONFIG.copy()
	config.update(dati)
	return config, None

def salva_configurazione(config: dict) -> None:
	"""Solleva un'eccezione se il salvataggio fallisce."""
	with open(ottieni_percorso_config(), "w", encoding="utf-8") as f:
		json.dump(config, f, indent=4, ensure_ascii=False)
