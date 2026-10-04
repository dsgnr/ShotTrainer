//! Conversions between [`Frame`] and OpenCV matrices.

use crate::frame::{Frame, PixelFormat};
use opencv::boxed_ref::BoxedRef;
use opencv::core::{CV_8UC1, CV_8UC3, Mat, Vec3b};
use opencv::prelude::*;

/// Borrows the frame's bytes as a matrix without copying.
pub fn frame_as_mat(frame: &Frame) -> opencv::Result<BoxedRef<'_, Mat>> {
    let rows = i32::try_from(frame.height()).map_err(|_| too_large())?;
    let cols = i32::try_from(frame.width()).map_err(|_| too_large())?;
    match frame.format() {
        PixelFormat::Grey => Mat::new_rows_cols_with_data::<u8>(rows, cols, frame.data()),
        PixelFormat::Bgr => Mat::new_rows_cols_with_bytes::<Vec3b>(rows, cols, frame.data()),
    }
}

/// Copies an 8-bit one or three channel matrix into a frame.
pub fn mat_to_frame(mat: &Mat) -> opencv::Result<Frame> {
    let format = match mat.typ() {
        CV_8UC1 => PixelFormat::Grey,
        CV_8UC3 => PixelFormat::Bgr,
        other => {
            return Err(opencv::Error::new(
                opencv::core::StsUnsupportedFormat,
                format!("unsupported frame type {other}"),
            ));
        }
    };
    let continuous;
    let source = if mat.is_continuous() {
        mat
    } else {
        continuous = mat.try_clone()?;
        &continuous
    };
    let width = u32::try_from(source.cols()).unwrap_or(0);
    let height = u32::try_from(source.rows()).unwrap_or(0);
    Frame::new(width, height, format, source.data_bytes()?.to_vec())
        .map_err(|e| opencv::Error::new(opencv::core::StsBadSize, e.to_string()))
}

fn too_large() -> opencv::Error {
    opencv::Error::new(
        opencv::core::StsOutOfRange,
        "frame dimensions exceed i32".to_owned(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frames_round_trip_through_mat() {
        for format in [PixelFormat::Grey, PixelFormat::Bgr] {
            let len = 5 * 3 * format.channels();
            let data: Vec<u8> = (0..len).map(|i| (i * 7 % 256) as u8).collect();
            let frame = Frame::new(5, 3, format, data).unwrap();
            let mat = frame_as_mat(&frame).unwrap().try_clone().unwrap();
            assert_eq!(mat_to_frame(&mat).unwrap(), frame);
        }
    }
}
