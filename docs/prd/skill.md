---
summary: "PRD spoke: requirements for the Claude Code skill that turns natural-language questions about docs into atd CLI calls."
---
# ask-the-docs: agent skill requirements

Part of the [product requirements](../prd.md). D-skill-owns-language there
explains why the skill, not the CLI, handles natural language.

## Requirements

A Claude Code plugin ships with the tool. Its skill turns a natural-language
question into CLI calls, so the CLI only ever takes structured input.

- R-skill-routing: the skill maps question types to commands. Topic
  questions go to `atd docs`, passage questions to `atd search`, structure
  questions to `atd toc`, and a known section to `atd show`.
- R-skill-query-rewrite: the skill turns a question into search terms. It
  may run more than one query, such as synonyms, before it answers.
- R-skill-minimal-reads: the skill reads only the line ranges it needs,
  never whole files when a section will do.
- R-skill-authority: the skill reports each source's authority. It flags a
  conflict with a `binding` doc rather than working around it.
- R-skill-not-running: when the CLI or Elasticsearch is unavailable, the
  skill says so and how to fix it. It may then fall back to grep.
