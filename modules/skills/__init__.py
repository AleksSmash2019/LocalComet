"""LocalComet Skills subsystem.

Secure-by-default skill lifecycle:
upload -> quarantine -> validate archive -> validate manifest -> inspect
permissions -> verify checksum -> install (atomic) -> register -> DISABLED by
default -> explicit enable -> execute (restricted) -> disable -> uninstall.

The skill code is NEVER executed during scan/validate/install. Untrusted skills
never run in the host process and never receive secrets. See docs/SECURITY.md.
"""

from modules.skills.skills_contract import (
    SKILL_CONTRACT_VERSION,
    SkillError,
    SkillErrorCode,
    SkillManifest,
    SkillPermission,
    SkillState,
    validate_manifest_dict,
)
from modules.skills.skills_manager import SkillsManager

__all__ = [
    "SKILL_CONTRACT_VERSION",
    "SkillError",
    "SkillErrorCode",
    "SkillManifest",
    "SkillPermission",
    "SkillState",
    "SkillsManager",
    "validate_manifest_dict",
]
