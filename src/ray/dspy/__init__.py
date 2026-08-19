"""Build-time DSPy compilation for the specialist prompts that the data labels.

Two compiles live here, one per labelled specialist:

  - `compile_reviewer.py` writes `prompts/reviewer.compiled.json`, with
    `metric.py` supplying the verdict metric and its two label sets (ADR-009).
  - `compile_correlator.py` writes `prompts/correlator.compiled.json`, with
    `correlation.py` supplying the set metric, the seeds, and the three shortcut
    baselines (ADR-012).

Three specialists carry no compile target, because the database holds no label for a
priority order, a response plan, or an authentication judgement that the prompt's own
rule does not already state. ADR-012 records that test as IR11.

See docs/decisions/ADR-009-dspy-compiles-offline.md,
docs/decisions/ADR-012-compile-every-labelled-prompt.md, and plan.md 4.5b.

This package stays outside the four request-time layers (IR8). Nothing in the
serving path imports it, and `metric.py` and `correlation.py` in particular must
import cleanly with DSPy absent, so `tests/test_dspy_metric.py` and
`tests/test_dspy_correlation.py` run without the dev dependency.

The package name shadows the third-party `dspy` library only from inside this
package's own modules if they used a relative import; they do not. An absolute
`import dspy` inside `compile_reviewer.py` resolves to the installed library,
not to this package, because Python resolves top-level absolute imports from
`sys.path`.
"""

from __future__ import annotations
