import os
import json
from typing import Dict, List, Tuple

from PySide6.QtCore import QLocale

from utilita import ottieni_percorso_base

LINGUA_PREDEFINITA = "en"
# Lingue da cui prendere i testi di riserva per le chiavi mancanti in un file di lingua; la seconda ha la precedenza sulla prima.
LINGUE_RIFERIMENTO = ("it", "en")

def normalizza_codice_lingua(codice: str) -> str:
	return codice.strip().lower().replace("_", "-")

def cartelle_locales() -> List[str]:
	"""I file di lingua non sono incorporati nell' eseguibile: si leggono solo dalla cartella 'locales' accanto al programma,
	cosi' si possono modificare o aggiungere lingue senza ricompilare."""
	return [os.path.join(ottieni_percorso_base(), "locales")]

def elenca_lingue() -> Tuple[Dict[str, Tuple[str, dict]], List[str]]:
	"""Legge tutti i .json delle cartelle 'locales'. Restituisce ({codice: (nome_visualizzato, testi)}, elenco_errori)."""
	lingue: Dict[str, Tuple[str, dict]] = {}
	errori: List[str] = []
	for cartella in cartelle_locales():
		if not os.path.isdir(cartella):
			continue
		for nome_file in sorted(os.listdir(cartella)):
			if not nome_file.lower().endswith(".json"):
				continue
			codice = normalizza_codice_lingua(nome_file[:-5])
			if codice in lingue:
				continue
			percorso = os.path.join(cartella, nome_file)
			try:
				with open(percorso, "r", encoding="utf-8-sig") as f:
					testi = json.load(f)
				if not isinstance(testi, dict):
					raise ValueError("il file non contiene un oggetto JSON")
			except Exception as e:
				errori.append(f"{percorso}: {e}")
				continue
			lingue[codice] = (str(testi.get("language_name") or codice.upper()), testi)
	return lingue, errori

def rileva_lingua_sistema(disponibili: Dict[str, Tuple[str, dict]]) -> str:
	"""Cerca prima il codice completo del sistema (es. pt-br), poi la lingua base (pt), poi una qualunque variante (pt-*).
	Se non c' e' nulla restituisce la lingua predefinita."""
	completo = normalizza_codice_lingua(QLocale.system().name())
	if completo in disponibili:
		return completo
	base = completo.split("-")[0]
	if base in disponibili:
		return base
	for codice in sorted(disponibili):
		if codice.startswith(f"{base}-"):
			return codice
	return LINGUA_PREDEFINITA

def unisci_testi(disponibili: Dict[str, Tuple[str, dict]], codice: str) -> Tuple[Dict[str, str], List[str]]:
	"""Restituisce (testi, chiavi_mancanti): i testi della lingua scelta, completati con quelli delle lingue di riferimento
	per le chiavi che il file della lingua non contiene."""
	riserva: Dict[str, str] = {}
	for rif in LINGUE_RIFERIMENTO:
		if rif in disponibili:
			riserva.update(disponibili[rif][1])
	propri = disponibili[codice][1]
	testi = dict(riserva)
	testi.update(propri)
	mancanti = sorted(k for k in riserva if k not in propri)
	return testi, mancanti
