# Contributing

Thanks for contributing to Review Robin Web.

## Workflow

1. Create a branch for each bounded task.
2. Keep pull requests small and focused.
3. Add or update tests for behavior changes.
4. Keep route handlers thin and business logic in services.
5. Update documentation when setup or behavior changes.

## Pull request checklist

- [ ] Tests pass locally (`pytest`).
- [ ] New behavior has tests.
- [ ] Documentation is updated if needed.
- [ ] No unrelated refactoring is included.

## Project conventions

Please follow repository conventions documented in `AGENTS.md`, including:

- Python 3.12+
- FastAPI backend patterns
- Pydantic schemas at boundaries
- Small, PR-sized changes
