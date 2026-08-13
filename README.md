# Smart-Organizer

Local-first Windows assistant for file, project and version management.

## Principles
- Local-first architecture.
- No paid APIs.
- User data and learned knowledge stay on the PC.
- GitHub stores code, build automation and update metadata, not the user's database.
- Existing user folder trees and real placement habits have priority over generated templates.
- Existing project internals are protected from automatic rearrangement.
- Analysis and planning never silently change user files.
- Confirmed filesystem operations are journaled, conflict-checked and reversible.

## v0.2.13

The organizer now follows the user's real existing layout instead of relying mainly on generic folder names. During every scan it learns how folders are already being used from the files stored directly inside them: category, extension, project association and archive usage. This evidence outranks names such as `Images`, `Archives`, `src` or `app`.

Important safety changes:
- a loose archive is preferentially routed to the folder where the user already keeps archives;
- folders with an existing history of the same category/extension/project receive higher confidence;
- generic folder names alone are weak evidence and cannot pull files into unrelated project trees;
- nested project folders are protected from receiving unrelated loose files;
- files already inside a project tree stay where the user put them;
- selecting a project root freezes its internal structure;
- identical `main.py`, `config.json`, images, libraries and other files in different projects are not treated as removable duplicates;
- exact duplicate detection remains limited to a safe project scope and still requires full SHA-256;
- an already planned duplicate quarantine is revalidated before execution;
- manual update checks now compare against the exact version of the published release commit instead of relying only on potentially stale raw metadata.

## Implemented
- modern dark Windows GUI with rounded buttons and black/white/purple/turquoise/cyan palette;
- live CPU, RAM, disk and current network traffic counters;
- real Windows Desktop and Downloads resolution, including redirected folders on another drive;
- scanning of Desktop, Downloads, selected folders and drive roots;
- local SQLite knowledge database in `data/knowledge.db`;
- read-only recursive scanning with safe system-folder filtering;
- text folder-tree view for the latest scan;
- file type classification for images, documents, code, archives, drawings/CAD, video, audio and programs;
- project hints with token-boundary matching to avoid substring collisions;
- known project summaries plus generic templates for Telegram/VK Mini Apps, Minecraft servers, games, websites, production systems and CAD/drawings;
- local Smart Brain overview with categories, project matches, project-template hints, newest/old version candidates and copy-name candidates;
- version grouping with protection against ordinary counters, years and calendar dates being misclassified as versions;
- duplicate candidate analysis by normalized name and by size without falsely calling them exact duplicates;
- exact duplicate detection with quick content prefiltering followed by full SHA-256 verification;
- ZIP analysis in Python and RAR/7Z listing through 7-Zip without extraction;
- organization planning that learns from the user's current folder usage and prefers existing destinations supported by real evidence;
- persistent reversible-operation journal in SQLite;
- reviewed journal batches apply only after explicit confirmation;
- whole-batch preflight checks sources, destination conflicts and parent folders before the first filesystem change;
- applied journal batches can be undone in reverse order; Undo refuses to overwrite occupied paths or remove folders containing untracked user content;
- local installation diagnostics integrated into the UI;
- atomic full-runtime updates using `SmartOrganizer-runtime.zip` with SHA-256 verification;
- update candidate self-test before replacement and installed-runtime self-test before old-runtime backup removal;
- legacy v0.2.x migration bridge installs a fail-safe `main.py` first so a missing frozen dependency cannot brick startup;
- automatic idle restart after a verified runtime update;
- update process preserves `data/` and `logs/`;
- Windows CI runs core tests, frozen dependency tests, a real installed-package import test and a real GUI screen-construction smoke test before publishing a runtime release.

## Safety model

Smart Organizer does **not** silently reorganize or delete user files. Scanning, duplicate-candidate analysis, exact duplicate detection, archive inspection, Smart Brain analysis and organization planning are read-only. A filesystem change can happen only from a persisted journal batch after a separate confirmation in the UI.

The executor does not overwrite an existing destination. A batch is preflighted before the first change; a failed batch is not silently resumed. Undo performs its own safety checks before reversing applied operations.

A similar name or equal size is only a duplicate candidate. Exact duplicate status requires a full SHA-256 match inside the same safe project scope. Files belonging to different projects are independent even if their contents are byte-for-byte identical.

Local learned knowledge, `data/knowledge.db`, local rule/project files and logs are intentionally excluded from GitHub and from runtime replacement.
