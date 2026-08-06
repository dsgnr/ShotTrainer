//! OpenCV 5 moved the contour geometry functions out of `imgproc`.

#[cfg(opencv_5)]
pub use opencv::geometry::{
    arc_length, bounding_rect, contour_area, fit_ellipse, min_enclosing_circle, moments,
};
#[cfg(not(opencv_5))]
pub use opencv::imgproc::{
    arc_length, bounding_rect, contour_area, fit_ellipse, min_enclosing_circle, moments,
};
