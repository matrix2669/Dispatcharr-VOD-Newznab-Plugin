# Branches

This ledger records why every current branch exists. GitHub remains authoritative for live refs, commits, pull requests, and checks.

## Maintenance rules

- Add or update a record before substantive work begins on a branch.
- Refresh observed heads and validation before review or promotion.
- Use a branch record as source material for a pull request, but verify it against the current diff first.
- Before deleting a branch, transfer user-visible results to `CHANGELOG.md` and durable rationale to `DECISIONS.md`, then remove its entry here.

## Branch index

| Branch | Type | Status | Base | Target | Purpose |
|---|---|---|---|---|---|
| `main` | long-lived | active | initial project history | stable source | Production-ready plugin source and explicitly approved GitHub Releases. |
| `dev` | long-lived | active | `main` | `main` | Integrate and validate the next plugin version; synchronized to stable Arr Stack Connector `0.2.0`. |
| `docs/bootstrap-release-sync` | documentation | superseded | `main` at `1b35bf4` | none | Historical bootstrap follow-up; later documentation on `main` supersedes its two commits. |
| `v0.1.0` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.0`; replace with tag `v0.1.0`. |
| `v0.1.1` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.1`; replace with tag `v0.1.1`. |
| `v0.1.2` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.2`; replace with tag `v0.1.2`. |
| `v0.1.3` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.3`; replace with tag `v0.1.3`. |
| `v0.1.4` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.4`; replace with tag `v0.1.4`. |
| `v0.1.5` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.5`; replace with tag `v0.1.5`. |
| `v0.1.6` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.6`; replace with tag `v0.1.6`. |
| `v0.1.7` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.7`; replace with tag `v0.1.7`. |
| `v0.1.8` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.8`; replace with tag `v0.1.8`. |
| `v0.1.9` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.9`; replace with tag `v0.1.9`. |
| `v0.1.10` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.10`; replace with tag `v0.1.10`. |
| `v0.1.11` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.11`; replace with tag `v0.1.11`. |
| `v0.1.12` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.12`; replace with tag `v0.1.12`. |
| `v0.1.13` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.13`; replace with tag `v0.1.13`. |
| `v0.1.14` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.14`; replace with tag `v0.1.14`. |
| `v0.1.15` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.15`; replace with tag `v0.1.15`. |
| `v0.1.16` | historical version branch | superseded | project history | immutable tag | Preserves the source advertised as plugin version `0.1.16`; replace with tag `v0.1.16`. |

## Active branch records

### `main`

- Purpose: production-ready source and the line for stable tags and explicitly approved GitHub Releases.
- Current plugin version: `0.2.0`.
- Current distribution: approved for normal GitHub Release `v0.2.0` and focused publication through the registry `main` channel.
- Promotion source: the live-tested `v0.2.0-beta.1` state, with only version and release metadata changed for the stable build.
- Last verified at: `2026-08-22`.

### `dev`

- Purpose: integrate and validate the next plugin version before promotion to `main`.
- Base: `main` at `13c5d114fce94ae4c802128bae224d8623163141`.
- Current plugin version: `0.2.0`.
- Current state: synchronized to the completed stable source promoted to `main` and approved for release.
- Intended target: `main` after versioned testing is complete.
- Validation: 28 unit tests pass; all Python modules compile; `plugin.json` parses; version and identity assertions agree; the beta installed successfully on Dispatcharr; and the clean release ZIP is required to contain only the top-level `arr-stack-connector/` directory.
- Last verified at: `2026-08-22`.

## Historical branch cleanup

The `v0.1.0` through `v0.1.16` branches are remnants of the former registry workflow. Before deleting them, create immutable tags with the same names at the exact recorded branch heads and verify every existing registry archive resolves to the same commit. The `docs/bootstrap-release-sync` branch may be deleted after confirming its useful results are already present or superseded on `main`. Remove these entries only after the remote branches are actually deleted.
