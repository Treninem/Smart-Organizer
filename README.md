# Smart-Organizer

Local-first Windows assistant for file, project and version management.

## Principles
- Local-first architecture.
- No paid APIs.
- User data and learned knowledge stay on the PC.
- GitHub stores code, build automation and update metadata, not the user's database.
- Existing user folder trees have priority over generated templates.
- Safe mode remains the default: analysis and planning never silently change user files.

## v0.2.10

Current Windows builds use a PyInstaller **onedir** runtime rather than onefile extraction. This avoids `_MEI` / `base_library.zip` failures during self-update and makes the installed runtime deterministic.

Implemented:
- Windows GUI with live CPU, RAM, disk and current network traffic counters;
- real Windows Desktop resolution, including redirected Desktop folders on another drive;
- local SQLite knowledge database in `data/knowledge.db`;
- read-only recursive scanning with a safe file-count limit;
- system folders are skipped when scanning an entire volume, while legitimate project folders such as `Windows` are no longer hidden inside normal user/project roots;
- file type classification and project hints with token-boundary matching to avoid substring collisions;
- project summaries and existing-folder ranking;
- version grouping with protection against ordinary counters, years and calendar dates being misclassified as versions;
- exact duplicate detection with quick content prefiltering followed by full SHA-256 verification;
- ZIP analysis in Python and RAR/7Z listing through 7-Zip without extraction;
- read-only organization planning that prefers existing folders and clearly marks suggestions that require creating a new folder;
- UI preview of the organization plan;
- persistent reversible-operation journal in SQLite;
- safe move intents can be recorded only for already existing destination folders;
- a reviewed journal batch can be applied only after explicit user confirmation;
- whole-batch preflight checks sources, destination conflicts and parent folders before the first filesystem change;
- applied journal batches can be undone in reverse order; Undo refuses to overwrite occupied paths or remove non-empty created folders;
- atomic full-runtime updates using `SmartOrganizer-runtime.zip` with SHA-256 verification;
- update candidate self-test before replacement and installed-runtime self-test before old-runtime backup removal;
- automatic idle restart after a verified runtime update;
- update process preserves `data/` and `logs/`;
- Windows CI tests the core modules, frozen runtime, installed package and updater before publishing a runtime release.

## Safety model

Smart Organizer does **not** automatically reorganize or delete user files. Scanning, duplicate detection, archive inspection and organization planning are read-only. A filesystem change can happen only from a persisted journal batch after a separate confirmation in the UI.

The executor does not overwrite an existing destination and does not silently create a missing destination folder. A batch is preflighted before the first change; a failed batch is not silently resumed. Undo performs its own safety checks before reversing applied operations.

Local learned knowledge, `data/knowledge.db` and logs are intentionally excluded from GitHub and from runtime replacement.
