# Graphical user interface for yt-dlp (Codenamed: YTDLP-GUI-Federico)

*(Note: The Italian language file is the official reference document for this project. Translations into other languages are subordinate to that document).*

YTDLP-GUI-Federico is a free cross-platform graphical user interface (Windows, macOS, Linux) for the notoriously difficult command-line tool `yt-dlp`. It is designed to be simple to use while maintaining granular control over audio, video, and subtitle tracks, and to do what other interfaces do not.

> ## 🔊 Multilingual Audio
> **Download audio tracks in all available languages.**
> If a video offers multiple audio languages (author dubbing or automatic translation), the program lists them all and lets you choose which ones to download, even multiple tracks. You can save them as separate files or merge them into a single MKV/MKA file, without re-compression.

## Quick guide
On the first run, it will download the necessary libraries; on subsequent launches, it will check for updates.
Enter the YouTube URL in the top field, then click Analyze (in light blue).
When the status bar indicates the end of the analysis, select the tracks from the tabs on the right.
If you wish, you can change the destination folder.
Press the (green) download button at the bottom.

### Development notes
It does not require Python, FFmpeg, or Deno to be installed on the host system: the program is a single executable file downloadable from the releases; FFmpeg and Deno are downloaded by the program itself after asking for confirmation, and placed next to the executable. It is therefore necessary to place the program in a folder with write permissions. So on Windows, avoid `Program Files` (`Programmi`).
* The program is compiled, so Python is not required (yay! 🎉🎉🎉🎉)
* The presence of FFmpeg is checked by the program at startup. If missing or outdated, it asks to download it and updates it.
* yt-dlp is integrated along with the JavaScript components required by YouTube.
* Deno (the JavaScript interpreter yt-dlp uses to display all YouTube formats) is also checked at startup: if missing, it asks to download it, and if a newer version exists, it asks to update it. Without Deno, some formats may be missing.
* Language files are in a separate folder so they can be downloaded or created individually.

Note on Deno: I had never heard of it.

## Current specifications

- **Data extraction:** Analyzes URLs supported by yt-dlp and displays the thumbnail preview.
- **Selection of available tracks:**
  - Resolutions and framerates sorted from highest to lowest among those available from YouTube. Video tracks are grouped by resolution and framerate: each row shows the resolution (e.g., 1080p60) followed by a checkbox for each available format (codec, bitrate).
  - Complete and accurate list of all audio tracks actually present and made available by YouTube, allowing you to select and download them individually or in combination. Tracks are grouped by language: each row shows the language name followed by a checkbox for each available format for that language.
  - Every track YouTube exposes is listed, of any type (video, audio, subtitles, and others); those YouTube does not expose are not listed. If the user selects one, the program finds a way to download it. Subtitles have one row per language with a checkbox for each type (manual, automatic) for each variant (such as Generic Italian, Italian-Italy, Italian-Switzerland): each checkbox is independent and represents a track.
  - Tracks that are neither video nor audio (for example, YouTube storyboards) are in the "Other tracks" tab, visible only if the site exposes them, and are downloaded as separate files `filename.type.dimension.ext`. Audio tracks with no known codec (YouTube HLS) are also listed.
  - Audio and subtitle languages sorted according to the specified preferred languages (e.g., all `it-*` variants if `it` is set), followed by other languages in alphabetical order.
  - Clear distinction between manual tracks (video/audio/subtitles uploaded by author) and auto-generated/automatically translated tracks. This distinction is also saved in the track name.
  - The program checks a field provided by YouTube to know whether each track is automatic or manual.
  - The user selects which tracks to download (including multiple selection).
- **Session controls vs Permanent settings:**
  - Session options (track save mode, subtitle handling, subtitle format, and SponsorBlock) are visually placed below the video preview for quick and immediate configuration.
  - Default values for session controls are configurable and saved permanently along with global preferences (interface language, preferred languages, default save folder) in the `config.json` file.
  - When you modify a setting, the button changes to indicate that settings are not saved.
