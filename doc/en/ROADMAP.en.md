# Project Roadmap

This document lists hypothetical features for future versions. There is no timeline, but you are welcome to collaborate.

- [ ] **Cancel button:** To stop the download and ask whether to keep or delete already created files.
- [ ] **Download queues:** Ability to paste multiple URLs and queue them up, setting global or item-specific parameters.
- [ ] **Filename template:** Customizable string in settings to define generated filename (e.g. `%(title)s - %(uploader)s [%(resolution)s].%(ext)s`).
- [ ] **In-App update:** Button to force internal update of `yt-dlp` engine without redownloading the entire GUI from GitHub.
- [ ] **Program update:** Button to check (possibly automatically) for availability of program updates, not just libraries.
- [ ] **Profile support:** Saving presets (e.g. "Music", "High Quality Video") to quickly recall complex settings. This will include handling exceptions when requested track is missing.
- [ ] **Account support:** To allow downloading private videos.
- [ ] **Playlist search:** Search, at least on the same channel, for playlists containing this video.
- [ ] **Content navigator:** YB has a bad habit of poorly listing playlists and videos, so I intend to create a module listing all of them without infinite scroll loading and indicating full names.
- [ ] **Asynchronous thumbnail download:** Currently video thumbnail is downloaded on main thread, blocking window on slow network connections.
