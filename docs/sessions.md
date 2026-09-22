---
description: "Record a shooting practice session in ShotTrainer. Name and categorise sessions, capture shots and aim traces, then save them for replay and export."
---

# Recording sessions

Enter a name and select a category in the session controls. Press
**Start session** to begin recording and **Stop session** to finish. The
summary shows the current recording state. Name and category controls are
locked while recording. **Clear shots** is also disabled during recording.

Shots appear in the shot list with their score and offset. Selecting a shot
loads its saved trace window for review. Use [replay](replay.md) to inspect
movement before and after the shot.

Sessions are stored in a local SQLite database. Open **Sessions** from the
navigation rail to find previous sessions, rename them, change categories,
delete them or export their data. See [session browser](session-browser.md).
Stop recording before deleting the active session.
Synthetic desktop sessions use a separate temporary data directory.
