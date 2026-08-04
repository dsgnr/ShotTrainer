//! `tracking` imports no other workspace crate. `testkit` is allowed only as a
//! dev-dependency.

#[test]
fn tracking_depends_on_no_workspace_crate() {
    let manifest = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/Cargo.toml"))
        .expect("read Cargo.toml");
    let mut section = String::new();
    for line in manifest.lines().map(str::trim) {
        if line.starts_with('[') {
            section = line.to_owned();
            continue;
        }
        let runtime = section == "[dependencies]"
            || section == "[build-dependencies]"
            || (section.starts_with("[target.") && section.ends_with(".dependencies]"));
        if runtime {
            assert!(
                !line.contains("path")
                    && !line.starts_with("shottrainer-")
                    && !line.starts_with("testkit"),
                "workspace dependency in {section}: {line}"
            );
        }
    }
}
