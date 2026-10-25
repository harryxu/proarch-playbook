# Issue tracker: GitHub

Issues and specs live in GitHub Issues for `harryxu/proarch-playbook`.
Use the `gh` CLI from this repository, or pass `--repo harryxu/proarch-playbook`
when running elsewhere.

## Conventions

- Create an issue: `gh issue create --title "..." --body-file <path>`.
- Read an issue: `gh issue view <number> --json number,title,body,labels,comments`.
- List issues: `gh issue list --state open --json number,title,body,labels`, with appropriate label and state filters. Read individual issues when comments are needed.
- Comment: `gh issue comment <number> --body-file <path>`.
- Apply or remove labels: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`. Use the mapping in `triage-labels.md`.
- Close: `gh issue close <number>`.

Write multiline issue bodies and comments to a UTF-8 file and pass it with
`--body-file` to preserve literal text and newlines.

## Relationships

Use native GitHub sub-issues and dependencies when available.

- Link a child to a parent: `gh issue edit <parent> --add-sub-issue <child>`.
- Add a dependency: `gh api --method POST repos/harryxu/proarch-playbook/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`.
- Resolve a database ID: `gh api repos/harryxu/proarch-playbook/issues/<number> --jq .id`. Dependency endpoints use database IDs, not issue numbers or node IDs.

Where native relationships are unavailable, put `Part of #<parent>` at the top
of the child body and add the child to a task list in the parent. Record
dependencies as `Blocked by: #<number>, #<number>`. An issue is unblocked when
all its blockers are closed.

## Pull requests as a triage surface

**PRs as a request surface: no.**

GitHub issues and pull requests share a number space. Resolve ambiguous
references before treating them as issues.

## Skill operations

- "Publish to the issue tracker": create a GitHub issue.
- "Fetch the relevant ticket": read the referenced GitHub issue, including its comments.

## Wayfinding operations

- Map: one issue labelled `wayfinder:map`, holding Notes, Decisions-so-far, and Fog.
- Child ticket: a sub-issue of the map, labelled `wayfinder:<type>` where type is `research`, `prototype`, `grilling`, or `task`. Use the relationship fallback above when needed.
- Frontier: open children without an open blocker or assignee, in map order.
- Claim: assign the ticket to the driving developer before starting work.
- Resolve: comment with the answer, close the ticket, and add a brief finding with a link to the map's Decisions-so-far.
