//! A rolling buffer of recent tracking samples.

use crate::bisect::bisect_left;
use shottrainer_tracking::models::TrackingSample;
use std::collections::VecDeque;

const DEFAULT_CAPACITY: usize = 6000;

/// The most recent samples, oldest first. A capacity of zero keeps nothing,
/// as with a Python `deque(maxlen=0)`.
#[derive(Debug, Clone)]
pub struct TraceBuffer {
    samples: VecDeque<TrackingSample>,
    capacity: usize,
}

impl TraceBuffer {
    pub fn new(capacity: usize) -> Self {
        TraceBuffer {
            samples: VecDeque::with_capacity(capacity.min(DEFAULT_CAPACITY)),
            capacity,
        }
    }

    pub fn len(&self) -> usize {
        self.samples.len()
    }

    pub fn is_empty(&self) -> bool {
        self.samples.is_empty()
    }

    pub fn capacity(&self) -> usize {
        self.capacity
    }

    pub fn append(&mut self, sample: TrackingSample) {
        if self.capacity == 0 {
            return;
        }
        if self.samples.len() == self.capacity {
            self.samples.pop_front();
        }
        self.samples.push_back(sample);
    }

    pub fn extend<I: IntoIterator<Item = TrackingSample>>(&mut self, samples: I) {
        for sample in samples {
            self.append(sample);
        }
    }

    pub fn clear(&mut self) {
        self.samples.clear();
    }

    pub fn snapshot(&self) -> Vec<TrackingSample> {
        self.samples.iter().cloned().collect()
    }

    /// Returns the sample closest to `timestamp`. On an exact tie the later
    /// sample wins, matching the candidate order of the Python reference.
    pub fn nearest(&self, timestamp: f64) -> Option<&TrackingSample> {
        if self.samples.is_empty() {
            return None;
        }
        let i = bisect_left(self.samples.len(), |i| self.samples[i].timestamp, timestamp);
        let distance = |idx: usize| (self.samples[idx].timestamp - timestamp).abs();
        let mut best = if i < self.samples.len() { i } else { i - 1 };
        // Python's `min` keeps the first candidate unless a later one is strictly smaller.
        if i < self.samples.len() && i > 0 && distance(i - 1) < distance(i) {
            best = i - 1;
        }
        self.samples.get(best)
    }

    /// Returns the samples with timestamps in `[start_ts, end_ts]` in insertion order.
    pub fn window(&self, start_ts: f64, end_ts: f64) -> Vec<TrackingSample> {
        self.samples
            .iter()
            .filter(|s| start_ts <= s.timestamp && s.timestamp <= end_ts)
            .cloned()
            .collect()
    }
}

impl Default for TraceBuffer {
    fn default() -> Self {
        TraceBuffer::new(DEFAULT_CAPACITY)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::trace_fixture::*;

    #[test]
    fn buffer_matches_python() {
        let (mut nearest_checked, mut window_checked, mut ties) = (0, 0, 0);
        for case in cases() {
            let name = case["name"].as_str().unwrap().to_string();
            let mut buf = TraceBuffer::new(case["capacity"].as_u64().unwrap() as usize);
            buf.extend(samples(&case["appended"]));
            assert_refs(&buf.snapshot(), &case["snapshot"], &name);
            assert_eq!(buf.len(), case["snapshot"].as_array().unwrap().len());
            for q in case["nearest"].as_array().unwrap() {
                let got = buf.nearest(number(&q["query"]));
                assert_ref(got, &q["result"], &format!("{name} {q}"));
                nearest_checked += 1;
            }
            for w in case["windows"].as_array().unwrap() {
                let got = buf.window(number(&w["start"]), number(&w["end"]));
                assert_refs(&got, &w["result"], &format!("{name} {w}"));
                window_checked += 1;
            }
            if name == "ten_even" {
                // 10.25 sits exactly between the samples at 10.0 and 10.5.
                assert_eq!(buf.nearest(10.25).unwrap().timestamp, 10.5);
                ties += 1;
            }
        }
        assert!(nearest_checked > 100 && window_checked > 100 && ties == 1);
    }

    #[test]
    fn overflow_keeps_the_newest_samples() {
        let mut buf = TraceBuffer::new(5);
        for i in 0..12 {
            let mut s = TrackingSample::new(i as f64, 0.0, 0.0);
            s.frame_id = i;
            buf.append(s);
        }
        let ids: Vec<_> = buf.snapshot().iter().map(|s| s.frame_id).collect();
        assert_eq!(ids, vec![7, 8, 9, 10, 11]);
        assert_eq!(buf.capacity(), 5);
    }

    #[test]
    fn zero_capacity_keeps_nothing_as_python_deque_maxlen_zero() {
        let mut buf = TraceBuffer::new(0);
        buf.append(TrackingSample::new(1.0, 0.0, 0.0));
        assert!(buf.is_empty());
        assert!(buf.nearest(1.0).is_none());
        assert!(buf.window(0.0, 2.0).is_empty());
    }

    #[test]
    fn equal_timestamps_keep_insertion_order_and_clear_empties() {
        let mut buf = TraceBuffer::default();
        assert_eq!(buf.capacity(), 6000);
        for id in 0..3 {
            let mut s = TrackingSample::new(1.0, 0.0, 0.0);
            s.frame_id = id;
            buf.append(s);
        }
        let ids: Vec<_> = buf.window(1.0, 1.0).iter().map(|s| s.frame_id).collect();
        assert_eq!(ids, vec![0, 1, 2]);
        assert_eq!(buf.nearest(1.0).unwrap().frame_id, 0);
        buf.clear();
        assert!(buf.is_empty());
    }

    #[test]
    fn non_finite_timestamps_never_panic() {
        let mut buf = TraceBuffer::new(8);
        buf.extend(
            [f64::NAN, 1.0, f64::INFINITY, f64::NEG_INFINITY]
                .map(|t| TrackingSample::new(t, 0.0, 0.0)),
        );
        for q in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY, 1.0] {
            let _ = buf.nearest(q);
            let _ = buf.window(q, q);
        }
    }
}
