# Smart-Organizer

Local-first Windows assistant for practical file, project and version organization.

## Principles
- Local-first: no paid APIs and no cloud database requirement.
- `data/`, `logs/` and learned `knowledge.db` stay on the user's PC and are preserved by updates.
- Existing user folder trees and real placement habits have priority over generated templates and historical memory.
- Existing project internals are protected from automatic rearrangement.
- Existing destinations are never overwritten.
- Applied batches are journaled and reversible with Undo.
- Background automation is intentionally stricter than interactive suggestions.

## v0.2.16

This release turns Smart Organizer into an always-on Windows helper while keeping the safety model conservative.

### Background mode and Windows startup
- optional per-user Windows autostart using the real frozen `SmartOrganizer.exe`;
- `--background` startup mode opens minimized and continues periodic checks;
- closing the main window can keep the organizer running in the background;
- the interval is configurable in minutes;
- a separate **Полностью выйти** action remains available;
- CI application self-test bypasses background hiding and performs a real clean exit.

### Smarter Downloads routing
Completed top-level files in the real Windows Downloads folder can be routed in the background after a configurable quiet period. Partial browser downloads such as `.crdownload`, `.part`, `.partial` and `.download` are ignored.

Routing priority is deliberately explicit:
1. known project route;
2. ChatGPT/OpenAI route when the filename contains an explicit ChatGPT/OpenAI/DALL-E/Sora marker;
3. explicit file-category route;
4. only then a unique mature local placement rule learned from repeated confirmations.

Destination folders must already exist. A collision at the destination blocks the move. Nothing is overwritten.

### Project catalog and per-project destinations
The local starter catalog now contains separate identities for projects that have been worked on historically, including:
- VoxLyra → `Treninem/Voxlyra`;
- Boostora;
- ImPuls-Minecraft → `Treninem/ImPuls-Minecraft`;
- ImPuls bot/simulation → `Treninem/Impuls`;
- ProControl / ProChckbot / Производство → `Treninem/Proizvodstvo`;
- Smart-Organizer → `Treninem/Smart-Organizer`;
- Zveroboy;
- LoveMi;
- Pubgbot;
- the separate open-world survival-game concept;
- extrusion/vacuum-calibrator CAD and engineering work.

The Settings screen exposes a destination field for each known project. Project routes are kept separate, so Minecraft ImPuls is not mixed with the different `Treninem/Impuls` project, and VoxLyra is not merged with older Boostora files.

The generic template catalog was also expanded for Telegram/VK Mini Apps, Telegram bots, VK bots, FastAPI services, Python desktop applications, Minecraft servers/datapacks, Godot/Unity/Unreal games, websites/React/Next, production systems, reader/library platforms, CAD, engineering documentation, VoxLyra comics-import packages and Windows runtime releases.

### Richer local type recognition
The classifier now distinguishes more practical local formats, including:
- images: PNG/JPEG/WebP/GIF/TIFF/SVG/PSD/XCF plus AVIF/HEIC/HEIF/JXL and common camera RAW formats;
- video: MP4/MKV/AVI/MOV/WebM plus MPEG/MPG/M2TS/MTS/VOB/OGV/3GP/MXF;
- audio: MP3/WAV/FLAC/OGG/M4A/AAC/OPUS plus AIFF/ALAC/APE/AMR;
- documents: office formats, PDF, EPUB/MOBI/FB2, ODS/ODP/DJVU/TEX;
- code/config: Python/JS/TS/Java/C#/C/C++/Go/Rust/PHP/SQL/JSON/YAML/TOML/XML plus shells, Swift, Lua, notebooks, protobuf, GraphQL and Minecraft functions;
- CAD/3D: DWG/DXF/STEP/STL/OBJ/BLEND/FBX/GLTF/GLB plus SolidWorks, Inventor, FreeCAD and SketchUp formats;
- Windows/application packages and additional archive formats.

ChatGPT/OpenAI provenance is intentionally conservative: the program separates files only when the filename itself contains an explicit marker. It does not pretend that every AI-generated file can be reliably identified after arbitrary renaming.

### Self-correction
When the user later defines a more precise explicit project/origin/category route, Smart Organizer can inspect **only its own still-applied journal moves** and correct files that it previously placed in the wrong folder.

Self-correction safety rules:
- arbitrary user files are never swept;
- the old move must still be recorded as applied in the local journal;
- the moved file must still exist at the previous target;
- the new destination must be an existing explicit route;
- historical learning alone cannot trigger self-correction;
- the destination must be free;
- the correction itself is a new reversible journal batch with Undo.

