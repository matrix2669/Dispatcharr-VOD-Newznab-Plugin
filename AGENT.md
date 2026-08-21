# AGENT.md

## Purpose

This repository contains the Dispatcharr VOD Newznab plugin.

The plugin exposes Dispatcharr VOD content to Sonarr and Radarr through Newznab-compatible and SABnzbd-compatible APIs. It is the intermediary between Servarr applications and Mustarrd while keeping Dispatcharr as the source of VOD data and Mustarrd as the download engine.

This project follows the AI project standards defined in the matrix2669/workspace repository.

Review `DECISIONS.md` before making architectural changes.

## Related Projects

Changes require understanding:

- Dispatcharr (`Dispatcharr/Dispatcharr`)
  - plugin framework
  - VOD catalog
  - provider handling
  - VOD proxy behavior

- Mustarrd (`matrix2669/mustarrd`)
  - download queue
  - retries
  - processing
  - completion lifecycle

## Architecture Rules

### Dispatcharr is the source of truth

The plugin must not bypass Dispatcharr VOD handling.

Dispatcharr owns:

- VOD availability
- provider selection
- stream resolution
- account/provider behavior

### This plugin is the Servarr intermediary

The plugin owns:

- Newznab API
- SABnzbd-compatible API
- Servarr release generation
- Dispatcharr VOD lookup
- Dispatcharr proxy integration

Mustarrd owns:

- downloading
- retries
- queue management
- completion handling
- final download lifecycle

Do not move Servarr-specific behavior into Mustarrd.

## Servarr Workflow Rules

### Current workflow

The primary supported workflow is interactive search in Sonarr/Radarr.

Interactive searches may perform:

- Dispatcharr VOD lookups
- metadata matching
- ffprobe analysis
- quality determination

### Validation and RSS

Validation, RSS, and feed requests must remain lightweight.

Do not perform:

- large provider scans
- unnecessary metadata enrichment
- ffprobe probing unless required

Future RSS support should use background-generated cached data rather than live expensive searches.

## Future Roadmap Considerations

Potential future improvements:

- background idle-time VOD scanning
- cache probed stream metadata
- generate RSS feeds from cached data
- investigate season pack support when Dispatcharr data supports it
- return SAB-compatible errors when Mustarrd is unavailable

## Media Metadata

Dispatcharr is authoritative for VOD availability.

TMDB and IMDb identifiers are used for Sonarr/Radarr matching. After download completion, Sonarr/Radarr own metadata processing and library organization.

The plugin does not manage Plex/Jellyfin libraries.

## Media Probing

ffprobe must be resolved dynamically.

Do not assume fixed paths such as `/usr/bin/ffprobe`.

Probe only when codec, HDR, resolution, or audio metadata is required.

Probed stream data should be cached. Cache entries should be validated when VOD data refreshes and removed when the source item no longer exists.

A long cache lifetime is acceptable because VOD metadata changes primarily by availability.

## Download/File Handling

The plugin follows SABnzbd behavior.

The plugin:

- creates Servarr-compatible releases
- determines categories/download handling
- submits jobs through SAB-compatible APIs

Mustarrd:

- handles incomplete downloads
- moves completed files
- manages retries

After completion, Sonarr/Radarr take ownership of renaming and library management.

## Authentication

Authentication should follow existing Newznab and SABnzbd API conventions.

Do not introduce custom authentication models without an architectural decision.

## Deployment

The Newznab/SAB service lifecycle is tied to the Dispatcharr plugin.

When the plugin is enabled:

- service should run
- health checks should be available
- failures should be reported clearly

Avoid duplicate service instances.

## Multi Instance Support

Multiple Dispatcharr instances are not currently supported or planned.

Each plugin instance is tied to its Dispatcharr VOD catalog and accounts.

## Development Workflow

Use:

```
main
 |
 +-- feature/*
 |
 +-- dev-test
 |
 +-- dev
```

Changes should be tested before promotion.

## Testing Requirements

Before release validate:

- plugin installation
- plugin loading
- service health
- Sonarr validation
- Sonarr search/grab
- Radarr validation
- Radarr search/grab
- Mustarrd queue behavior
- Mustarrd completion behavior

## Known Pitfalls

- Do not assume ffprobe locations.
- Validation paths must remain fast.
- Do not bypass Dispatcharr proxy URLs.
- Do not replace Mustarrd download lifecycle without an architectural decision.
- Do not add Plex/Jellyfin integration; Sonarr/Radarr own library management.

## Documentation Rules

README.md is for users.

CHANGELOG.md is for release history.

AGENT.md is for architecture and future AI/developer guidance.

DECISIONS.md documents why architectural choices were made.
