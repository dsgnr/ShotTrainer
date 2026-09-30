---
description: "Browse saved ShotTrainer sessions, review shots and aim traces, export practice data and manage your local session history."
---

# Session browser

Open the **Sessions** page from the navigation rail. Search by session name or filter by
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

The navigation rail highlights the current page. Select the Target icon to return
to the target, or open a saved session to review it there.

Select **New session** to choose a name, category, target face, shot diameter
and timing settings. Choose **Prone**, **Standing** or **Kneeling** using the
illustrated shooting position controls. The position is saved with the session. **Create session** opens an empty target with those
settings. **Start session** begins recording immediately. Cancel leaves the
current session unchanged. Stop an active recording before creating another
session.

Set **Shots per series** when creating a session or in its settings before
recording. The default is 10. Recording starts a new series automatically when
the current series fills. The shot list separates each series. Both targets
show the latest series, or the selected shot's series when reviewing earlier
shots. A new shot returns the targets to the latest series. Deleting a shot
keeps the remaining shots in their original series.
