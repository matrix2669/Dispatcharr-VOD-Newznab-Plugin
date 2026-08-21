# AGENT.md

## Purpose

This repository contains the Dispatcharr VOD Newznab plugin.

The plugin exposes Dispatcharr VOD content to Sonarr and Radarr through a Newznab-compatible API and SABnzbd-compatible download interface while keeping Dispatcharr as the source of truth and Mustarrd as the download engine.

This project follows the AI project standards defined in the matrix2669/workspace repository.

Review `DECISIONS.md` before making architectural changes.

## Related Projects

Changes to this repository require understanding related systems:

- Dispatcharr: `Dispatcharr/Dispatcharr`
  - Provides the plugin framework, VOD catalog, provider handling, and native VOD proxy behavior.
- Mustarrd: `matrix2669/mustarrd`
  - Provides download queueing, retries, processing, and completion lifecycle.

When modifying integration behavior, review related projects before making changes.

## Architecture Rules

### Dispatcharr is the source of truth

The plugin must not bypass Dispatcharr VOD handling.

Downloads must resolve through the Dispatcharr VOD proxy so provider accounting, stream selection, and profiles remain controlled by Dispatcharr.

### Mustarrd performs downloads

The plugin translates Servarr requests and submits jobs.

Plugin responsibilities:

- Newznab API
- SAB compatibility
- Servarr release generation
- Dispatcharr VOD resolution
- Dispatcharr proxy integration

Mustarrd responsibilities:

- downloading
- retries
- queue management
- completion handling

## Request Path Rules

### Validation and RSS

Sonarr/Radarr validation, RSS, and feed requests must remain lightweight.

Do not add:

- ffprobe operations;
- large provider scans;
- unnecessary metadata lookups.

Use cached or local Dispatcharr relations where possible.

### Real Searches

Interactive searches may perform deeper processing:

- provider lookups;
- metadata enrichment;
- ffprobe probing.

Expensive operations should only be used when they improve returned media accuracy.

## Media Probing

ffprobe must be resolved dynamically.

Do not assume fixed paths such as `/usr/bin/ffprobe` because Dispatcharr deployments may use different container layouts.

Probe only when codec, HDR, resolution, or audio metadata is required.

## Detached Servarr Service

The detached Newznab/SAB-compatible service must:

- start reliably;
- expose health status;
- report failures clearly;
- avoid duplicate service instances.

Operational deployments use a dedicated service endpoint and health checks.

## Development Workflow

Use the standard workspace workflow:

```
main
 |
 +-- feature/*
 |
 +-- dev-test
 |
 +-- dev
```

Changes should be tested before moving into production branches.

## Testing Requirements

Before release validate:

- plugin installation;
- plugin loading;
- service health;
- Sonarr indexer validation;
- Sonarr search and grab;
- Radarr indexer validation;
- Radarr search and grab;
- Mustarrd queue and completion.

## Known Pitfalls

- Do not assume fixed ffprobe locations.
- Validation paths must remain fast.
- Do not bypass Dispatcharr proxy URLs.
- Do not move Servarr-specific behavior into Mustarrd.
- Do not modify released versions; create a new release.

## Documentation Rules

README.md is for users.

CHANGELOG.md is for release history.

AGENT.md is for architecture and future AI/developer guidance.

DECISIONS.md documents why architectural choices were made.

Update this file only when architecture, workflow, or development rules change.
