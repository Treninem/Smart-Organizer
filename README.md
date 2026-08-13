# Smart-Organizer

Local-first Windows assistant for file, project and version management.

## Principles
- Local-first architecture.
- No paid APIs.
- User data and learned knowledge stay on the PC.
- GitHub stores code, build automation and update metadata, not the user's database.
- Existing user folder trees have priority over generated templates.
- Safe mode remains the default: analysis and planning do not silently change user files.

## v0.2.9

Current Windows builds use a PyInstaller **onedir** runtime rather than onefile extraction. This avoids `_MEI` / `base_library.zip` failures during self-update and makes the installed runtime deterministic.

Implemented:
- Windows GUI with live CPU, RAM, disk and current network traffic counters;
- real Windows Desktop resolution, including redirected Desktop folders on another drive;
- local SQLite knowledge database in `data/knowledge.db`;
- read-only recursive scanning with excluded system/dependency directories and a safe file-count limit;
- file type classification and project hints;
- project summaries and existing-folder ranking;
- version grouping with protection against ordinary numbers being misclassified as versions;
- exact duplicate detection with quick content prefiltering followed by full SHA-256 verification;
- ZIP analysis in Python and RAR/7Z listing through 7-Zip without extraction;
- read-only organization planning that prefers existing folders and clearly marks suggestions that require creating a new folder;
- UI preview of the organization plan;
- reversible-operation journal architecture in SQLite;
- ability to record only safe move intents targeting already existing folders, without executing them;
- atomic full-runtime updates using `SmartOrganizer-runtime.zip` with SHA-256 verification;
- automatic idle restart after a verified runtime update;
- update process preserves `data/` and `logs/`;
- Windows CI tests the core modules, frozen runtime, installed package and updater before publishing a runtime release.

## Safety model

Smart Organizer currently does **not** automatically delete or move user files. Planning can be written to the local operation journal, but filesystem execution remains disabled until the reversible executor and undo path are fully verified.

Local learned knowledge is intentionally excluded from GitHub.
