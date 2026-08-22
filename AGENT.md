# AGENT.md

## Purpose

This repository owns the **Dispatcharr Arr Stack Plugin**, formerly named **Dispatcharr VOD Newznab Plugin**. It exposes raw Dispatcharr VOD variants to Sonarr and Radarr through a Newznab-compatible indexer, emulates the SABnzbd API subset those applications use, and hands selected downloads to Mustarrd.

The rename changes both the public and installed plugin identity through a documented one-time migration. Review `DECISIONS.md`, `BRANCHES.md`, and `RELEASE.md` before making changes.

## Architecture

- `arr-stack-connector/plugin.json` declares Dispatcharr settings, actions, public display metadata, and the plugin version.
- `arr-stack-connector/plugin.py` owns plugin lifecycle, one detached-service process, health actions, and API-key initialization.
- `arr-stack-connector/service.py` initializes Django and logging before starting the detached service.
- `arr-stack-connector/servarr_bridge/server.py` exposes Newznab, synthetic NZB, SAB-compatible, and health endpoints.
- `provider.py` queries enabled original Xtream providers, matches content identifiers, materializes a missing Dispatcharr relation only when required, and builds a Dispatcharr-native proxy URL pinned to the selected account and provider stream.
- `newznab.py`, `recent.py`, `releases.py`, and `probe.py` own search responses, lightweight validation feeds, compatible release naming, and media probing.
- `sab.py` translates Mustarrd queue/history state into SAB-compatible responses.
- `mustarrd.py` maintains the shared authenticated Mustarrd client.
- `tests/test_core.py` covers portable helpers and isolated lifecycle behavior.

Data flow:

```text
Sonarr / Radarr
  ├─ Newznab validation or interactive search
  └─ SABnzbd-compatible grab / queue / history
                         │
                         ▼
             Dispatcharr Arr Stack Plugin
  raw provider matching ─ synthetic signed NZB ─ SAB translation
                         │
                         ▼
          Dispatcharr native VOD proxy URL
                         │
                         ▼
                      Mustarrd
                         │
                         ▼
             Sonarr / Radarr import and rename
```

## Ownership boundaries

- Dispatcharr owns the plugin API, manifest contract, VOD catalog models, provider accounts, native proxy behavior, connection tracking, and installation/update behavior.
- This repository owns Sonarr/Radarr compatibility, raw-variant search, synthetic release metadata, exact-stream resolution, plugin service lifecycle, SAB translation, and Mustarrd handoff.
- Mustarrd owns authentication for its API, job execution, concurrency, retries, queue state, remuxing, and completion.
- Sonarr and Radarr own media matching after acquisition, imports, final naming, organization, and downstream media-library integration.
- `matrix2669/dispatcharr-plugins` owns which immutable tag its `dev` and `main` channels advertise; it does not own plugin behavior.

## Non-negotiable rules

- Route downloads through Dispatcharr's native VOD proxy. Do not expose provider credentials or raw provider URLs to Sonarr, Radarr, synthetic NZBs, or Mustarrd.
- Keep provider selection and VOD connection accounting in Dispatcharr.
- Keep the download lifecycle in Mustarrd; do not turn the plugin into a second downloader.
- Preserve signed synthetic descriptors and re-resolve the exact account and stream at grab time.
- Keep validation and recent-feed paths lightweight. Do not perform full provider scans, metadata enrichment, or ffprobe work during frequent validation/RSS requests.
- Probe only when accurate codec, resolution, dynamic range, or audio metadata is required. Resolve ffprobe dynamically across supported Dispatcharr layouts.
- Preserve the SAB category/job layout `mustarrd/<category>/<release>/<release>.<ext>` and report paths as Sonarr/Radarr see them.
- Reuse a shared authenticated Mustarrd session and serialize access that can be polled concurrently. Do not restore per-request login behavior.
- Avoid duplicate detached service instances and preserve update-safe service restart behavior.
- Multiple Dispatcharr instances from one plugin instance are out of scope.
- The Dispatcharr URL setting is an external reachability exception, not an instruction to call Dispatcharr's administrative API. It supplies Mustarrd with a native media proxy URL and must never be paired with Dispatcharr credentials.

## Rename compatibility contract

The public project name is **Dispatcharr Arr Stack Plugin** and the in-Dispatcharr display name is **Arr Stack Connector**.

The rename intentionally changes the public plugin identity:

- registry slug and source archive directory: `arr-stack-connector`;
- normalized installed directory/key: `arr_stack_connector`;
- state root: `/data/arr_stack_connector`;
- plugin-owned environment variables: `ARR_STACK_CONNECTOR_*`.

Preserve the `servarr_bridge` Python package, settings field IDs, API routes, port defaults, descriptor format, namespaced job IDs, and Newznab/SAB behavior. Those contracts allow the existing configuration values and Sonarr/Radarr setup to be copied to the renamed plugin.

This is a one-time manual migration for existing installations. Disable the old plugin first, migrate `/data/plugins/dispatcharr_vod_newznab` to `/data/plugins/arr_stack_connector`, migrate `/data/dispatcharr_vod_newznab` to `/data/arr_stack_connector`, install the new slug, copy the old settings/API key into the new plugin record, and verify service health before deleting the old plugin entry. Do not run both identities simultaneously because they use the same default port.

The canonical GitHub repository is `matrix2669/Dispatcharr-Arr-Stack-Plugin`. Preserve the old GitHub URL redirect and verify every historical archive before changing or deleting legacy references.

## Development workflow

This is a standalone Dispatcharr plugin:

