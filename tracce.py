from typing import Callable, Dict, List, Optional, Set, Tuple

CATEGORIA_ORIGINALE = "original"
CATEGORIA_SINTETICA = "synthetic"
CATEGORIA_STANDARD = "standard"

# Ordine di visualizzazione delle categorie a parita' di lingua
TIPO_FORMATO_VIDEO = "video"
TIPO_FORMATO_AUDIO = "audio"
TIPO_FORMATO_ALTRO = "altro"

def tipo_formato(f: dict) -> str:
	"""Classifica un formato esposto dal sito. Ogni formato rientra in un solo tipo, cosi' nessuna traccia esposta resta fuori dagli elenchi:
	video (anche con audio incluso, o senza codec noto), audio (anche senza codec noto: l' audio HLS di YouTube ha acodec nullo),
	altro (ne' video ne' audio: es. le immagini 'storyboard' di YouTube)."""
	video = f.get('vcodec')
	audio = f.get('acodec')
	if video not in (None, 'none'): return TIPO_FORMATO_VIDEO
	if audio not in (None, 'none'): return TIPO_FORMATO_AUDIO
	if video == 'none' and audio is None: return TIPO_FORMATO_AUDIO
	if video == 'none': return TIPO_FORMATO_ALTRO
	return TIPO_FORMATO_VIDEO

ORDINE_CATEGORIE = {CATEGORIA_ORIGINALE: 0, CATEGORIA_SINTETICA: 1, CATEGORIA_STANDARD: 2}

PAROLE_ORIGINALE = ("original", "default")
PAROLE_SINTETICA = ("dubbed", "translated", "descriptive")

# Valore con cui yt-dlp contrassegna la lingua originale (documentato in extractor/common.py: 10 = "e' la lingua di cui parla l' URL", -1 = sconosciuto).
# YouTube lo usa per la traccia originale; le tracce doppiate hanno -1.
LANGUAGE_PREFERENCE_ORIGINALE = 10

def categoria_da_nota(nota: str) -> Optional[str]:
	"""Deduce la categoria dal testo di format_note; None se il testo non contiene indicazioni."""
	testo = nota.lower()
	if any(parola in testo for parola in PAROLE_ORIGINALE): return CATEGORIA_ORIGINALE
	if any(parola in testo for parola in PAROLE_SINTETICA): return CATEGORIA_SINTETICA
	return None

def mappa_categorie_per_lingua(formati: List[dict]) -> Dict[str, str]:
	"""YouTube segnala 'original' e 'dubbed-auto' solo nei formati audio m3u8, che non hanno acodec: le tracce DASH della stessa lingua non lo dicono.
	Restituisce {lingua: categoria} ricavata da quei formati; le lingue che vi compaiono con categorie diverse sono escluse (non si indovina)."""
	viste: Dict[str, Set[str]] = {}
	for f in formati:
		if f.get('vcodec') != 'none' or f.get('acodec') is not None or not f.get('language'): continue
		categoria = categoria_da_nota(f.get('format_note') or '')
		if categoria is None: continue
		viste.setdefault(f['language'], set()).add(categoria)
	return {lingua: next(iter(categorie)) for lingua, categorie in viste.items() if len(categorie) == 1}

def categoria_formato(f: dict, mappa: Dict[str, str]) -> str:
	"""Precedenza: indicazione nella nota del formato stesso, poi language_preference, poi la categoria della lingua ricavata dai formati m3u8."""
	categoria = categoria_da_nota(f.get('format_note') or '')
	if categoria is not None: return categoria
	if f.get('language_preference') == LANGUAGE_PREFERENCE_ORIGINALE: return CATEGORIA_ORIGINALE
	return mappa.get(f.get('language') or '', CATEGORIA_STANDARD)

def raggruppa_audio(formati: List[dict], peso_lingua: Callable[[Optional[str]], Tuple]) -> List[dict]:
	"""Raggruppa tutti i formati audio esposti dal sito per (lingua, categoria).
	Restituisce [{'lingua': str, 'categoria': str, 'formati': [dict, ...]}, ...] ordinato per lingua preferita (peso_lingua), poi originale prima;
	i formati di ogni gruppo sono ordinati per bitrate decrescente."""
	scaricabili = [f for f in formati if tipo_formato(f) == TIPO_FORMATO_AUDIO]
	mappa = mappa_categorie_per_lingua(formati)
	gruppi: Dict[Tuple[str, str], List[dict]] = {}
	for f in scaricabili:
		chiave = (f.get('language') or '', categoria_formato(f, mappa))
		gruppi.setdefault(chiave, []).append(f)
	risultato = []
	for (lingua, categoria), elenco in gruppi.items():
		elenco.sort(key=lambda f: (-(f.get('abr') or 0.0), str(f.get('format_id'))))
		risultato.append({'lingua': lingua, 'categoria': categoria, 'formati': elenco})
	risultato.sort(key=lambda g: (peso_lingua(g['lingua'] or None), ORDINE_CATEGORIE[g['categoria']], g['lingua']))
	return risultato

def raggruppa_altre(formati: List[dict]) -> List[dict]:
	"""Raggruppa i formati ne' video ne' audio (es. storyboard) per tipo, indicato da format_note (altrimenti dall' estensione).
	Restituisce [{'nome': str, 'formati': [dict, ...]}, ...]; i formati di ogni gruppo vanno dal piu' grande al piu' piccolo."""
	gruppi: Dict[str, List[dict]] = {}
	for f in formati:
		if tipo_formato(f) != TIPO_FORMATO_ALTRO: continue
		gruppi.setdefault(str(f.get('format_note') or f.get('ext') or ''), []).append(f)
	return [{'nome': nome, 'formati': sorted(elenco, key=lambda f: -((f.get('width') or 0) * (f.get('height') or 0)))} for nome, elenco in sorted(gruppi.items())]