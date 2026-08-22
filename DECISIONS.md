# Architecture Decisions

This file documents important architectural decisions for the **Dispatcharr Arr Stack Plugin**, formerly named **Dispatcharr VOD Newznab Plugin**.

It was reconstructed from the complete available `Sonarr Radarr VOD Connector` ChatGPT history, the current standalone-workflow task, the full repository history and remote branch state, the implementation and tests, the Dispatcharr plugin registry, and related Dispatcharr/Mustarrd contracts. Conversation proposals are evidence rather than decisions by themselves; accepted behavior reflects the implementation and user-approved outcomes that survived testing.

## Evidence index

- ChatGPT `Sonarr Radarr VOD Connector`: `6a7c763c-62d4-83ea-a2a6-0fddaab941e4`
- ChatGPT `Simplify Plugin Versioning`: `6a898c9e-1ffc-83ea-8fcc-b44788fea3c0`
- Codex `Update standalone release workflow`: `01a02969-01f0-7803-8031-37f7f4f2803c`
- Repository history: initial commit `833bc16` through documentation baseline `13c5d11`
- Distribution repository: `matrix2669/dispatcharr-plugins`
- Related projects: `Dispatcharr/Dispatcharr` `v0.29.0` at `d9abece081c9edf637d4c3fdd41443eb993a3c08`; `matrix2669/mustarrd:dev` at `7c56b83879f76faff8f303c139063a1f51a75431`

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

The Dispatcharr Arr Stack Plugin exists as an intermediary compatibility layer between Sonarr/Radarr and Mustarrd.

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

# ADR-022: Rename the Public and Installed Plugin Identity With a One-Time Migration

## Status

Accepted

## Date

2026-08-22

## Decision

Use **Dispatcharr Arr Stack Plugin** as the public project name and **Arr Stack Connector** as the plugin's display name. Use `matrix2669/Dispatcharr-Arr-Stack-Plugin` as the canonical GitHub repository name.

Adopt `arr-stack-connector` as the registry slug and source archive directory, `arr_stack_connector` as the normalized Dispatcharr installation key/directory, `/data/arr_stack_connector` as the persistent state root, and `ARR_STACK_CONNECTOR_*` for plugin-owned environment variables.

Preserve the `servarr_bridge` package, settings IDs, routes, descriptor format, namespaced job IDs, and default port. Existing installations perform a one-time manual migration of the plugin directory, state directory, and saved settings/API key while the old plugin is disabled.

## Reason

The implementation connects more than a Newznab endpoint: it coordinates Sonarr, Radarr, Dispatcharr, the SAB-compatible handoff, and Mustarrd. “Arr Stack Connector” describes that broader responsibility. The user accepted a one-time migration on the single existing installation so the long-term public and installed identities can be consistent.

## Alternatives Considered

- Keep the old public name. Rejected because it describes only one protocol surface and obscures the complete integration.
- Preserve every legacy slug and path indefinitely. Initially proposed for automatic upgrade compatibility, then rejected because the user preferred a clean identity and accepted the one-time migration.
- Rename the internal `servarr_bridge` package and persisted protocol formats. Rejected because those are implementation/protocol contracts and provide no user-facing naming benefit.

## Consequences

The renamed plugin appears as a new Dispatcharr key rather than an in-place update. The old service must be disabled before the new one starts, and settings/API key plus persistent state must be transferred once. The registry retains the legacy manifest only as unindexed history after the new slug is published.

## Provenance

- User direction in Codex `Update standalone release workflow`, 2026-08-22
- Current registry slug and historical archives in `matrix2669/dispatcharr-plugins`
- Existing runtime/state contracts in `plugin.py`, `service.py`, and `servarr_bridge`

---

# ADR-023: Use the Standalone Main/Dev and Immutable-Tag Workflow

## Status

Accepted; supersedes permanent version branches

## Date

2026-08-22

## Decision

Operate this repository as a standalone Dispatcharr plugin:

