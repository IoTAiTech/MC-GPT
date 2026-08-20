<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.8.0-beta.1 | Date: 2026-08-20 -->

# GitHub Packages

The repository **Releases** tab holds wheels, sdists and ZIP archives.
The repository **Packages** tab is a different registry. GitHub Packages
hosts npm, container (GHCR), Maven, NuGet and RubyGems. It does **not**
host PyPI wheels. Uploading a `.whl` to a GitHub Release therefore leaves
Packages empty.

## What this repository publishes on every version

Every annotated `v*` tag, every GitHub Release `published` event, and
every `workflow_dispatch` of `.github/workflows/release.yml` publishes:

| Registry | Name | Appears on Packages tab |
|---|---|---|
| GitHub Container Registry | `ghcr.io/iotaitech/mc-gpt` | Yes, linked by `org.opencontainers.image.source` |
| GitHub npm | `@iotaitech/mc-gpt` | Yes, scoped to org `IoTAiTech` |

Python wheels stay on **Releases**. They are not GitHub Packages.

## Pull the container

```bash
docker pull ghcr.io/iotaitech/mc-gpt:v6.7.0-beta.6
docker run --rm ghcr.io/iotaitech/mc-gpt:v6.7.0-beta.6 --help
```

Replace the tag with the Suite version that was published.

## Install the npm bootstrap from GitHub Packages

```bash
npm install @iotaitech/mc-gpt --registry=https://npm.pkg.github.com
```

The npm package name on GitHub Packages is `@iotaitech/mc-gpt` because
GitHub requires the scope to match the GitHub owner. The npmjs.org name
`@iot-ai-tech/iot-ai` is unchanged.

## Why a previous update left Packages empty

1. `release.yml` only ran `gh release create dist/*` with `contents: write`.
2. There was no Dockerfile and no `packages: write` permission.
3. GitHub no longer accepts Python packages on GitHub Packages.

Those three conditions are closed. Future version tags keep Packages in
lockstep with Releases.
