//! The controller may use every workspace crate but no interface framework and
//! no JSON library. Interface code serialises the events itself.

const FORBIDDEN: [&str; 6] = ["tauri", "wry", "tao", "serde", "serde_json", "testkit"];

#[test]
fn controller_runtime_dependencies_are_allowed() {
    let manifest = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/Cargo.toml"))
        .expect("read Cargo.toml");
    let mut section = String::new();
    let mut seen = 0;
    for line in manifest.lines().map(str::trim) {
        if line.starts_with('[') {
            section = line.to_owned();
            continue;
        }
        let runtime = section == "[dependencies]"
            || section == "[build-dependencies]"
            || section.starts_with("[dependencies.")
            || (section.starts_with("[target.") && section.contains("dependencies"));
        if runtime && !line.is_empty() && !line.starts_with('#') {
            seen += 1;
            let name = line.split(['=', '.', ' ']).next().unwrap_or_default();
            assert!(
                !FORBIDDEN.contains(&name),
                "forbidden runtime dependency in {section}: {line}"
            );
        }
    }
    assert!(
        seen >= 5,
        "expected the workspace crates and log, saw {seen} lines"
    );
}
