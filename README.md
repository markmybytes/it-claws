# it-claws

<a id="readme-top"></a>

<!-- PROJECT SHIELDS -->
<div align="center">

[![Tag][tag-shield]][tag-url]
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![License][license-shield]][license-url]

</div>

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/install-it/it-claws">
    <img src="https://github.com/user-attachments/assets/83d46686-2893-41c1-9077-ef0fede26dcc" alt="Logo" width="892" height="552">
  </a>

  <h3 align="center">it-claws</h3>

  <p align="center">
    Automated concurrent scraper for staging PC driver deployment environments
    <br />
    <a href="https://github.com/install-it/it-claws/issues/new?labels=bug&template=bug-report---.md">Report Bug</a>
    ·
    <a href="https://github.com/install-it/it-claws/issues/new?labels=enhancement&template=feature-request---.md">Request Feature</a>
  </p>
</div>

<!-- ABOUT THE PROJECT -->

## About The Project

it-claws is a Python-based tool that automatically downloads the latest PC hardware drivers, diagnostic tools, and common software from official vendor websites. Using Selenium for browser automation and httpx for static requests, it navigates vendor sites to retrieve up-to-date installation packages — suitable for staging driver packs for enterprise deployment.

Unlike simple download utilities, it-claws runs concurrently with configurable retry logic, supports dynamic and static page scraping, and can pack everything into a compressed ZIP archive.

