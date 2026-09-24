---
description: "Browse saved ShotTrainer sessions, review shots and aim traces, export practice data and manage your local session history."
---

# Session browser

Open **Sessions** from the navigation rail. Search by session name or filter by
category, then select a session.

- **Open** loads the session for review. Double-clicking also opens it.
- **Rename...** asks for a new name.
- **Category...** accepts one of the categories shown in the prompt.
- **Delete** asks for confirmation before removing the session and its trace.
  Stop an active recording before deleting its session.
- **Export CSV...** asks for an export folder path.

Export writes `session_<id>_shots.csv` and `session_<id>_trace.csv` into that
folder, creating it if necessary. Shot rows contain index, timestamp,
coordinates in millimetres, audio level, confidence and score. Trace rows
contain timestamp, pixel and millimetre coordinates, confidence and frame ID.
Exporting again to the same folder replaces files for that session.
