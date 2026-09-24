---
title: "Microphone setup and shot detection"
description: "Set up microphone input for automatic shot detection in ShotTrainer. Adjust sensitivity and timing to capture shots and avoid false triggers."
---

# Audio setup

Open **Preferences** and select **Microphone** in the **Audio** section. Adjust
**Gain**, then configure **Shot threshold** and **Refractory** in **Detection**.
The refractory interval prevents repeated registration of one sound event. Save
your changes.

Check that a deliberate shot sound registers once and that ordinary background
noise does not register. Raise the threshold if unrelated sounds trigger shots.
Lower it or increase gain if shots are missed. Recheck after changing microphone
position or the room environment.

**Pre-shot window**, **Post-shot window** and **Release window** control the
trace intervals used for shot review. Camera and audio measurements share a
monotonic time base in the controller.

Real microphone input requires the desktop application with system backends.
Synthetic devices and the browser mock cannot verify microphone sensitivity,
latency or permissions on your machine.
