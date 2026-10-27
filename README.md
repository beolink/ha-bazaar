# Bazaar

*Unofficial catalog of HACS-ready repositories for Home Assistant.*

Home Assistant integrations, dashboard cards and themes that HACS can install but does not list yet.

Over a thousand repositories wait in the review queue of [hacs/default](https://github.com/hacs/default/pulls), some of them for months, and many more carry a `hacs.json` without ever having been submitted. HACS can install every one of them as a custom repository, but only if you already know where to look. Bazaar is the place to look.

It has two parts:

- **The catalog** at [beolink.github.io/ha-bazaar](https://beolink.github.io/ha-bazaar/), rebuilt every night. Each repository is held up against the checks HACS runs before it lists one, and the Python of each integration gets a first read for things worth a second look.
- **The Bazaar integration**, which puts the catalog in Home Assistant's sidebar, shows what HACS already has, and adds a repository to HACS with one click.

Either way, HACS does the installing. A repository added from Bazaar is an ordinary custom repository in HACS, which downloads it, offers its updates and removes it like any other. Bazaar never writes a file in your configuration.

## Nothing here is reviewed

HACS reviews a repository before listing it. The repositories in Bazaar have not been through that, which is the point of Bazaar and also its risk: they are other people's code, running inside your Home Assistant with the same rights as everything else there.

Bazaar tries to make that risk visible rather than hide it:

- **HACS's checks.** The same checks the HACS action runs: description, topics, issues, README, `hacs.json`, licence, and for integrations a complete `manifest.json` and a brand icon. For repositories in the queue, the result of HACS's own action on the pull request is shown as well.
- **Clashes.** An integration whose domain is already taken, by one in HACS, by one built into Home Assistant, or by another repository in the catalog, is marked. Home Assistant loads only one integration per domain, so installing such a copy beside the original makes one of them disappear.
- **A first read of the code.** Every integration's Python is read through its syntax tree, so a method that happens to be called `exec`, or a path named in a comment, does not count. It looks for running text as code (`exec`, `eval`), decoding data and running it, reading Home Assistant's own login store, starting programs, installing packages at runtime, creating users or tokens, and long encoded strings. Each finding links to the file and line. A flag is a reason to read the code, not a verdict: plenty of honest integrations start a program.
- **Left out entirely.** Repositories HACS already lists (also under a new name after a rename), repositories HACS has removed or blacklisted, archived repositories, forks that were never submitted, and unchanged copies of the `integration_blueprint` template.

If something in the catalog should not be there, use **Report** on its card. Authors who would rather not be listed can ask the same way, or open a pull request that adds the repository to `denylist.json`; it is left out from the next night on.

## The integration

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=beolink&repository=ha-bazaar&category=integration)

1. Add this repository to HACS with the button above, or in HACS under the menu, *Custom repositories*, category *Integration*.
2. Download Bazaar in HACS and restart Home Assistant.
3. Add the integration under *Settings, Devices & services*. The only setting is the catalog's address; keep the default unless you run your own copy.

**Bazaar** then appears in the sidebar for administrators. *Add to HACS* on a card shows what the checks and the code reading found, adds the repository to HACS when you confirm, and opens it in HACS for the download.

The integration fetches the catalog every six hours and keeps a copy for the next start, so the panel works without a network. It needs HACS to add repositories, and HACS 2.0 or later.

What it sends: one request for the catalog to the address in its settings. The panel loads repository icons from GitHub and Home Assistant's brands site.

## Running the catalog yourself

The catalog is built by `catalog/`, which needs nothing beyond Python 3.13 or later and a GitHub token with public read access (from `GITHUB_TOKEN`, `GH_TOKEN` or a logged-in `gh`):

```bash
python -m catalog.collect --out site/catalog.json
python scripts/build_site.py --catalog site/catalog.json --out public
```

A full run takes most of an hour, nearly all of it waiting on GitHub's code search limit of ten requests a minute. `--no-search` builds the catalog from the HACS queue alone in a few minutes, and `--previous` points at last night's `scan-cache.json`, written next to the catalog, and reuses the code reading for integrations that have not changed. The GitHub workflow in `.github/workflows/catalog.yml` does this every night and publishes the result on GitHub Pages; give it a `CATALOG_TOKEN` secret, since code search does not accept the workflow's own token everywhere.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-test.txt
.venv/bin/pytest
```

The integration tests run against a real Home Assistant through `pytest-homeassistant-custom-component`, which also needs the `home-assistant-frontend` package Home Assistant pins.

## Licence

Apache 2.0. Not affiliated with HACS or Home Assistant.

The icons are from [Material Design Icons](https://pictogrammers.com/library/mdi/) by Pictogrammers, also under Apache 2.0.
