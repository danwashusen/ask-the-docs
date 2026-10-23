---
summary: "PRD spoke: requirements for the YAML config file that holds tool settings and the list of monitored codebases."
---
# ask-the-docs: configuration requirements

Part of the [product requirements](../prd.md).

## Requirements

- R-yaml-config: read settings and the codebase list from one YAML file.
  The default path is `~/.config/ask-the-docs/config.yaml`.
- R-config-override: `--config <path>` or the `ATD_CONFIG` variable selects
  another file.
- R-config-precedence: a flag beats an environment variable, which beats
  the file, which beats the built-in default.
- R-codebase-settings: each codebase entry sets its root and may set its
  docs folders, exclude globs, catalogue path and section size limit. The
  defaults are `docs/`, none, `docs/README.md` and the global limit.
- R-tool-settings: top-level settings cover the Elasticsearch URL, the
  default result limit, the watch debounce interval, lazy sync and its
  budget, and the section size limit.
- R-config-validation: an invalid file, unknown key or duplicate name fails
  at startup. The error names the file and the offending key.
- R-config-restart: config changes take effect when `atd watch` restarts.

A minimal file looks like this:

```yaml
elasticsearch:
  url: http://localhost:9200
codebases:
  - root: ~/Development/Projects/ask-the-docs
  - name: billing
    root: ~/work/billing-service
    docs: [docs/, adr/]
    exclude: ["docs/archive/**"]
```
