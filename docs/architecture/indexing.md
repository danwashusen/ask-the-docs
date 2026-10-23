---
summary: "Architecture spoke: how atd discovers and parses Markdown, the record model and mapping, index naming, rebuilds and per-file updates."
---
# Indexing

Part of the [architecture](../architecture.md).

## File discovery

Inside a git repo, `codebase` runs `git ls-files -co --exclude-standard`
over each configured docs folder. This lists tracked and untracked files
and honours every `.gitignore`. Outside git, it walks the folders directly.
Either way it keeps `*.md` files and drops paths matching the codebase's
exclude globs.

## Parsing

`parse` turns one file into records in a single pass:

1. Split off YAML front matter. Keep `title` and `summary`, and drop the
   block from the body.
2. Tokenise with markdown-it-py. Heading tokens carry source line ranges,
   and fenced code never yields headings.
3. Cut sections at every heading, per D-leaf-sections. Text before the
   first heading becomes a preamble section with an empty anchor.
4. Build each heading's anchor with GitHub's slug rules, adding `-1`, `-2`
   for repeats, so anchors match rendered links.
5. Split any section over the size limit into parts at blank lines outside
   code fences. Parts share the anchor and keep their own line ranges.

The size limit comes from config, per R-tunable-section-limit.

## Records

Each index holds three kinds of document, told apart by a `kind` field.

- `section`: one per section or part. Fields: path, anchor, part, ordinal,
  heading, heading trail, level, start and end lines, section end line,
  body. It also carries copies of the file's title, summary, role and
  authority, so a query needs no join.
- `file`: one per file. Fields: path, modified time, size, content hash,
  title, summary, role, authority and section count. Sync compares against
  these, and `atd docs` lists them.
- `state`: one per index. Fields: codebase name, root, schema version,
  section size limit and last sync time. `atd status` and `atd list` read
  it.

Section IDs are `<path>#<ordinal>`, so an update overwrites in place.

## Mapping

- Title, heading, heading trail, summary and body are `text` with the
  English analyzer. A `.std` subfield with the standard analyzer catches
  exact terms that stemming would blur.
- Body uses `index_options: offsets`, so highlighting stays fast on large
  sections.
- Path, anchor, role, authority and kind are `keyword`. Lines, level, part
  and ordinal are integers.

## Index lifecycle

- The alias is `atd-<name>-<hash>`, where `<hash>` is 8 hex characters of
  the root path's hash. Renaming a codebase or moving its root gives a new
  alias.
- The backing index is the alias plus a timestamp. Only `store` knows
  backing names; everything else uses the alias.
- A rebuild creates a new backing index, indexes every file, then moves the
  alias in one `_aliases` call and deletes the old index.
- `atd sync` and `atd watch` startup rebuild when the `state` record's
  schema version or section size limit differs from the code and config.
- `atd prune` computes the aliases the current config implies. It deletes
  every `atd-` alias and backing index not in that set. Matching on the
  alias, not the name, also catches a codebase whose root moved.

## Per-file updates

To write a changed file, `store` bulk-indexes its section records by ID.
It updates the `file` record, then deletes that path's sections with an
ordinal at or above the new count. A deleted file loses its `file` record
and all its sections, by path. A rename is a delete plus a create.
