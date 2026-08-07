//! Port of `tracking/frame_ops.py` and the greyscale conversion the
//! controller runs on every frame. Pure Rust, so it needs no OpenCV.

use crate::frame::{Frame, FrameError, PixelFormat};

/// What the camera preferences ask for. The default is the identity.
#[derive(Debug, Clone, PartialEq)]
pub struct FrameTransform {
    pub rotation_degrees: i32,
    pub flip_horizontal: bool,
    pub flip_vertical: bool,
    pub brightness: f64,
    pub contrast: f64,
}

impl Default for FrameTransform {
    fn default() -> Self {
        FrameTransform {
            rotation_degrees: 0,
            flip_horizontal: false,
            flip_vertical: false,
            brightness: 0.0,
            contrast: 1.0,
        }
    }
}

/// OpenCV's generic 8-bit BGR to grey conversion,
/// `(1868 B + 9617 G + 4899 R + 8192) >> 14`. A grey frame is returned as is.
pub fn bgr_to_grey(frame: Frame) -> Frame {
    if frame.format() == PixelFormat::Grey {
        return frame;
    }
    let (pixels, _) = frame.data().as_chunks::<3>();
    let data = pixels
        .iter()
        .map(|&[b, g, r]| {
            ((1868 * u32::from(b) + 9617 * u32::from(g) + 4899 * u32::from(r) + 8192) >> 14) as u8
        })
        .collect();
    Frame::from_parts(frame.width(), frame.height(), PixelFormat::Grey, data)
}

/// Rotates clockwise by a multiple of 90 degrees. Negative and large angles
/// are reduced modulo 360 as Python's `%` does.
pub fn rotate_frame(frame: Frame, degrees: i32) -> Result<Frame, FrameError> {
    let (w, h) = (frame.width() as usize, frame.height() as usize);
    let rotated = match degrees.rem_euclid(360) {
        0 => return Ok(frame),
        90 => remap(&frame, h, w, |x, y| (y, h - 1 - x)),
        180 => remap(&frame, w, h, |x, y| (w - 1 - x, h - 1 - y)),
        270 => remap(&frame, h, w, |x, y| (w - 1 - y, x)),
        _ => return Err(FrameError::UnsupportedRotation(degrees)),
    };
    Ok(rotated)
}

/// Mirrors horizontally, vertically or both.
pub fn flip_frame(frame: Frame, horizontal: bool, vertical: bool) -> Frame {
    if !horizontal && !vertical {
        return frame;
    }
    let (w, h) = (frame.width() as usize, frame.height() as usize);
    remap(&frame, w, h, |x, y| {
        (
            if horizontal { w - 1 - x } else { x },
            if vertical { h - 1 - y } else { y },
        )
    })
}

/// `cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)`. OpenCV
/// works in `f32` with a fused multiply-add, takes the absolute value and
/// rounds half to even. The identity returns the frame without a copy.
pub fn adjust_image(frame: Frame, brightness: f64, contrast: f64) -> Frame {
    if contrast == 1.0 && brightness == 0.0 {
        return frame;
    }
    let (alpha, beta) = (contrast as f32, brightness as f32);
    let (w, h, format) = (frame.width(), frame.height(), frame.format());
    let mut data = frame.into_data();
    for value in &mut data {
        // `as u8` saturates and maps NaN to 0, as `saturate_cast<uchar>` does.
        *value = f32::from(*value)
            .mul_add(alpha, beta)
            .abs()
            .round_ties_even() as u8;
    }
    Frame::from_parts(w, h, format, data)
}

/// Rotation, then flips, then brightness and contrast, as in Python.
pub fn transform_frame(frame: Frame, transform: &FrameTransform) -> Result<Frame, FrameError> {
    let frame = rotate_frame(frame, transform.rotation_degrees)?;
    let frame = flip_frame(frame, transform.flip_horizontal, transform.flip_vertical);
    Ok(adjust_image(
        frame,
        transform.brightness,
        transform.contrast,
    ))
}

