---
description: "Find ShotTrainer releases and learn how upgrades, version numbers and configuration changes are handled for this open-source shooting trainer."
---

# Releases

ShotTrainer is transitioning to a Rust, Tauri and Svelte desktop application.
The source build instructions are in [installation](installation.md).

Releases currently require manual preparation. This repository has no active
automated publication pipeline. Release bundles are built through Tauri with the
OpenCV feature for real camera input. Bundle availability, installation
requirements, signing and platform support must be established for each
published release. A source build or synthetic-device test is not a platform
certification.

Check the [GitHub releases page](https://github.com/dsgnr/ShotTrainer/releases)
for published downloads and their release notes. Back up the application data
directory before upgrading. Any intentional changes to persisted data or
configuration formats should be documented in release notes.
