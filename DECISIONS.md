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

Dispatcharr must remain responsible for provider selection, stream tracking, account usage, and VOD connection management.

## Alternatives Considered

- Expose original provider URLs directly.
- Let Mustarrd download directly from providers.

## Consequences

The plugin must maintain Dispatcharr-native stream resolution.

---

# ADR-002: Mustarrd Owns the Download Lifecycle

## Status

Accepted

## Date

2026-08

## Decision

The plugin translates Servarr requests and submits jobs, but Mustarrd performs downloading, retries, queue management, and completion handling.

## Reason

Download lifecycle behavior belongs in the dedicated download service.

## Alternatives Considered

- Implement downloading inside the plugin.
- Stream directly using SAB compatibility.

## Consequences

The plugin must maintain compatibility with Mustarrd APIs.

---

# ADR-003: Sonarr and Radarr Validation Must Be Lightweight

## Status

Accepted

## Date

2026-08

## Decision

Indexer validation and RSS-style requests must avoid expensive provider operations, metadata lookups, and ffprobe operations.

## Reason

Servarr performs validation frequently. Full metadata processing caused multi-minute validation times.

## Alternatives Considered

- Run full searches during validation.
- Probe every available stream.

## Consequences

Validation uses local relations and cached data. Full enrichment is reserved for actual searches.

---

# ADR-004: ffprobe Is Only Used When Media Metadata Is Required

## Status

Accepted

## Date

2026-08

## Decision

ffprobe is used for searches requiring accurate codec, HDR, resolution, and audio metadata. It is not used for validation feeds.

## Reason

Media probing is expensive and unnecessary for indexer health checks.

## Alternatives Considered

- Probe every result.
- Return fabricated quality metadata.

## Consequences

Searches remain accurate while validation remains fast.

---

# ADR-005: Plugin Must Support Multiple Dispatcharr Runtime Layouts

## Status

Accepted

## Date

2026-08

## Decision

The plugin must not assume a fixed Dispatcharr installation path.

## Reason

Dispatcharr deployments may use different container layouts.

## Alternatives Considered

- Hard-code `/opt/dispatcharr`.

## Consequences

Runtime paths must be detected dynamically.

---

# ADR-006: Related Project Contracts Must Be Reviewed Before Integration Changes

## Status

Accepted

## Date

2026-08

## Decision

Changes affecting Dispatcharr or Mustarrd integration must be reviewed against the related project's behavior before implementation.

## Reason

The plugin depends on contracts owned by other repositories. A local change can unintentionally break another component.

## Related Projects

- Dispatcharr: plugin framework, VOD providers, VOD proxy.
- Mustarrd: queue, downloading, retries, completion lifecycle.

## Alternatives Considered

- Treat the plugin repository as standalone.

## Consequences

Future architectural changes require cross-project review.
