"""session_kit — backing implementation for the `sk` CLI dispatcher.

Skill markdown holds the contract; this package holds the deterministic plumbing
(session-id resolution, manifest read-modify-write, durable-first artifact
writes). See ADR-0005 for the architectural rationale.
"""

__version__ = "0.1.0"
