# Cameras tested

A community-maintained log of cameras people have used with ShotTrainer,
their results, and the distance they worked well at. The grades describe
the experience, not the hardware in absolute terms. A camera that struggles
at 50 m may be excellent indoors at 10 m.

## Grading

- **Excellent** Sub-millimetre tracking, no manual fiddling, robust to
  typical indoor lighting.
- **Good** Reliable tracking after sensible setup. Expect ~1 mm noise.
- **Workable** Tracking is achievable but needs careful framing, lighting,
  or extra zoom. Suitable for hobby use.
- **Poor** Either does not detect reliably or has too much noise to be
  useful at the listed distance.

## Reported results

Each camera has its own page with photos, mount notes and any
discipline-specific tweaks. Add a new entry by copying
[`cameras/template.md`](cameras/template.md), filling it in, and
sending a pull request along with photos in
[`cameras/images/`](https://github.com/dsgnr/ShotTrainer/tree/main/docs/cameras/images).

| Camera | Resolution | Range | Grade | Details |
|--------|------------|-------|-------|---------|
| [Arducam OV9281](cameras/arducam-ov9281.md) | 1280 x 800 (~1MP) | TBC | TBC | More to come |

## What hurts the most

In rough order of impact:

1. **Pixels across the target mark.** Below 30 pixels the centroid wobbles.
   See [`accuracy.md`](accuracy.md) for sizing guidance.
2. **Mount rigidity on the rifle.** Any flex or play between the camera
   and the rifle adds spurious motion to the trace that has nothing to
   do with hold.
3. **Lighting.** Hard shadows, backlighting and glare on glossy paper
   change which pixels the detector picks as the edge.
4. **Auto-focus.** A focus hunt during a hold reframes the target a
   fraction of a millimetre. Lock focus before calibrating.
5. **Atmospheric mirage.** At long range, heat shimmer alone can move the
   apparent target by more than a typical group size.

## Reaching longer ranges

For ranges beyond about 25 m a webcam without optical zoom won't have
enough pixels on the target. Common solutions:

- A telephoto C-mount or CS-mount lens on a board camera.
- A USB camera marketed for surveillance / inspection that includes
  optical zoom.
- A smartphone with a long-throw lens, sharing video over Continuity
  Camera or NDI.

ShotTrainer doesn't endorse any specific lens or camera. Choices depend
on the rifle discipline being shot. Reports welcome.
