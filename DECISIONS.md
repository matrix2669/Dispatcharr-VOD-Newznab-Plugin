# Architecture Decisions

This file documents important architectural decisions for the Dispatcharr VOD Newznab plugin.

Each decision records:

- what was decided;
- why it was chosen;
- alternatives considered;
- consequences.

---

# ADR-012: Lightweight Servarr Feeds Are Separate From Full Searches

## Status

Accepted

## Date

2026-08

## Decision

Servarr validation and recent-feed requests use lightweight processing paths, while interactive searches may perform full enrichment.

## Reason

Sonarr and Radarr frequently poll indexers. Full provider scans and metadata processing during these requests caused unnecessary load and slow validation.

## Alternatives Considered

- Use the same processing path for validation and searches.
- Perform ffprobe and provider scans for every request.

## Consequences

The plugin must maintain separate lightweight and full-resolution workflows.

---

# ADR-013: ffprobe Resolution Must Support Multiple Runtime Layouts

## Status

Accepted

## Date

2026-08

## Decision

The plugin must dynamically locate ffprobe rather than relying on a fixed filesystem path.

## Reason

Dispatcharr deployments may use different container layouts and package locations.

## Alternatives Considered

- Hard-code `/usr/bin/ffprobe`.
- Require users to manually configure every installation.

## Consequences

Media enrichment remains portable across Dispatcharr deployments.

---

# ADR-014: Release History Must Reflect User-Facing Changes Only

## Status

Accepted

## Date

2026-08

## Decision

CHANGELOG.md documents releases, features, fixes, and breaking changes. Architectural rationale belongs in this file.

## Reason

Separating release history from design decisions allows future maintainers to understand both what changed and why it changed.

## Alternatives Considered

- Put all project history into CHANGELOG.md.

## Consequences

New architectural decisions require ADR entries instead of changelog entries.

---

# ADR-015: Servarr Release Generation Hides Provider Implementation Details

## Status

Accepted

## Date

2026-08

## Decision

The plugin generates Servarr-compatible releases while keeping provider selection and connection details inside Dispatcharr.

## Reason

Sonarr and Radarr need standard release metadata, but provider handling remains a Dispatcharr responsibility.

## Alternatives Considered

- Expose provider URLs directly.
- Allow Servarr applications to select providers.

## Consequences

Release metadata must accurately represent available media without leaking provider internals.
