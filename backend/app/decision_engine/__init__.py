"""Aaroh's deterministic decision engine (ADR-0059).

Pure by construction: no database, no network, no clock, no environment, no
randomness. Enforced by the engine purity check, which activates on the
existence of this package.

The implementation module is `ranking`, not `rank`. Re-exporting a function
named `rank` from a module named `rank` makes `app.decision_engine.rank`
resolve to the FUNCTION and silently shadow the module -- which already caused
a purity test to inspect one function's source instead of the whole file, and
pass while a float division sat two functions away.
"""

from .ranking import RankedCandidate, RankedResult, ReasonCode, rank

__all__ = ["RankedCandidate", "RankedResult", "ReasonCode", "rank"]
