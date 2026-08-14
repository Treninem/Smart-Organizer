# Smart-Organizer

Local-first Windows assistant for practical file, project and version organization.

## Principles
- Local-first: no paid APIs and no cloud database requirement.
- `data/`, `logs/` and learned `knowledge.db` stay on the user's PC and are preserved by updates.
- Existing user folder trees and real placement habits have priority over generated templates and historical memory.
- Existing project internals are protected from automatic rearrangement.
- A filesystem change happens only after a visible plan and explicit confirmation.
- Existing destinations are never overwritten.
- Applied batches are journaled and reversible with Undo.

## v0.2.15

This release makes the organizer adaptive instead of relying only on hard-coded folder rules.

### Local placement learning
When the user confirms a successful file placement, Smart Organizer stores a compact semantic example locally in `knowledge.db`: project identity (when known), category, extension and destination folder. The rule is not uploaded anywhere.

Safety rules for learning:
- one confirmation is **not** enough for an automatic decision;
- a route becomes mature only after repeated confirmations;
- current real folder usage always outranks old learned history;
- learning applies only to loose/root/inbox files, never to files already inside normal project trees;
- project-specific learning cannot cross into another project;
- two equally confirmed destinations are treated as ambiguous and blocked;
- Undo removes the positive example and remembers the exact rejected source → destination pair;
- stale learned folders are ignored when they no longer exist in the current scan.

The Files screen now shows how many placement rules are learned, how many are mature, how many are still learning, how many decisions were boosted by confirmed history and how many memory conflicts were blocked.

### One planner for every button
`Навести порядок`, `План порядка` and `В журнал` now use the same final safety/learning pipeline. Older toolbar actions can no longer bypass newer ambiguity checks or route medium-confidence suggestions into the operation journal.

The journal shortcut is intentionally stricter: it accepts only high-confidence moves into already existing folders. Creating new grouping folders remains available only through the main reviewed workflow.

### Smarter project classification
Project matching no longer silently chooses one project when two projects receive the same evidence score. Generic shared words such as `bot`, `app` or `server` therefore produce an ambiguous/no-project result instead of a random project assignment.

Local file classification was expanded for practical formats including CBZ/CBR, EPUB/MOBI/FB2, PSD/XCF, BLEND/FBX/GLTF/GLB, APK, OPUS and additional archive/code formats.

### Real organization workflow
1. Scan the selected Desktop/folder/drive read-only.
2. Learn how the user already groups archives, images, documents, project files and other content.
3. Combine current layout evidence with repeatedly confirmed local placement rules.
4. Build one plan with source, destination, confidence and explanation.
5. Block ambiguous, conflicting or medium-confidence automatic moves.
6. Show files/folders that are safe enough to apply and keep uncertain suggestions read-only.
7. Preflight the whole confirmed batch before the first change.
8. Apply without overwriting existing paths.
9. Rescan, store useful confirmed examples and keep full Undo information.

### Existing-layout learning
Folder names alone are not trusted. Real direct contents of a folder are stronger evidence: category, extension, archive use and recognized project association. If two destinations receive nearly equal evidence, the move is stopped instead of guessed.

Undo acts as negative local feedback: when the user reverses a normal move, the exact same source → destination pair is remembered locally and is not offered again as an automatic action.

### Whole-folder compaction
The organizer can recognize obvious top-level project folders and move the **whole folder** into an already existing user container. Known project types still understand containers such as `Боты`, `Minecraft` or `Программы`, but v0.2.15 also learns generic project containers directly from the user's hierarchy.

A folder becomes a learned project container only when it already contains at least two immediate child project roots detected by real project markers such as `main.py`, `pyproject.toml`, `package.json`, `project.godot`, `server.properties`, `Cargo.toml` or `go.mod`. A loose top-level project can enter that container only when exactly one compatible container exists. Two possible containers stop the move. Project folders are always moved whole and are never flattened or merged.

A loose root-level project file is routed into a project folder only when the destination is unambiguous. Several version folders without a clear canonical project folder cause the file to stay in place.

### Version-folder families
Three or more sibling folders with the same artifact identity and explicit versions can be recognized as one version family. If an existing unversioned family folder exists, it is preferred. Otherwise Smart Organizer may propose one new family container, but creation is allowed only by this explicit high-confidence rule and still requires confirmation. Version folders are moved whole; their `main.py`, `config.json`, assets and other internal files are never merged.

### Duplicate safety
- Similar names or equal sizes are only candidates.
- Exact duplicate status requires full SHA-256 after a quick content prefilter.
- Exact duplicate grouping is constrained by conservative project/tree scope.
- Identical `main.py`, `config.json`, images, libraries or other files in different projects remain independent even when byte-for-byte identical.
- Duplicate quarantine is revalidated immediately before execution and remains reversible.

## Implemented
- modern dark Windows GUI with rounded buttons and black/white/purple/turquoise/cyan palette;
- simplified stable navigation centered around the main organization workflow;
- live CPU, RAM, disk and current network traffic counters;
- real Windows Desktop and Downloads resolution, including redirected folders;
- read-only recursive scanning of Desktop, Downloads, chosen folders and drive roots;
- safe system-folder filtering only where appropriate;
- local SQLite knowledge, settings, action history, adaptive placement memory and operation journal;
- file classification for images, documents, code, archives, drawings/CAD, video, audio and programs;
- boundary-safe and ambiguity-safe project recognition plus generic project templates;
- local Smart Brain overview without paid/network AI;
- version recognition protected against ordinary counters, years and calendar dates;
- existing-layout scoring plus ambiguity blocking;
- repeated-confirmation placement learning with Undo demotion;
- learned generic project-container compaction from actual existing hierarchy;
- known project-folder compaction into existing user containers;
- conservative version-folder family grouping;
- exact duplicate detection using quick signature plus full SHA-256 inside project scope;
- ZIP analysis and RAR/7Z listing without extraction;
- whole-batch conflict/source/target/parent preflight;
- reversible move, rename, approved mkdir and quarantine operations;
- Undo protection against occupied paths and untracked content;
- local memory of exact destinations rejected through Undo;
- installation diagnostics;
- atomic PyInstaller onedir runtime updates with candidate and installed-runtime self-tests;
- legacy v0.2.x recovery bridge;
- preservation of `data/` and `logs/` during runtime replacement;
- Windows CI with core tests, frozen import self-test, real installation smoke test and GUI construction test before rolling release publication.

## Safety model

Smart Organizer is deliberately biased toward false negatives rather than destructive guesses. If confidence is insufficient, the item stays where it is. Automatic execution requires a high-confidence existing destination; the only new-folder exception is a separately confirmed, high-confidence version-family grouping rule.

Project folders are treated as structural units. Their internal files are not redistributed merely because another project contains files with the same names. Exact duplicates are never inferred from names alone.

Local learned knowledge, placement examples and Undo feedback are stored on the PC and are not committed to GitHub.
