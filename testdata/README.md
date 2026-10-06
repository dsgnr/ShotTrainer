# Test fixtures

The Rust tests use the committed golden JSON and synthetic detector frames in
this directory.

`golden/` and `frames/detector/` provide fixed expected outputs for processing
and detector tests. Do not regenerate these outputs from the code being tested,
because that would lose the independent check.

Run `cargo test --workspace` to exercise the default fixture tests.
Detector tests additionally require `cargo test -p shottrainer-tracking
--features opencv` on a machine with OpenCV and libclang.
