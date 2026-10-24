import json
from typing import Dict, List, Optional

# Campi documentati da yt-dlp (classe InfoExtractor in extractor/common.py) che si possono rappresentare come testo.
# Sono esclusi di proposito: le immagini (thumbnail, thumbnails), l' elenco completo dei formati, gli indirizzi dei flussi e le intestazioni HTTP.
CAMPI_DOCUMENTATI = (
	"id", "display_id", "title", "fulltitle", "alt_title",
	"webpage_url", "original_url", "webpage_url_basename", "webpage_url_domain",
	"extractor", "extractor_key", "_type", "media_type", "ext",
	"uploader", "uploader_id", "uploader_url",
	"channel", "channel_id", "channel_url", "channel_follower_count", "channel_is_verified",
	"creators", "creator", "license",
	"timestamp", "upload_date", "release_timestamp", "release_date", "release_year",
	"modified_timestamp", "modified_date", "duration", "duration_string",
	"description", "tags", "categories", "cast", "location", "language", "age_limit",
	"availability", "playable_in_embed", "is_live", "was_live", "live_status", "start_time", "end_time",
	"view_count", "concurrent_view_count", "like_count", "dislike_count", "repost_count", "save_count", "average_rating", "comment_count",
	"chapters", "section_start", "section_end",
	"subtitles", "automatic_captions",
	"format", "format_id", "format_note", "container", "protocol",
	"width", "height", "aspect_ratio", "resolution", "dynamic_range", "fps", "vcodec", "vbr",
	"acodec", "abr", "asr", "audio_channels", "tbr", "filesize_approx",
	"series", "series_id", "season", "season_number", "season_id",
	"episode", "episode_number", "episode_id", "chapter", "chapter_number", "chapter_id",
	"track", "track_number", "track_id", "artist", "artists", "composer", "composers", "genre", "genres",
	"album", "album_type", "album_artist", "album_artists", "disc_number",
	"entries", "playlist_count"
)

# Per questi campi (dizionario lingua -> formati) si scrivono solo i codici lingua disponibili
CAMPI_ELENCO_LINGUE = ("subtitles", "automatic_captions")

def formatta_tempo(secondi: float) -> str:
	totale = int(secondi)
	return f"{totale // 3600:02d}:{(totale % 3600) // 60:02d}:{totale % 60:02d}"

def valore_in_testo(chiave: str, valore: object) -> Optional[str]:
	"""Rappresenta il valore come testo; None se il valore e' vuoto e va omesso."""
	if valore is None or valore == "" or valore == [] or valore == {}: return None
	if isinstance(valore, bool): return "true" if valore else "false"
	if chiave in CAMPI_ELENCO_LINGUE and isinstance(valore, dict): return ", ".join(sorted(valore))
	if chiave == "entries" and isinstance(valore, list): return str(len(valore))
	if chiave == "chapters" and isinstance(valore, list):
		righe: List[str] = []
		for capitolo in valore:
			righe.append(f"{formatta_tempo(capitolo.get('start_time') or 0)} - {formatta_tempo(capitolo.get('end_time') or 0)}  {capitolo.get('title') or ''}")
		return "\n".join(righe)
	if isinstance(valore, list) and all(isinstance(v, (str, int, float)) for v in valore): return ", ".join(str(v) for v in valore)
	if isinstance(valore, (str, int, float)): return str(valore)
	return json.dumps(valore, ensure_ascii=False, default=str)

# Sezioni con l' elenco di tutte le tracce disponibili: (chiave in elenco_tracce, nome della sezione nel file)
SEZIONI_TRACCE = (("video", "video_tracks"), ("audio", "audio_tracks"), ("subtitles", "subtitle_tracks"), ("other", "other_tracks"))

def costruisci_testo_metadati(info: dict, elenco_tracce: Dict[str, List[str]]) -> str:
	"""Una riga 'campo: valore' per ogni campo documentato presente in info, nell' ordine di CAMPI_DOCUMENTATI; i valori su piu' righe vanno a capo dopo i due punti.
	Poi, per video, audio, sottotitoli e altre tracce, una sezione con una riga per ogni traccia disponibile (elenco_tracce)."""
	blocchi: List[str] = []
	for chiave in CAMPI_DOCUMENTATI:
		testo = valore_in_testo(chiave, info.get(chiave))
		if testo is None: continue
		blocchi.append(f"{chiave}:\n{testo}" if "\n" in testo else f"{chiave}: {testo}")
	for chiave_elenco, nome_sezione in SEZIONI_TRACCE:
		righe = elenco_tracce.get(chiave_elenco) or []
		if righe: blocchi.append(f"\n{nome_sezione}:\n" + "\n".join(righe))
	return "\n".join(blocchi) + "\n"