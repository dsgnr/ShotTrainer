---
title: "Browse, search and export saved sessions"
description: "Browse saved ShotTrainer sessions, review shots and aim traces, export practice data and manage your local session history."
---

# Session browser

## Browse and search sessions

Open the **Sessions** page from the navigation rail. Search by session name or
notes, or filter by category, then select a session. Points are displayed to one decimal
place.

## Create, manage and delete sessions

**New session** opens the name, category and session settings dialogue.
Creating or importing a session is unavailable while recording. Select a saved
session before using Rename, Category, Notes, Delete or Export. These actions use
in-app dialogues. **Cancel** or Escape dismisses a dialogue without sending its
action.

- **Open** loads the session for review. Double-clicking also opens it.
- **Rename...** opens a dialogue for a new name, up to 120 characters.
- **Category...** opens a dropdown of session categories.
- **Notes...** opens a text box for free-form notes on the whole session, up to 4000 characters.
  Notes can be edited at any time, including during a recording. The first line shows under the session in the list.
- **Delete** asks for confirmation before removing the session and its trace.
  Stop an active recording before deleting its session.
- **Export...** opens the system save dialogue and writes the session to a single `.json` file, including its settings, shots and trace.
- **Import...** opens the system file dialogue to pick a file written by **Export...** and adds it as a new session.
  Stop recording before importing.

## Session file format

The file is JSON with a `format` and `version` field, the session settings
(name, notes, category, target face, position, timing settings, shot diameter,
series length and start and end times), every shot and every trace sample.
Import creates a new session with the same values, so shot series, scores and
timestamps are preserved. A file with an unknown format, version or category
is rejected and leaves the database unchanged.

## Navigation rail and About

The navigation rail highlights the current page. Select the Target icon to return
to the target, or open a saved session to review it there. Select **About** for
the installed version number and a link to the GitHub repository.

## Create a session with settings

Select **New session** to choose a name, category, target face, shot diameter
and timing settings. Choose **Prone**, **Standing** or **Kneeling** using the
illustrated shooting position controls. The position is saved with the session. **Create session** opens an empty target with those
settings. **Start session** begins recording immediately. Cancel leaves the
current session unchanged. Stop an active recording before creating another
session.

## Shots per series

Set **Shots per series** when creating a session or in its settings before
recording. The default is 10. Recording starts a new series automatically when
the current series fills. The shot list separates each series. Both targets
show the latest series, or the selected shot's series when reviewing earlier
shots. A new shot returns the targets to the latest series. Deleting a shot
keeps the remaining shots in their original series.
