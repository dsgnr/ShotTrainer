//! Detects the OpenCV major version when the `opencv` feature is on.
//!
//! OpenCV 5 moved the contour geometry functions from `imgproc` into a new
//! `geometry` module, and the `opencv` crate mirrors that split in its Rust
//! paths. The crate's own version cfg is not visible to dependants, so this
//! script reads `CV_VERSION_MAJOR` from the same headers and sets `opencv_5`.
use std::env;
use std::path::{Path, PathBuf};
use std::process::Command;

fn main() {
    println!("cargo::rustc-check-cfg=cfg(opencv_5)");
    println!("cargo::rerun-if-env-changed=SHOTTRAINER_OPENCV_MAJOR");
    println!("cargo::rerun-if-env-changed=OPENCV_INCLUDE_PATHS");
    println!("cargo::rerun-if-env-changed=PKG_CONFIG_PATH");
    if env::var_os("CARGO_FEATURE_OPENCV").is_none() {
        return;
    }
    let major = match env::var("SHOTTRAINER_OPENCV_MAJOR") {
        Ok(text) => text.trim().parse::<u32>().ok(),
        Err(_) => include_dirs().iter().find_map(|dir| major_from_header(dir)),
    };
    match major {
        Some(5) => println!("cargo::rustc-cfg=opencv_5"),
        Some(_) => {}
        None => println!(
            "cargo::warning=OpenCV version header not found, assuming OpenCV 4. \
             Set SHOTTRAINER_OPENCV_MAJOR to override."
        ),
    }
}

fn include_dirs() -> Vec<PathBuf> {
    let mut dirs = Vec::new();
    if let Ok(paths) = env::var("OPENCV_INCLUDE_PATHS") {
        dirs.extend(
            paths
                .split(',')
                .map(|p| p.trim().trim_start_matches('+'))
                .filter(|p| !p.is_empty())
                .map(PathBuf::from),
        );
    }
    for package in ["opencv5", "opencv4"] {
        let Ok(output) = Command::new("pkg-config")
            .args(["--cflags-only-I", package])
            .output()
        else {
            continue;
        };
        if !output.status.success() {
            continue;
        }
        let text = String::from_utf8_lossy(&output.stdout);
        dirs.extend(
            text.split_whitespace()
                .filter_map(|flag| flag.strip_prefix("-I"))
                .map(PathBuf::from),
        );
    }
    dirs
}

fn major_from_header(dir: &Path) -> Option<u32> {
    let text = std::fs::read_to_string(dir.join("opencv2/core/version.hpp")).ok()?;
    text.lines().find_map(|line| {
        let rest = line.trim().strip_prefix("#define")?.trim_start();
        let value = rest.strip_prefix("CV_VERSION_MAJOR")?;
        value.trim().parse().ok()
    })
}
