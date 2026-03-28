WARMUP_PROMPT_TEMPLATE = """Review the attached gameplay segment and all attached session context.

Reply with short bullets covering:
- current gameplay state
- current player objective
- major carryover threads still active
- recurring friction or clarity patterns already established
- what will matter most for the next specialized analyses

Do not perform specialized analysis yet.
Do not ignore the earlier session context.
"""

__all__ = ["WARMUP_PROMPT_TEMPLATE"]
