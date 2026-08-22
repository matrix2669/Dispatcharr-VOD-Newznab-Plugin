# Release Process

## Version rules

- Use Semantic Versioning in `VERSION`, `Plugin.version`, and `arr-stack-connector/plugin.json`.
- Prefix Git tags with `v`; store versions without `v` in files.
- Use `MAJOR.MINOR.PATCH-beta.N` for test tags and increment `N` for every published beta of the same target version.
- Use a normal `MAJOR.MINOR.PATCH` tag when feature or fix work is complete.
- Never move a published tag, replace an advertised archive, or mutate an existing Release. Corrections receive a new version.
- Keep the registry slug and source archive directory `arr-stack-connector` synchronized with the normalized Dispatcharr installation key `arr_stack_connector`.

## Required validation

Run:

```bash
python3 -m unittest discover -s arr-stack-connector/tests -v
python3 -m py_compile arr-stack-connector/plugin.py arr-stack-connector/service.py arr-stack-connector/servarr_bridge/*.py
python3 -m json.tool arr-stack-connector/plugin.json >/dev/null
```

Also verify:

- `VERSION`, `Plugin.version`, and `plugin.json` agree;
- the exact tag archive exposes `arr-stack-connector/plugin.json` beneath the stable source directory and Dispatcharr installs it as `arr_stack_connector`;
- installation and update preserve saved settings, API key, state files, and the managed service lifecycle;
- Dispatcharr loads the plugin under the existing normalized key;
- Sonarr and Radarr validation, interactive search, grab, queue, history, retry, and deletion still work;
- Mustarrd receives a Dispatcharr-native VOD proxy URL and reports completion through the existing SAB-compatible layout.

If the supported, minimum, tested, or deployed Dispatcharr version changed, complete the official-repository compatibility refresh gate in `AGENT.md` before tagging or publishing.

## Beta tag and testing registry

1. Integrate the intended work into `dev` and complete required validation.
2. Set the beta version consistently in all three version sources.
3. Finalize the matching changelog section.
4. Commit the exact tested state on `dev` and create the immutable `vMAJOR.MINOR.PATCH-beta.N` tag.
5. Push the tag without creating a GitHub prerelease.
6. Update only `matrix2669/dispatcharr-plugins:dev` to the exact tag, commit, version, repository URL, and archive URL.
7. Validate an actual Dispatcharr update from the previously advertised version.

Untagged `dev` commits are development state. Dispatcharr update detection is version-driven, so they do not replace a published test build.

## Completed stable tag

1. Confirm feature/fix work and testing are complete on `dev`.
2. Replace any beta version with the final `MAJOR.MINOR.PATCH` consistently.
3. Promote the exact tested state to `main` without unrelated changes.
4. Run the complete release validation again on `main`.
5. Create and push the immutable normal tag `vMAJOR.MINOR.PATCH`.
6. Point `dispatcharr-plugins:dev` at this newest completed tag.
7. Synchronize `dev` with the completed stable state.

A completed stable tag does not automatically authorize a GitHub Release or publication through `dispatcharr-plugins:main`.

## GitHub Release and stable registry

Only proceed after the user explicitly approves a GitHub Release for the exact stable tag.

1. Build `dispatcharr-arr-stack-plugin-vMAJOR.MINOR.PATCH.zip` with this layout:

   ```text
   arr-stack-connector/
   ├── plugin.json
   ├── plugin.py
   ├── service.py
   └── servarr_bridge/
   ```

   Include the tests only when intentionally distributing them; never include repository documentation as a sibling of the plugin files inside the source directory.
   Build from the committed release tree so generated Python caches and macOS metadata cannot enter the artifact:

   ```bash
   git archive \
     --format=zip \
     --prefix=arr-stack-connector/ \
     --output=dispatcharr-arr-stack-plugin-vMAJOR.MINOR.PATCH.zip \
     HEAD:arr-stack-connector
   ```
2. Produce a SHA-256 checksum and validate installation from a clean extraction.
3. Publish a normal GitHub Release from the existing immutable tag with release notes, the ZIP, and its checksum.
4. Make a focused `dispatcharr-plugins:main` update referencing the exact released tag, commit, version, minimum Dispatcharr version, repository URL, and verified archive.
5. Validate a clean install and an update through the stable registry.

GitHub's automatic source archive does not replace the documented manual ZIP for users installing without the registry.

## Public repository rename

Rename the GitHub repository to `matrix2669/Dispatcharr-Arr-Stack-Plugin` only as a coordinated publication step. Update source documentation and both registry branches to the canonical URL, verify GitHub's old URL redirect, refresh local remotes, and confirm old installed versions can still download their immutable archives. The repository rename must not be combined with a plugin slug or state-path migration.
