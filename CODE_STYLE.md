# Code Style

This project should stay simple, explicit, and close to the osu! server domain.
The goal is not to recreate the full production Akatsuki stack in Python; it is
to keep bancho.py approachable while preserving the core behavior that matters.

The project's core ethos is:
> The all-in-one osu! server backend for everyone. Simpler than Akatsuki's
> production stack, while maintaining core functionality, plus a few unique
> features.

## Architecture

- Keep controllers thin. HTTP and bancho protocol controllers should parse
  request data, handle protocol-specific responses, and delegate app logic.
- Put business logic in services. A controller should not decide how
  score submission, stats updates, achievements, or leaderboard behavior works.
- Expose service behavior through service classes. Module-level functions in
  service modules should be private implementation helpers, not the public app
  logic surface called by controllers.
- Use repositories for database access. Services should orchestrate
  repositories, transactions, and domain decisions.
- Do not use repository/service locators for new code. The legacy repository
  bridge exists only for command handlers and active-record-style objects that
  have not yet moved behind services.
- Prefer explicit dependencies over hidden package behavior. Import from direct
  source modules instead of relying on `__init__.py` re-exports.
- Avoid dynamic imports as an architecture tool. If an import cycle appears,
  fix the dependency direction or extract a smaller boundary.
- Add abstractions only when they remove real complexity or create a useful
  boundary. Do not add generic flexibility for a single use.
- Prefer explicit composition at real boundaries. Pass dependencies such as
  repositories, clients, clocks, metrics, and filesystem adapters into functions
  instead of reaching through module globals.
- Treat hard-to-test code as composition feedback. If logic can only be tested
  by patching imports, globals, or classmethods, the production code likely
  needs a clearer dependency boundary.

## Typing

- Prefer real types over `dict[str, Any]` when a value has a known shape.
  Use `TypedDict`, enums, protocols, or small models as appropriate.
- Avoid `cast()` and `type: ignore` as type-checker appeasement. They should be
  rare and isolated to hard third-party boundaries.
- If a third-party package has weak types, prefer an available public stubs package,
  a small wrapper, adapter, or local stub over spreading casts through app code.
- Use full enums for domain states instead of magic ints or partial constants.
- Keep sentinel values explicit, such as `Unset`, instead of relying on vague
  `None` semantics when `None` is meaningful.

## Services

- Prefer domain verbs that make sense to an osu! developer:
  `submit_score`, `save_replay_file`, `announce_first_place`,
  `persist_score_submission_stats`, `unlock_achievements`.
- Avoid vague function names such as `finalize_*`, `prepare_*`, or
  `update_*_state` when the function actually performs several unrelated
  decisions or side effects.
- Keep orchestration readable. A high-level service should show the main domain
  steps in order instead of hiding important branches behind broad helper names.
- Put transactions at the service layer when a workflow needs
  all-or-nothing semantics.
- Keep protocol response formatting in the controller when it is specific to
  HTTP, bancho, or osu! client response formats.

## Testing

- Test app logic, not Python itself. Do not add tests that only prove object
  construction, dataclass behavior, or trivial assignment works.
- Prefer clear arrange, act, assert tests over helper-heavy tests.
- Use helpers sparingly. A helper is good when it removes noise; it is bad when
  it hides the behavior or state being tested.
- Unit tests should use explicit composition over monkeypatching. If a unit test
  needs to patch imports, globals, or classmethods, prefer improving the
  production dependency boundary.
- Prefer small, local test doubles with clear intent. Use `_FakeX` for a
  cooperative dependency with visible state, and `_FailingX` for a dependency
  whose purpose is to trigger an error path.
- Keep fakes simple and behavior-focused. If a fake needs complex internal
  logic, the production boundary may be too broad or the test may be covering
  too much at once.
- Prefer small unit tests for important logic. Use integration tests for broad
  flows, but do not let broad tests replace focused coverage of critical rules.
- Refactor code when necessary to make meaningful tests possible, but keep the
  refactor scoped to the behavior under test. For agent-assisted or high-risk
  refactors, add test coverage and get human approval when coverage is not
  already present.
- For critical osu! behavior, compare against official osu! code or docs when
  practical, then decide whether bancho.py should match it or intentionally
  diverge.

## osu! Compatibility

- You should almost always match the official osu! server behavior, up until
  it significantly adds complexity for extremely minor gain. Intentional
  divergence should be rare and documented.
- When bancho.py intentionally diverges from official behavior, leave a code
  comment explaining why, especially if changing it later may need a migration
  or data backfill.
- Avoid large operational changes, migrations, or backfills unless the project
  is ready to support their impact. Remember that several projects now maintain
  forks or run bancho.py/master directly, and need to keep up to date with their
  own userbases.

## Pull Requests

- Keep each PR coherent. Larger PRs are acceptable when they move one theme
  forward and are well covered by tests.
- Every changed line should trace back to the PR's purpose.
- Preserve existing comments when moving or refactoring code unless they are no
  longer true.
- Do not amend review follow-up commits unless explicitly requested. Add a new
  commit so review deltas stay easy to inspect.