The tool serves as a companion to [install-it](https://github.com/install-it/install-it/). See the [Usage](#usage) section for more information.

it-claws also supports **Docker** deployment with tmpfs RAM disk and automated cloud upload via rclone. See [scripts](scripts/) for the automation pipeline.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

[<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white">](https://www.python.org/)
[<img src="https://img.shields.io/badge/Selenium-01a71c?style=for-the-badge&logo=selenium&logoColor=white">](https://www.selenium.dev/)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE -->

## Usage

### Basic flow

1. **Select targets**
   - Use `-t` to specify space-separated target names
   - Use `-i` for interactive selection
   - Use `--all` to select all targets
   - Use `--target-from <file>` to load a preset text file

2. **Download**
   - The tool resolves download URLs (static or dynamic)
   - Files are downloaded concurrently with configurable retries

3. **Archive & output**
   - Results are staged in the output directory
   - Optionally pack into a compressed ZIP archive

### Selecting targets

```sh
it-claws -t "AMD Chipset Drivers" "Realtek HD Universal Audio"
it-claws -i
it-claws --all
```

Use a preset file (one target per line, `#` for comments):

```sh
it-claws --target-from presets/default.txt
```

Combine with interactive to tweak the preset before running:

```sh
it-claws --target-from presets/default.txt -i
```

### Output options

```sh
it-claws -o ./my-drivers --max-concurrent 10
```

### Resilience options

```sh
it-claws --max-concurrent 10 --retries 2
```

- `--max-concurrent`: parallel downloads (default: `3`, `1` = sequential)
- `--retries`: retry attempts per failed download (default: `1`)

### Archiving options

```sh
it-claws -o ./downloads -z ./driver-pack.zip --zip-include install-it/conf --compress-level 9
```

- `-z` / `--zip PATH`: destination for the output ZIP archive
- `--zip-include SOURCE[=LAYOUT]`: additional files or directories to include in the archive. The `<source>[=<layout>]` syntax lets you map a source path to a custom entry name inside the ZIP. For example, `install-it/conf=settings` adds the contents of `install-it/conf` under a `settings/` prefix inside the archive. Can be specified multiple times.
- `--zip-prefix PREFIX`: control how the output directory is represented in the ZIP. By default, the output directory name is stripped from archive paths. Specify a name to prefix all entries (e.g. `--zip-prefix pkg` places entries under `pkg/`).
- `-l` / `--compress-level`: compression level `0`–`9` (default: `5`)
- `--manifest`: generate a `manifest.json` file at the root of the ZIP archive

### How zip entries are determined

By default, the output directory name is stripped from archive paths. Entries are placed directly under the archive root:

```sh
it-claws -o ./downloads -z ./driver-pack.zip
# → zip contains: network/..., display/...  (downloads/ prefix stripped)
```

Use `--zip-prefix` to add a custom prefix to all entries:

```sh
it-claws -o ./downloads -z ./driver-pack.zip --zip-prefix drivers
# → zip contains: drivers/network/..., drivers/display/...
```

Additional files or directories can be included with `--zip-include`. Each flag accepts a single source path, optionally followed by `=<layout>` to remap the entry name inside the archive:

```sh
it-claws -o ./downloads -z ./driver-pack.zip --zip-include install-it/conf
# → zip contains: network/..., display/... + install-it/conf/...

it-claws -o ./downloads -z ./driver-pack.zip --zip-include install-it/conf=settings
# → zip contains: network/..., display/... + settings/...  (remapped from install-it/conf)
```

You can specify `--zip-include` multiple times to include several paths:

```sh
it-claws -o ./downloads -z ./driver-pack.zip \
  --zip-include install-it/conf \
  --zip-include scripts/startup
# → zip contains: network/..., display/... + install-it/conf/... + scripts/startup/...
```

When the same directory is included via both `-o` and `--zip-include`, or when two `--zip-include` paths overlap, the entries are merged without duplication.

### Manifest hashes

With `--manifest`, the generated `manifest.json` keeps `format_version` and `exported_at` and gains a `hashes` object:

```json
"hashes": { "settings": "<sha1 hex>", "data": "<sha1 hex>" }
```

- **`settings`** — SHA1 (lowercase hex) of the bytes of the entry named `conf/setting.json`. Omitted when that entry is not in the archive.
- **`data`** — a fold over `conf/data.db` and every file under `drivers/`:
  1. dedupe by arcname, keeping the **last** occurrence in archive order;
  2. frame each file as `len(arcname_bytes) + ":" + arcname + ":" + sha1_hex + "\n"`, where `len` is the **byte** length of the UTF-8 arcname (not the codepoint length);
  3. sort the frame **strings** (byte-wise), not the arcnames;
  4. SHA1 of the concatenation of the sorted frames. Omitted when there are no data entries (never the SHA1 of an empty string).

`manifest.json` is written **last** in the ZIP. Verify an existing archive from a terminal without it-claws:

```sh
python - <<'EOF'
import hashlib, zipfile
z=zipfile.ZipFile("driver-pack.zip"); names=z.namelist(); H=lambda b:hashlib.sha1(b).hexdigest()
print("settings:", H(z.read("conf/setting.json")) if "conf/setting.json" in names else None)
d={n:H(z.read(n)) for n in names if n=="conf/data.db" or n.startswith("drivers/")}
f=sorted(f"{len(n.encode())}:{n}:{h}\n" for n,h in d.items())
print("data:", H("".join(f).encode()) if d else None)
EOF
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- DEPLOYMENT -->

## Deployment

This project can be deployed via Docker with tmpfs RAM disk and automated rclone upload. See [`scripts/`](scripts/) for the automation pipeline and environment variable reference.

```bash
docker run --rm --privileged \
  -v /my/host/config:/config \
  -e RC_REMOTE_PATH="onedrive:PC_Deployments" \
  -e RETRIES="2" \
  -e COMPRESS_LEVEL="9" \
  it-claws
```

Override the default command:

```bash
docker run --name=it-claws \
  -v /path/to/config:/config \
  ghcr.io/install-it/it-claws:latest \
  it-claws -t "AMD Chipset Drivers" "Realtek HD Universal Audio"
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- GETTING STARTED -->

## Getting Started

### Prerequisites

- [uv](https://docs.astral.sh/uv/)
- A supported web browser (Chrome, Edge, or Firefox)

### Install dependencies

```bash
uv sync

uv sync --group dev # install dev dependencies
```

### Common commands

**Run the scraper**

```bash
it-claws
```

**Display help**

```bash
it-claws -h
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->

[tag-url]: https://github.com/install-it/it-claws/releases
[tag-shield]: https://img.shields.io/github/v/tag/install-it/it-claws?style=for-the-badge&label=LATEST&color=%23B1B1B1
[contributors-shield]: https://img.shields.io/github/contributors/install-it/it-claws.svg?style=for-the-badge
[contributors-url]: https://github.com/install-it/it-claws/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/install-it/it-claws.svg?style=for-the-badge
[forks-url]: https://github.com/install-it/it-claws/network/members
[stars-shield]: https://img.shields.io/github/stars/install-it/it-claws.svg?style=for-the-badge
[stars-url]: https://github.com/install-it/it-claws/stargazers
[issues-shield]: https://img.shields.io/github/issues/install-it/it-claws.svg?style=for-the-badge
[issues-url]: https://github.com/install-it/it-claws/issues
[license-shield]: https://img.shields.io/github/license/install-it/it-claws.svg?style=for-the-badge
[license-url]: https://github.com/install-it/it-claws/blob/master/LICENSE.txt