/// Builds an `out_w` by `out_h` frame whose pixel `(x, y)` is the source
/// pixel `source(x, y)`.
fn remap(
    frame: &Frame,
    out_w: usize,
    out_h: usize,
    source: impl Fn(usize, usize) -> (usize, usize),
) -> Frame {
    let channels = frame.format().channels();
    let in_w = frame.width() as usize;
    let input = frame.data();
    let mut data = Vec::with_capacity(out_w * out_h * channels);
    for y in 0..out_h {
        for x in 0..out_w {
            let (sx, sy) = source(x, y);
            let start = (sy * in_w + sx) * channels;
            data.extend_from_slice(&input[start..start + channels]);
        }
    }
    Frame::from_parts(out_w as u32, out_h as u32, frame.format(), data)
}

#[cfg(test)]
mod tests {
    use std::collections::HashMap;

    use serde_json::Value;
    use testkit::load_golden;

    use super::*;
    use crate::test_support::{f64_at, frame_from_json};

    fn golden() -> (Value, HashMap<String, Frame>) {
        let golden = load_golden("frame_ops");
        let images = golden["images"]
            .as_array()
            .unwrap()
            .iter()
            .map(|v| (v["name"].as_str().unwrap().to_owned(), frame_from_json(v)))
            .collect();
        (golden, images)
    }

    fn image(images: &HashMap<String, Frame>, case: &Value) -> Frame {
        images[case["image"].as_str().unwrap()].clone()
    }

    /// `"error"` in the fixture means Python raised `ValueError`.
    fn check(got: Result<Frame, FrameError>, expected: &Value, context: &Value) {
        match (got, expected) {
            (Err(FrameError::UnsupportedRotation(_)), Value::String(s)) if s == "error" => {}
            (Ok(frame), Value::Object(_)) => {
                assert_eq!(frame, frame_from_json(expected), "{context}")
            }
            (got, _) => panic!("{context}: got {got:?}"),
        }
    }

    #[test]
    fn rotate_matches_python() {
        let (golden, images) = golden();
        for case in golden["rotate"].as_array().unwrap() {
            let degrees = i32::try_from(case["degrees"].as_i64().unwrap()).unwrap();
            check(
                rotate_frame(image(&images, case), degrees),
                &case["out"],
                case,
            );
        }
    }

    #[test]
    fn flip_matches_python() {
        let (golden, images) = golden();
        for case in golden["flip"].as_array().unwrap() {
            let (h, v) = (case["h"].as_bool().unwrap(), case["v"].as_bool().unwrap());
            check(
                Ok(flip_frame(image(&images, case), h, v)),
                &case["out"],
                case,
            );
        }
    }

    #[test]
    fn adjust_matches_python_exactly() {
        let (golden, images) = golden();
        for case in golden["adjust"].as_array().unwrap() {
            let out = adjust_image(
                image(&images, case),
                f64_at(case, "brightness"),
                f64_at(case, "contrast"),
            );
            check(Ok(out), &case["out"], case);
        }
    }

    #[test]
    fn transform_matches_python() {
        let (golden, images) = golden();
        for case in golden["transform"].as_array().unwrap() {
            let transform = FrameTransform {
                rotation_degrees: i32::try_from(case["rotation"].as_i64().unwrap()).unwrap(),
                flip_horizontal: case["h"].as_bool().unwrap(),
                flip_vertical: case["v"].as_bool().unwrap(),
                brightness: f64_at(case, "brightness"),
                contrast: f64_at(case, "contrast"),
            };
            check(
                transform_frame(image(&images, case), &transform),
                &case["out"],
                case,
            );
        }
    }

