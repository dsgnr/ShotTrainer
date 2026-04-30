# Running a session

A session is a recording period during which ShotTrainer captures shots and the
aiming trace around them. Once saved, sessions can be replayed, reviewed, and
exported at any time.

## Starting a session

Enter a session name if you want one, or leave the field blank and ShotTrainer
will create a name automatically using the current date and time.

To begin recording:

- Click **Start session**
- Press **Ctrl+S** (or **Cmd+S** on macOS)

Once recording starts, the session name is locked and the Start button changes
to **Stop session**.

ShotTrainer will begin monitoring the microphone for shots and recording trace
data around each one. The amount of pre-shot and post-shot trace captured can be
configured in **Preferences > Recording**.

## While recording

As you shoot:

- Detected shots are added to the shot list.
- Each shot is scored using the active target face.
- Aim trace data is continuously buffered so the hold leading up to the shot can
  be analysed.
- The session summary shows the current shot count.

## Stopping a session

To finish recording:

- Click **Stop session**
- Press **Ctrl+S** (or **Cmd+S**) again

The session is saved automatically and becomes available in the session browser
for replay, analysis, and export.

## Closing the app during a session

If you try to close ShotTrainer while recording, you will be asked what to do
with the active session.

### Stop and quit

Ends the session normally, saves it, and then closes the application.

### Quit anyway

Closes the application immediately. Any buffered data is written to disk where
possible, but the session may be incomplete.

### Keep recording

Cancels the close operation and returns to the active session.

## Clearing shots

The **Clear shots** button (or **Ctrl+R** / **Cmd+R**) removes all shots from
the current view.

This option is only available when a session is not being recorded. It cannot be
used while recording is active.

Use it to clear the target view and reset the statistics display before starting
a new session.

## Where sessions are stored

Sessions are stored locally in a SQLite database within ShotTrainer's data
folder.

For platform-specific locations, see the [Troubleshooting](troubleshooting.md)
guide.

You can also open the folder directly from the application using **Tools > Open
data folder**.
