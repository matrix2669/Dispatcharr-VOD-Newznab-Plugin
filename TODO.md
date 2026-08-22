# TODO.md

## Arr Stack Automation Roadmap

### Background VOD Stream Discovery and Cache

- Create an idle/background process to scan available Dispatcharr VOD content.
- Probe VOD streams when system resources are available.
- Store probed stream metadata in a persistent cache.
- Use cached stream data for faster Sonarr/Radarr searches.
- Validate cached objects when Dispatcharr VOD data is refreshed.
- Remove cached entries for VOD content that is no longer available.
- Evaluate a long cache TTL (approximately 6 months) because VOD availability is expected to change less frequently than metadata.

### RSS Feed Support

- Build Newznab RSS feed support from cached VOD stream data.
- Allow Sonarr/Radarr automatic downloads once reliable cached release data exists.
- Ensure RSS generation does not perform expensive live provider searches or ffprobe operations.

### Season Pack Support

- Investigate whether Dispatcharr VOD metadata contains enough information to generate Sonarr-compatible season packs.
- Determine how season packs should map to individual episodes and download requests.

## Reliability Improvements

### Mustarrd Availability Handling

- Verify current behavior when Mustarrd is unavailable.
- Return a SAB-compatible error to Sonarr/Radarr when downloads cannot be handed off.
- Match expected behavior of existing SAB download client failures.

## Future Media Types

- Evaluate whether Dispatcharr VOD catalogs contain sports, events, or other non-movie/non-TV content.
- Define handling rules before supporting additional media categories.

## Testing Expansion

- Add automated validation tests.
- Add Sonarr integration testing.
- Add Radarr integration testing.
- Add Mustarrd handoff and failure-path testing.
- Add cache lifecycle testing.
