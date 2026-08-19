# AGENTS.md — instructions for coding agents

This file routes you to the right document. It duplicates none of them, because
every fact in this repository lives in exactly one place.

## 1. Read first

Read these, in this order, before you change a file.

| # | Document | What you get |
|---|---|---|
| 1 | `docs/vision.md` | Purpose, scope, project goals, and the terminology table. |
| 2 | `docs/tasks/ray-email-threat-investigator/plan.md` | The design. **Section 8 holds the implementation rules IR1 to IR10 that bind your work. Section 9 holds the definition of done.** Section 2 records what the database actually contains. |
| 3 | `docs/tasks/ray-email-threat-investigator/progress.md` | The delivered stages and the defects found. |
| 4 | `docs/tasks/ray-soc-role-subagents/plan.md` | The current task. It amends IR7, extends IR8, and adds IR11. Its section 2 holds the five-specialist roster. |
| 5 | `docs/decisions/` | The thirteen ADRs. Each rule in a `plan.md` section 8 cites the ADR behind it. |

`docs/structure.md` owns the repository layout and the layer rules. `README.md`
owns the commands, the environment variables, and the tech stack.

## 2. What Ray is

Ray is an investigator agent inside a security portal. A SOC analyst asks a
question in natural language, and Ray answers it from `data/ocean_home_task.db`.
Detection already ran. Ray explains what happened, why, and what to do next.

Ray serves one organization: Acme Robotics, primary domain `acme.com`.

## 3. Before you write code

1. Read `plan.md` and follow it.
2. Work the three priority tiers in `plan.md` section 5 in order. Do not start a
   tier-3 stage while a tier-1 stage is open.
3. Put a query in `src/ray/tools/`. Put reasoning in `src/ray/subagents.py`. A tool
   that returns a judgement breaks IR7, whatever it is called. `docs/structure.md`
   section 2 owns the layer rules, and section 3a owns the roster.
4. Verify every number you write against the database. Run the query. Six claims
   failed this check during planning, and `progress.md` records them.

## 4. Drift checklist — clear this before you finish

- [ ] New directory or file category? Update `docs/structure.md` in the same change.
- [ ] Changed the task? Update `plan.md`, `progress.md`, and `conversation.md`.
- [ ] Made a non-trivial technical decision? Add or update an ADR in `docs/decisions/`.
- [ ] Changed a command, a dependency, or an environment variable? Update `README.md`
      and `.env.example`.
- [ ] Changed the scope or the terminology? Update `docs/vision.md`.
- [ ] Moved ownership of a fact? Update the references so that each fact still lives
      in exactly one place.

## 5. Writing style

Every document in this repository uses Simplified Technical English.

1. One instruction per sentence. Keep a sentence under about 20 words.
2. Active voice. Present tense.
3. Use one term for one thing. `docs/vision.md` section 3 holds the term table, and
   this repository uses no synonym for a term in it.
4. Prefer the positive form. Avoid a contraction.
5. State a number with its source. A count without a query behind it is a guess.

## 6. Conventions

- File names: kebab-case. Python modules: snake_case, because the import system
  requires it.
- Branch names: flat kebab-case.
- Commits: Conventional Commits.
- Commit only when the analyst asks.