    /// opencv-python on Apple silicon converts with KleidiCV's 15-bit
    /// coefficients, so the fixture may differ by one level from the generic
    /// formula Rust uses on every platform.
    #[test]
    fn bgr_to_grey_is_within_one_level_of_python() {
        let (golden, images) = golden();
        for case in golden["bgr_to_grey"].as_array().unwrap() {
            let got = bgr_to_grey(image(&images, case));
            let want = frame_from_json(&case["out"]);
            assert_eq!(
                (got.width(), got.height(), got.format()),
                (want.width(), want.height(), want.format())
            );
            let differing = got
                .data()
                .iter()
                .zip(want.data())
                .filter(|(a, b)| a != b)
                .inspect(|(a, b)| assert!(a.abs_diff(**b) <= 1, "{case}: {a} vs {b}"))
                .count();
            assert!(
                differing * 50 <= got.data().len(),
                "{differing} pixels differ"
            );
        }
    }

    #[test]
    fn bgr_to_grey_uses_the_generic_opencv_formula() {
        let frame = Frame::new(
            4,
            1,
            PixelFormat::Bgr,
            vec![15, 220, 253, 154, 2, 133, 255, 255, 255, 7, 7, 7],
        )
        .unwrap();
        assert_eq!(bgr_to_grey(frame).data(), &[206, 59, 255, 7]);
    }

    #[test]
    fn identities_return_the_same_buffer() {
        let frame = Frame::filled(3, 2, PixelFormat::Bgr, 9).unwrap();
        let ptr = frame.data().as_ptr();
        let frame = rotate_frame(frame, 360).unwrap();
        let frame = flip_frame(frame, false, false);
        let frame = adjust_image(frame, 0.0, 1.0);
        let frame = transform_frame(frame, &FrameTransform::default()).unwrap();
        let grey = Frame::filled(3, 2, PixelFormat::Grey, 9).unwrap();
        let grey_ptr = grey.data().as_ptr();
        assert_eq!(frame.data().as_ptr(), ptr);
        assert_eq!(bgr_to_grey(grey).data().as_ptr(), grey_ptr);
    }

    #[test]
    fn empty_and_single_row_frames_do_not_panic() {
        for (w, h) in [(0, 0), (0, 5), (5, 0), (1, 1), (7, 1), (1, 7)] {
            for format in [PixelFormat::Grey, PixelFormat::Bgr] {
                let frame = Frame::filled(w, h, format, 3).unwrap();
                for degrees in [90, 180, 270] {
                    let out = rotate_frame(frame.clone(), degrees).unwrap();
                    assert_eq!(out.data().len(), frame.data().len());
                }
                let _ = flip_frame(frame.clone(), true, true);
                let _ = adjust_image(frame.clone(), f64::NAN, f64::INFINITY);
                let _ = bgr_to_grey(frame);
            }
        }
        let square = Frame::filled(2, 2, PixelFormat::Grey, 0).unwrap();
        assert!(rotate_frame(square.clone(), -270).is_ok());
        assert_eq!(
            rotate_frame(square, i32::MIN),
            Err(FrameError::UnsupportedRotation(i32::MIN))
        );
    }

    #[test]
    fn non_finite_adjustments_saturate_like_opencv() {
        let frame = Frame::new(3, 1, PixelFormat::Grey, vec![0, 100, 255]).unwrap();
        assert_eq!(
            adjust_image(frame.clone(), f64::NAN, 1.0).data(),
            &[0, 0, 0]
        );
        assert_eq!(
            adjust_image(frame.clone(), f64::INFINITY, 1.0).data(),
            &[255, 255, 255]
        );
        assert_eq!(adjust_image(frame, 0.0, -1e9).data(), &[0, 255, 255]);
    }

    #[test]
    fn frame_new_rejects_a_wrong_length() {
        assert_eq!(
            Frame::new(2, 2, PixelFormat::Bgr, vec![0; 11]),
            Err(FrameError::WrongLength {
                expected: 12,
                actual: 11
            })
        );
    }
}
