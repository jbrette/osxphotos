# Developer Notes for osxphotos

These are notes for developers working on osxphotos. They're mostly to help me remember how to do things in this repo but will be useful to anyone who wants to contribute to osxphotos.

## Installing osxphotos

osxphotos requires python 3.14 or later and uses [uv](https://docs.astral.sh/uv/) to manage the development environment.

- Clone the repo: `git clone git@github.com:RhetTbull/osxphotos.git`
- Install [uv](https://docs.astral.sh/uv/getting-started/installation/), e.g. `brew install uv`
- Create the virtual environment (`.venv`) with python 3.14, osxphotos (editable) and all development dependencies in one step:

```bash
uv sync
```

The `dev` dependency group in `pyproject.toml` holds everything that was previously in `dev_requirements.txt` (pytest, ruff, sphinx, bump-my-version, etc.) and is installed by `uv sync` by default. Exact versions are pinned in `uv.lock`. Run tools in the environment with `uv run`, e.g. `uv run osxphotos --help`. To add or change a dependency use `uv add PACKAGE` (or `uv add --dev PACKAGE` for a development tool), which updates both `pyproject.toml` and `uv.lock`.

## Running tests

- Run all tests: `uv run pytest`

See the [test README.md](tests/README.md) for more information on running tests.

## Opening a pull request

If you want to contribute to osxphotos, please open a pull request. Here's how to do it:

- Fork the repo on GitHub
- Clone your fork: `git clone git@github.com:YOUR_USERNAME/osxphotos.git`
- Create a virtual environment and install osxphotos as described above
- Create a branch for your changes: `git checkout -b my_branch`
- Make your changes
- Add tests for your changes
- Run the tests: `uv run pytest`
- Lint and format the code: `uv run ruff check --fix` then `uv run ruff format` (ruff also sorts imports; `ruff check` must pass cleanly)
- Update the README.md and other files as needed
- Add your changes using `git add`
- Commit your changes: `git commit -m "My changes description"`
- Push your changes to your fork: `git push origin my_branch`
- Open a [pull request on GitHub](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request)

## Building the package and executable

**Note**: Do not do this unless you are releasing a new version of osxphotos. This should not be run for normal pull requests. In general, only the maintainer should run the build script.

- Run `./build.sh` to run the build script.

## Release

For release, follow the following steps:

0. Create a new branch for the release: `git checkout -b release_v0.75.10`
1. Bump the version using `bump-my-version` (replaces `bump2version`):
   ```bash
   uv run bump-my-version bump [major|minor|patch] --verbose
   ```
   This updates `osxphotos/_version.py`, `applecrate.toml`, and the `current_version` in `pyproject.toml` in one step.
2. Run the `build.sh` script
3. Commit the changes and push to GitHub
4. Merge the changes into the main branch
5. Checkout the main branch: `git checkout main`
6. Pull the changes to your local repository: `git pull`
7. Upload to PyPI: `uv run twine upload dist/osxphotos*.whl dist/*.tar.gz`
8. Create a new release on GitHub: `gh release create "v0.75.10" dist/*`
9. Pull the changes to your local repository: `git pull`

The GitHub release must occur *after* the `twine upload` command so the GitHub action that updates the homebrew formula can be triggered.

## pyproject.toml is the single source of truth

The project has been fully migrated from `setup.py` to `pyproject.toml`. The following files are **no longer used** and have been deleted:

| Deleted file | Replaced by |
|---|---|
| `setup.py` | `[project]` section in `pyproject.toml` |
| `requirements.txt` | `[project].dependencies` in `pyproject.toml` |
| `dev_requirements.txt` | `[dependency-groups].dev` in `pyproject.toml` |
| `pytest.ini` | `[tool.pytest.ini_options]` in `pyproject.toml` |
| `.isort.cfg` | `[tool.isort]` in `pyproject.toml` |
| `.bumpversion.cfg` | `[tool.bumpversion]` in `pyproject.toml` |
| `MANIFEST.in` | `[tool.setuptools.package-data]` in `pyproject.toml` |

### Important: data directories

`osxphotos/docs`, `osxphotos/templates`, `osxphotos/queries`, `osxphotos/lib`, and `osxphotos/share` are **data-only directories** — they have no `__init__.py`. The original `setup.py` included them by manually appending them to the `packages` list (a common workaround). The `pyproject.toml` handles this correctly via `[tool.setuptools.package-data]`.

## Other Notes

[cogapp](https://nedbatchelder.com/code/cog/index.html) is used to update the README.md and other files. cog will be called from the build script as needed.

There are some pre-built libraries in the `osxphotos/lib` directory. These are used by osxphotos to handle permissions. If you need to rebuild these libraries, see the [README_DEV.md](osxphotos/lib/README_DEV.md) file in the `osxphotos/lib` directory.
