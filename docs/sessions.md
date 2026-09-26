---
description: "Record a shooting practice session in ShotTrainer. Name and categorise sessions, capture shots and aim traces, then save them for replay and export."
---

# Recording sessions

The session controls and current session status sit at the bottom of the right
sidebar. Press **Start session** to open the dialog. Enter a name and select a
category, then press **Start session** to begin recording or
**Cancel** to return without recording. Press **Stop session** to finish.
The summary shows the current recording state. **Clear shots** is hidden
during recording.

**Clear shots** removes the displayed shots and clears the main target trace
and replay overlays. Saved sessions are unchanged.

Shots appear in the shot list with their score and offset. Selecting a shot
loads its saved trace window for review. Use [replay](replay.md) to inspect
movement before and after the shot.

Sessions are stored in a local SQLite database. Open **Sessions** from the
navigation rail to find previous sessions, rename them, change categories,
delete them or export their data. See [session browser](session-browser.md).
Stop recording before deleting the active session. Synthetic desktop sessions
use a separate temporary data directory.
