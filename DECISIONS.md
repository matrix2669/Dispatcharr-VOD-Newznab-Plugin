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

The plugin translates *arr Stack requests and submits jobs, but Mustarrd performs downloading, retries, queue management, and completion handling.

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

Sonarr/Radarr performs validation frequently. Full metadata processing caused multi-minute validation times.

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

# ADR-007: SABnzbd Compatibility Layer Is the Sonarr/Radarr Integration Boundary

## Status

Accepted

## Date

2026-08

## Decision

The plugin exposes a SABnzbd-compatible interface to Sonarr and Radarr instead of implementing a custom Sonarr/Radarr download client integration.

## Reason

Sonarr and Radarr already have mature SABnzbd support. Using this compatibility layer allows Sonarr/Radarr applications to treat Mustarrd as a download backend while the plugin handles Dispatcharr-specific resolution.

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

Newznab endpoint applications require a persistent HTTP endpoint. Separating the service improves reliability and isolates external API traffic from plugin loading.

## Alternatives Considered

- Run the HTTP server directly in the plugin loader process.
- Create a separate standalone container.

## Consequences

The plugin must manage service startup, health checks, and failure reporting.

---

# ADR-009: Synthetic Releases Must Preserve Sonarr/Radarr Expectations Without Exposing Provider Details

## Status

Accepted

## Date

2026-08

## Decision

The plugin generates Sonarr/Radarr-compatible releases representing Dispatcharr VOD availability while hiding provider implementation details.

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

# ADR-011: Sonarr/Radarr Validation and Real Searches Follow Different Performance Paths

## Status

Accepted

## Date

2026-08

## Decision

Validation requests prioritize speed and availability checks, while actual searches may perform deeper enrichment.

## Reason

Sonarr/Radarr validates indexers frequently. Expensive operations during validation caused poor user experience.

## Alternatives Considered

- Use identical processing for validation and searches.

## Consequences

The implementation must maintain separate lightweight and full-resolution workflows.

---

# ADR-012: Lightweight Sonarr/Radarr Feeds

## Status

Accepted

## Date

2026-08

## Decision

Sonarr/Radarr feed requests (RSS, recent releases, and validation-related requests) must use lightweight processing paths and must not trigger full provider searches or media enrichment.

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

# ADR-015: Sonarr/Radarr Release Generation Boundary

## Status

Accepted

## Date

2026-08

## Decision

The plugin generates Sonarr/Radarr-compatible releases while keeping provider-specific implementation details hidden behind Dispatcharr.

## Reason

Sonarr and Radarr require release metadata, categories, and download targets, but provider selection and stream resolution belong to Dispatcharr.

The plugin acts as the compatibility layer between Sonarr/Radarr applications and Dispatcharr VOD.

## Alternatives Considered

- Expose provider URLs directly to Sonarr/Radarr.
- Allow Mustarrd to resolve provider-specific streams.
- Implement a custom Sonarr/Radarr download client.

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

---

# ADR-016: Sonarr/Radarr Compatibility Scope

## Status

Accepted

## Date

2026-08

## Decision

The Dispatcharr VOD Newznab plugin exists as an intermediary compatibility layer between Sonarr/Radarr and Mustarrd.

The plugin provides:

- Newznab-compatible search/indexer functionality;
- SABnzbd-compatible download submission;
- translation between Sonarr/Radarr requests and Dispatcharr/Mustarrd workflows.

The plugin does not replace functionality already provided by Sonarr/Radarr.

## Reason

Sonarr and Radarr already handle:

- media naming;
- file organization;
- metadata management;
- library imports;
- Plex/Jellyfin integration workflows.

Duplicating these responsibilities would create unnecessary complexity.

## Alternatives Considered

- Build custom library management into the plugin.
- Add direct Plex/Jellyfin integration.
- Create custom Sonarr/Radarr plugins.

## Consequences

The plugin should focus only on:

- making Dispatcharr VOD content available to Sonarr/Radarr;
- creating compatible releases;
- submitting downloads.

---

# ADR-017: Sonarr/Radarr Release Naming Ownership

## Status

Accepted

## Date

2026-08

## Decision

The plugin generates release names following standard Sonarr/Radarr-compatible naming conventions.

Sonarr/Radarr remain responsible for final file naming and organization.

## Reason

Sonarr/Radarr applications use release metadata for matching and import workflows. Once downloaded, Sonarr/Radarr already provide the correct renaming and library management behavior.

## Alternatives Considered

- Have Mustarrd create final Plex/Jellyfin filenames.
- Have the plugin manage completed files.
- Create custom naming logic outside Sonarr/Radarr.

## Consequences

The plugin should not attempt to manage final media paths after download completion.

---

# ADR-018: Metadata Ownership

## Status

Accepted

## Date

2026-08

## Decision

Dispatcharr is authoritative for VOD availability.

TMDB and IMDb identifiers are used for Sonarr/Radarr matching.

Sonarr/Radarr remain authoritative for post-download metadata management.

## Reason

The plugin's purpose is exposing available VOD content, not replacing metadata systems.

## Alternatives Considered

- Implement a separate metadata management system.
- Have the plugin maintain the final media library state.

## Consequences

The plugin should:

- preserve Dispatcharr availability data;
- provide matching identifiers;
- avoid becoming a metadata management layer.

---

# ADR-019: Interactive Search First Architecture

## Status

Accepted

## Date

2026-08

## Decision

The primary supported workflow is interactive Sonarr/Radarr searching.

Current flow:
Sonarr/Radarr
      |
      v
Plugin Newznab API
      |
      v
Dispatcharr VOD
      |
      v
ffprobe enrichment
      |
      v
SAB API
      |
      v
Mustarrd


RSS and automatic acquisition workflows are future enhancements.

## Reason

Interactive searches allow accurate stream probing and quality determination.

## Alternatives Considered

- Build RSS support before caching exists.
- Return unverified release metadata.

## Consequences

Future RSS support requires:

- background VOD scanning;
- stream metadata caching;
- release generation from cached data.

---

# ADR-020: SAB-Compatible Download Lifecycle

## Status

Accepted

## Date

2026-08

## Decision

The plugin follows the SABnzbd workflow model.

Plugin responsibilities:

- create Sonarr/Radarr-compatible download jobs;
- return SAB-compatible responses;
- determine categories/download destinations.

Mustarrd responsibilities:

- manage incomplete downloads;
- perform downloads;
- handle retries;
- move completed downloads.

Sonarr/Radarr responsibilities:

- import completed downloads;
- rename files;
- organize libraries.

## Reason

This mirrors existing Sonarr/Radarr download client behavior and keeps responsibilities separated.

## Alternatives Considered

- Implement downloading inside the plugin.
- Have the plugin manage completed media.

## Consequences

The plugin should not manage completed media libraries or final organization.

---

# ADR-021: Dispatcharr Instance Scope

## Status

Accepted

## Date

2026-08

## Decision

A plugin instance is tied to a single Dispatcharr instance.

Multi-instance Dispatcharr support is not planned.

## Reason

Dispatcharr owns:

- provider accounts;
- VOD availability;
- stream resolution;
- VOD proxy behavior.

A plugin instance cannot correctly represent multiple independent catalogs.

## Alternatives Considered

- Support multiple Dispatcharr backends from one plugin instance.
- Aggregate multiple Dispatcharr catalogs.

## Consequences

The plugin lifecycle follows the Dispatcharr instance lifecycle.

---
