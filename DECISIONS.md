# Architecture Decisions

This file documents important architectural decisions for the Dispatcharr VOD Newznab plugin.

Each decision records:

- what was decided;
- why it was chosen;
- alternatives considered;
- consequences.

---

# ADR-001: Dispatcharr Remains the Source of Truth

## Status

Accepted

## Date

2026-08

## Decision

All VOD downloads must resolve through Dispatcharr's native VOD proxy. The plugin must not expose raw provider URLs directly to Sonarr, Radarr, SABnzbd, or Mustarrd.

## Reason

Dispatcharr must remain responsible for provider selection, stream tracking, account usage, and VOD connection management. Bypassing Dispatcharr would remove visibility and control over the selected stream.

## Alternatives Considered

- Expose the original Xtream provider URL directly.
- Let Mustarrd download directly from providers.

## Consequences

The plugin must materialize missing Dispatcharr relations when needed and generate Dispatcharr-native proxy URLs for downloads.

---

# ADR-002: Mustarrd Owns the Download Lifecycle

## Status

Accepted

## Date

2026-08

## Decision

The plugin translates Servarr requests and submits jobs, but Mustarrd performs the actual download, retry, queue, and completion lifecycle.

## Reason

Mustarrd already provides the required download management behavior. Reimplementing downloading inside the plugin would duplicate functionality and create competing workflows.

## Alternatives Considered

- Implement downloading directly inside the Dispatcharr plugin.
- Stream directly from providers using the SAB compatibility layer.

## Consequences

The plugin must maintain compatibility with Mustarrd APIs and translate between SAB semantics and Mustarrd jobs.

---

# ADR-003: Sonarr and Radarr Validation Must Be Lightweight

## Status

Accepted

## Date

2026-08

## Decision

Indexer validation and RSS-style requests must avoid expensive provider operations, metadata lookups, and ffprobe operations.

## Reason

Servarr performs validation and RSS requests frequently. Performing full stream analysis caused multi-minute validation times.

## Alternatives Considered

- Run complete searches for validation requests.
- Probe every available stream before returning results.

## Consequences

Validation uses local Dispatcharr relations and cached catalog data. Full enrichment is reserved for real user searches.

---

# ADR-004: ffprobe Is Only Used When Media Metadata Is Required

## Status

Accepted

## Date

2026-08

## Decision

ffprobe is used for real searches where codec, HDR, Dolby Vision, resolution, and audio metadata improve release naming. It is not used for validation feeds.

## Reason

Media probing is expensive and unnecessary when Servarr only needs confirmation that the indexer is functional.

## Alternatives Considered

- Probe every Newznab result.
- Return fabricated quality metadata.

## Consequences

Searches provide accurate release metadata while validation remains fast.

---

# ADR-005: Plugin Must Support Multiple Dispatcharr Runtime Layouts

## Status

Accepted

## Date

2026-08

## Decision

The plugin must not assume a fixed Dispatcharr installation path.

## Reason

Dispatcharr deployments may run from different container layouts, including `/app` and `/opt/dispatcharr`.

## Alternatives Considered

- Hard-code a single application path.

## Consequences

Runtime paths must be detected dynamically.
