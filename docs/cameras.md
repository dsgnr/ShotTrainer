# Cameras overview

This page collects community reports on cameras that have been tested with
ShotTrainer.

The aim is to help shooters understand what works in practice, how different
cameras perform at various distances, and what setup considerations may be
required.

The ratings below describe the overall ShotTrainer experience rather than the
quality of the camera itself. A camera that performs well at 10 metres may not
be suitable for 50 metres without additional optics.

## Rating guide

### Excellent

- Reliable tracking with minimal setup
- Consistent results under typical indoor lighting
- Sub-millimetre tracking noise
- Little or no adjustment required

### Good

- Reliable tracking after normal setup and alignment
- Stable results for regular practice
- Typically around 1 mm of tracking noise

### Workable

- Can produce useful results, but requires careful setup
- Often benefits from additional zoom, lighting control, or precise framing
- Suitable for experimentation and hobby use

### Poor

- Tracking is unreliable at the reported distance
- Excessive noise or frequent detection failures
- Difficult to recommend for practical use

## Camera reports

Each camera has its own page containing setup notes, mounting information,
photos, and any discipline-specific recommendations.

To contribute a report:

1. Copy the [camera template](cameras/template.md).
2. Fill in your test results.
3. Add any supporting photos to the `docs/cameras/images/` directory.
4. Submit a pull request.

## Reported cameras

| Camera                                      | Resolution         | Range | Rating | Details                     |
| ------------------------------------------- | ------------------ | ----- | ------ | --------------------------- |
| [Arducam OV9281](cameras/arducam-ov9281.md) | 1280 × 800 (~1 MP) | TBC   | TBC    | Initial testing in progress |

## Factors that affect tracking quality

Several factors have a much larger impact on tracking performance than the
camera model itself.

### 1. Target size in the image

The most important factor is the number of pixels covering the aiming mark.

When the target occupies too few pixels, small changes in edge detection can
produce visible movement in the trace.

As a rule of thumb, aim for at least 30 pixels across the tracking circle.

See [Accuracy and target sizing](accuracy.md) for guidance.

### 2. Mount rigidity

The camera should be mounted as rigidly as possible to the rifle.

Any movement between the camera and the rifle introduces apparent motion that is
unrelated to the shooter's hold and will appear in the trace.

### 3. Lighting

Even lighting generally produces the best results.

Strong shadows, glare, reflections, or backlighting can affect how the detector
identifies the edge of the aiming mark.

### 4. Focus stability

Auto-focus can introduce unwanted movement as the camera adjusts focus during a
hold.

Where possible, lock focus before use.

### 5. Mirage and atmospheric effects

At longer distances, heat shimmer and atmospheric distortion can move the
apparent position of the target.

In some conditions, mirage can contribute more apparent movement than the
shooter.

## Cameras for longer distances

As distance increases, the target occupies fewer pixels in the image.

For many disciplines beyond approximately 25 metres, a basic webcam or laptop
camera will not provide enough resolution on target without additional optics.

Common solutions include:

- Board cameras fitted with telephoto C-mount or CS-mount lenses
- USB cameras designed for inspection or surveillance use
- Cameras with optical zoom capability
- Smartphones with telephoto lenses used through Continuity Camera, NDI, or
  similar video-sharing solutions

There is no single recommended camera for all shooting disciplines. The best
choice depends on the target size, shooting distance, mounting method, and
budget.

Community reports are always welcome.
