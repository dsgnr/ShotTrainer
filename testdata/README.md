# Test fixtures

The Rust tests use the committed golden JSON, synthetic detector frames and
versioned SQLite schema dumps in this directory.

`golden/` and `frames/detector/` provide fixed expected outputs for processing
and detector tests. Do not regenerate these outputs from the code being tested,
because that would lose the independent check.

`legacy/` contains SQL dumps for schema versions 1, 2 and 3. The standard
library helper `scripts/make_legacy_db.py` can reproduce those synthetic dumps
without importing application code or accessing real user data.

Run `cargo test --workspace` to exercise the default fixture tests.
Detector tests additionally require `cargo test -p shottrainer-tracking
--features opencv` on a machine with OpenCV and libclang.
