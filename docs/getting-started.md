# Get started

ShotTrainer is a camera-based hold tracking and shot analysis tool for shooting
practice.

Using a camera mounted to your rifle and a microphone positioned near the firing
point, ShotTrainer records how the rifle moves before, during, and after each
shot. It can display a live hold trace, score shots against a selected target
face, and save complete shooting sessions for later review.

All processing is performed locally on your computer.

> ShotTrainer is a hobby project and should not be considered a certified
> training or scoring system. See [Accuracy and target sizing](accuracy.md) for
> a discussion of the practical limits of this approach.

## How it works

1. Mount a camera to your rifle.
2. Aim at a printed target or marker sheet.
3. Start a recording session.
4. ShotTrainer tracks the movement of the target within the camera image and
   converts that movement into a hold trace.
5. When a shot is detected by the microphone, the current trace position is
   recorded as the shot location.
6. The shot can then be scored, replayed, and analysed.

## Features

- Live target tracking using USB and built-in cameras
- Automatic millimetre scaling from a known target diameter
- Audio-based shot detection with adjustable sensitivity
- Automatic scoring using configurable target faces
- Session recording with full pre-shot and post-shot trace data
- Shot replay with colour-coded trace visualisation
- Hold stability and performance statistics
- CSV export for external analysis
- Persistent settings and dark-theme user interface

## Before you begin

For the best experience, it is worth reading the setup guides before your first
session.

### Recommended reading

- [Installation](installation.md)
- [Setup and camera alignment](setup.md)
- [Accuracy and target sizing](accuracy.md)
- [Using federation targets (NSRA, ISSF)](provided-targets.md)
- [Cameras overview](cameras.md)

### Technical documentation

- [How tracking works](how-tracking-works.md)
- [Development setup](https://github.com/dsgnr/ShotTrainer#development-setup)

### Troubleshooting

- [Troubleshooting](troubleshooting.md)

## Project status

ShotTrainer is actively developed and features may change between releases.

Bug reports, suggestions, and contributions are welcome through the project's
GitHub repository.

## Licence

ShotTrainer is released under the **GPL-3.0-or-later** licence.

See the project's
[`LICENCE`](https://github.com/dsgnr/ShotTrainer/blob/main/LICENCE) file for
details.
