---
summary: "MVP product requirements hub: a local CLI that indexes codebases' docs in a shared Elasticsearch, keeps them fresh, and serves section and document queries to coding agents."
---
# ask-the-docs: product requirements (MVP)

## Problem

Coding agents find project docs with grep and whole-file reads. On a large
`docs/` folder that costs many tool calls and much context, and still misses
sections that use different words. Agents also cannot tell a binding spec from
a historical note without opening both.

## Hypothesis

A local search index over the docs, queried by section, lets an agent find the
right passage in one or two calls. It should use fewer tokens than grep and
whole-file reads. The MVP exists to test this on a real repo with a large
`docs/` folder.

## Users

- Primary: a coding agent, such as Claude Code, running shell commands in the
  repo. It needs stable, compact, machine-readable output.
- Secondary: the developer who installs the tool, starts it, and checks it
  works.

## How it works

1. The developer starts Elasticsearch once from the shipped compose file.
   Every codebase on the machine shares it.
2. The developer lists their codebases in the YAML config file.
3. `atd watch` indexes every Markdown file in each configured codebase,
   then watches for changes. Watching is optional: queries catch up on
   changed files themselves.
4. An agent runs `atd search "how are retries configured" --json`. It gets
   ranked sections with path, heading trail, line range and snippet.
5. The agent reads only the lines it needs, or runs `atd show` for one
   section.

`atd` is a working name for the command.

## Requirements

### Indexing

- R-markdown-only: index `*.md` files under each configured docs folder,
  recursively. Respect `.gitignore` and the codebase's exclude globs.
- R-section-chunks: split each file into one record per heading section.
  Each record holds the file path, heading trail, anchor, start and end
  lines, and body text.
- R-oversized-sections: split a section larger than the configured size
  limit into parts at paragraph boundaries. Parts share the heading and
  anchor, and each keeps its own line range.
- R-tunable-section-limit: the size limit defaults to 32 KB. It can be set
  globally and per codebase. Changing it rebuilds the affected indexes on
  the next sync.
- R-front-matter: parse YAML front matter. Store `summary` and `title` when
  present, and keep them out of the body text.
- R-content-hash: store a content hash per file. A sync skips files whose
  hash is unchanged.

### Codebases

One Elasticsearch instance serves every codebase on the machine, so the
container runs once.

- R-codebase-identity: a codebase is a config entry with a unique name and
  an absolute root path. The name defaults to the root folder's name.
- R-index-per-codebase: store each codebase in its own index, named from its
  identity. Removing or rebuilding one codebase never touches another.
- R-scoped-queries: `atd search`, `atd show` and `atd status` resolve the
  codebase from the current directory. They pick the configured root that
  contains it, the deepest when roots nest. They return results from that
  codebase only.
- R-codebase-override: `--codebase <name>` targets a codebase other than the
  current one. A query never spans more than one codebase.
- R-unknown-codebase: a query from a folder outside every configured root
  fails. It prints one line naming the config file to add it to, rather than
  searching another codebase.
- R-list-codebases: `atd list` shows each configured codebase with its name,
  root path, file count and last sync time. It also flags indexes whose
  codebase is no longer configured.
- R-prune-indexes: `atd prune` deletes indexes whose codebase is no longer
  in the config.
- R-watch-all: `atd watch` watches every configured codebase in one process.
  `atd watch <name>` watches just one.

### Configuration

One YAML file holds tool settings and the list of codebases. Its
requirements live in [prd/configuration.md](prd/configuration.md).

### Doc catalogue

- R-catalogue-metadata: read the `<!-- doc-catalogue -->` block from the
  codebase's catalogue path when present. Attach its role, authority and
  summary to every record from a listed file or directory set.
- R-catalogue-optional: index all files whether or not the catalogue lists
  them. Files outside the catalogue get no role and no authority.
- R-catalogue-boost: rank records from `binding` docs above `informative`
  and unlisted docs, all else equal.
- R-catalogue-refresh: re-read the catalogue when its file changes,
  and update the metadata of affected records.

### Freshness

- R-startup-sync: on start, reconcile the index with the folder. Add new
  files, update changed ones, and remove deleted ones. Edits made while the
  watcher was off are picked up.
- R-watch-changes: watch the folder and apply creates, edits, renames and
  deletes. Debounce bursts, such as a branch checkout.
- R-watch-optional: `atd watch` speeds things up but is never required.
  Every query command works without it.
- R-freshness-target: while `atd watch` runs, a saved edit is searchable
  within 2 seconds.
- R-lazy-sync: when no watcher serves a codebase, a query first compares
  file modified times and sizes with the index. It reindexes changed files
  before answering.
- R-sync-budget: lazy sync stops after a time budget, 1 second by default
  and configurable. The query then answers from the index as it stands.
- R-stale-results: results from files that changed but were not reindexed
  carry `stale: true` in JSON. One stderr line suggests `atd sync` or
  `atd watch`.
