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
<?/catalog?>
