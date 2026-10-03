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
    let entry = [
        (0.0, -72.0, 70.0),
        (0.1, -72.0, 70.0),
        (0.2, -72.0, 70.0),
        (0.3, -68.0, 68.0),
        (0.4, -49.0, 62.0),
        (0.5, -40.0, 54.0),
        (0.6, -31.0, 46.0),
        (0.7, -26.721, 41.031),
        (0.8, -26.91, 39.609),
        (0.9, -21.681, 41.778),
        (1.0, -10.692, 43.317),
        (1.1, -9.225, 47.772),
        (1.2, -6.03, 51.138),
        (1.3, -3.609, 55.161),
        (1.4, -2.457, 59.175),
        (1.5, -1.017, 62.775),
        (1.6, 0.423, 60.975),
        (1.7, 1.152, 56.034),
        (1.8, 5.157, 51.813),
        (1.9, 4.428, 46.737),
        (2.0, 7.308, 39.789),
        (2.1, 2.097, 36.891),
        (2.2, 0.054, 32.04),
        (2.3, 0.549, 28.71),
        (2.4, -1.872, 25.371),
        (2.5, -1.53, 19.98),
        (2.6, 1.008, 17.937),
        (2.7, -0.639, 15.975),
        (2.8, -0.747, 14.463),
        (2.9, -0.666, 12.591),
        (3.0, -0.909, 11.547),
        (3.1, 1.719, 9.729),
        (3.2, 1.188, 7.353),
        (3.3, 0.828, 5.733),
        (3.4, 5.184, 4.257),
        (3.5, -1.125, 1.854),
        (3.6, 1.44, -0.54),
        (3.7, -0.09, 0.684),
        (3.8, 0.0, 0.0),
        (4.0, 0.0, 0.0),
        (4.1, -0.27, -0.54),
        (4.2, 0.189, -1.413),
        (4.3, 0.999, -1.503),
        (4.4, 0.099, -1.836),
        (4.5, -0.855, -2.124),
        (4.6, 0.108, -3.186),
        (4.7, -1.971, -3.951),
        (4.8, -1.161, -4.653),
        (4.9, 0.423, -4.527),
        (5.0, 0.504, -5.166),
        (5.1, -1.179, -4.005),
        (5.2, -0.261, -5.049),
        (5.3, 1.602, -6.507),
        (5.4, 3.672, -6.426),
        (5.5, -0.387, -6.057),
        (5.6, -0.945, -6.84),
        (5.7, 0.144, -5.031),
        (5.8, 1.368, -6.129),
        (5.9, -0.153, -5.589),
        (6.0, 0.288, -6.624),
        (6.1, 3.807, -6.48),
        (6.2, -0.027, -6.093),
        (6.3, -0.585, -6.048),
        (6.4, -0.306, -6.039),
        (6.5, -2.403, -5.598),
        (6.6, -0.99, -4.941),
        (6.7, -1.944, -4.842),
        (6.8, 1.224, -4.212),
        (6.9, -1.701, -3.366),
        (7.0, -0.684, -3.6),
        (7.1, -0.234, -4.401),
        (7.2, -0.612, -2.286),
        (7.3, -0.369, -0.909),
        (7.4, -0.954, -1.17),
        (7.5, -0.774, -1.521),
        (7.6, -2.565, -2.511),
        (7.7, 1.935, -2.871),
        (7.8, 3.267, -4.158),
        (7.9, -0.054, -2.133),
        (8.0, -0.144, -0.72),
        (8.1, -0.09, 0.135),
        (8.2, -0.648, -0.27),
    ];
    let time = if phase < 7.0 {
        ((phase - 1.5) / 5.5 * 4.0).max(0.0)
    } else {
        (4.0 + (phase - 7.0) / 3.0 * 4.2).min(8.2)
    };
    let index = entry
        .iter()
        .position(|point| point.0 >= time)
        .unwrap_or(entry.len() - 1)
        .saturating_sub(1)
        .min(entry.len() - 2);
    let from = entry[index];
    let to = entry[index + 1];
    let p = (time - from.0) / (to.0 - from.0);
    let previous = entry[index.saturating_sub(1)];
    let next = entry[(index + 2).min(entry.len() - 1)];
    let curve = |a: f64, b: f64, before: f64, after: f64| {
        (2.0 * p.powi(3) - 3.0 * p.powi(2) + 1.0) * a
            + (p.powi(3) - 2.0 * p.powi(2) + p) * (b - before) * 0.5
            + (-2.0 * p.powi(3) + 3.0 * p.powi(2)) * b
            + (p.powi(3) - p.powi(2)) * (after - a) * 0.5
    };
    let scale = 0.95 + uniform(seed.wrapping_add(17)) * 0.1;
    let seconds = f64::from(shot) * 10.0 + phase.max(if shot == 0 { 0.0 } else { 1.5 });
    (
        cx + curve(from.1, to.1, previous.1, next.1) * scale
            + tremor(seconds * 0.45, seed.wrapping_add(101)) * 0.25,
        cy + curve(from.2, to.2, previous.2, next.2) * scale
            + tremor(seconds * 0.45, seed.wrapping_add(303)) * 0.25
            + 0.2 * (std::f64::consts::TAU * 0.2 * seconds).sin(),
    )
}

