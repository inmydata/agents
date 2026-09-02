# Releasing

This package is published to PyPI as [`inmydata`](https://pypi.org/project/inmydata/).

Releases are driven by tags. Pushing a `v*` tag runs
[`.github/workflows/publish.yml`](.github/workflows/publish.yml), which builds the sdist and
wheel, runs the tests on the oldest and newest supported Python, and uploads to PyPI. Merging to
`main` publishes nothing, so an ordinary merge is never a release.

## One-time setup on PyPI

The workflow authenticates with **trusted publishing** (OIDC), so there is no API token in this
repository or on anyone's laptop. This has to be configured once, and until it is, tag pushes
will build and test but fail at the upload step.

On <https://pypi.org/manage/project/inmydata/settings/publishing/>, add a GitHub publisher:

| Field | Value |
| --- | --- |
| Owner | `inmydata` |
| Repository name | `agents` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

The environment name must match, because the workflow's `publish` job runs in an environment
called `pypi`. If you want a human approval step between pushing the tag and the upload
happening, add a protection rule to that environment under the repository's
Settings → Environments.

## Cutting a release

1. **Decide the version.** This package is pre-1.0, so breaking changes go in a patch bump, but
   they must be written up. Anything that changes what existing calling code does needs release
   notes in [README.md](README.md) under a `### x.y.z` heading, as 0.0.19 does.
2. **Bump `version` in [`pyproject.toml`](pyproject.toml)** and land it on `main` through a pull
   request, together with the release notes.
3. **Tag the commit on `main`** that carries the new version, and push the tag:

   ```bash
   git checkout main
   git pull
   git tag v0.0.20            # must match pyproject.toml exactly, with a v prefix
   git push origin v0.0.20
   ```

   Tag the merge commit on `main`, not the tip of the feature branch. The workflow refuses to
   publish if the tag number and `pyproject.toml` disagree, which catches the usual mistake of
   tagging before the bump has landed.
4. **Watch the run** under the Actions tab. On success the version appears on PyPI within a
   minute or so.
5. **Check it installs**, from a clean environment:

   ```bash
   pip install --no-cache-dir inmydata==0.0.20
   python -c "import inmydata; print(inmydata.__name__)"
   ```

Existing tags are lightweight (`git tag v0.0.20`), so keep using that form for consistency.

## Rehearsing without publishing

Run the workflow manually from the Actions tab with the **Publish** input left off. It builds,
checks and tests, and skips the upload. Useful for confirming a version bump is sound before
committing to a tag.

## Publishing by hand

Only needed if the workflow is unavailable, or for a release predating it. PyPI does not allow a
version to be replaced once uploaded, so get the version right first.

Build from a checkout of the tag, not from a feature branch, so that what you upload is what the
tag says. Do the whole thing in a virtualenv: `build` and `twine` are release tooling and do not
belong in a system-wide Python, and on Windows `py` often resolves to an install under
`C:\Program Files` where they are unwelcome.

```bash
git checkout main && git pull          # or: git checkout v0.0.20
rm -rf dist                            # stale artefacts would be re-uploaded and fail
py -m venv .venv                       # .venv is gitignored
.venv/Scripts/python -m pip install --upgrade build twine   # Linux/macOS: .venv/bin/python
.venv/Scripts/python -m build          # writes dist/*.tar.gz and dist/*.whl
.venv/Scripts/python -m twine check --strict dist/*
.venv/Scripts/python -m twine upload dist/*
```

`twine upload` prompts for credentials: the username is the literal `__token__` and the password
is a PyPI API token, `pypi-` prefix included. Generate one at
<https://pypi.org/manage/account/token/>, scoped to this project. Tokens are shown once, so if
you cannot find an old one, issue a new token and revoke the old.

Before uploading it is worth confirming the artefact itself, since this is the last point at
which a mistake is cheap:

```bash
py -m venv /tmp/smoke
/tmp/smoke/Scripts/python -m pip install --no-cache-dir dist/inmydata-0.0.20-py3-none-any.whl
/tmp/smoke/Scripts/python -c "import inmydata; from importlib.metadata import version; print(version('inmydata'))"
```

`dist/` is gitignored; do not commit build artefacts. That is what happened up to 0.0.18 and was
stopped deliberately in `beb4029`.

## Version history and tags

Tagging was inconsistent before this document existed. Only `v0.0.15` and `v0.0.17` were tagged
at the time; `0.0.12`, `0.0.13`, `0.0.14`, `0.0.16` and `0.0.18` all appear as versions in
`pyproject.toml` history with no tag. `v0.0.18` and `v0.0.19` were added retrospectively,
`v0.0.18` pointing at `d8b424b`, the commit that both set the version and carried the built
artefacts. The earlier gaps have been left alone.

`v0.0.19` was tagged before this workflow existed, so nothing fired for it, and 0.0.19 was
never published. `0.0.20` was published by hand for the same reason and tagged afterwards.

Re-running a release, or tagging a version that is already on PyPI, is safe: the publish step
passes `skip-existing`, so an existing version is skipped rather than failing the run. PyPI
never allows a version to be replaced, so nothing can be overwritten either way. What the
workflow does still refuse is a tag whose number disagrees with `pyproject.toml`, which is the
mistake worth catching.

Every future release should have a tag, because the tag is what triggers publishing.
