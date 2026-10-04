//! The controller may use every workspace crate but no interface framework and
//! no JSON library. Interface code serialises the events itself.

const FORBIDDEN: [&str; 7] = [
    "tauri",
    "wry",
    "tao",
    "serde",
    "serde_json",
    "testkit",
    "shottrainer-testkit",
];
const FORBIDDEN_PREFIXES: [&str; 4] = ["tauri-", "tauri_", "serde-", "serde_"];

fn is_forbidden(name: &str) -> bool {
    FORBIDDEN.contains(&name) || FORBIDDEN_PREFIXES.iter().any(|p| name.starts_with(p))
}

/// How a manifest section relates to runtime dependencies.
#[derive(Debug, PartialEq)]
enum Section {
    Other,
    /// `[dependencies]`, `[build-dependencies]` or their target forms, with
    /// one `name = spec` per line.
    Table,
    /// `[dependencies.name]` or its target form, with the spec as keys.
    Named(String),
}

fn classify(header: &str) -> Section {
    let inner = header.trim_matches(|c| c == '[' || c == ']').trim();
    for kind in ["dependencies", "build-dependencies"] {
        if inner == kind {
            return Section::Table;
        }
        if let Some(name) = inner.strip_prefix(&format!("{kind}.")) {
            return Section::Named(name.trim_matches(['"', '\'']).to_owned());
        }
        if inner.starts_with("target.") {
            let marker = format!(".{kind}");
            if let Some(at) = inner.rfind(&marker) {
                let rest = &inner[at + marker.len()..];
                if rest.is_empty() {
                    return Section::Table;
                }
                if let Some(name) = rest.strip_prefix('.') {
                    return Section::Named(name.trim_matches(['"', '\'']).to_owned());
                }
            }
        }
    }
    Section::Other
}

/// The `package = "name"` rename in a dependency spec, if it has one.
fn renamed_package(spec: &str) -> Option<&str> {
    let after = spec.split("package").nth(1)?.trim_start();
    let value = after.strip_prefix('=')?.trim_start();
    let quote = value.chars().next().filter(|c| matches!(c, '"' | '\''))?;
    value[1..].split(quote).next()
}

/// Every forbidden runtime or build dependency, as `section: line`.
/// Development dependencies are not checked.
fn forbidden_runtime_dependencies(manifest: &str) -> (Vec<String>, usize) {
    let mut section = Section::Other;
    let mut header = String::new();
    let mut found = Vec::new();
    let mut seen = 0;
    for line in manifest.lines().map(str::trim) {
        if line.starts_with('[') {
            section = classify(line);
            header = line.to_owned();
            if let Section::Named(name) = &section {
                seen += 1;
                if is_forbidden(name) {
                    found.push(format!("{header}: {line}"));
                }
            }
            continue;
        }
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let key = line.split('=').next().unwrap_or_default().trim();
        match &section {
            Section::Other => {}
            Section::Table => {
                seen += 1;
                let name = key.split('.').next().unwrap_or_default().trim_matches('"');
                if is_forbidden(name) || renamed_package(line).is_some_and(is_forbidden) {
                    found.push(format!("{header}: {line}"));
                }
            }
            Section::Named(_) => {
                if key == "package" && renamed_package(line).is_some_and(is_forbidden) {
                    found.push(format!("{header}: {line}"));
                }
            }
        }
    }
    (found, seen)
}

#[test]
fn controller_runtime_dependencies_are_allowed() {
    let manifest = std::fs::read_to_string(concat!(env!("CARGO_MANIFEST_DIR"), "/Cargo.toml"))
        .expect("read Cargo.toml");
    let (found, seen) = forbidden_runtime_dependencies(&manifest);
    assert!(found.is_empty(), "forbidden dependencies: {found:?}");
    assert!(
        seen >= 5,
        "expected the workspace crates and log, saw {seen} dependencies"
    );
}

#[test]
fn the_parser_rejects_every_form_of_forbidden_dependency() {
    let bad = [
        "[dependencies]\nserde = \"1\"\n",
        "[dependencies]\nserde_json.workspace = true\n",
        "[dependencies]\nserde_derive = \"1\"\n",
        "[dependencies]\ntauri-plugin-fs = \"2\"\n",
        "[dependencies]\ntauri-build = \"2\"\n",
        "[dependencies]\nj = { version = \"1\", package = \"serde_json\" }\n",
        "[dependencies.serde]\nversion = \"1\"\n",
        "[dependencies.j]\nversion = \"1\"\npackage = \"serde_json\"\n",
        "[build-dependencies]\ntauri-build = \"2\"\n",
        "[target.'cfg(unix)'.dependencies]\nserde = \"1\"\n",
        "[target.x86_64-pc-windows-msvc.dependencies.serde]\nversion = \"1\"\n",
        "[target.'cfg(windows)'.build-dependencies]\nwry = \"1\"\n",
    ];
    for manifest in bad {
        let (found, _) = forbidden_runtime_dependencies(manifest);
        assert_eq!(found.len(), 1, "not caught: {manifest:?}");
    }
}

#[test]
fn the_parser_ignores_development_and_allowed_dependencies() {
    let fine = "[dependencies]\nlog = \"0.4\"\nthiserror = \"2\"\n\
        shottrainer-core = { path = \"../core\" }\n\
        [dependencies.shottrainer-audio]\npath = \"../audio\"\n\
        [dev-dependencies]\nserde_json = \"1\"\n\
        [target.'cfg(unix)'.dev-dependencies]\nserde = \"1\"\n\
        [dev-dependencies.shottrainer-testkit]\npath = \"../testkit\"\n\
        [features]\nopencv = [\"serde\"]\n";
    let (found, seen) = forbidden_runtime_dependencies(fine);
    assert!(found.is_empty(), "{found:?}");
    assert_eq!(seen, 4);
}
