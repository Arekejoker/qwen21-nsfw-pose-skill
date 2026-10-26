# Changelog

Notable changes to this package. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions are git tags. The package ships as a skill, not a library, so versions mark
documented, reproducible states of the scripts + docs rather than an API contract.

## [Unreleased]

### Added

- `VNCCS_LORA` environment variable: choose the VNCCS PoseStudio LoRA file for routes ③ and ④
  (`run_pose_transfer.py`, `run_vnccs_ui.py`) and for the `doctor.py` LoRA check. The default is
  still `VNCCS_QI2_PoseStudioV1.1.safetensors`. Route ③'s `--lora` flag still takes precedence.

## [1.1.0] — 2026-10-20

Since 1.0.0: a new browser-free route, a self-check script, macOS and Windows support, and a
rewritten README showcase. Routes are now ①②③④ with no gaps.

### Added

- **Route ③ — scripted pose transfer** (`scripts/run_pose_transfer.py`): change a character's pose
  from a textureless 3D mannequin render, no browser involved. Dual-image edit + VNCCS PoseStudio
  LoRA @1.0. Route ④ saves suitable mannequin renders (`doll_*.png`) automatically.
- **`scripts/doctor.py`** — read-only environment self-check: ComfyUI connectivity, base models,
  LoRAs, VNCCS nodes, pose library and browser backend, each with fix instructions.
- **`scripts/make_custom_pose.py`** — build custom poses from poses already in the library (#4).
- **English README** (`README.en.md`), with a language switcher on both READMEs.
- **macOS (Apple Silicon) support**: documented guidance, plus a `macos-latest` CI job that runs
  the offline package checks on Apple's runner.
- **Windows compatibility** for `doctor.py` output, the media lock and the pose index (#9).
- Hardware requirements section (issue #5) and an acknowledgements section.

### Changed

- Licensed original code and docs under **Apache-2.0** (third-party assets keep their own terms).
- README showcase rewritten: full-width animated cover card for the NSFW author originals,
  click-to-expand instead of inline, plus a Route ④ demo GIF at the top.
- Setup guide corrected for the edit LoRA, VNCCS and the pose library (#2).
- `--list-poses` hint, usage text and setup wording polished; dead code dropped.
- Photo/illustration pose references are now called out explicitly as unsupported (the model
  composites or redraws the reference person) — use a 3D mannequin render instead.

### Fixed

- Result naming for full pose keys (#1).
- Five pose previews replaced; `validate_package.py` now fails on empty preview files.
- Placeholder pose renamed.
- `validate_package.py` also validates `README.en.md` images.

## [1.0.0] — 2026-10-13

Initial stable release: Routes ① T2I and ② Edit, the author recipe and prompt structure,
boldness tiers L0–L3, the 136-pose VNCCS library, install guide and the author-case reproduction.

[1.1.0]: https://github.com/Arekejoker/qwen21-nsfw-pose-skill/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Arekejoker/qwen21-nsfw-pose-skill/releases/tag/v1.0.0
