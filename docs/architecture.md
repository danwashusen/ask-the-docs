---
summary: "Architecture hub: process model, components, package layout, libraries, testing and design decisions for the atd CLI and its Claude Code plugin."
---
# ask-the-docs: architecture

How the tool meets the [product requirements](prd.md). This hub gives the
overall shape. The spokes hold the detail:

- [architecture/indexing.md](architecture/indexing.md): file discovery,
  parsing, records, mapping and index lifecycle.
- [architecture/freshness.md](architecture/freshness.md): locks, the
  watcher, lazy sync and `atd sync`.
- [architecture/query.md](architecture/query.md): codebase scoping, the
  query commands, ranking and output.

## Process model

There is no daemon. Elasticsearch is the only long-running service and the
only shared state.

- Every `atd` command is a short-lived process that talks to Elasticsearch
  directly. Query commands never go through a watcher.
- `atd watch` is a long-running CLI command. It writes to the same indexes
  any other command could.
- A per-codebase lock file makes sure only one process writes to a
  codebase's index at a time. A query that finds the lock held skips lazy
  sync, because another process is already updating the index.

```text
config.yaml ──► atd (any command) ──► Elasticsearch (one container)
                    │                     ▲
docs/**/*.md ──────►┘ parse + sync ───────┘
                    │
plugin skill ──► runs atd --json ──► agent reads line ranges
```

## Components

Each module has one job. The CLI layer only parses arguments and renders
output.

- `cli`: Typer app. Maps commands to the modules below.
- `config`: loads YAML, applies precedence, validates with pydantic.
- `codebase`: resolves the current codebase from the working directory and
  lists its Markdown files.
- `parse`: splits a file into front matter and section records.
- `catalogue`: parses the `<!-- doc-catalogue -->` block into path
  metadata.
- `store`: Elasticsearch client, mapping, aliases and bulk writes.
- `sync`: diffs files against the index and applies changes, with or
  without a budget.
- `locks`: per-codebase lock files.
- `watch`: file events, debouncing and burst handling.
- `query`: builds the search, docs, toc and show requests.
- `output`: text and JSON rendering, including the stale flag.

## Package layout

```text
pyproject.toml          # package atd, entry point atd = ask_the_docs.cli:app
compose.yaml            # single-node Elasticsearch, localhost only
src/ask_the_docs/       # one module per component above
plugin/                 # Claude Code plugin
  .claude-plugin/plugin.json
  skills/ask-the-docs/SKILL.md
tests/unit/             # no Elasticsearch needed
tests/integration/      # needs the compose Elasticsearch
eval/                   # question sets and the scoring script
```

## Libraries

- markdown-it-py: CommonMark tokens with source line maps. It ignores
  headings inside code fences.
- PyYAML: front matter and config parsing.
- pydantic: config models with unknown keys forbidden.
- Typer: CLI commands and help text.
- watchdog: cross-platform file events.
- elasticsearch: the official client. Its major version matches the
  server's, and both are pinned in `pyproject.toml` and `compose.yaml`.

## Plugin

The plugin lives in `plugin/` and ships from this repo, so the skill and the
JSON schema change together. The skill calls `atd` with `--json` and reads
the stated line ranges. It checks `atd --version` and tells the user to
upgrade when the CLI is older than the plugin expects. The skill
requirements are in [prd/skill.md](prd/skill.md).

## Testing

- Unit tests cover parsing, anchors, front matter, section splitting, the
  catalogue grammar, config validation and the sync diff. A fake store
  stands in for Elasticsearch.
- Integration tests run against the compose Elasticsearch. They use an
  `atd-test-` index prefix and cover writes, deletes, alias swaps, scoping
  and collapse queries.
- The eval harness in `eval/` holds the PRD's question sets with expected
  sections and documents. A script reports top-3 hit rates and timings.
- The first spike times parsing and indexing of the largest files in the
  real-world repo. It sets the defaults for the sync budget and section
  size limit.

## Decisions

- D-no-daemon: commands talk to Elasticsearch directly, and the watcher is
  one more writer. No local API to version, start or debug.
- D-alias-per-codebase: each codebase reads and writes through an alias
  that points at a versioned index. Rebuilds swap the alias in one step, so
  queries never see a half-built index.
- D-git-file-discovery: list files with `git ls-files` inside a repo. It
  applies nested `.gitignore` rules exactly, which a hand-rolled matcher
  would not.
- D-leaf-sections: a section runs from its heading to the next heading of
  any level. No text is indexed twice, and the heading trail supplies the
  parent context.
- D-single-writer-lock: one lock file per codebase, taken by watch, sync and
  lazy sync alike. Two writers can never interleave updates to one index.
