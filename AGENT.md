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
- Dispatcharr-Mustarrd integration components may affect API contracts and workflow behavior.

When modifying integration behavior, review related projects before making changes.

## AI Agent Instructions

Before modifying code:

1. Read this file completely.
2. Review `DECISIONS.md` for architectural context.
3. Review related project behavior when integrations are affected.
4. Understand the complete request flow before changing implementation.
5. Preserve existing architecture unless intentionally changing design.
6. Do not optimize one component while breaking Sonarr/Radarr compatibility.
7. Test both Sonarr and Radarr workflows after changes.

## Non-Negotiable Architecture Rules

### Dispatcharr is the source of truth

The plugin must not bypass Dispatcharr VOD handling.

Downloads must resolve through the Dispatcharr VOD proxy so that:

- provider accounting remains correct;
- stream selection remains controlled by Dispatcharr;
- profiles/providers are respected.

### Mustarrd performs downloads

The plugin translates requests and submits jobs.

Responsibilities:

Plugin:

- Newznab API
- SAB compatibility
- stream resolution
- Dispatcharr proxy integration
- Servarr release generation

Mustarrd:

- downloading
- retries
- queue management
- completion handling

The plugin must not move Dispatcharr-specific provider logic into Mustarrd.

## Request Path Rules

### Sonarr/Radarr Validation and RSS

Validation and recent-feed requests must be lightweight.

Do not add:

- ffprobe operations;
- large provider scans;
- unnecessary metadata lookups.

Use cached or local Dispatcharr relations where possible.

### Real Searches

Actual title/TMDB/episode searches may perform:

- provider lookups;
- metadata enrichment;
- ffprobe probing.

Use expensive operations only when they improve returned media accuracy.

Validation and interactive searches intentionally follow different performance paths.

## Media Probing Rules

ffprobe is only used when media metadata is required.

Requirements:

- never assume `/usr/bin/ffprobe`;
- resolve ffprobe dynamically;
- support different Dispatcharr runtime layouts.

Codec, HDR, resolution, and audio enrichment belongs in full searches, not validation paths.

## Dispatcharr Integration

Never assume a fixed installation path.

Dispatcharr containers may run from locations such as:

- `/app`
- `/opt/dispatcharr`

Detect paths dynamically.

The detached Newznab/SAB service must:

- start reliably;
- expose health status;
- log failures clearly.

The embedded service currently uses port `9192` and must prevent duplicate startup conflicts.

## Plugin Settings

Important settings include:

- Dispatcharr URL
- Mustarrd URL
- API key
- ffprobe path
- categories
- cache settings

API key behavior:

- blank key generates a new key;
- existing keys remain unchanged;
- intentional rotation is done by clearing the key, saving, disabling, and re-enabling the plugin.

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

- "Missing plugin files" may actually indicate plugin initialization failure.
- Do not assume `/usr/bin/ffprobe`; resolve ffprobe safely.
- Validation paths must remain fast.
- Do not bypass Dispatcharr proxy URLs.
- Do not modify released versions; create a new release.
- Do not make validation paths perform full enrichment.

## Documentation Rules

README.md is for users.

CHANGELOG.md is for release history.

AGENT.md is for architecture and future AI/developer guidance.

DECISIONS.md documents why architectural choices were made.

Update this file only when architecture, workflow, or development rules change.
