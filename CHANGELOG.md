# Changelog

All notable changes to this project are documented here.

This file contains release history only. Architectural decisions belong in `DECISIONS.md`.

The format follows Keep a Changelog principles where practical.

## [0.2.0] - 2026-08-22

### Added

- Added project AI documentation structure with `AGENT.md` and `DECISIONS.md`.
- Documented architecture decisions for Dispatcharr proxy handling, Mustarrd integration, and Servarr compatibility.
- Added standalone branch tracking, canonical version, and release procedures.

### Changed

- Improved documentation separation between user guidance, agent instructions, architectural decisions, and release history.
- Renamed the public project to **Dispatcharr Arr Stack Plugin** and the in-Dispatcharr display name to **Arr Stack Connector**.
- Adopted the standalone `main`/`dev` workflow with immutable beta and stable tags instead of permanent version branches.
- Changed the registry/archive slug to `arr-stack-connector`, installed key to `arr_stack_connector`, state root to `/data/arr_stack_connector`, and plugin-owned environment variables to `ARR_STACK_CONNECTOR_*`.
- Added a one-time migration path from the legacy plugin and state directories while preserving settings IDs, API behavior, and job-state formats.

## [0.1.16]

### Added

- Added lightweight Servarr recent-feed handling.
- Added improved Servarr release naming behavior.

### Changed

- Improved Sonarr/Radarr validation performance.
- Reduced unnecessary metadata probing during validation.
- Improved ffprobe discovery across Dispatcharr runtime layouts.

### Fixed

- Fixed ffprobe path assumptions across different Dispatcharr container layouts.
- Fixed validation workflows performing expensive operations unnecessarily.

## [0.1.15]

### Added

- Added lightweight recent-feed support for Servarr workflows.

### Changed

- Optimized indexer validation paths.
- Improved compatibility with different ffprobe installation layouts.
- Improved Servarr feed performance.

## [0.1.14]

### Added

- Improved plugin service startup and health handling.
- Added API key generation and display improvements.
- Improved Sonarr/Radarr indexer validation performance.
- Reduced unnecessary ffprobe work during validation requests.

### Fixed

- Fixed plugin loading failures caused by detached service startup handling.
- Fixed cases where indexer validation took several minutes to complete.

## [0.1.13]

### Added

- Initial public plugin release.
- Newznab-compatible indexer support.
- SABnzbd-compatible download client support.
- Mustarrd-backed VOD download lifecycle.
- Dispatcharr native VOD proxy integration.
