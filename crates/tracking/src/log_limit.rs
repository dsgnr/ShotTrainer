//! Limits how often one repeated warning is logged. A detector that fails on
//! every frame would otherwise log thirty warnings a second.

/// The first occurrence of a message is logged. Identical repeats are counted
/// and every `every`th is logged with the count. A different message, or a
/// [`reset`](Self::reset) after a success, starts again.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RepeatLimiter {
    every: u64,
    last: Option<String>,
    repeats: u64,
}

impl RepeatLimiter {
    /// `every` below 1 is treated as 1, which logs every message.
    pub fn new(every: u64) -> Self {
        RepeatLimiter {
            every: every.max(1),
            last: None,
            repeats: 0,
        }
    }

    /// The text to log for `message`, or `None` to stay quiet.
    pub fn check(&mut self, message: &str) -> Option<String> {
        if self.last.as_deref() == Some(message) {
            self.repeats += 1;
            return self
                .repeats
                .is_multiple_of(self.every)
                .then(|| format!("{message} (repeated {} times)", self.repeats));
        }
        self.last = Some(message.to_owned());
        self.repeats = 0;
        Some(message.to_owned())
    }

    pub fn reset(&mut self) {
        self.last = None;
        self.repeats = 0;
    }

    /// Repeats of the current message since it was first logged.
    pub fn repeats(&self) -> u64 {
        self.repeats
    }
}

/// About ten seconds of frames at 30 fps.
impl Default for RepeatLimiter {
    fn default() -> Self {
        RepeatLimiter::new(300)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_first_message_is_logged_and_repeats_are_counted() {
        let mut limiter = RepeatLimiter::new(3);
        let logged: Vec<Option<String>> = (0..7).map(|_| limiter.check("boom")).collect();
        assert_eq!(
            logged,
            [
                Some("boom".to_owned()),
                None,
                None,
                Some("boom (repeated 3 times)".to_owned()),
                None,
                None,
                Some("boom (repeated 6 times)".to_owned()),
            ]
        );
        assert_eq!(limiter.repeats(), 6);
    }

    #[test]
    fn a_different_message_is_logged_at_once() {
        let mut limiter = RepeatLimiter::new(100);
        assert!(limiter.check("a").is_some());
        assert!(limiter.check("a").is_none());
        assert_eq!(limiter.check("b").as_deref(), Some("b"));
        assert_eq!(limiter.repeats(), 0);
    }

    #[test]
    fn reset_logs_the_next_failure_again() {
        let mut limiter = RepeatLimiter::new(100);
        limiter.check("a");
        limiter.check("a");
        limiter.reset();
        assert_eq!(limiter.check("a").as_deref(), Some("a"));
    }

    #[test]
    fn zero_logs_every_message() {
        let mut limiter = RepeatLimiter::new(0);
        assert!(limiter.check("a").is_some());
        assert_eq!(limiter.check("a").as_deref(), Some("a (repeated 1 times)"));
    }

    #[test]
    fn the_default_logs_every_three_hundredth_repeat() {
        let mut limiter = RepeatLimiter::default();
        let logged = (0..=600).filter_map(|_| limiter.check("x")).count();
        assert_eq!(logged, 3);
    }
}
