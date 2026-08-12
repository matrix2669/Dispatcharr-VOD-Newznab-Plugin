# Dispatcharr VOD Newznab Plugin

A Dispatcharr plugin that exposes **raw Xtream VOD provider variants** to Sonarr and Radarr as a Newznab indexer and emulates the subset of SABnzbd used by Servarr. Selected releases are handed to Mustarrd for the actual download/remux lifecycle.

## Architecture

```text
Sonarr / Radarr
  ├─ Newznab Interactive Search ─┐
  └─ SABnzbd Download Client ────┤
                                ▼
                  Dispatcharr VOD Newznab Plugin
                    ├─ raw enabled Xtream accounts
                    ├─ TMDB matching + ffprobe
                    ├─ DV/HDR10+/HDR10/HDR/SDR naming
                    ├─ output templates
                    └─ SAB queue/history translation
                                │
                                ▼
                    Dispatcharr native VOD proxy
                                │
                                ▼
                           Mustarrd API
                                │
                     downloads → completed
                                │
                                ▼
                         Sonarr / Radarr import
```

The plugin deliberately queries the **original Xtream providers configured in Dispatcharr**, not Dispatcharr's deduplicated XC VOD output. This allows multiple 720p/1080p/2160p/HDR/DV variants of the same TMDB title to appear in Interactive Search.

When a selected raw variant was skipped by Dispatcharr's normal importer, the plugin materializes only the missing provider relation needed for that grabbed stream. Mustarrd is then given a native Dispatcharr `/proxy/vod/...` URL pinned to the selected account and stream ID.

The proxy URL contains a unique VOD session ID in the path. This intentionally bypasses Dispatcharr's first-request **Redirect** behavior for Mustarrd jobs, so the media bytes pass through Dispatcharr's VOD connection manager and remain visible in Dispatcharr VOD statistics even when the global default stream profile is Redirect.

## Requirements

- A current Dispatcharr build with plugin support.
- `ffprobe` available at `/usr/bin/ffprobe` by default. The path is configurable.
- Mustarrd with `POST /api/vod/external/download` support.
- A dedicated local Mustarrd user is recommended for the plugin.
- Mustarrd must be able to reach the configured **Dispatcharr URL Seen by Mustarrd**.
- The Mustarrd completed folder must be mounted into Sonarr/Radarr. Configure **Completed Directory Seen by Sonarr/Radarr** to the path those applications see.

## Install

Install from the Matrix2669 Dispatcharr plugin registry. Dispatcharr normalizes the installed plugin key to underscores, so the installed directory is normally:

```text
/data/plugins/dispatcharr_vod_newznab/
```

Then reload plugins in Dispatcharr and enable **Dispatcharr VOD Newznab**. When enabled, the plugin starts one managed service process (default port `9192`) even when Dispatcharr has multiple uWSGI workers.

An API key is generated automatically on first enable. Use the plugin's **Service Status** action to display the service status and key.

## Dispatcharr plugin settings

Important settings:

- **Listen Address / Port**: defaults to `0.0.0.0:9192`.
- **Newznab / SAB API Key**: generated automatically.
- **Dispatcharr URL Seen by Mustarrd**: defaults to `http://dispatcharr:9191`. Set this to the Dispatcharr base URL that Mustarrd can actually reach.
- **Mustarrd URL / Username / Password**: credentials for a local Mustarrd user.
- **Mustarrd Account ID**: existing Mustarrd account used for job ownership/concurrency.
- **Completed Directory Seen by Sonarr/Radarr**: e.g. `/completed`.
- **Movie Output Template** and **TV Output Template**: resolved by this plugin and sent to Mustarrd as a safe relative output path.
- **ffprobe Path**: defaults to `/usr/bin/ffprobe`.
- **Respect Enabled Dispatcharr VOD Groups**: limits raw provider results to VOD categories enabled for each account in Dispatcharr.

Default movie template:

