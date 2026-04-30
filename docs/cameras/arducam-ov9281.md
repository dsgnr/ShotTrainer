# Arducam OV9281 (USB, Global Shutter)

| Field               | Value                                                 |
| ------------------- | ----------------------------------------------------- |
| Manufacturer        | Arducam                                               |
| Model               | B0332 (1MP OV9281 Global Shutter, no microphones)     |
| Sensor / resolution | OV9281, 1280 x 800, monochrome, global shutter        |
| Connection          | USB 2.0 (UVC, plug-and-play)                          |
| Frame rate          | Up to 120 fps @ 1280x800 MJPEG                        |
| Lens mount          | M12 (interchangeable)                                 |
| Approximate price   | ~£30-40 + lenses                                      |
| Tested by           | [@dsgnr](https://github.com/dsgnr){:target="\_blank"} |

## What it looks like

The board is small and bare, without an enclosure. Below are front, back,
and a shot taken with digital calipers so you can gauge the size.

<figure markdown="span">
  ![Arducam OV9281 front view, lens facing camera](./images/arducam-ov9281/arducam-ov9281-front.jpeg)
  <figcaption>Front of the board with the M12 lens mount.</figcaption>
</figure>

<figure markdown="span">
  ![Arducam OV9281 back view showing the USB connector](./images/arducam-ov9281/arducam-ov9281-back.jpeg)
  <figcaption>Back of the board with the USB connector and OV9281 sensor markings.</figcaption>
</figure>

<figure markdown="span">
  ![Arducam OV9281 measured with digital calipers](./images/arducam-ov9281/arducam-ov9281-measurement-scale.jpeg)
  <figcaption>Size reference, measured with digital calipers.</figcaption>
</figure>

## Why this camera

I picked this camera for two reasons. It has a global shutter and it supports
interchangeable lenses.

Rolling shutter on a normal camera exposes each row of pixels at a slightly
different time. When the rifle is moving (shouldering, transitioning onto
target, recoil) the image shears and the circle the detector finds isn't quite
the right shape. Global shutter exposes the whole sensor at once, so the
geometry is always correct regardless of how fast the rifle is moving. The hope
is that the detector will hold lock through movements that would occasionally
cause a dropout on a rolling shutter camera.

The sensor is monochrome. There's no
[Bayer filter](https://en.wikipedia.org/wiki/Bayer_filter) (the colour mosaic
that sits over a normal camera sensor and blocks most of the light hitting each
pixel so it only sees red, green, or blue). Every pixel on this sensor sees all
the light that hits it, which means better sensitivity and sharper edges in
greyscale. ShotTrainer converts to greyscale before detection anyway, so nothing
useful is lost. The circle edge should read slightly cleaner in the threshold
step compared to a colour sensor at the same resolution.

120 fps at full resolution (1280x800). 1MP sounds low on paper but ShotTrainer
only needs enough pixels across the tracking circle for a stable centroid, not a
sharp photograph. The low resolution is what allows the high frame rate over USB
2.0, and 4x more frames per second than a typical 30 fps camera should mean
smoother traces and tighter shot timing. Whether that actually matters for
coaching or just looks nicer is something to evaluate.

### Lenses tried

| Lens                        | FoV (approx)       | Holder needed | Notes                               |
| --------------------------- | ------------------ | ------------- | ----------------------------------- |
| Stock (wide-angle)          | ~70 deg horizontal | 9 mm (stock)  | Useless past ~2 m                   |
| [16 mm M12](#16mm-m12-lens) | 27 deg horizontal  | 9 mm (stock)  | Not usable for 25 yard NSRA targets |
| [50 mm M12](#50mm-m12-lens) | ~8 deg             | 16 mm         | Needs taller holder                 |

Tests below are at a 25 yards indoor range. LED lighting, standard NSRA 25 yard
card (NSRA 2510 BM/89-18) on firing point 8 (rightmost).

Specifications below are from manufacturer specs. FOV is converted to the OV9281
sensor.

#### 16mm M12 lens

Useless at 25 yards.

Spec:

| Specification | Value                                            |
| ------------- | ------------------------------------------------ |
| Focal Length  | 16mm                                             |
| Aperture      | F2.0                                             |
| FOV (DxHxV)   | 16.4° × 13.9° × 8.8° (5.6m x 3.5m x 6.6m at 25y) |

![Arducam OC9281 preview 16mm lens](./images/arducam-ov9281/arducam-ov9281-preview-16mm-lens.jpg)

#### 50mm M12 lens

Each black target is 51.5mm, and this works out to ~33px for the tracker. This
is probably usable with a single target on the card, but unlikely to get
"millimetre accuracy". Needs to be tested properly on the rifle.

Spec:

| Specification | Value                                             |
| ------------- | ------------------------------------------------- |
| Focal Length  | 50mm                                              |
| Aperture      | f/2.8                                             |
| FOV (DxHxV)   | 5.3° × 4.5° × 2.8° (1.77m x 1.12m x 2.10m at 25y) |

![Arducam OC9281 preview 16mm lens](./images/arducam-ov9281/arducam-ov9281-preview-50mm-lens.jpg)

## 3D-printed case

The bare PCB doesn't make for a great mounting platform on its own. I'm using
[Arducam OV9281 case](https://www.printables.com/model/306628-arducam-ov9281-case)
by [3rdwall on Printables](https://www.printables.com/@3rdwall_138596), a
two-part enclosure where the PCB sits in a tray and the top is fixed down
with self-tapping screws. The lens stays exposed and there is a channel for
the cable to exit cleanly, so once the cable is plugged into the PH
connector and the lid is on you have a tidy assembly.

!!! note "Looking for something better"
    This is what I have for now, not a final answer. The case protects the
    PCB but has no proper mounting interface, so it currently has to be
    strapped or zip-tied to the rifle. Ideally it would clamp to a Picatinny
    rail or an Anschutz-style accessory dovetail.

<figure markdown="span">
  ![3D-printed case open](./images/arducam-ov9281/arducam-ov9281-3d-print-v1-open.jpeg)
  <figcaption>The case opened up. The PCB drops in and the lid screws down with self-tapping screws.</figcaption>
</figure>

<figure markdown="span">
  ![Arducam OV9281 in its 3D-printed case ready to use](./images/arducam-ov9281/arducam-ov9281-3d-print-v1.jpeg)
  <figcaption>The case assembled and ready to mount on the rifle.</figcaption>
</figure>

## Still to do

- Screenshot the stock wide-angle lens at 25 yards.
- Test with a 90mm focal length lens.
- Mount the PCB on the rifle and capture some initial test footage.
- Test at 50 m and 100 yards using NSRA targets. Since the aiming mark scales
  with distance, the same lens should theoretically keep the circle at a similar
  size in the image.
- Measure the noise floor with the rifle clamped to separate system noise from
  shooter-induced movement.
- Compare 120 fps and 60 fps to determine whether the higher frame rate provides
  any meaningful benefit to the trace.
