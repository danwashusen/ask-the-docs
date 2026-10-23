# ask-the-docs

## Commands

- `mise exec -- mdsmith check .`: lint all Markdown; `fix` auto-fixes.

## Doc conventions

Docs are edited on parallel branches, so write them to merge cleanly.

- Give requirements and other referenced items a slug ID, `R-<slug>`, such
  as R-dry-run-default. Never number them (`R1`, `R-1`): two branches adding
  a requirement would pick the same number. mdsmith's `occurrence` rule
  rejects numeric IDs.
- Write IDs as plain text, not in code spans, so the lint rule sees them.
- Never rename or reuse a slug. To retire an item, delete it and update
  every reference.
- Use one bullet per item for lists that grow, such as requirements and
  decisions. Avoid tables there: mdsmith pads every row to the widest
  cell, so one new row rewrites the whole table.
- Start every file under `docs/` with a `summary` front-matter field. The
  index below is built from it.

## Docs

Read a doc only when the task needs it. The index below is generated from
each file's `summary` front matter; edit the summary, then run
`mdsmith fix AGENTS.md`.

<?catalog
glob: "docs/**/*.md"
sort: path
row: "- [{summary}]({filename})"
?>
- [Architecture hub: process model, components, package layout, libraries, testing and design decisions for the atd CLI and its Claude Code plugin.](docs/architecture.md)
- [Architecture spoke: how atd keeps indexes fresh with the per-codebase lock, the optional watcher, budgeted lazy sync and atd sync.](docs/architecture/freshness.md)
- [Architecture spoke: how atd discovers and parses Markdown, the record model and mapping, index naming, rebuilds and per-file updates.](docs/architecture/indexing.md)
- [Architecture spoke: how atd resolves the codebase for a query, builds search, docs, toc and show requests, ranks results and renders output.](docs/architecture/query.md)
- [MVP product requirements hub: a local CLI that indexes codebases' docs in a shared Elasticsearch, keeps them fresh, and serves section and document queries to coding agents.](docs/prd.md)
- [PRD spoke: requirements for the YAML config file that holds tool settings and the list of monitored codebases.](docs/prd/configuration.md)
- [PRD spoke: requirements for the Claude Code skill that turns natural-language questions about docs into atd CLI calls.](docs/prd/skill.md)
- [Documentation map and the doc-catalogue block that tells the github-pipeline skills which docs ground work on this repo.](docs/README.md)
<?/catalog?>
