# Changelog

All notable changes to this project are documented here.

This file contains release history only. Architectural decisions belong in `DECISIONS.md`.

The format follows Keep a Changelog principles where practical.

## [Unreleased]

### Added

- Added project AI documentation structure with `AGENT.md` and `DECISIONS.md`.
- Documented architecture decisions for Dispatcharr proxy handling, Mustarrd integration, and Servarr compatibility.

### Changed

- Improved documentation separation between user guidance, agent instructions, architectural decisions, and release history.

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
