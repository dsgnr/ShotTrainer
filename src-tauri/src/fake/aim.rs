//! Reproducible practice traces with an approach, hold and follow-through.

fn uniform(seed: u32) -> f64 {
    let mut value = seed.wrapping_add(0x9e37_79b9);
    value = (value ^ (value >> 16)).wrapping_mul(0x21f0_aaad);
    value = (value ^ (value >> 15)).wrapping_mul(0x735a_2d97);
    f64::from(value ^ (value >> 15)) / 4_294_967_296.0
}

fn normal(seed: u32) -> f64 {
    (-2.0 * uniform(seed).max(1e-9).ln()).sqrt()
        * (std::f64::consts::TAU * uniform(seed.wrapping_add(1))).cos()
}

fn centre(shot: u32) -> (f64, f64) {
    (
        normal(shot.wrapping_mul(31).wrapping_add(7)) * 1.5,
        normal(shot.wrapping_mul(31).wrapping_add(11)) * 1.5,
    )
}

fn tremor(t: f64, seed: u32) -> f64 {
    let n = (t * 12.0).floor() as u32;
    let p = (t * 12.0).fract();
    let p = p * p * (3.0 - 2.0 * p);
    normal(seed.wrapping_add(n)) * (1.0 - p) + normal(seed.wrapping_add(n + 1)) * p
}

fn smoothstep(value: f64) -> f64 {
    let p = value.clamp(0.0, 1.0);
    p * p * (3.0 - 2.0 * p)
}

fn approach(shot: u32, phase: f64) -> (f64, f64) {
    let (cx, cy) = centre(shot);
    let seed = shot.wrapping_mul(31);
    let entry_y = 110.0 + uniform(seed.wrapping_add(17)) * 10.0;
    let angle = (entry_y - cy).atan2(-cx);
    let distance = cx.hypot(entry_y - cy);
    let start = if shot == 0 { 0.0 } else { 1.5 };
    let phase = phase.max(start);
    let p = ((phase - start) / (4.85 - start)).clamp(0.0, 1.0);
    let progress = 0.35 * p + 0.65 * smoothstep(p);
    let remaining = (1.0 - progress).powf(1.4) * distance;
    let movement = 2.5 + (1.0 - p) * 18.0;
    let seconds = f64::from(shot) * 5.0 + phase;
    let sway = phase * std::f64::consts::TAU * 3.2
        + uniform(seed.wrapping_add(29)) * std::f64::consts::TAU;
    let winding = movement * sway.sin();
    (
        cx + angle.cos() * remaining - angle.sin() * winding + tremor(seconds, 101) * 0.55,
        cy + angle.sin() * remaining
            + angle.cos() * winding
            + 0.25 * sway.cos()
            + tremor(seconds, 303) * 0.55
            + 1.2 * (std::f64::consts::TAU * 0.2 * seconds).sin(),
    )
}

fn follow_through(shot: u32, elapsed: f64) -> (f64, f64) {
    let (x, y) = approach(shot, 5.0);
    let seed = shot.wrapping_mul(31);
    let response = smoothstep(elapsed / 0.015);
    let duration = 0.22 + uniform(seed.wrapping_add(23)) * 0.12;
    let progress = (elapsed / duration).clamp(0.0, 1.0).powf(0.35);
    let angle = std::f64::consts::TAU * progress;
    let direction = normal(seed.wrapping_add(27)).signum();
    let width = 140.0 + uniform(seed.wrapping_add(31)) * 50.0;
    let height = 240.0 + uniform(seed.wrapping_add(33)) * 30.0;
    let skew = (uniform(seed.wrapping_add(35)) - 0.5) * 14.0;
    let ripple = 3.0 * (angle * 3.0).sin();
    (
        x + response
            * (direction * width * (1.0 - angle.cos()) / 1.5 + skew * angle.sin() + ripple),
        y - response
            * (height * angle.sin() + 25.0 * (1.0 - angle.cos()) + 8.0 * (angle * 3.0).sin()),
    )
}

pub fn position(seconds: f64) -> (f64, f64) {
    let shot = (seconds / 5.0).floor() as u32;
    let phase = seconds % 5.0;
    if shot > 0 && phase <= 1.0 {
        return follow_through(shot - 1, phase);
    }
    let target = approach(shot, phase);
    if shot > 0 && phase < 1.5 {
        let previous = follow_through(shot - 1, 1.0);
        let p = smoothstep((phase - 1.0) / 0.5);
        return (
            previous.0 * (1.0 - p) + target.0 * p,
            previous.1 * (1.0 - p) + target.1 * p,
        );
    }
    target
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn straight_approaches_vary_speed_before_fast_recoil() {
        let mut centres = Vec::new();
        for shot in 0..10 {
            let t = f64::from(shot) * 5.0;
            let (cx, cy) = centre(shot);
            let start = position(t + 1.51);
            assert!((start.0 - cx).hypot(start.1 - cy) > 20.0);
            let trigger = approach(shot, 5.0);
            let entry_phase = if shot == 0 { 0.0 } else { 1.5 };
            let entry = position(t + entry_phase);
            let advancing = position(t + entry_phase + 0.2);
            assert!(advancing.1 < entry.1 - 0.5);
            let axis = (entry.0 - trigger.0, entry.1 - trigger.1);
            let length = axis.0.hypot(axis.1);
            for frame in 0..101 {
                let point =
                    position(t + entry_phase + (4.85 - entry_phase) * f64::from(frame) / 100.0);
                let lateral = ((point.0 - trigger.0) * axis.1 - (point.1 - trigger.1) * axis.0)
                    .abs()
                    / length;
                assert!(lateral < 40.0);
            }
            assert!(entry.0.abs() < 28.0 && entry.1 > 100.0);
            assert!(trigger.0.hypot(trigger.1) < 8.0);
            let fast_start = position(t + 3.9);
            let early = position(t + 4.1);
            let late_start = position(t + 4.6);
            let late_end = position(t + 4.8);
            assert!((fast_start.1 - early.1).abs() > 2.0 * (late_start.1 - late_end.1).abs());
            for frame in 0..8 {
                let hold = position(t + 4.75 + f64::from(frame) / 32.0);
                assert!((hold.0 - trigger.0).hypot(hold.1 - trigger.1) < 7.0);
            }
            let kick = position(t + 5.02);
            assert!((kick.0 - trigger.0).hypot(kick.1 - trigger.1) > 70.0);
            let loop_points: Vec<_> = (0..13)
                .map(|i| position(t + 5.015 + f64::from(i) * 0.03))
                .collect();
            assert!(
                loop_points
                    .iter()
                    .any(|p| (p.0 - trigger.0).hypot(p.1 - trigger.1) > 200.0)
            );
            assert!(loop_points.iter().any(|p| (p.0 - trigger.0).abs() > 35.0));
            assert!(loop_points.iter().any(|p| p.1 > trigger.1 + 50.0));
            let follow = position(t + 5.8);
            assert!((follow.0 - trigger.0).hypot(follow.1 - trigger.1) < 8.0);
            for boundary in [5.0, 6.0, 6.5] {
                let before = position(t + boundary - 0.00001);
                let after = position(t + boundary + 0.00001);
                assert!((before.0 - after.0).hypot(before.1 - after.1) < 0.02);
            }
            centres.push((cx, cy));
        }
        assert!(centres.windows(2).all(|pair| pair[0] != pair[1]));
    }
}
