"""Build-time DSPy compilation for the verdict-adjudicator prompt.

See docs/decisions/ADR-009-dspy-compiles-offline.md and plan.md 4.5b.

This package stays outside the four request-time layers (IR8). Nothing in the
serving path imports it, and `metric.py` in particular must import cleanly with
DSPy absent, so `tests/test_dspy_metric.py` runs without the dev dependency.

The package name shadows the third-party `dspy` library only from inside this
package's own modules if they used a relative import; they do not. An absolute
`import dspy` inside `compile_adjudicator.py` resolves to the installed library,
not to this package, because Python resolves top-level absolute imports from
`sys.path`.
"""

from __future__ import annotations
