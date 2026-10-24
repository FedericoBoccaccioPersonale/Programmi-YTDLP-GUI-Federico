# How to contribute

I am happy to accept contributions. The entire build process is automated via GitHub Actions, so you won't need to worry about providing executables, only clean source code.

## Translations (adding a new language or improving existing ones)
1. Fork the repository.
2. Copy `locales/it.json` (or a language you know better) and rename it with language ISO code (e.g., `es.json`, `fr.json`).
3. Translate values on the right keeping left keys unchanged.
4. If possible, also translate documentation files and update readme to include references to newly translated files.
5. Open a Pull Request.

Translations are responsibility of authors and reviewers.

## Code development
- Project rejects Python usage on user side, but engine is written in Python using `PySide6`.
- PySide6 was chosen as cross-platform GUI library.
- Use tab indentation.
- Line endings: project files use LF line endings (GitHub and Linux default), not CRLF. If editing files locally on Windows, set editor to LF (in Visual Studio Code: click "CRLF" in bottom right status bar and choose "LF") and give Git command `git config core.autocrlf input`; otherwise diffs will show all lines modified. GitHub online editor already uses LF.
- Always test compilation by running personal branch with GitHub Actions before sending Pull Request to main branch.
- Any modification to yt-dlp logic must be validated making sure it doesn't break FFmpeg metadata tagging.
- If you know Python better than me, feel free to improve project architecture... without breaking anything and respecting specifications.

## GitHub Actions specifications
- Buttons list appears allowing building for specific platforms, plus button generating output for all platforms.
- On each build, system automatically downloads latest version of yt-dlp (with JavaScript components and `curl-cffi`, required for downloading YouTube subtitles), PySide6, PyInstaller, and certifi via pip package manager. These tools are embedded in program.
- Since caching FFmpeg also consumes too much bandwidth and increased usage, FFmpeg is not embedded in single executable: program itself downloads precompiled static builds (FFmpeg, FFprobe, and Deno) and places them next to compiled executable. Sources are BtbN for Windows and Linux, Martin Riedl for macOS Apple Silicon, and evermeet.cx for macOS Intel (uncompiled by workflows); Deno downloads from official GitHub releases.
- Since language files are separate, they will also be included in zip.
- ZIP Naming: Final archive format is: YTDLP-GUI-Federico-[Version]-[OperatingSystem].zip. Version is repository's latest tag (excluding `anteprima`) followed by build date in `yyyy-mm-dd` format, e.g., `V1.2_2026-10-21`; operating system is `Windows-x64`, `Linux-x64`, or `macOS-arm64`. Before building at least one tag must exist (on GitHub: Releases > Draft a new release > Choose a tag > Create new tag), otherwise build fails with an error.
- There are two workflows differing only in destination: `build (crea artefatto).yml` saves zips as artifacts (kept 1 day), `build (crea release).yml` attaches them to `anteprima` pre-release.
- `versione.py` file is not in repository (ignored by Git): workflow creates it during compilation with version number. Running program from source it doesn't exist and "sviluppo" appears. Without this file program cannot know its version number.
- `ico` folder contains icon: workflow applies `.ico` (Windows) or `.icns` (macOS) to executable with `--icon` and embeds `.png` for window icon.
- Read also guide for [publishing](publishing.en.md).

#### This is the theory. In practice there are unresolved limitations.
* Persists in compiling with deprecated components

These horrors appear:
> **Annotations**
>
> 4 notices
>
> |   |
> |---|
> |**Matrix configuration**<br><br>"The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026. For more information, see [https://github.com/actions/runner-images/issues/14748](https://github.com/actions/runner-images/issues/14748)"|
> |**Preparation Preview Release**<br><br>"The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026. For more information, see [https://github.com/actions/runner-images/issues/14748](https://github.com/actions/runner-images/issues/14748)"|
> |**macOS arm64**<br><br>Due to capacity constraints, jobs targeting macOS arm64 runners may experience longer queue times.|
> |**Linux x64**<br><br>"The ubuntu-latest label will migrate to Ubuntu 26 beginning October 19, 2026. For more information, see [https://github.com/actions/runner-images/issues/14748](https://github.com/actions/runner-images/issues/14748)"|

* Should have been 3 buttons instead of a combo