- `main` is production-ready and is the source for explicitly approved GitHub Releases;
- `dev` integrates the next version;
- short-lived feature and fix branches start from and return to `dev`;
- tested beta builds use immutable `vMAJOR.MINOR.PATCH-beta.N` tags on `dev` without GitHub prereleases;
- completed feature/fix work uses a normal Semantic Version tag, whether or not a GitHub Release is approved;
- `dispatcharr-plugins:dev` advertises the newest approved tag;
- `dispatcharr-plugins:main` changes only after explicit approval of a normal GitHub Release;
- `BRANCHES.md` tracks only branches that currently exist.

Convert historical `v0.1.0` through `v0.1.16` branch heads to same-name immutable tags at the exact commits before deleting those branches. Delete the superseded bootstrap documentation branch only after verifying its durable content is already incorporated.

## Reason

Dispatcharr update detection depends on version increments and the registry requires immutable archive targets. Tags express version identity without permanent branch clutter. Separating the testing registry from GitHub Releases also allows completed stable builds to remain available for plugin testing without implying public release approval.

## Alternatives Considered

- Keep permanent version branches. Rejected because tags provide the required immutable archive identity more directly.
- Point the testing registry at moving `dev`. Rejected because Dispatcharr will not update unless the plugin version changes.
- Create a GitHub prerelease for every beta. Rejected because the registry `dev` channel is the testing publication mechanism.
- Automatically copy every stable tag into the released registry. Rejected because stable feature completion and explicit public Release approval are separate decisions.

## Consequences

Every advertised build needs synchronized version metadata and a new immutable tag. Historical branch cleanup must preserve each legacy registry URL's commit. The repository rename and change to the `arr-stack-connector` slug must be coordinated across both registry branches, with the legacy manifest retained only as unindexed history.

## Provenance

- ChatGPT `Simplify Plugin Versioning`
- Codex `Update standalone release workflow`
- Workspace standalone standards and Dispatcharr plugin distribution profile
- Live GitHub and registry state reviewed 2026-08-22

---

# ADR-024: Search Original Provider Catalogs and Materialize Only the Grabbed Variant

## Status

Accepted

## Date

2026-08-12

## Decision

Interactive searches query the enabled original Xtream VOD accounts configured in Dispatcharr rather than only its deduplicated XC output. Return separate synthetic releases for matching raw variants so Sonarr and Radarr can distinguish available resolution, codec, audio, and dynamic-range choices.

If the chosen raw movie or episode was omitted by normal Dispatcharr import deduplication, create only the missing relation for that exact provider account and stream at grab time. Do not bulk-import or maintain a competing VOD catalog.

## Reason

The deduplicated catalog can collapse multiple encodes of the same TMDB title into one item. The purpose of interactive search is to expose real provider choices while retaining Dispatcharr as the VOD authority.

## Alternatives Considered

- Return only the deduplicated Dispatcharr item. Rejected because it hides real quality variants.
- Let Mustarrd search providers independently. Rejected because provider ownership belongs to Dispatcharr.
- Import every raw variant permanently in advance. Rejected because it expands Dispatcharr state unnecessarily and duplicates catalog responsibility.

## Consequences

Interactive search can be more expensive and is bounded by configured limits. Exact provider account and stream identity must survive in the signed descriptor and be verified again on grab. Validation feeds remain on the separate lightweight path.

## Provenance

- ChatGPT `Sonarr Radarr VOD Connector`, 2026-08-12 discussion of collapsed results and quality variants
- Commits `3b9286b`, `0fbf846`, and `26f243c`

---

# ADR-025: Force Downloads Through an Explicit Session-Bearing Dispatcharr Proxy URL

## Status

Accepted

## Date

2026-08-12

## Decision

Require the operator to configure the Dispatcharr base URL reachable by Mustarrd. For each grab, build a native `/proxy/vod/...` URL containing a unique session identifier plus the exact provider account and stream ID.

Do not guess the Dispatcharr hostname and do not pass the provider redirect URL to Mustarrd.

## Reason

Dispatcharr's Redirect profile can issue a provider redirect before it creates the tracked proxy session when no session ID is present. Mustarrd would then bypass Dispatcharr's connection manager and the download would disappear from Dispatcharr VOD statistics. A pre-existing session ID keeps the transfer on the native proxy path, and an explicit URL avoids deployment-specific hostname assumptions.

