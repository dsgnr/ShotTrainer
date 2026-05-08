# ShotTrainer

ShotTrainer is a DIY hold-tracking and shot-scoring tool for shooting
practice. You bring your own camera and microphone, mount the camera
to your rifle's barrel or stock, and point it at a printed paper
target. As you aim, the camera sees the target drift through its
frame, ShotTrainer turns that drift into a hold trace, and the
microphone catches the shot to mark the hit.

It's a hobby project, not a product. No accuracy guarantees. See
[accuracy.md](accuracy.md) for what is and isn't achievable with this
kind of setup, and [cameras.md](cameras.md) for what's worked and
what hasn't with various cameras.

## What it does

- Live target tracking from any USB or built-in camera.
- A4 sheet calibration that converts pixels to millimetres on the target.
- Audio shot detection with adjustable sensitivity and a refractory window.
- Automatic ring scoring against your selected target face, with a
  running session total.
- Session recording to local SQLite, with full pre/post-shot trace.
- Replay with a colour-coded pre-shot / post-shot trace and stats.
- CSV export of shots and trace data.
- Dark theme, tabbed preferences, persistent calibration and settings.

## Get started

- [Setup and camera alignment](setup.md)
- [Setup and development workflow](https://github.com/dsgnr/ShotTrainer#development-setup) on GitHub.
- [How tracking works](how-tracking-works.md)
- [Accuracy and target sizing](accuracy.md)
- [Federation targets (NSRA, ISSF)](provided-targets.md)
- [Cameras tested](cameras.md)
- [Troubleshooting](troubleshooting.md)

## Status

The app is functional and under active development. Expect changes
between releases. See the GitHub project for the issue tracker and to
contribute.

## Licence

GPL-3.0-or-later. See the [`LICENCE`](https://github.com/dsgnr/ShotTrainer/blob/main/LICENCE) file in the
repository.
