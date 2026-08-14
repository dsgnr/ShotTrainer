# Releases and upgrades

ShotTrainer follows [Semantic Versioning](https://semver.org/) starting from
`0.x`. Pre-`1.0` releases may break configuration formats. We'll always note
that in the release notes when it happens.

## Release cycle

- **Patch releases (`0.x.y`)** Bug fixes and small improvements that don't
  change behaviour. Released as needed.
- **Minor releases (`0.x.0`)** New features. Released roughly when a meaningful
  bundle of features is ready.
- **Major releases (`x.0.0`)** Reserved for breaking changes once the project
  hits `1.0`.

Releases are tagged in git as `vMAJOR.MINOR.PATCH`. The release workflow builds
binaries for Linux, macOS and Windows and attaches them to the GitHub release.
The artefacts are:

- **Windows.** A signed-once-you-sign-it `ShotTrainer-Setup.exe` built with Inno
  Setup, plus a portable `ShotTrainer-Windows.zip` for users who'd rather run
  without installing.
- **macOS.** A `.dmg` containing `ShotTrainer.app` and a shortcut to
  `/Applications`, plus a `ShotTrainer-macOS.tar.gz` of the raw folder build for
  advanced users.
- **Linux.** A `ShotTrainer-Linux.tar.gz` of the standalone Nuitka folder.

## How a release happens

1. A maintainer bumps the version in `pyproject.toml` and commits.
2. They tag the commit: `git tag v0.2.0 && git push --tags`.
3. The release workflow builds the binaries and creates a GitHub release with
   auto-generated notes from the commit history.
4. Documentation on GitHub Pages updates from the same commit.

## Upgrading

For most upgrades, replace the application binary or `uv sync --upgrade` if
you're running from source. Local data lives in the data directory (see
[Troubleshooting](troubleshooting.md)) and is preserved across upgrades.

When a release changes a stored format we add a migration. The schema version
recorded in the database is bumped and the app upgrades the file on first
launch. If we ever need to make an irreversible change we'll say so in the
release notes and ship a one-shot tool to handle it.

## Reporting regressions

If a new release breaks something that worked before, please file an issue on
GitHub with the version you upgraded from, the version you upgraded to, and a
short description. The platform and a screenshot of the relevant pane usually
help.