```text
mustarrd/Movies/{title} ({year}) {tmdb_tag}/{release}.{ext}
```

Default TV template:

```text
mustarrd/TV Shows/{series} ({year}) {tmdb_tag}/Season {season:02d}/{release}.{ext}
```

If a provider title already ends in the same `(year)`, the template renderer strips that copy before adding the configured year token.

Available movie tokens: `{title}`, `{year}`, `{tmdb_id}`, `{tmdb_tag}`, `{release}`, `{ext}`.

TV also supports: `{series}`, `{season}`, `{episode}`.

## Service logging and diagnostics

The plugin uses Dispatcharr's `apps.plugins.loader` logger for plugin lifecycle messages, prefixed with `[Dispatcharr VOD Newznab]`.

The detached Newznab/SAB service writes its own rotating log beside the installed plugin:

```text
/data/plugins/dispatcharr_vod_newznab/servarr_service.log
```

The log rotates at 5 MB and keeps three backups. Very early child-process stdout/stderr is captured separately in:

```text
/data/plugins/dispatcharr_vod_newznab/servarr_service_bootstrap.log
```

Routine `/health` probes are logged only at DEBUG.

## Radarr / Sonarr indexer

Add a generic Newznab indexer using:

```text
http://DISPATCHARR_HOST:9192/api
```

Use the generated plugin API key.

Set the indexer to **Interactive Search only**:

- RSS: disabled
- Automatic Search: disabled
- Interactive Search: enabled

The plugin advertises:

```text
movie-search: q,tmdbid
tv-search:    q,tmdbid,season,ep
```

## SABnzbd download client

Add SABnzbd to Sonarr/Radarr with:

```text
Host: DISPATCHARR_HOST
Port: 9192
API Key: <same plugin API key>
```

Recommended categories:

```text
Sonarr: sonarr
Radarr: radarr
```

The plugin implements the Servarr-used SAB modes:

- `version`
- `get_config`
- `fullstatus`
- `addfile`
- `queue`
- `history`
- queue/history delete
- `retry`

## Search behavior

### Movies

Radarr's TMDB ID is matched against each enabled original Xtream provider. Every exact raw stream match is probed (up to the configured maximum) and returned as a separate release.

### TV

Sonarr's TMDB ID selects raw provider series. Exact episode searches probe the actual episode stream. Season searches use provider episode metadata to avoid probing an entire season.

Dynamic range classification order is:

```text
DV → HDR10+ → HDR10 → HDR → SDR
```

Dolby Vision detection precedes HDR10 because DV streams may expose PQ/BT.2020 fallback metadata.

## Synthetic NZBs and download routing

Newznab results contain a small signed synthetic NZB. It contains no provider username/password or provider source URL.

On `addfile`, the plugin verifies the descriptor and resolves the exact account/stream again. If Dispatcharr's importer did not retain that raw variant, the plugin creates the missing `M3UMovieRelation` or `M3UEpisodeRelation` for that real provider stream. The source passed to Mustarrd is then a Dispatcharr-native proxy URL of the form:

```text
http://DISPATCHARR:9191/proxy/vod/movie/<uuid>/mustarrd_<session>?m3u_account_id=<id>&stream_id=<provider-stream-id>
```

Episodes use `/proxy/vod/episode/...` in the same way.

Because the session ID is already present, Dispatcharr skips the initial Redirect branch and proxies the transfer through its VOD connection manager. The selected provider variant therefore appears in Dispatcharr's active VOD statistics while Mustarrd downloads it.

## State

`servarr_jobs.json` is written beside the plugin and stores only the mapping needed to translate Mustarrd jobs back to SAB category/title/output path. Provider passwords are not written to this file.

## Development tests

Pure helper tests can be run without a Dispatcharr instance:

```bash
python -m unittest discover -s tests -v
```

End-to-end provider, Django model, Newznab, SAB, native VOD proxy, and Mustarrd tests require a running Dispatcharr/Mustarrd environment.
