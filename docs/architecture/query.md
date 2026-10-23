---
summary: "Architecture spoke: how atd resolves the codebase for a query, builds search, docs, toc and show requests, ranks results and renders output."
---
# Query

Part of the [architecture](../architecture.md).

## Codebase scoping

`codebase` resolves the target before any request is built:

1. With `--codebase <name>`, use that config entry.
2. Otherwise pick the configured root that contains the working directory.
   When roots nest, the deepest wins.
3. If none matches, fail with one line naming the config file.

Every request then goes to that codebase's alias only, per
D-index-per-codebase. No query names more than one index.

## Search

`atd search` sends one request to the alias:

- A `multi_match` of type `best_fields` with a tie breaker. Starting
  boosts are title 3, heading 3, heading trail 2, summary 2 and body 1,
  each with its `.std` subfield.
- A filter on `kind: section`, plus the role, binding and path filters.
- A `function_score` weight on `authority: binding`, per
  R-catalogue-boost. The weight starts at 1.2.
- A body highlight with one short fragment, used as the snippet.

The boosts and weight are starting points. The eval harness tunes them
against the question set.

Path globs become an anchored regular expression on the `path` keyword.
`**` matches across folders and `*` stays within one.

## Docs

- With a query, `atd docs` reuses the search request and collapses on
  `path`. Each file's best section supplies the score. `inner_hits`
  returns its top three matching headings.
- Without a query, it lists `file` records sorted by path, with the same
  filters.

## Toc and show

- `atd toc <path>` fetches the path's `section` records with `part: 0`,
  sorted by ordinal. Each entry gives heading, level, anchor, start line and
  section end line. Parts are invisible here.
- `atd show <path>#<anchor>` fetches every part with that path and anchor,
  sorted by part, and joins the bodies.
- Both fail with one line when the path or anchor is unknown, and suggest
  `atd toc` or `atd docs`.

## Output

`output` renders every command in two forms.

- Text: two lines per result. The first line holds path, anchor and line
  range. The second holds the heading trail and snippet. Stale results are
  tagged.
- JSON: one array, per R-json-output and R-metadata-json. Fields use
  snake_case, and line numbers are 1-based and inclusive. The schema lives
  beside the code and in the plugin's skill.

Warnings such as stale results go to stderr, so stdout stays parseable.

## Errors

- Elasticsearch unreachable: exit code 2 and one line with the
  `docker compose` command that starts it.
- Unknown codebase, path or anchor: exit code 1 and one line saying what
  to run instead.
- Bad config: exit code 1, naming the file and the key.