- `main` is production-ready and contains explicitly approved GitHub Releases.
- `dev` integrates the next version.
- short-lived `feature/*` and `fix/*` branches start from and return to `dev`.
- immutable beta tags use `vMAJOR.MINOR.PATCH-beta.N` on tested `dev` commits.
- completed stable work uses a normal Semantic Version tag; a completed tag does not require a GitHub Release.
- permanent version branches are historical and must not be created for new versions.

Record every current branch in `BRANCHES.md` before substantive work. Before deleting a branch, transfer user-visible results to `CHANGELOG.md` and durable rationale to `DECISIONS.md`, then remove its live branch record.

## Version and distribution requirements

- `VERSION`, `Plugin.version`, `plugin.json`, the changelog version, and Git tag must agree for a published build.
- Dispatcharr updates are version-driven. Untagged branch movement does not replace an advertised build.
- `dispatcharr-plugins:dev` advertises the newest approved immutable tag: beta while testing is active, otherwise the latest completed stable tag.
- `dispatcharr-plugins:main` advertises only a stable tag that has an explicitly approved GitHub Release.
- Never merge the registry's `dev` channel wholesale into `main`; publication is a focused metadata update.
- Preserve older versions in the per-plugin manifest and never move a published tag or replace an advertised archive.
- Follow `RELEASE.md` and inspect the exact tagged archive layout before publication.

## Dispatcharr compatibility refresh gate

The current recorded minimum is Dispatcharr `v0.29.0`. Whenever the supported, minimum, tested, or deployed Dispatcharr version changes, revalidate this plugin and its registry manifest against the matching revision of the official `Dispatcharr/Dispatcharr` repository before tagging or publishing.

Baseline evidence: Dispatcharr `v0.29.0` at `d9abece081c9edf637d4c3fdd41443eb993a3c08` was reviewed on 2026-08-22. Its registry installer sanitizes hyphens to underscores, so slug `arr-stack-connector` installs as key/directory `arr_stack_connector`. Its plugin loader derives the key from that installed directory, reads `plugin.json` without executing disabled plugin code, and supports the field/action shapes used here. Its VOD proxy accepts the preferred account/stream parameters used here and bypasses the Redirect-to-provider path when a session is already present. Its movie and episode relations remain unique by `(m3u_account, stream_id)`.

Mustarrd integration was refreshed against `matrix2669/mustarrd:dev` at `7c56b83879f76faff8f303c139063a1f51a75431` on 2026-08-22. The external VOD endpoint still accepts the account, media ID, title, absolute source URL, relative output path, and duration used here; authentication still uses session cookies plus CSRF; active deletion still returns `cancelled` before finished-history deletion; and retry still accepts failed or cancelled jobs.

Record the Dispatcharr version or tag, exact commit, repository URL, review date, and relevant findings. Inspect at minimum:

- plugin discovery and `plugin.json` field/action schema;
- plugin lifecycle, settings persistence, action results, and multi-worker loading;
- VOD movie/episode/account/relation models used by provider lookup;
- native VOD proxy routing, stream profiles, session handling, and connection tracking;
- archive download, extraction, plugin-directory discovery, version comparison, and minimum-version handling;
- root and per-plugin registry manifest fields;
- installation and update behavior for the proposed archive.

Treat a `min_dispatcharr_version` change or an upgrade of the validation instance as a Dispatcharr version change. If the matching official revision cannot be verified, stop publication rather than relying on cached assumptions.

## Validation

For every change run:

```bash
python3 -m unittest discover -s arr-stack-connector/tests -v
python3 -m py_compile arr-stack-connector/plugin.py arr-stack-connector/service.py arr-stack-connector/servarr_bridge/*.py
python3 -m json.tool arr-stack-connector/plugin.json >/dev/null
```

Also check version agreement, Git whitespace, documented branch state, and the exact archive layout. Branding changes require tests or direct inspection proving that public names changed while compatibility identifiers did not.

Behavioral or compatibility changes require applicable live validation:

- clean install and update from the previous registry version;
- plugin discovery, enable/disable, service health, and restart;
- Sonarr and Radarr validation;
- interactive movie and episode search and grab;
- SAB queue, history, retry, and deletion;
- Mustarrd queue and completion behavior;
- native Dispatcharr VOD statistics during the download;
- state recovery after Dispatcharr and plugin restart.

## Known pitfalls

- A GitHub repository redirect does not migrate Dispatcharr's plugin key, saved settings, or persistent state. Follow the one-time migration sequence and validate the new identity before deleting the old one.
- Existing versions were published as branches rather than tags. Create equivalent immutable tags at the exact branch heads and verify registry resolution before deleting those branches.
- Dispatcharr deployments have used more than one application and Python layout; do not hard-code one.
- Dispatcharr's Redirect profile can bypass VOD statistics when no session is present. Preserve the explicit session-bearing native proxy URL.
- Sonarr and Radarr poll validation, queue, and history frequently. Avoid expensive feed work and repeated Mustarrd authentication.
- A cached synthetic NZB may outlive plugin changes. Recompute the output path and resolve stream identity at `addfile` time.

## Future-agent checklist

- [ ] Read `AGENT.md`, `DECISIONS.md`, `BRANCHES.md`, `CHANGELOG.md`, and `RELEASE.md`
- [ ] Review all relevant project conversations, repository history, and related project contracts
- [ ] Confirm branch base, intended target, next version, and registry channel
- [ ] Refresh the `BRANCHES.md` record before substantive work
- [ ] Preserve the rename compatibility contract
- [ ] If any Dispatcharr version changed, complete and record the compatibility refresh gate
- [ ] Run proportionate automated and live validation
- [ ] Verify version agreement and immutable archive layout before tagging
- [ ] Obtain explicit approval before a GitHub Release or `dispatcharr-plugins:main` update
