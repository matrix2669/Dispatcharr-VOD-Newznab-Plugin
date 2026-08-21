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

---

# ADR-012: Lightweight Servarr Feeds

## Status

Accepted

## Date

2026-08

## Decision

Servarr feed requests (RSS, recent releases, and validation-related requests) must use lightweight processing paths and must not trigger full provider searches or media enrichment.

## Reason

Sonarr and Radarr poll indexers frequently. Performing full provider searches, metadata enrichment, or media probing during these requests creates unnecessary load and can cause slow or failed indexer validation.

## Alternatives Considered

- Use the same full search workflow for RSS, validation, and interactive searches.
- Probe all available media before returning feed results.

## Consequences

The plugin maintains separate workflows:

- lightweight paths for validation and feeds;
- full enrichment paths for interactive searches.

Feed results must rely on cached data and existing Dispatcharr relationships whenever possible.

---

# ADR-013: Dynamic ffprobe Resolution

## Status

Accepted

## Date

2026-08

## Decision

The plugin must dynamically locate and invoke ffprobe rather than assuming a fixed installation path.

## Reason

Dispatcharr deployments may run in different environments including containers with different filesystem layouts. Hardcoded paths such as `/usr/bin/ffprobe` reduce compatibility.

## Alternatives Considered

- Hardcode a known ffprobe path.
- Require administrators to manually configure paths for every deployment.

## Consequences

The plugin should:

- detect available ffprobe locations;
- respect configured overrides;
- fail clearly when probing is required but unavailable.

Media probing remains limited to workflows where codec, HDR, resolution, or audio metadata is required.

---

# ADR-014: Release History and Documentation Boundaries

## Status

Accepted

## Date

2026-08

## Decision

Release documentation, architecture documentation, and AI/developer guidance must remain separate concerns.

## Reason

The project contains three different types of documentation:

- CHANGELOG.md describes user-visible releases.
- DECISIONS.md describes architectural reasoning.
- AGENT.md describes development guidance and operational expectations.

Mixing these responsibilities makes future maintenance and historical review more difficult.

## Alternatives Considered

- Store all project history in CHANGELOG.md.
- Put architectural decisions only in commit messages.

## Consequences

Future changes must update the appropriate documentation file:

- new feature/fix release → CHANGELOG.md;
- architectural decision → DECISIONS.md;
- workflow or AI/developer behavior change → AGENT.md.

---

# ADR-015: Servarr Release Generation Boundary

## Status

Accepted

## Date

2026-08

## Decision

The plugin generates Servarr-compatible releases while keeping provider-specific implementation details hidden behind Dispatcharr.

## Reason

Sonarr and Radarr require release metadata, categories, and download targets, but provider selection and stream resolution belong to Dispatcharr.

The plugin acts as the compatibility layer between Servarr applications and Dispatcharr VOD.

## Alternatives Considered

- Expose provider URLs directly to Sonarr/Radarr.
- Allow Mustarrd to resolve provider-specific streams.
- Implement a custom Servarr download client.

## Consequences

The plugin is responsible for:

- Newznab responses;
- synthetic release metadata;
- SAB-compatible handoff.

Dispatcharr remains responsible for:

- provider selection;
- stream resolution;
- VOD proxy handling.

Mustarrd remains responsible for:

- downloading;
- retries;
- queue management;
- completion processing.
