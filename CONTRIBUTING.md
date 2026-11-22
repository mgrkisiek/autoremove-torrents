# Contributing

Thanks for helping improve autoremove-torrents! Bug reports, fixes and new features are welcome.

## Reporting bugs

Open an [issue](https://github.com/mgrkisiek/autoremove-torrents/issues) with:

- the version (`autoremove-torrents` prints it at the start of every run) and how you installed it (pip or Docker);
- your torrent client and its version;
- your configuration, **with passwords and hostnames removed**;
- the log output, preferably from a run with `--debug`.

## Development setup

```sh
git clone https://github.com/mgrkisiek/autoremove-torrents.git
cd autoremove-torrents
python -m venv .venv
. .venv/bin/activate
pip install -e ".[test]"
```

## Running tests

```sh
pytest --deselect tests/test_clients/test_clients.py::test_client
flake8 . --select=E9,F63,F7,F82
```

`test_client` talks to real qBittorrent, Transmission, Deluge and μTorrent instances. The CI workflow
([.github/workflows/build.yml](.github/workflows/build.yml)) starts them as Docker services and runs the full suite on
every push and pull request.

## Pull requests

- Keep each pull request focused on one change and add tests for new behaviour.
- Strategy tests are data-driven: add a YAML case under `tests/test_strategies/cases/`.
- Update [docs/config.rst](docs/config.rst) for new options and add an entry to [docs/changelog.rst](docs/changelog.rst).
- Never commit real credentials. Use `config.example.yml` and `.env.example` for examples.

## Releasing

1. Update `__version__` in [autoremovetorrents/version.py](autoremovetorrents/version.py) and the date in the changelog.
2. Commit, then tag and push: `git tag v1.6.0 && git push origin v1.6.0`.
3. The release workflow builds the Python packages, publishes the Docker image to
   `ghcr.io/mgrkisiek/autoremove-torrents` and creates a GitHub release.
