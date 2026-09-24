---
title: Free optical shooting trainer
description: Free, open-source shooting trainer for air rifle, air pistol and smallbore practice. Track aim, score shots and replay sessions with your own camera.
template: landing.html
hide:
  - navigation
  - toc
---

# ShotTrainer

ShotTrainer is an optical shooting trainer built with Rust, Tauri and Svelte. A
rifle-mounted camera tracks a dark circular aiming mark. Microphone input
registers shots. The application records aim traces, scores shots against a
selected target face, and stores sessions locally for review and CSV export.

Start with [installation](installation.md) and [getting
started](getting-started.md). Development builds use synthetic devices by
default. Real camera capture requires the OpenCV feature and native
dependencies. Hardware behaviour and platform packaging still need validation on
the intended machine.

See [architecture](architecture.md) for the implementation and
[accuracy](accuracy.md) for measurement limitations.
