---
description: "Record a shooting practice session in ShotTrainer. Name and categorise sessions, capture shots and aim traces, then save them for replay and export."
---

# Recording sessions

The session controls and current session status sit at the bottom of the right
sidebar. Press **Start session** to open the dialog. Enter a name and select a
category, then press **Start session** to begin recording or
**Cancel** to return without recording. Press **Stop session** to finish.
Before starting, open **Session settings** on the target page, choose the target
face from the built-in or custom catalogue and shot diameter, set the timing
windows and refractory interval, then press
**Apply session settings**. These values are fixed once recording starts.
The summary shows the current recording state.

Shots appear in the shot list with their score and offset. Selecting a shot
loads its saved trace window for review. Use [replay](replay.md) to inspect
movement before and after the shot.

Sessions are stored in a local SQLite database. Open **Sessions** from the
navigation rail to find previous sessions, rename them, change categories,
delete them or export their data. See [session browser](session-browser.md).
Stop recording before deleting the active session. Synthetic desktop sessions
use a separate temporary data directory.

Select the muted **Print shot sheet** icon beside the target controls on the
main page to print the results. Printing includes all shots, scores and offsets.