fn follow_through(shot: u32, elapsed: f64) -> (f64, f64) {
    let (x, y) = approach(shot, 10.0);
    let seed = shot.wrapping_mul(31);
    let times = [0.0, 0.025, 0.07, 0.13, 0.21, 0.3, 0.45, 0.6, 0.8, 1.0];
    let radii = [0.0, 15.0, 120.0, 150.0, 85.0, 8.0, 18.0, 5.0, 10.0, 6.0];
    let point = |index: usize| {
        let offset = index as u32 * 7;
        let angle = uniform(seed.wrapping_add(41 + offset)) * std::f64::consts::TAU;
        let distance = radii[index] * 1.12 * (0.8 + uniform(seed.wrapping_add(43 + offset)) * 0.4);
        (angle.cos() * distance, angle.sin() * distance)
    };
    let index = times
        .iter()
        .position(|time| *time >= elapsed)
        .unwrap_or(times.len() - 1)
        .saturating_sub(1)
        .min(times.len() - 2);
    let p = ((elapsed - times[index]) / (times[index + 1] - times[index])).clamp(0.0, 1.0);
    let before = point(index.saturating_sub(1));
    let from = point(index);
    let to = point(index + 1);
    let after = point((index + 2).min(times.len() - 1));
    let interpolate = |a: f64, b: f64, previous: f64, next: f64| {
        let tangent_a = (b - previous) * 0.5;
        let tangent_b = (next - a) * 0.5;
        (2.0 * p.powi(3) - 3.0 * p.powi(2) + 1.0) * a
            + (p.powi(3) - 2.0 * p.powi(2) + p) * tangent_a
            + (-2.0 * p.powi(3) + 3.0 * p.powi(2)) * b
            + (p.powi(3) - p.powi(2)) * tangent_b
    };
    (
        x + interpolate(from.0, to.0, before.0, after.0),
        y + interpolate(from.1, to.1, before.1, after.1),
    )
}

pub fn position(seconds: f64) -> (f64, f64) {
    let shot = (seconds / 10.0).floor() as u32;
    let phase = seconds % 10.0;
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
    fn compact_traces_settle_before_a_short_follow_through() {
        let mut shots = Vec::new();
        for shot in 0..10 {
            let t = f64::from(shot) * 10.0;
            let entry_phase = if shot == 0 { 0.0 } else { 1.5 };
            let entry = position(t + entry_phase);
            let trigger = position(t + 10.0);
            assert!(entry.0.hypot(entry.1) > 85.0);
            assert!(entry.0 < -60.0 && entry.1 > 60.0);
            assert!((entry.0 - trigger.0).hypot(entry.1 - trigger.1) < 110.0);
            assert!(entry.1 > trigger.1 + 25.0);
            for frame in 0..31 {
                let hold = position(t + 9.5 + f64::from(frame) / 60.0);
                assert!((hold.0 - trigger.0).hypot(hold.1 - trigger.1) < 10.0);
            }
            let kick = position(t + 10.025);
            assert!((kick.0 - trigger.0).hypot(kick.1 - trigger.1) > 10.0);
            let replay_entry = position(t + 2.5);
            assert!(replay_entry.0.hypot(replay_entry.1) > 38.0);
            let early = position(t + 3.0);
            assert!((early.0 - trigger.0).hypot(early.1 - trigger.1) > 40.0);
            let late = position(t + 5.0);
            assert!((late.0 - trigger.0).hypot(late.1 - trigger.1) > 8.0);
            let release = (0..=15)
                .map(|frame| position(t + 9.75 + f64::from(frame) / 60.0))
                .map(|point| (point.0 - trigger.0).hypot(point.1 - trigger.1))
                .fold(0.0_f64, f64::max);
            assert!(release > 3.0);
            let entry_x: Vec<_> = (0..61)
                .map(|frame| position(t + 2.0 + f64::from(frame) / 20.0).0)
                .collect();
            let minimum = entry_x.iter().copied().fold(f64::INFINITY, f64::min);
            let maximum = entry_x.iter().copied().fold(f64::NEG_INFINITY, f64::max);
            assert!(maximum - minimum > 5.0);
            let mut maximum_follow: f64 = 0.0;
            for frame in 0..61 {
                let follow = position(t + 10.0 + f64::from(frame) / 60.0);
                maximum_follow =
                    maximum_follow.max((follow.0 - trigger.0).hypot(follow.1 - trigger.1));
            }
            assert!(maximum_follow > 100.0 && maximum_follow < 220.0);
            for boundary in [10.0, 11.0, 11.5] {
                let before = position(t + boundary - 0.00001);
                let after = position(t + boundary + 0.00001);
                assert!((before.0 - after.0).hypot(before.1 - after.1) < 0.05);
            }
            for frame in 151..600 {
                let before = position(t + f64::from(frame - 1) / 60.0);
                let after = position(t + f64::from(frame) / 60.0);
                assert!((before.0 - after.0).hypot(before.1 - after.1) < 12.0);
            }
            shots.push(trigger);
        }
        assert!(shots.windows(2).all(|pair| pair[0] != pair[1]));
    }
}
