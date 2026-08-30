"""Compatibility marker for the declarative v2 workflow.

This file is intentionally not an execution path. SkillsManager rejects
entrypoint execution for localcomet.skill/2.0 packages and compiles
workflow.json into host-approved typed steps instead.
"""

if __name__ == "__main__":
    raise SystemExit("declarative workflow skill: use workflow compiler")