- R-lazy-sync-off: `lazy_sync: false` in config, or `--no-sync` on a query,
  skips the check.
- R-sync-command: `atd sync [name]` reconciles one or all codebases once,
  with no budget.

### Search

- R-search-cli: `atd search <query>` runs a BM25 query. Heading trail and
  summary fields are boosted over body text.
- R-search-filters: support `--limit`, `--path <glob>`, `--role <slug>` and
  `--binding`.
- R-json-output: `--json` prints one JSON array of results. Each holds path,
  heading trail, anchor, start and end lines, role, authority, score, stale
  flag and a short snippet. The schema is documented and stable.
- R-compact-text: the default text output fits one result per two lines, so
  an agent can scan it cheaply.
- R-show-section: `atd show <path>#<anchor>` prints the full text of one
  section.

### Document metadata

These answer questions about documents, not passages. Both come from the
section records already indexed, so Elasticsearch needs no extra data.

- R-docs-by-topic: `atd docs <query>` ranks whole documents by relevance.
  It groups matching sections by file. Each result holds path, title,
  summary, role, authority, score and the headings of the matching sections.
- R-docs-list: `atd docs` with no query lists every indexed document with
  the same fields, minus score. It takes the same filters as `atd search`.
- R-toc: `atd toc <path>` prints the document's heading tree, with each
  heading's anchor and line range. It reads the index, not the file.
- R-metadata-json: `atd docs` and `atd toc` support `--json`, with a
  documented, stable schema.

### Agent skill

A Claude Code plugin ships with the tool. Its requirements live in
[prd/skill.md](prd/skill.md).

### Operations

- R-compose-file: ship a compose file for a single-node Elasticsearch. Bind
  it to localhost with security off. Document it as local-only. It uses a
  fixed container name and data volume, so every codebase shares one
  instance.
- R-es-url: connect to `http://localhost:9200` by default. Allow an override
  by config file, flag or environment variable.
- R-status: `atd status` reports Elasticsearch health, indexed file and
  section counts, and the last sync time.
- R-clear-errors: when Elasticsearch is unreachable, fail fast. Print one
  line that says how to start it.
- R-python-package: build in Python, installable with `uv tool install` or
  `pipx`.

## Out of scope for the MVP

- Semantic or hybrid search, such as ELSER or dense vectors.
- An MCP server. The CLI and skill come first; MCP may wrap the CLI later.
- Natural-language parsing inside the CLI. The skill owns it.
- Answer synthesis by an LLM. The agent is the reader.
- Formats other than Markdown.
- A single query across several codebases. Each query targets one.
- Remote hosting and authentication.
- A background daemon or OS service. `atd watch` runs in the foreground.

## Decisions

- D-elasticsearch: use Elasticsearch over embedded options such as SQLite
  FTS5 or Tantivy. It leaves a direct path to hybrid search later, at the
  cost of Docker and more memory. One shared instance for all codebases
  keeps that cost paid once.
- D-index-per-codebase: isolate codebases by index, not by a filter on a
  shared index. A missed filter can then never leak another codebase's
  docs.
- D-catalogue-as-metadata: the catalogue enriches and boosts records but
  never limits what gets indexed. The tool stays useful on repos without one.
- D-watch-optional: freshness comes from a watcher when one runs, and from
  budgeted lazy sync otherwise. Large files make unbounded sync on query
  too slow, so the budget caps the wait and marks what it skipped.
- D-skill-owns-language: the CLI takes structured queries and the skill
  translates questions. The CLI stays deterministic and testable without a
  model, and the agent already supplies the language understanding.

## Success criteria

Test on the real-world repo's `docs/` folder.

- Build a set of about 20 questions, each with a known answer section.
- Retrieval: the answer section ranks in the top 3 for at least 80 percent
  of questions.
- Topic questions: for a further 10 topic questions, `atd docs` ranks the
  expected document in the top 3 for at least 8.
- Agent cost: on the same questions, compare an agent using `atd` against
  one using grep and file reads. Measure tool calls and tokens read. `atd`
  should cut both.
- Indexing: a full index of the folder finishes in under a minute.
- Large files: an early spike times parsing and indexing of the largest
  files. Its results set the default sync budget and section size limit.
- Freshness: R-freshness-target holds while editing files by hand.

## Open questions

- Command name: keep `atd`, or use `ask-the-docs` with `atd` as an alias?
- Should `atd search` include a few lines of body around the match, or only
  a snippet?
- Is the skill enough for agents to find the tool, or should a
  `CLAUDE.md` snippet also point at it?
- Should the mdsmith `summary` front matter fill in the summary for files
  the catalogue does not list?
- Should `atd add <path>` append a codebase to the config, or is
  hand-editing enough for the MVP?
- After the MVP, which next step: hybrid search, or the MCP server?
