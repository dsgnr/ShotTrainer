# Camera name

> Replace this entire file with notes about the camera. Copy it to
> `docs/cameras/<short-slug>.md` (lowercase, hyphenated) and update
> the entry on [`cameras.md`](../cameras.md) with a row pointing
> here.

| Field | Value |
|-------|-------|
| Manufacturer | |
| Model | |
| Sensor / resolution | e.g. 1920 x 1080, MJPEG |
| Connection | USB-A / USB-C / network |
| Focal length or zoom | fixed / variable, mm or x |
| Approximate price | |
| Tested by | GitHub username |

## Setup

How was the camera mounted? Which rifle? Any adapters or rails?
A photo or two helps a lot here.

> Add a mount photo at `docs/cameras/images/<slug>-mount.jpg` and
> embed it here:
> `![Mount on the rifle](images/<slug>-mount.jpg)`

## Range and conditions

What distance did testing happen at, indoors or outdoors, what
lighting was available, what target was used? Note the ShotTrainer
"Tracking circle" diameter you set in Preferences.

## Result

- **Grade**: Excellent / Good / Workable / Poor (delete the rest).
- **Noise**: roughly how many mm of jitter on a steady hold.
- **Detection reliability**: did the tracker hold the lock through
  movement, or did it lose the target at any point?
- **Anything that needed tweaking**: rotation, mirror flips,
  brightness slider, the auto-optimise button, etc.

## Example frame

A still from the live preview is useful so other readers can judge
how much of their frame the printed circle should fill. Keep the
file under 500 KB. Resize before committing if necessary.

> Add a preview frame at `docs/cameras/images/<slug>-preview.jpg` and
> embed it here:
> `![Live preview frame](images/<slug>-preview.jpg)`

## Notes

Anything else worth knowing: rolling-shutter behaviour, autofocus
hunt, USB bandwidth quirks, supported drivers on the target OS, etc.
