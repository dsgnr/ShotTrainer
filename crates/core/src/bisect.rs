//! Binary searches that follow the probing order of Python's `bisect`.
//!
//! Following the same order keeps results identical to the reference on input
//! that is not sorted, such as a NaN timestamp, where the comparisons are all false.

pub(crate) fn bisect_left(len: usize, key: impl Fn(usize) -> f64, x: f64) -> usize {
    let (mut lo, mut hi) = (0, len);
    while lo < hi {
        let mid = lo + (hi - lo) / 2;
        if key(mid) < x {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    lo
}

pub(crate) fn bisect_right(len: usize, key: impl Fn(usize) -> f64, x: f64) -> usize {
    let (mut lo, mut hi) = (0, len);
    while lo < hi {
        let mid = lo + (hi - lo) / 2;
        if x < key(mid) {
            hi = mid;
        } else {
            lo = mid + 1;
        }
    }
    lo
}
