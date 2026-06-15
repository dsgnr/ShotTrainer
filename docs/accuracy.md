# Accuracy notes

ShotTrainer is designed to provide useful feedback on hold quality, shot timing,
and follow-through. It is not intended to be a laboratory-grade measurement
system.

The accuracy you achieve depends as much on the camera, optics, mounting method,
and environment as it does on the software itself.

This page explains the main factors that affect accuracy and what you can
realistically expect from a typical setup.

## How ShotTrainer measures movement

ShotTrainer assumes a rifle-mounted camera looking towards a fixed target.

As the rifle moves, the target appears to move within the camera image. By
tracking that movement frame by frame, ShotTrainer can estimate how the rifle
was being aimed over time.

The quality of those measurements depends on how accurately the target can be
detected in each frame.

## What affects accuracy

### Camera resolution

The more pixels available on the target, the more accurately ShotTrainer can
measure movement.

If the aiming mark occupies only a small number of pixels, small changes in
detection can produce noticeable movement in the trace.

Higher-resolution cameras generally provide better results, especially at longer
distances.

### Optical magnification

Resolution alone is not enough if the target occupies only a tiny portion of the
image.

At longer distances, optical magnification is often more important than sensor
resolution.

Common solutions include:

- Telephoto lenses
- C-mount or CS-mount optics
- Cameras with optical zoom

### Focus and lens quality

A sharply focused target produces a well-defined edge that can be detected
consistently.

Soft focus, motion blur, lens distortion, and chromatic aberration can all
reduce tracking precision.

### Mount rigidity

The camera must move with the rifle.

Any movement between the rifle and the camera introduces apparent motion that
has nothing to do with the shooter's hold.

A rigid mount is one of the most important factors in obtaining useful results.

### Lighting

The detector relies on identifying the edge of a dark circular target.

Strong shadows, glare, reflections, or uneven lighting can change the apparent
edge position and introduce noise into the trace.

### Atmospheric conditions

At longer distances, mirage and heat shimmer can visibly move the apparent
position of the target.

In some conditions, atmospheric distortion contributes more movement than the
shooter.

### Timing accuracy

Shot positions are determined by combining:

- Camera-based tracking data
- Audio-based shot detection

Both systems have finite latency and resolution, which limits timing accuracy.

## Target size and framing

Good tracking requires balancing two competing requirements:

### Enough pixels on target

The aiming mark must occupy enough pixels for the detector to locate its centre
reliably.

As a general guideline:

- Below about **30 pixels across**, tracking noise becomes increasingly
  noticeable.
- More pixels generally improve precision.

### Enough room for movement

The target must also remain comfortably within the camera image during normal
aiming movement.

If the target moves out of view, tracking stops until it reappears.

### Recommended framing

A good starting point is to frame the aiming mark so that it occupies
approximately:

**25–33% of the image width**

This usually provides a good balance between precision and tracking stability.

## Suggested aiming mark sizes

The table below provides rough guidance for a 1080p camera using the recommended
framing approach.

| Distance | Suggested mark diameter | Notes                                                 |
| -------- | ----------------------- | ----------------------------------------------------- |
| 5 m      | 25–50 mm                | Indoor air rifle and classroom practice               |
| 10 m     | 30–60 mm                | Standard 10 m air rifle and air pistol                |
| 25 m     | 80–150 mm               | General practice and pistol shooting                  |
| 50 m     | 150–250 mm              | Smallbore distances. Optical magnification is helpful |
| 100 yd   | 300 mm or larger        | A telephoto lens is usually required                  |

These figures are intended as practical guidelines rather than strict
requirements.

## Understanding detector noise

If the aiming mark occupies only a small number of pixels, the reported aim
position may move slightly even when the rifle is perfectly still.

This movement is detector noise rather than genuine hold movement.

In practice, detector noise often appears as a small amount of random wobble
around the true position.

## Using the mm-per-pixel value

ShotTrainer displays a live millimetres-per-pixel value derived from the
detected tracking circle.

This value provides a quick indication of the theoretical resolution of the
setup.

As an example:

- A 10 mm scoring ring
- A measured scale of 2 mm per pixel

means the ring spans only about five pixels.

At that point, stable sub-millimetre measurements become difficult regardless of
the tracking algorithm.

## Timing alignment

Tracking samples are timestamped when camera frames are received.

Shot events are timestamped when the microphone signal crosses the detection
threshold.

Both use the same monotonic clock source, but camera and audio devices do not
share a common hardware clock.

In practice, alignment accuracy is typically on the order of a few milliseconds
rather than microseconds.

For hold analysis and replay, this level of accuracy is generally sufficient.

## What ShotTrainer does well

While overall accuracy depends heavily on the hardware setup, ShotTrainer is
designed to keep its own contribution to measurement error as small as
practical.

Specifically:

- Pixel-to-millimetre conversion is applied consistently throughout the
  application.
- The same coordinate system is used during recording, replay, and analysis.
- Configurable pre-shot and post-shot windows preserve the full context around
  each shot.
- Detection confidence is recorded for each tracking sample.
- Raw tracking data is retained for later replay and analysis.

As a result, the quality of the measurements you see is primarily determined by
the quality of the image and the stability of the setup rather than by hidden
processing or smoothing.
