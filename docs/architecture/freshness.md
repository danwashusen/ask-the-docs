---
summary: "Architecture spoke: how atd keeps indexes fresh with the per-codebase lock, the optional watcher, budgeted lazy sync and atd sync."
---
# Freshness

Part of the [architecture](../architecture.md). Three paths keep an index
fresh, and all three share one diff routine in `sync`.

## The lock

Each codebase has a lock file under `~/.local/state/ask-the-docs/locks/`,
named after its alias. Writers take it with a non-blocking `flock`.

- `atd watch` holds it for as long as it runs.
- `atd sync` holds it for one reconcile, and waits if it is taken.
- A query tries it once. If it is taken, another process is already
  updating the index, so the query skips the check.

The OS frees an `flock` when its process dies, so a crashed watcher never
leaves a stale lock.

## The diff

`sync` lists the codebase's files and stats each one. It then fetches every
`file` record's path, modified time and size from the index. The result
falls into four groups:

- New: on disk, not in the index.
- Changed: modified time or size differs. The content hash is checked
  next, and a matching hash only refreshes the `file` record.
- Deleted: in the index, not on disk.
- Unchanged: skipped without being read.

Only new and changed files are read and parsed.

## Watcher

`atd watch` covers every configured codebase, or one when named. It skips a
codebase whose lock another process holds, and says so.

1. Take the lock, then run a full reconcile, per R-startup-sync.
2. Watch each docs folder and the catalogue file with watchdog.
3. Collect events into a set of paths. Flush the set once no event has
   arrived for the debounce interval.
4. When a flush holds more paths than the burst threshold, run a full
   reconcile instead of per-path updates. A branch checkout lands here.
5. Each flush ends with a refresh. Debounce, parsing and refresh together
   must fit inside R-freshness-target.
6. When the catalogue file changes, re-parse it and rewrite the role,
   authority and summary of every affected path.

## Lazy sync

Before a query runs, unless turned off in config or by flag, the command:

1. Tries the lock. If it is held, it queries straight away.
2. Runs the diff. If nothing changed, it releases the lock and queries.
3. Removes deleted files from the index. This is cheap and always runs.
4. Reindexes new and changed files, smallest first, until the budget runs
   out. The last bulk write uses `refresh=wait_for`, and that wait counts
   against the budget.
5. Releases the lock and runs the query.

Elasticsearch only makes writes searchable after a refresh. Without the
wait in step 4, the query would still see the old content.

Changed files left over go to `output`, which sets `stale: true` on their
results. The command prints one stderr line naming the count and suggesting
`atd sync` or `atd watch`. New files left over cannot appear in results, so
that same line counts them too.

This path never rebuilds an index, since a rebuild cannot finish in a
budget. When a rebuild is pending, it answers from the current index and
the stderr line says to run `atd sync`. Only `atd sync` and `atd watch`
perform rebuilds.

Smallest-first fits the most files in the budget. A single huge file never
blocks a query: it is skipped once the budget is spent.

## atd sync

`atd sync [name]` runs the full diff for one or all codebases and applies
every change, with no budget. It also performs any pending rebuild. It is
the manual refresh when no watcher runs, and fits scripts and CI.
