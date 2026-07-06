# Arducam OV9281 (USB, Global Shutter)

| Field | Value |
|-------|-------|
| Manufacturer | Arducam |
| Model | B0332 (1MP OV9281 Global Shutter, no microphones) |
| Sensor / resolution | OV9281, 1280 x 800, monochrome, global shutter |
| Connection | USB 2.0 (UVC, plug-and-play) |
| Frame rate | Up to 120 fps @ 1280x800 MJPEG |
| Lens mount | M12 (interchangeable) |
| Approximate price | ~£30-40 + lenses |
| Tested by | @dsgnr |

## Why this camera

I picked this camera for two reasons. It has a global shutter and
it supports interchangeable lenses.

Rolling shutter on a normal camera exposes each row of pixels at a
slightly different time. When the rifle is moving (shouldering,
transitioning onto target, recoil) the image shears and the circle the
detector finds isn't quite the right shape. Global shutter exposes the
whole sensor at once, so the geometry is always correct regardless of
how fast the rifle is moving. The hope is that the detector will hold
lock through movements that would occasionally cause a dropout on a
rolling shutter camera.

The sensor is monochrome. There's no
[Bayer filter](https://en.wikipedia.org/wiki/Bayer_filter) (the colour
mosaic that sits over a normal camera sensor and blocks most of the
light hitting each pixel so it only sees red, green, or blue). Every
pixel on this sensor sees all the light that hits it, which means
better sensitivity and sharper edges in greyscale. ShotTrainer converts
to greyscale before detection anyway, so nothing useful is lost. The
circle edge should read slightly cleaner in the threshold step compared
to a colour sensor at the same resolution.

120 fps at full resolution (1280x800). 1MP sounds low on paper but
ShotTrainer only needs enough pixels across the tracking circle for a
stable centroid, not a sharp photograph. The low resolution is what
allows the high frame rate over USB 2.0, and 4x more frames per second
than a typical 30 fps camera should mean smoother traces and tighter
shot timing. Whether that actually matters for coaching or just looks
nicer is something to evaluate.

## Still to do

- Mount the PCB on the rifle and capture some initial test footage.
- Test the stock wide-angle lens at 25 yards to confirm whether it is
  too wide to put enough pixels on the target.
- Try a longer M12 lens, around 16 mm, at 25 yards and measure the
  pixel diameter of the tracking circle.
- Test at 50 m and 100 yards using NSRA targets. Since the aiming mark
  scales with distance, the same lens should theoretically keep the
  circle at a similar size in the image.
- Investigate longer focal lengths such as 50 mm and 90 mm for tighter
  framing at longer ranges, and check whether the stock 9 mm lens holder
  provides enough back-focus adjustment.
- Replace the bare PCB with a 3D-printed enclosure once the lens
  selection is finalised.
- Measure the noise floor with the rifle clamped to separate system
  noise from shooter-induced movement.
- Compare 120 fps and 60 fps to determine whether the higher frame
  rate provides any meaningful benefit to the trace.
