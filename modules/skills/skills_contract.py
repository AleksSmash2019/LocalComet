"""Immutable contracts, permissions model and manifest validation for skills.

Strict, dependency-free. Manifest is UNTRUSTED input: every field is bounded,
paths are traversal-checked, permissions are validated against a closed set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Mapping

SKILL_CONTRACT_VERSION = "localcomet.skill/1.0"
SKILL_WORKFLOW_CONTRACT_VERSION = "localcomet.skill/2.0"
SUPPORTED_SKILL_CONTRACTS = frozenset({SKILL_CONTRACT_VERSION, SKILL_WORKFLOW_CONTRACT_VERSION})

# Bounded limits (defence in depth).
MAX_SKILL_ID_CHARS = 64
MAX_SKILL_NAME_CHARS = 128
MAX_SKILL_VERSION_CHARS = 32
MAX_SKILL_DESCRIPTION_CHARS = 2048
MAX_SKILL_AUTHOR_CHARS = 128
MAX_SKILL_ENTRYPOINT_CHARS = 256
MAX_SKILL_FIELD_CHARS = 512
MAX_PERMISSIONS = 32
MAX_CAPABILITIES = 32
MAX_DEPENDENCIES = 16
MAX_MANIFEST_BYTES = 65_536
MAX_WORKFLOW_BYTES = 128 * 1024
MAX_WORKFLOW_STEPS = 16
MAX_WORKFLOW_ID_CHARS = 64
MAX_WORKFLOW_PARAM_CHARS = 120
MAX_WORKFLOW_TEXT_CHARS = 240
MAX_WORKFLOW_TIMEOUT_MS = 60_000
MAX_WORKFLOW_RETRIES = 1

# Archive / upload safety limits.
ALLOWED_ARCHIVE_SUFFIXES = (".zip", ".tar.gz", ".tgz")
MAX_ARCHIVE_BYTES = 32 * 1024 * 1024          # 32 MiB compressed
MAX_EXTRACTED_BYTES = 64 * 1024 * 1024        # 64 MiB uncompressed (compression-bomb guard)
MAX_ARCHIVE_FILES = 512
MAX_ARCHIVE_MEMBER_CHARS = 256
ARCHIVE_BOMB_RATIO = 100                      # max uncompressed:compressed ratio
ZIP_MAGIC = b"PK\x03\x04"
GZIP_MAGIC = b"\x1f\x8b"

SKILL_ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
WINDOWS_ABS_RE = re.compile(r"^[A-Za-z]:[\\/]")


class SkillState(str, Enum):
    QUARANTINED = "QUARANTINED"
    INSTALLED = "INSTALLED"      # registered, DISABLED by default
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    FAILED = "FAILED"


class SkillPermission(str, Enum):
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    NETWORK = "network"
    MODEL_INVOKE = "model.invoke"
    CLIPBOARD = "clipboard"
    PROCESS_SPAWN = "process.spawn"
    SETTINGS_READ = "settings.read"
    SETTINGS_WRITE = "settings.write"
    UI_EXTENSION = "ui.extension"


# Never grantable, never accepted from a manifest.
FORBIDDEN_PERMISSIONS = frozenset({"secrets.access", "secrets.read", "secrets.write"})

ALLOWED_PERMISSIONS = frozenset(p.value for p in SkillPermission)


class SkillErrorCode(str, Enum):
    ARCHIVE_TOO_LARGE = "ARCHIVE_TOO_LARGE"
    ARCHIVE_BOMB = "ARCHIVE_BOMB"
    ARCHIVE_TYPE_DENIED = "ARCHIVE_TYPE_DENIED"
    ARCHIVE_PATH_TRAVERSAL = "ARCHIVE_PATH_TRAVERSAL"
    ARCHIVE_SYMLINK_DENIED = "ARCHIVE_SYMLINK_DENIED"
    ARCHIVE_CORRUPT = "ARCHIVE_CORRUPT"
    MANIFEST_MISSING = "MANIFEST_MISSING"
    MANIFEST_TOO_LARGE = "MANIFEST_TOO_LARGE"
    MANIFEST_INVALID = "MANIFEST_INVALID"
    MANIFEST_UNSUPPORTED_VERSION = "MANIFEST_UNSUPPORTED_VERSION"
    SKILL_ID_INVALID = "SKILL_ID_INVALID"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PERMISSION_UNKNOWN = "PERMISSION_UNKNOWN"
    CHECKSUM_MISMATCH = "CHECKSUM_MISMATCH"
    ENTRYPOINT_MISSING = "ENTRYPOINT_MISSING"
    SKILL_NOT_FOUND = "SKILL_NOT_FOUND"
    SKILL_STATE_CONFLICT = "SKILL_STATE_CONFLICT"
    INSTALL_FAILED = "INSTALL_FAILED"
    WORKFLOW_MISSING = "WORKFLOW_MISSING"
    WORKFLOW_INVALID = "WORKFLOW_INVALID"
    WORKFLOW_UNSUPPORTED_ACTION = "WORKFLOW_UNSUPPORTED_ACTION"
    WORKFLOW_PARAMETER_INVALID = "WORKFLOW_PARAMETER_INVALID"
    SKILL_WORKFLOW_ONLY = "SKILL_WORKFLOW_ONLY"


class SkillError(Exception):
    """Safe, structured skill error. Never leaks absolute paths or stacks."""

    def __init__(self, code: SkillErrorCode, message: str, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details) if details else {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "message": self.message, "details": self.details}


def _is_safe_relative_path(value: str) -> bool:
    if not value or len(value) > MAX_ARCHIVE_MEMBER_CHARS:
        return False
    if value.startswith(("/", "\\")) or WINDOWS_ABS_RE.match(value):
        return False
    parts = re.split(r"[\\/]", value)
    if any(p in ("", ".", "..") for p in parts):
        return False
    return True


def _require_str(data: Mapping[str, Any], key: str, max_len: int) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest field '{key}' must be a non-empty string")
    value = value.strip()
    if len(value) > max_len:
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest field '{key}' exceeds {max_len} chars")
    return value


def _optional_str(data: Mapping[str, Any], key: str, max_len: int) -> str:
    value = data.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest field '{key}' must be a string")
    value = value.strip()
    if len(value) > max_len:
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest field '{key}' exceeds {max_len} chars")
    return value


def _validate_permissions(data: Mapping[str, Any]) -> tuple[str, ...]:
    raw = data.get("permissions", [])
    if not isinstance(raw, list):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, "manifest 'permissions' must be a list")
    if len(raw) > MAX_PERMISSIONS:
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest 'permissions' exceeds {MAX_PERMISSIONS} entries")
    result: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise SkillError(SkillErrorCode.MANIFEST_INVALID, "permission entries must be strings")
        perm = item.strip()
        if perm in FORBIDDEN_PERMISSIONS:
            raise SkillError(SkillErrorCode.PERMISSION_DENIED, f"permission '{perm}' is never grantable")
        if perm not in ALLOWED_PERMISSIONS:
            raise SkillError(SkillErrorCode.PERMISSION_UNKNOWN, f"unknown permission '{perm}'")
        if perm not in result:
            result.append(perm)
    return tuple(result)


def _validate_str_list(data: Mapping[str, Any], key: str, max_items: int) -> tuple[str, ...]:
    raw = data.get(key, [])
    if raw is None:
        return ()
    if not isinstance(raw, list) or len(raw) > max_items:
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest '{key}' must be a list of at most {max_items}")
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str) or len(item) > MAX_SKILL_FIELD_CHARS:
            raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"manifest '{key}' entries must be bounded strings")
        out.append(item.strip())
    return tuple(out)


ALLOWED_WORKFLOW_ACTIONS = frozenset({
    "computer_use.open_app",
    "computer_use.wait_for_window",
    "computer_use.observe",
    "computer_use.type_element",
    "computer_use.close_owned",
})

WORKFLOW_ACTION_RISK = {
    "computer_use.open_app": "guarded",
    "computer_use.wait_for_window": "read_only",
    "computer_use.observe": "read_only",
    "computer_use.type_element": "guarded",
    "computer_use.close_owned": "dangerous",
}
ALLOWED_WORKFLOW_RISKS = frozenset({"read_only", "guarded", "dangerous"})
ALLOWED_TRUST_TIERS = frozenset({"builtin_verified", "vendor_verified", "workspace_reviewed", "community_unreviewed", "blocked"})


@dataclass(frozen=True, slots=True)
class SkillManifest:
    skill_id: str
    name: str
    version: str
    entrypoint: str
    permissions: tuple[str, ...]
    description: str = ""
    author: str = ""
    compatible_app_version: str = ""
    capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    checksum: str = ""
    contract: str = SKILL_CONTRACT_VERSION
    workflow: str = ""
    trust_tier: str = "community_unreviewed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.skill_id,
            "name": self.name,
            "version": self.version,
            "entrypoint": self.entrypoint,
            "permissions": list(self.permissions),
            "description": self.description,
            "author": self.author,
            "compatibleAppVersion": self.compatible_app_version,
            "capabilities": list(self.capabilities),
            "dependencies": list(self.dependencies),
            "checksum": self.checksum,
            "contract": self.contract,
            "workflow": self.workflow,
            "trustTier": self.trust_tier,
        }


def validate_manifest_dict(data: Mapping[str, Any]) -> SkillManifest:
    """Validate an untrusted manifest mapping into an immutable SkillManifest."""
    if not isinstance(data, Mapping):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, "manifest must be an object")

    contract = _optional_str(data, "contract", MAX_SKILL_FIELD_CHARS) or SKILL_CONTRACT_VERSION
    if contract not in SUPPORTED_SKILL_CONTRACTS:
        raise SkillError(
            SkillErrorCode.MANIFEST_UNSUPPORTED_VERSION,
            f"unsupported skill contract '{contract}'",
        )

    skill_id = _require_str(data, "id", MAX_SKILL_ID_CHARS)
    if not SKILL_ID_RE.fullmatch(skill_id):
        raise SkillError(SkillErrorCode.SKILL_ID_INVALID, f"invalid skill id '{skill_id}'")

    name = _require_str(data, "name", MAX_SKILL_NAME_CHARS)
    version = _require_str(data, "version", MAX_SKILL_VERSION_CHARS)
    if not SEMVER_RE.fullmatch(version):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, f"invalid semver '{version}'")

    entrypoint = _require_str(data, "entrypoint", MAX_SKILL_ENTRYPOINT_CHARS)
    if not _is_safe_relative_path(entrypoint):
        raise SkillError(SkillErrorCode.ARCHIVE_PATH_TRAVERSAL, "entrypoint must be a safe relative path")
    if not entrypoint.endswith(".py"):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, "entrypoint must be a .py file")

    workflow = _optional_str(data, "workflow", MAX_SKILL_ENTRYPOINT_CHARS)
    if workflow:
        if not _is_safe_relative_path(workflow) or not workflow.endswith(".json"):
            raise SkillError(SkillErrorCode.ARCHIVE_PATH_TRAVERSAL, "workflow must be a safe relative .json path")
    if contract == SKILL_WORKFLOW_CONTRACT_VERSION and not workflow:
        raise SkillError(SkillErrorCode.WORKFLOW_MISSING, "workflow v2 skills require a workflow path")

    trust_tier = _optional_str(data, "trustTier", MAX_SKILL_FIELD_CHARS) or "community_unreviewed"
    if trust_tier not in ALLOWED_TRUST_TIERS:
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, "unknown skill trust tier")

    permissions = _validate_permissions(data)
    capabilities = _validate_str_list(data, "capabilities", MAX_CAPABILITIES)
    dependencies = _validate_str_list(data, "dependencies", MAX_DEPENDENCIES)

    checksum = _optional_str(data, "checksum", MAX_SKILL_FIELD_CHARS)
    if checksum and not SHA256_RE.fullmatch(checksum):
        raise SkillError(SkillErrorCode.MANIFEST_INVALID, "checksum must be lowercase sha256 hex")

    return SkillManifest(
        skill_id=skill_id,
        name=name,
        version=version,
        entrypoint=entrypoint,
        permissions=permissions,
        description=_optional_str(data, "description", MAX_SKILL_DESCRIPTION_CHARS),
        author=_optional_str(data, "author", MAX_SKILL_AUTHOR_CHARS),
        compatible_app_version=_optional_str(data, "compatibleAppVersion", MAX_SKILL_VERSION_CHARS),
        capabilities=capabilities,
        dependencies=dependencies,
        checksum=checksum,
        contract=contract,
        workflow=workflow,
        trust_tier=trust_tier,
    )


@dataclass(frozen=True, slots=True)
class WorkflowParameter:
    name: str
    type: str = "string"
    required: bool = True
    max_length: int = MAX_WORKFLOW_TEXT_CHARS


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    step_id: str
    action: str
    risk: str
    requires_approval: bool
    arguments: Mapping[str, Any]
    precondition: Mapping[str, Any]
    postcondition: Mapping[str, Any]
    timeout_ms: int
    max_retries: int


@dataclass(frozen=True, slots=True)
class SkillWorkflow:
    schema_version: str
    skill_id: str
    parameters: tuple[WorkflowParameter, ...]
    steps: tuple[WorkflowStep, ...]
    max_runtime_ms: int


def _workflow_id(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > MAX_WORKFLOW_ID_CHARS:
        raise SkillError(SkillErrorCode.WORKFLOW_INVALID, f"workflow {field_name} is invalid")
    value = value.strip()
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", value):
        raise SkillError(SkillErrorCode.WORKFLOW_INVALID, f"workflow {field_name} is invalid")
    return value


def _workflow_object(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SkillError(SkillErrorCode.WORKFLOW_INVALID, f"workflow {field_name} must be an object")
    return value


def _validate_workflow_arguments(value: Any) -> Mapping[str, Any]:
    obj = _workflow_object(value, "step.arguments")
    if len(obj) > 12:
        raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow step has too many arguments")
    for key, item in obj.items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", key):
            raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow argument key is invalid")
        if isinstance(item, str) and len(item) > MAX_WORKFLOW_PARAM_CHARS and not item.startswith("${"):
            raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow argument string is too long")
        if isinstance(item, (dict, list)):
            raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "nested workflow argument objects are not allowed")
    return dict(obj)


def validate_workflow_dict(data: Mapping[str, Any], *, expected_skill_id: str = "") -> SkillWorkflow:
    if not isinstance(data, Mapping):
        raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow must be an object")
    schema_version = data.get("schema_version", data.get("schemaVersion"))
    if schema_version != "localcomet.skill.workflow/1.0":
        raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "unsupported workflow schema")
    skill_id = _workflow_id(data.get("skill_id", data.get("skillId", "")), "skill_id")
    if expected_skill_id and skill_id != expected_skill_id:
        raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow skill_id does not match manifest")

    raw_params = data.get("parameters", {})
    if not isinstance(raw_params, Mapping) or len(raw_params) > 12:
        raise SkillError(SkillErrorCode.WORKFLOW_PARAMETER_INVALID, "workflow parameters must be a bounded object")
    parameters: list[WorkflowParameter] = []
    for name, raw in raw_params.items():
        pname = _workflow_id(name, "parameter name")
        pobj = _workflow_object(raw, f"parameter '{pname}'")
        ptype = pobj.get("type", "string")
        if ptype != "string":
            raise SkillError(SkillErrorCode.WORKFLOW_PARAMETER_INVALID, "only string workflow parameters are supported")
        required = pobj.get("required", True)
        max_length = pobj.get("max_length", pobj.get("maxLength", MAX_WORKFLOW_TEXT_CHARS))
        if not isinstance(required, bool) or not isinstance(max_length, int) or not 1 <= max_length <= MAX_WORKFLOW_TEXT_CHARS:
            raise SkillError(SkillErrorCode.WORKFLOW_PARAMETER_INVALID, f"workflow parameter '{pname}' bounds are invalid")
        parameters.append(WorkflowParameter(pname, ptype, required, max_length))

    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= MAX_WORKFLOW_STEPS:
        raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow steps must contain 1..16 steps")
    steps: list[WorkflowStep] = []
    seen: set[str] = set()
    for raw_step in raw_steps:
        step = _workflow_object(raw_step, "step")
        step_id = _workflow_id(step.get("id"), "step id")
        if step_id in seen:
            raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow step ids must be unique")
        seen.add(step_id)
        action = step.get("action")
        if action not in ALLOWED_WORKFLOW_ACTIONS:
            raise SkillError(SkillErrorCode.WORKFLOW_UNSUPPORTED_ACTION, "workflow action is not allowlisted")
        risk = step.get("risk", WORKFLOW_ACTION_RISK[action])
        if risk not in ALLOWED_WORKFLOW_RISKS or risk != WORKFLOW_ACTION_RISK[action]:
            raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow step risk does not match host policy")
        requires_approval = step.get("requires_approval", step.get("requiresApproval", risk != "read_only"))
        if not isinstance(requires_approval, bool) or (risk == "dangerous" and not requires_approval):
            raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "dangerous workflow steps require approval")
        timeout_ms = step.get("timeout_ms", step.get("timeoutMs", 5000))
        max_retries = step.get("max_retries", step.get("maxRetries", 0))
        if not isinstance(timeout_ms, int) or not 100 <= timeout_ms <= MAX_WORKFLOW_TIMEOUT_MS:
            raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow step timeout is out of bounds")
        if not isinstance(max_retries, int) or not 0 <= max_retries <= MAX_WORKFLOW_RETRIES:
            raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow step retry count is out of bounds")
        precondition = _workflow_object(step.get("precondition", {"kind": "none"}), "step.precondition")
        postcondition = _workflow_object(step.get("postcondition", {"kind": "none"}), "step.postcondition")
        if not isinstance(precondition.get("kind"), str) or not isinstance(postcondition.get("kind"), str):
            raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow pre/postcondition kind is required")
        steps.append(WorkflowStep(step_id, action, risk, requires_approval, _validate_workflow_arguments(step.get("arguments", {})), dict(precondition), dict(postcondition), timeout_ms, max_retries))

    max_runtime_ms = data.get("max_runtime_ms", data.get("maxRuntimeMs", 30_000))
    if not isinstance(max_runtime_ms, int) or not 100 <= max_runtime_ms <= 120_000:
        raise SkillError(SkillErrorCode.WORKFLOW_INVALID, "workflow max runtime is out of bounds")
    return SkillWorkflow("localcomet.skill.workflow/1.0", skill_id, tuple(parameters), tuple(steps), max_runtime_ms)


def bind_workflow(workflow: SkillWorkflow, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
    supplied = dict(arguments or {})
    allowed = {param.name for param in workflow.parameters}
    unknown = sorted(set(supplied) - allowed)
    if unknown:
        raise SkillError(SkillErrorCode.WORKFLOW_PARAMETER_INVALID, "unknown workflow parameter")
    values: dict[str, str] = {}
    for param in workflow.parameters:
        value = supplied.get(param.name)
        if value is None and param.required:
            raise SkillError(SkillErrorCode.WORKFLOW_PARAMETER_INVALID, f"missing workflow parameter '{param.name}'")
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip() or len(value) > param.max_length:
            raise SkillError(SkillErrorCode.WORKFLOW_PARAMETER_INVALID, f"workflow parameter '{param.name}' is invalid")
        values[param.name] = value

    def substitute(value: Any) -> Any:
        if isinstance(value, str):
            exact = re.fullmatch(r"\$\{([a-zA-Z0-9._-]+)\}", value)
            if exact:
                name = exact.group(1)
                if name not in values:
                    raise SkillError(SkillErrorCode.WORKFLOW_PARAMETER_INVALID, f"unbound workflow parameter '{name}'")
                return values[name]
            for name, bound in values.items():
                value = value.replace("${" + name + "}", bound)
            return value
        if isinstance(value, list):
            return [substitute(item) for item in value]
        if isinstance(value, Mapping):
            return {str(key): substitute(item) for key, item in value.items()}
        return value

    steps = []
    for step in workflow.steps:
        steps.append({
            "id": step.step_id,
            "action": step.action,
            "risk": step.risk,
            "requires_approval": step.requires_approval,
            "arguments": substitute(step.arguments),
            "precondition": substitute(step.precondition),
            "postcondition": substitute(step.postcondition),
            "timeout_ms": step.timeout_ms,
            "max_retries": step.max_retries,
        })
    return {"schema_version": "localcomet.skill.plan/1.0", "skill_id": workflow.skill_id, "steps": steps, "max_runtime_ms": workflow.max_runtime_ms, "parameters": values}
