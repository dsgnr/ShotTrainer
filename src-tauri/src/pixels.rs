//! Camera pixels for the webview canvas. Each packet is a fixed
//! little-endian header followed by RGBA bytes in rows from the top:
//!
//! | Offset | Type | Field |
//! | --- | --- | --- |
//! | 0 | `u32` | width |
//! | 4 | `u32` | height |
//! | 8 | `i64` | frame id, matching the `frame` event |
//! | 16 | `f64` | capture time in seconds on the controller clock |
//! | 24 | `f64` | send time in milliseconds since the Unix epoch |

use std::sync::{Mutex, MutexGuard, PoisonError};
use std::time::{SystemTime, UNIX_EPOCH};

use shottrainer_tracking::frame::{Frame, PixelFormat};

pub const HEADER_LEN: usize = 32;

/// Packets sent but not yet drawn. Further pixels are dropped until the
/// webview reports one drawn, so a slow webview cannot queue frames without
/// limit.
pub const MAX_FRAMES_IN_FLIGHT: usize = 2;

/// The header and RGBA pixels of one frame. Grey pixels are repeated into
/// red, green and blue, and BGR is reordered. Alpha is always opaque.
pub fn rgba_packet(frame: &Frame, frame_id: i64, timestamp: f64, sent_at_ms: f64) -> Vec<u8> {
    let data = frame.data();
    let pixels = (frame.width() as usize) * (frame.height() as usize);
    let mut packet = Vec::with_capacity(HEADER_LEN + pixels * 4);
    packet.extend_from_slice(&frame.width().to_le_bytes());
    packet.extend_from_slice(&frame.height().to_le_bytes());
    packet.extend_from_slice(&frame_id.to_le_bytes());
    packet.extend_from_slice(&timestamp.to_le_bytes());
    packet.extend_from_slice(&sent_at_ms.to_le_bytes());
    match frame.format() {
        PixelFormat::Grey => {
            for &g in data {
                packet.extend_from_slice(&[g, g, g, 255]);
            }
        }
        PixelFormat::Bgr => {
            for [b, g, r] in data.as_chunks::<3>().0 {
                packet.extend_from_slice(&[*r, *g, *b, 255]);
            }
        }
    }
    packet
}

/// Milliseconds since the Unix epoch, comparable with `Date.now()` in the
/// webview. Zero if the system clock is before 1970.
pub fn unix_millis() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0.0, |elapsed| elapsed.as_secs_f64() * 1000.0)
}

/// Counts packets the webview has not drawn yet.
#[derive(Debug, Default)]
pub struct FrameGate {
    in_flight: Mutex<usize>,
}

impl FrameGate {
    /// Reserves a slot, or returns false when [`MAX_FRAMES_IN_FLIGHT`]
    /// packets are already waiting.
    pub fn try_acquire(&self) -> bool {
        let mut in_flight = self.in_flight();
        if *in_flight < MAX_FRAMES_IN_FLIGHT {
            *in_flight += 1;
            true
        } else {
            false
        }
    }

    /// One packet was drawn, or could not be sent. Extra calls are ignored.
    pub fn release(&self) {
        let mut in_flight = self.in_flight();
        *in_flight = in_flight.saturating_sub(1);
    }

    /// Forgets every packet in flight, for a webview that subscribed again
    /// after a reload and will never draw the old ones.
    pub fn reset(&self) {
        *self.in_flight() = 0;
    }

    fn in_flight(&self) -> MutexGuard<'_, usize> {
        self.in_flight
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn header(packet: &[u8]) -> (u32, u32, i64, f64, f64) {
        let u32_at = |at: usize| u32::from_le_bytes(packet[at..at + 4].try_into().unwrap());
        let i64_at = |at: usize| i64::from_le_bytes(packet[at..at + 8].try_into().unwrap());
        let f64_at = |at: usize| f64::from_le_bytes(packet[at..at + 8].try_into().unwrap());
        (u32_at(0), u32_at(4), i64_at(8), f64_at(16), f64_at(24))
    }

    #[test]
    fn header_carries_size_id_and_both_times() {
        let frame = Frame::filled(3, 2, PixelFormat::Grey, 0).unwrap();
        let packet = rgba_packet(&frame, 41, 12.5, 1_700_000_000_123.0);
        assert_eq!(header(&packet), (3, 2, 41, 12.5, 1_700_000_000_123.0));
        assert_eq!(packet.len(), HEADER_LEN + 3 * 2 * 4);
    }

    #[test]
    fn grey_pixels_become_opaque_grey_in_row_order() {
        let frame = Frame::new(2, 2, PixelFormat::Grey, vec![10, 20, 30, 40]).unwrap();
        let packet = rgba_packet(&frame, 1, 0.0, 0.0);
        assert_eq!(
            &packet[HEADER_LEN..],
            &[
                10, 10, 10, 255, 20, 20, 20, 255, 30, 30, 30, 255, 40, 40, 40, 255
            ]
        );
    }

    #[test]
    fn bgr_pixels_are_reordered_to_rgba() {
        let frame = Frame::new(2, 1, PixelFormat::Bgr, vec![1, 2, 3, 4, 5, 6]).unwrap();
        let packet = rgba_packet(&frame, 1, 0.0, 0.0);
        assert_eq!(&packet[HEADER_LEN..], &[3, 2, 1, 255, 6, 5, 4, 255]);
    }

    #[test]
    fn an_empty_frame_is_a_bare_header() {
        let frame = Frame::new(0, 0, PixelFormat::Grey, Vec::new()).unwrap();
        let packet = rgba_packet(&frame, 7, 1.0, 2.0);
        assert_eq!(packet.len(), HEADER_LEN);
        assert_eq!(header(&packet), (0, 0, 7, 1.0, 2.0));
    }

    #[test]
    fn the_gate_admits_two_frames_until_one_is_drawn() {
        let gate = FrameGate::default();
        assert!(gate.try_acquire());
        assert!(gate.try_acquire());
        assert!(!gate.try_acquire());
        gate.release();
        assert!(gate.try_acquire());
        assert!(!gate.try_acquire());
    }

    #[test]
    fn extra_releases_do_not_open_the_gate_further() {
        let gate = FrameGate::default();
        gate.release();
        gate.release();
        assert!(gate.try_acquire());
        assert!(gate.try_acquire());
        assert!(!gate.try_acquire());
    }

    #[test]
    fn reset_reopens_a_full_gate() {
        let gate = FrameGate::default();
        assert!(gate.try_acquire());
        assert!(gate.try_acquire());
        gate.reset();
        assert!(gate.try_acquire());
        assert!(gate.try_acquire());
        assert!(!gate.try_acquire());
    }

    #[test]
    fn unix_millis_is_after_2020() {
        assert!(unix_millis() > 1_577_836_800_000.0);
    }
}
