---
description: "Find ShotTrainer releases and learn how upgrades, version numbers and configuration changes are handled for this open-source shooting trainer."
---

# Releases

ShotTrainer is transitioning to a Rust, Tauri and Svelte desktop application.
The source build instructions are in [installation](installation.md).

The desktop app checks for updates at startup. A new stable release appears in
an update banner. Select **Install and restart** to download a signed update,
stop the controller and install it. Installation is unavailable while recording.
If recording starts during the download, stop recording and select the button
again to install the downloaded update. **Later** hides the banner until the
next launch or a manual check from **About**.

**About** also offers **Check for updates**. Automatic checks stay quiet when
offline or when no public release exists. Manual checks display failures.
Linux AppImages can update in place. Other Linux packages offer **Download**,
which opens the releases page for manual installation.

The release workflow builds real-device bundles with OpenCV, signatures and
`latest.json` for macOS, Windows and Linux. A `v*` tag or manual dispatch builds
a draft release. The tag must match the Cargo workspace version. Publish the
draft only after verifying its bundles on each target platform. Drafts and
prereleases are excluded from the automatic stable update endpoint.

Updater signing is separate from operating-system code signing and macOS
notarisation. Signing setup is documented in the repository’s `packaging/README.md`.

Check the [GitHub releases page](https://github.com/dsgnr/ShotTrainer/releases)
for published downloads and their release notes. Back up the application data
directory before upgrading. Any intentional changes to persisted data or
configuration formats should be documented in release notes.
