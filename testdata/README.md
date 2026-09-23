# Compatibility fixtures

The Rust tests use the committed golden JSON, synthetic detector frames and
legacy SQLite schema dumps in this directory. They remain part of the test
suite after removal of the original application.

`golden/` and `frames/detector/` record the behaviour of the original
implementation. The source and fixture generator are available in Git at
commit `ed90a53`. Do not regenerate these expected outputs from the code being
tested, because that would lose the independent compatibility check.

`legacy/` contains SQL dumps for schema versions 1, 2 and 3. The standard
library helper `scripts/make_legacy_db.py` can reproduce those synthetic dumps
without importing application code or accessing real user data.

Run `cargo test --workspace` to exercise the default compatibility tests.
Detector parity additionally requires `cargo test -p shottrainer-tracking
--features opencv` on a machine with OpenCV and libclang.
