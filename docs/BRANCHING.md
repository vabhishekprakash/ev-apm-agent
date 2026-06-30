# Branch Strategy

## Rules

| Rule | Detail |
|------|--------|
| `main` | Always demoable. Never broken. |
| Feature branches | `feat/<name>` — e.g., `feat/layer1-rules`, `feat/akhil-drift-model` |
| Merge policy | PR + review required before merge to `main` |
| PR size | Keep under 400 lines when possible |

## Workflow

1. Pull latest `main`
2. Create `feat/<your-name>-<what-you-are-building>`
3. Push branch, open PR
4. Request review from the other person
5. Merge only when CI passes and reviewer approves

## Naming Conventions

- `feat/` — new feature
- `fix/` — bug fix
- `docs/` — documentation only
- `chore/` — tooling, deps, cleanup
