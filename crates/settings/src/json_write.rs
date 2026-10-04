//! Atomic JSON writing that matches `json.dumps(..., indent=2)`.

use std::io::Write;
use std::path::Path;

use serde::Serialize;

use crate::error::SettingsError;

/// Serialises `value` and replaces `path` through a temporary file in the same
/// directory, so a reader never sees a partial file. Creates missing parent
/// directories.
pub(crate) fn write_json_atomic<T: Serialize>(value: &T, path: &Path) -> Result<(), SettingsError> {
    let parent = match path.parent() {
        Some(p) if !p.as_os_str().is_empty() => p,
        _ => Path::new("."),
    };
    std::fs::create_dir_all(parent)?;
    let mut buf = Vec::new();
    let mut ser = serde_json::Serializer::with_formatter(&mut buf, PythonFormatter::default());
    value.serialize(&mut ser)?;
    let mut tmp = tempfile::NamedTempFile::new_in(parent)?;
    tmp.write_all(&buf)?;
    tmp.persist(path).map_err(|e| e.error)?;
    Ok(())
}

/// Pretty printing with two-space indent plus Python's `ensure_ascii` string
/// escaping and `repr` float formatting.
#[derive(Default)]
struct PythonFormatter {
    inner: serde_json::ser::PrettyFormatter<'static>,
}

macro_rules! delegate {
    ($($name:ident($($arg:ident: $ty:ty),*)),* $(,)?) => {
        $(fn $name<W: ?Sized + Write>(&mut self, w: &mut W $(, $arg: $ty)*) -> std::io::Result<()> {
            self.inner.$name(w $(, $arg)*)
        })*
    };
}

impl serde_json::ser::Formatter for PythonFormatter {
    delegate!(
        begin_array(),
        end_array(),
        begin_array_value(first: bool),
        end_array_value(),
        begin_object(),
        end_object(),
        begin_object_key(first: bool),
        end_object_key(),
        begin_object_value(),
        end_object_value(),
    );

    fn write_string_fragment<W: ?Sized + Write>(
        &mut self,
        w: &mut W,
        fragment: &str,
    ) -> std::io::Result<()> {
        let mut units = [0u16; 2];
        for c in fragment.chars() {
            if c <= '~' {
                write!(w, "{c}")?;
            } else {
                for unit in c.encode_utf16(&mut units) {
                    write!(w, "\\u{unit:04x}")?;
                }
            }
        }
        Ok(())
    }

    fn write_f64<W: ?Sized + Write>(&mut self, w: &mut W, value: f64) -> std::io::Result<()> {
        w.write_all(python_float_repr(value).as_bytes())
    }
}

/// `repr(float)` for finite values. serde_json writes a non-finite field as
/// `null` without calling the formatter, so it never reaches this function.
pub(crate) fn python_float_repr(value: f64) -> String {
    // `{:e}` yields the shortest round-trip digits as `d.ddde-N`.
    let sci = format!("{value:e}");
    let (mantissa, exp) = sci.split_once('e').unwrap_or((&sci, "0"));
    let exp: i32 = exp.parse().unwrap_or(0);
    let (sign, mantissa) = match mantissa.strip_prefix('-') {
        Some(rest) => ("-", rest),
        None => ("", mantissa),
    };
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    if (-4..16).contains(&exp) {
        let point = exp + 1;
        let body = if point <= 0 {
            format!("0.{}{digits}", "0".repeat((-point) as usize))
        } else if digits.len() as i32 <= point {
            format!("{digits}{}.0", "0".repeat((point as usize) - digits.len()))
        } else {
            format!(
                "{}.{}",
                &digits[..point as usize],
                &digits[point as usize..]
            )
        };
        format!("{sign}{body}")
    } else {
        let frac = if digits.len() > 1 {
            format!(".{}", &digits[1..])
        } else {
            String::new()
        };
        let exp_sign = if exp < 0 { '-' } else { '+' };
        format!("{sign}{}{frac}e{exp_sign}{:02}", &digits[..1], exp.abs())
    }
}
