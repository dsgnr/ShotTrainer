---
title: "Group size, hold stability and shot statistics"
description: "Understand ShotTrainer’s total score, group size, hold tremor and time-on-target statistics for live shooting practice and recorded shot analysis."
---

# Shot statistics

The right sidebar shows total score, group size, the percentage of trace
samples inside the innermost scoring ring, and hold tremor. Without scored
shots, the total figure shows the shot count. Missing tracking samples can
leave measurements unavailable.

**Group size** is the largest distance between any two positioned shots, shown
in millimetres. Its tooltip also gives mean radius from the group centre.
**Hold tremor** is the RMS deviation of the selected shot’s pre-shot trace from
its mean position. **Time inside** counts the plotted trace samples within the
innermost ring. It is a sample percentage rather than a duration in seconds.

Group measurements describe the recorded shot positions. Hold measurements
describe aim movement around a selected shot. They do not measure actual
projectile impact or replace a measured paper group.

Use [replay](replay.md) to interpret a trace alongside its numbers. See
[accuracy](accuracy.md) for limitations and [scoring](scoring.md) for scoring
rules.
