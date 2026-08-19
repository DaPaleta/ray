# ADR-006: Commit the supplied database to the repository

**Date:** 2026-08-19
**Status:** accepted

## Context

The brief requires that a clean checkout runs Ray with a `requirements.txt` and
one command. The supplied SQLite database arrived as an email attachment, and it
sat in the analyst's download directory. A path into a personal directory does not
survive a clean checkout.

The file is 1.9 MB. It holds synthetic data for one fictional organization, Acme
Robotics. It holds no secret and no personal data about a real person.

## Decision

Commit the database to `data/ocean_home_task.db`. `config.py` defaults to that
path. The environment variable `RAY_DB_PATH` overrides the default.

The `README.md` states both the default and the override.

## Alternatives Considered

**Read the path from `RAY_DB_PATH` only, and commit no data.** Rejected. The
reviewer must then set an environment variable before the first run, which breaks
the one-command requirement.

**Download the file at first run.** Rejected. No canonical URL exists for the
attachment, and a network call at startup adds a failure mode for no benefit.

**Commit the file through Git LFS.** Rejected. 1.9 MB is far below the size at
which LFS pays for its setup cost, and LFS adds a dependency for the reviewer.

## Consequences

**Positive.** A clean checkout runs with one command, which satisfies brief
requirement 1. The reviewer needs no setup step and no path knowledge. The
override still supports a different database, such as a reduced fixture for a
test.

**Negative.** The repository carries 1.9 MB of supplied data, and the history
grows if the file ever changes. A reviewer may question a binary file in version
control, so `docs/structure.md` section 5 names the file as a deliberate
inclusion and points here.

**Follow-up.** `.gitignore` excludes `.env` and every virtual environment. It must
not exclude `data/`. Risk R8 covers the review objection.