- **Save mode and track merging:** The user chooses whether to merge selected tracks into a single file or download them as separate files. The program automatically decides the container (**MKV** for video or **MKA** for audio-only in the case of a merged file) and saves native streams without any re-compression. Any re-compression or conversion to adapt to other formats or devices is beyond the scope of this program.
- **Chapters and SponsorBlock:** Automatic extraction and inclusion of original video chapters, with a `[SponsorBlock]` mark added to chapters corresponding to sponsored sections when segment marking is enabled.
- **Download progress:** Constant and linear monitoring of global progress (0-100%), eliminating freezes or fluctuations at 99%.
- **Status bar:** At the bottom of the window, a colored bar indicates what the program is doing and when it has finished: light blue for "Analysis in progress..." and "Downloading...", green for "Analysis completed" and "Download completed", orange when waiting (e.g., for error 429 on translated subtitles) or when completed with warnings, red when failed. The meaning is always written in words: color is not the only indicator. If the video has no subtitles, the subtitles tab shows "None".
- **Version number:** The version number is the latest GitHub repository tag (excluding `anteprima`) at compile time, followed by the compilation date (UTC) in `yyyy-mm-dd` format, e.g. `V1.2_2026-10-21`. It appears in the window title, in every entry of `errori.log`, and in the zip name (`YTDLP-GUI-Federico-V1.2_2026-10-21-Windows-x64.zip`). If the program is run from source, "sviluppo" appears instead of the version number. Compiling without any existing tag is an error.
- **External subtitles:** When saving subtitles as external files, they are named using the `filename.language.ext` structure recognized by VLC. Auto-generated subtitles have the word "auto" appended, yielding `filename.auto.language.ext`; translations also indicate the source language: `filename.auto.language.from-origin.ext` (e.g., `filename.auto.it.from-en.ext`).
- **Internal (embedded) subtitles:** Saved with language indication and the full track name as the title (e.g., Italian (Switzerland) - Automatic).
- Audio and video tracks follow the same rules as subtitles.\
  Here is an AI-proof explanation (I hope):\
  **Audio, video, and other tracks:** Each track has a full name. In the merged file, it is the stream title (e.g., `Italian (Italy) - Synthetic / Translated - mp4a 129k`, `1080p60 - avc1 5686k`). If tracks are saved separately, files are named `filename.language.ext` for originals, `filename.auto.language.ext` for synthetic or translated tracks, `filename.1080p60.ext` for video, and `filename.storyboard.160x90.ext` for others; if multiple tracks would have the same name, the format ID is appended to all of them.
- **Subtitles only:** If the user selects only subtitles (no video or audio tracks), the program does not download the video. With external subtitles it saves one file per subtitle. With embedded subtitles in a single file it asks for confirmation, warning that it is better to save them as external tracks, and creates a single Matroska file with only the subtitles (filename.mks), with the language and full name of each track; if the merge fails, the subtitles stay as external files.
- **Translated auto-generated subtitles:** YouTube rate-limits requests for automatically translated subtitles into another language (error 429 🤬). The program waits 20 seconds after extraction before downloading them and, upon each error, increases the wait time by an additional 30 seconds and retries (up to 4 times, waiting 20s, then 50s, then 80s, then 110s). The status bar at the bottom displays the wait time and error so the user knows downloading has not finished. For each language, YouTube exposes the track in that language itself (if present) and a translation for every other track from which it translates: each track has its own checkbox ("Automatic", "Translated from en", "Translated from de-DE"...) and the user chooses. If a subtitle fails to download, the rest of the download proceeds and a warning lists missing tracks.
- **Permanent settings panel:** Allows defining interface language (default: auto-detect system language or English if unavailable), ordered list of preferred languages, and default save folder. Includes three checkboxes (enabled by default) to prompt confirmation before download if no video, audio, or subtitle track has been selected. A second group contains default values for session controls: track save mode (single MKV/MKA file or separate files), subtitle handling (embedded or external), subtitle format (srt, vtt, ass, lrc), and SponsorBlock (disabled, remove, or mark). Subtitle embedding depends on single-file creation.
- **Textual metadata and equivalent command:** Upon download completion, the program saves a `.txt` file with the same base name as the main file (`filename.txt`) containing the source URL, equivalent `yt-dlp` CLI command (the terminal command the user would run to obtain the same result | NOTE: due to a poor implementation in `yt-dlp`, it uses language code as key, or so AI swears, so the command may split into multiple lines), full title, author (uploader), channel name, tags, and description; fields not provided by YouTube are omitted (missing title is "Unknown"). A second file `filename_metadata.txt` is created containing all yt-dlp documented metadata convertible to text (excluding images); examples include id, webpage_url_basename, extractor_key, _type, media_type, ext, uploader_id, channel_follower_count, creators, upload_date, duration, description, tags, categories, cast, location, age_limit, subtitles (list of available ones), format_id, width, height, aspect_ratio, resolution, dynamic_range, fps, series, series_id, season, season_number, season_id, track, track_number, track_id, artists, composers, genres, album, album_type, album_artists, disc_number, entries, playlist_count. After fields, it contains a list of all available tracks (video, audio, subtitles, and other tracks), one line per track with full name and technical details.
- **Multilingual:** Native Italian and English interface, expandable via JSON files.
- **SponsorBlock integration:** Option to enable skipping or marking sponsored segments directly from the interface, handled via a native function exposed by yt-dlp.
- **No silent errors:** All exceptions are caught and visually displayed via native dialogs.
- **Multithreading architecture:** Distinct QThread classes (data analysis, downloading, and FFmpeg/Deno update checking and downloading) so the GUI never freezes during network operations or FFmpeg processing.
- **Main GUI buttons:**
  - The **Analyze** button is highlighted in high-contrast light blue right from program launch.
  - The **Download** button turns high-contrast green as soon as it is enabled (after analysis completes) and keeps its green tint even when disabled to remain clearly visible.