Project recognition for background correction is based on the filename, not the current parent folder. This prevents a previous wrong destination from teaching the correction engine the wrong project name again.

### Five-version retention
Smart Organizer can keep the latest N explicit versions (default setting value: 5) and identify older archives or whole code-project folders for quarantine.

Retention is strict:
- there must be more than N distinct explicit versions;
- ordinary counters, years and calendar dates are not versions;
- dotted folder versions such as `SmartOrganizer_v1.15.9` keep all numeric components;
- whole code folders require a direct project marker such as `main.py`, `requirements.txt`, `package.json`, `project.godot`, `server.properties`, `Cargo.toml` or `go.mod`;
- generic families such as `release_v1`, `build_v2` and `backup_v3` are rejected because they can cross project boundaries;
- old folders move whole and are never flattened into another project;
- permanent deletion is not used: old versions go to local quarantine with Undo.

Automatic background retention is available but remains an explicit setting. The manual preview and manual quarantine actions are available in **Настройки → Версии 5+**.

### Local placement learning
When the user confirms a successful file placement, Smart Organizer stores a compact semantic example locally in `knowledge.db`: project identity (when known), category, extension and destination folder. One confirmation is not enough for an automatic rule. Current real folder usage outranks old history, ties are blocked, and Undo removes the positive example while remembering the rejected exact route.

### One planner for every main organization action
`Навести порядок`, `План порядка` and `В журнал` use the same final safety/learning pipeline. Older toolbar actions cannot bypass ambiguity checks or route medium-confidence suggestions into the operation journal.

### Whole-folder compaction and version families
The organizer can learn project containers from the user's actual hierarchy and move an obvious top-level project **whole** into one unique compatible existing container. Project internals such as `main.py`, `config.json`, assets and libraries are never flattened or merged.

Three or more sibling version folders with the same artifact identity can be recognized as a family for reviewed grouping. Five-version retention is a separate, stricter mechanism for older explicit versions.

### Duplicate safety
- Similar names or equal sizes are only candidates.
- Exact duplicate status requires full SHA-256 after a quick content prefilter.
- Exact duplicate grouping is constrained by conservative project/tree scope.
- Identical `main.py`, `config.json`, images, libraries or other files in different projects remain independent even when byte-for-byte identical.
- Duplicate quarantine is revalidated immediately before execution and remains reversible.

## Implemented
- modern dark Windows GUI with rounded buttons and black/white/purple/turquoise/cyan palette;
- broad tabbed settings for background behavior, Windows startup, Downloads, file types, known projects, version retention and safety;
- live CPU, RAM, disk and current network traffic counters;
- real redirected Windows Desktop and Downloads resolution;
- read-only recursive scanning of Desktop, Downloads, chosen folders and drive roots;
- local SQLite knowledge, settings, action history, adaptive placement memory and operation journal;
- ambiguity-safe project recognition plus broad generic project templates;
- local Smart Brain overview without paid/network AI;
- current-layout scoring plus repeated-confirmation placement learning;
- learned generic project-container compaction from actual existing hierarchy;
- known project-folder compaction into existing user containers;
- conservative version-family grouping and configurable latest-N retention quarantine;
- background Downloads routing using project/origin/type/learned priorities;
- self-correction limited to Smart Organizer's own previously applied moves;
- exact duplicate detection using quick signature plus full SHA-256 inside project scope;
- ZIP analysis and RAR/7Z listing without extraction;
- whole-batch conflict/source/target/parent preflight;
- reversible move, rename, approved mkdir and quarantine operations;
- Undo protection against occupied paths and untracked content;
- installation diagnostics;
- atomic PyInstaller onedir runtime updates with candidate and installed-runtime self-tests;
- preservation of `data/` and `logs/` during runtime replacement;
- Windows CI with core tests, frozen import self-test, real installation smoke test and GUI construction test before rolling release publication.

## Safety model

Smart Organizer is deliberately biased toward false negatives rather than destructive guesses. If confidence is insufficient, the item stays where it is. Background execution is allowed only for a narrow set of explicit or mature routes; existing targets are never overwritten.

Project folders are structural units. Their internal files are not redistributed merely because another project contains files with the same names. Exact duplicates are never inferred from names alone. Version retention never permanently deletes files; it uses a reversible local quarantine.

Local learned knowledge, project destinations, placement examples and Undo feedback are stored on the PC and are not committed to GitHub.