## Alternatives Considered

- Give Mustarrd the raw provider URL. Rejected because it bypasses Dispatcharr and exposes provider details.
- Use Dispatcharr's ordinary first-request URL without a session. Rejected because Redirect profiles can bypass tracking.
- Infer `http://dispatcharr:9191`. Initially used, then superseded because that hostname is not valid in every deployment.

## Consequences

Configuration must include a Mustarrd-reachable Dispatcharr URL. Proxy-route changes in Dispatcharr require compatibility review. The signed descriptor never contains provider credentials or the final source URL.

## Provenance

- ChatGPT `Sonarr Radarr VOD Connector`, 2026-08-12 live statistics and proxy-routing validation
- Commits `0fbf846` through `fdc8099`, and `9565aa4` through `59c4d20`

---

# ADR-026: Persist Bridge State and Preserve SAB Job Identity Across Updates

## Status

Accepted

## Date

2026-08-12

## Decision

Store bridge job mappings under the persistent `/data/arr_stack_connector` state root and use namespaced `mustarrd-<id>` identifiers for new SAB-facing jobs. During the rename, move the previous `/data/dispatcharr_vod_newznab` directory to the new root while the old plugin is disabled.

Preserve raw IDs for pre-v0.1.8 jobs and recover missing category, title, and relative path from Mustarrd output paths without inventing a new SAB ID. Recompute the category-based output path when `addfile` arrives rather than trusting an older cached descriptor.

## Reason

Atomic plugin updates replace plugin files and may restart services, while Sonarr/Radarr cache download IDs and synthetic NZBs. Moving state with the plugin or changing IDs mid-job breaks queue/history association and completed import.

## Alternatives Considered

- Keep state beside plugin code. Superseded because plugin updates can replace that directory.
- Renumber every legacy job during migration. Rejected because Sonarr/Radarr may already track the original ID.
- Store the final path inside the search descriptor. Superseded because the actual SAB category is supplied only during `addfile` and cached NZBs can outlive layout changes.

## Consequences

State writes must remain atomic. Queue/history translation must tolerate both legacy raw IDs and namespaced IDs. The old state root is migration input, not an ongoing runtime fallback.

## Provenance

- ChatGPT `Sonarr Radarr VOD Connector`, 2026-08-12 queue/history/import troubleshooting
- Commits `43ee70d` through `3698f53`, and `59c4d20` through `46ec44f`

---

# ADR-027: Reuse Mustarrd Authentication and Map SAB Lifecycle Actions Completely

## Status

Accepted

## Date

2026-08-12

## Decision

Use one shared authenticated Mustarrd client per detached service configuration. Serialize session access, retain cookies and CSRF state, and authenticate again only after `401`/`403` or a connection-setting change.

Translate SAB deletion into complete Mustarrd removal: cancel an active job, delete the resulting history row when necessary, and remove the local mapping. Translate SAB retry to Mustarrd's retry endpoint while preserving the SAB-facing ID.

## Reason

Sonarr and Radarr poll queue and history concurrently and frequently. Creating a new authenticated client per request hit Mustarrd's login rate limit. A single Mustarrd delete call can intentionally leave a cancelled history row, while SAB deletion means removal from the client view.

## Alternatives Considered

- Authenticate on every queue/history request. Superseded after live `429 Too Many Requests` failures.
- Share `requests.Session` without synchronization. Rejected because cookie/session mutation is not guaranteed thread-safe.
- Cancel active jobs but retain history after SAB deletion. Rejected because it does not match the expected SAB removal action.

## Consequences

Credential changes replace and close the shared client. Authentication failures may retry once after re-login. Mustarrd API lifecycle changes require coordinated review and queue/history/delete integration testing.

## Provenance

- ChatGPT `Sonarr Radarr VOD Connector`, 2026-08-12 live `429`, deletion, and polling evidence
- Commits `bff2746`, `82b9dd7`, and `4bad78d`

---
