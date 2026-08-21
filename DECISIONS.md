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

---

# ADR-007: SABnzbd Compatibility Layer Is the Servarr Integration Boundary

## Status

Accepted

## Date

2026-08

## Decision

The plugin exposes a SABnzbd-compatible interface to Sonarr and Radarr instead of implementing a custom Servarr download client integration.

## Reason

Sonarr and Radarr already have mature SABnzbd support. Using this compatibility layer allows Servarr applications to treat Mustarrd as a download backend while the plugin handles Dispatcharr-specific resolution.

## Alternatives Considered

- Create a custom Sonarr/Radarr download client.
- Have Sonarr/Radarr communicate directly with Mustarrd.

## Consequences

The plugin must preserve SAB-compatible responses and queue behavior.

---

# ADR-008: Detached Newznab/SAB Service Runs Separately From Plugin Discovery

## Status

Accepted

## Date

2026-08

## Decision

The plugin starts and manages a detached Newznab/SAB-compatible service rather than serving all requests directly inside the Dispatcharr plugin lifecycle.

## Reason

Servarr applications require a persistent HTTP endpoint. Separating the service improves reliability and isolates external API traffic from plugin loading.

## Alternatives Considered

- Run the HTTP server directly in the plugin loader process.
- Create a separate standalone container.

## Consequences

The plugin must manage service startup, health checks, and failure reporting.

---

# ADR-009: Synthetic Releases Must Preserve Servarr Expectations Without Exposing Provider Details

## Status

Accepted

## Date

2026-08

## Decision

The plugin generates Servarr-compatible releases representing Dispatcharr VOD availability while hiding provider implementation details.

## Reason

Sonarr and Radarr require release metadata and download targets, but the actual source selection belongs to Dispatcharr.

## Alternatives Considered

- Return direct provider URLs.
- Expose provider-specific release information.

## Consequences

Release metadata must accurately represent available media while keeping provider handling inside Dispatcharr.

---

# ADR-010: API Keys Are Managed Through Plugin Settings Lifecycle

## Status

Accepted

## Date

2026-08

## Decision

The API key is generated automatically when missing and remains stable unless intentionally reset.

## Reason

Sonarr/Radarr require a stable indexer credential. Accidental regeneration would break existing configurations.

## Alternatives Considered

- Add a separate rotate button.
- Generate a new key every save.

## Consequences

Key rotation is an intentional administrative action.

---

# ADR-011: Servarr Validation and Real Searches Follow Different Performance Paths

## Status

Accepted

## Date

2026-08

## Decision

Validation requests prioritize speed and availability checks, while actual searches may perform deeper enrichment.

## Reason

Servarr validates indexers frequently. Expensive operations during validation caused poor user experience.

## Alternatives Considered

- Use identical processing for validation and searches.

## Consequences

The implementation must maintain separate lightweight and full-resolution workflows.
