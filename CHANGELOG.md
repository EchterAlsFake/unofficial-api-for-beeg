# Changelog

## 1.7.4 — 2026-10-27

- Accept video IDs, links without a scheme, and video links copied from tag pages without losing the video key.
- Expose author, tags, thumbnails and publication dates from the API response.
- Report missing or malformed metadata as NotFound instead of failing with an indexing error.
- Handle missing batch files and output directories more gracefully in the CLI.
- Use the published `eaf-base-api>=4.2.5` dependency.