- **Warnings on selected tracks:**
  - If no tracks are selected (0 video, 0 audio, 0 subtitles, 0 other), download is blocked with a warning.
  - If user forgot to select at least one track of each type (video, audio, or subtitle) and respective warning checkboxes in permanent settings are active, up to 3 confirmation dialogs appear sequentially (order: Video, Audio, Subtitles) asking if user intends to proceed anyway, highlighting the missing track type in red. Selecting "No" on any warning cancels download with confirmation message. This setting was preferred over a single message assuming first-time users might hit download without reading docs or selecting anything, whereas subsequent times one only forgets a single track type.
- **Starting download:** At the bottom of the form is a field to select destination filename, defaulting to video title. Next to it is the button to start download. The program then downloads and merges tracks (if set), generating the requested file(s).
- **Resizable panels:** A splitter exists between the preview/session panel and the tabs: drag with mouse to widen either side. Expanding the window gives additional space to tabs.

## Note
Python is the ultimate evil. I used it only for consistency with yt-dlp to maximize compatibility across the same platforms. Therefore I do not know it well and the implementation is AI-generated.
For your information (which I believe I wrote elsewhere) I hate Python for at least the following reasons:
- It uses indentation to define blocks
- and this is a problem because visually a tab or 4 spaces look the same, but to the interpreter mixing tabs and spaces is a disaster, and copying code from the web risks confusion
- when returning from a long if inside another if and maybe a loop you end up with numerous spaces and aligning them correctly (is it 5 or 6?) becomes tricky
- furthermore Python programmers seem to prefer spaces (increasing character count), proving this language is not for me

OK, indeed it is more of a single argument. What should interest you if you intend to help develop this program is that here tabs are used.

Much of the executable size, exceeding 50MB (Windows) and 100MB (Linux), is due to the GUI library and curl_cffi, the library allowing yt-dlp to download YouTube subtitles (adding ~18MB on Linux build).\
FFmpeg is ~160MB, FFprobe another ~160MB, Deno ~100MB.\
Total estimated space is ~500MB.

## Notice
I have only been able to test the Windows version.

## Installation (or rather extraction)
1. Go to Releases tab (linked in readme) and download zip for your OS.
2. Extract to a folder where you have write permission, without separating executable from `locales` folder. No installation required (at least on Windows).
3. Run the program. On each startup it checks for FFmpeg and Deno and asks confirmation to download if missing or outdated.

yt-dlp is integrated into the program and updates with new compiled builds on GitHub Actions. FFmpeg and Deno are updated by the program itself.

### Requirements
* Windows x64 (tested), Linux x64 and macOS Apple Silicon (arm64) (compiled but untested). Intel Mac processers are currently not supported.
* Linux: requires `libxcb-cursor0` library (`xcb-util-cursor` on Fedora and Arch), without which Qt cannot launch GUI. Ubuntu example: `sudo apt install libxcb-cursor0`.
* Internet connection: otherwise you won't reach YB!
* Place program in a folder with write permissions: `config.json`, `errori.log`, `ffmpeg`, `ffprobe`, and `deno` will be saved alongside executable.
* The `locales` folder next to executable containing language files. Included in download.

Without FFmpeg downloads cannot start. Without Deno analysis works, but some YouTube formats may be missing.

## YT-DLP Limitations
yt-dlp can download any track: it just lacks a way to choose it from the command line.

**How it works**
1. When yt-dlp extracts a video, it returns a list of entries for each auto language (e.g. `it`). For instance there could be `it` tracks in 56 versions: 8 tracks each in 7 formats. Each entry has its own URL with `lang=<source>` and, if a translation, `tlang=it`.
2. From command line you can only pass `--sub-langs it`. yt-dlp chooses one entry per format by itself and downloads it.
3. The program uses yt-dlp as a library, not a command. In `sottotitoli.py` module there is a subclass of `YoutubeDL` that overrides the step where yt-dlp picks the entry. For each checked box:
   - keeps only entries for chosen track (language itself, or "translated from de-DE");
   - asks yt-dlp selection method to pick the right format from those;
   - delivers result to yt-dlp with a distinct name for each track.
4. Then yt-dlp downloads the URL we handed to it, as usual.

**Limitations**
- The equivalent CLI command cannot repeat source selection, which is why it ends with a comment line.
- Subclass uses an internal yt-dlp method (`process_subtitles`), not documented as public API. Workflow always installs latest yt-dlp version: if future versions change this method, track selection will break. You will need to manually download a previous version.

And with that my program just became better than the library I was simply trying to make easier to use.

## Roadmap

Check [ROADMAP.en.md](ROADMAP.en.md) to learn about upcoming features.

## Contributing and Code of Conduct

Interested in adding a language or improving code? Read [contributing.en.md](contributing.en.md) for instructions and [code_of_conduct.en.md](code_of_conduct.en.md) for community rules.
