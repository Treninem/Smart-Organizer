# Smart-Organizer

Local-first Windows assistant for file, project and version management.

## Principles
- Local-first architecture.
- No paid APIs.
- User data and learned knowledge stay on the PC.
- GitHub stores code, build automation and update metadata, not the user's database.
- Existing user folder trees have priority over generated templates.

## v0.1.0 — analysis-only foundation

This release is intentionally safe: it **does not move, rename or delete user files**.

Implemented:
- Windows GUI with simple navigation;
- local SQLite knowledge database in `data/knowledge.db`;
- starter knowledge for VoxLyra, legacy Boostora, ImPuls-Minecraft, ProControl and Smart-Organizer;
- read-only folder tree scanner;
- file type classification and project hints;
- action history;
- GitHub update manifest support;
- updater that never replaces `data/` or `logs/`;
- stable EXE bootstrap so future runtime modules can update without reinstalling the launcher every stage;
- Windows build workflow for `SmartOrganizer.exe` and `updater.exe`;
- PowerShell installer targeting `D:\Smart-Organizer` and creating `Smart Organizer.lnk` on the Desktop.

Local learned knowledge is intentionally excluded from GitHub.
