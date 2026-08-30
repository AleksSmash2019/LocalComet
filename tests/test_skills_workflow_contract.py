import unittest

from modules.skills.skills_contract import (
    SkillError,
    SkillErrorCode,
    bind_workflow,
    validate_workflow_dict,
)


def workflow_data():
    return {
        "schema_version": "localcomet.skill.workflow/1.0",
        "skill_id": "demo.skill",
        "parameters": {"text": {"type": "string", "required": True, "max_length": 40}},
        "max_runtime_ms": 30_000,
        "steps": [
            {
                "id": "observe",
                "action": "computer_use.observe",
                "risk": "read_only",
                "requires_approval": False,
                "arguments": {"target": "notepad"},
                "precondition": {"kind": "window_ready"},
                "postcondition": {"kind": "fresh_uia_observation"},
                "timeout_ms": 5000,
                "max_retries": 0,
            },
            {
                "id": "type",
                "action": "computer_use.type_element",
                "risk": "guarded",
                "requires_approval": True,
                "arguments": {"text": "${text}"},
                "precondition": {"kind": "fresh_uia_observation", "step": "observe"},
                "postcondition": {"kind": "fresh_uia_text_contains", "text": "${text}"},
                "timeout_ms": 5000,
                "max_retries": 0,
            },
        ],
    }


class SkillWorkflowContractTests(unittest.TestCase):
    def test_action_risk_mismatch_is_rejected(self):
        data = workflow_data()
        data["steps"][0]["risk"] = "guarded"
        with self.assertRaises(SkillError) as cm:
            validate_workflow_dict(data, expected_skill_id="demo.skill")
        self.assertEqual(cm.exception.code, SkillErrorCode.WORKFLOW_INVALID)

    def test_dangerous_step_cannot_disable_approval(self):
        data = workflow_data()
        data["steps"].append({
            "id": "close",
            "action": "computer_use.close_owned",
            "risk": "dangerous",
            "requires_approval": False,
            "arguments": {},
            "precondition": {"kind": "owned_process_started", "step": "type"},
            "postcondition": {"kind": "owned_process_terminated"},
            "timeout_ms": 5000,
            "max_retries": 0,
        })
        with self.assertRaises(SkillError) as cm:
            validate_workflow_dict(data, expected_skill_id="demo.skill")
        self.assertEqual(cm.exception.code, SkillErrorCode.WORKFLOW_INVALID)

    def test_malformed_precondition_is_rejected(self):
        data = workflow_data()
        data["steps"][0]["precondition"] = []
        with self.assertRaises(SkillError) as cm:
            validate_workflow_dict(data, expected_skill_id="demo.skill")
        self.assertEqual(cm.exception.code, SkillErrorCode.WORKFLOW_INVALID)

    def test_malformed_postcondition_kind_is_rejected(self):
        data = workflow_data()
        data["steps"][0]["postcondition"] = {"kind": 7}
        with self.assertRaises(SkillError) as cm:
            validate_workflow_dict(data, expected_skill_id="demo.skill")
        self.assertEqual(cm.exception.code, SkillErrorCode.WORKFLOW_INVALID)

    def test_unknown_parameter_is_rejected_during_binding(self):
        workflow = validate_workflow_dict(workflow_data(), expected_skill_id="demo.skill")
        with self.assertRaises(SkillError) as cm:
            bind_workflow(workflow, {"text": "ok", "unexpected": "nope"})
        self.assertEqual(cm.exception.code, SkillErrorCode.WORKFLOW_PARAMETER_INVALID)

    def test_unsupported_action_is_rejected(self):
        data = workflow_data()
        data["steps"][0]["action"] = "computer_use.press_key"
        with self.assertRaises(SkillError) as cm:
            validate_workflow_dict(data, expected_skill_id="demo.skill")
        self.assertEqual(cm.exception.code, SkillErrorCode.WORKFLOW_UNSUPPORTED_ACTION)


if __name__ == "__main__":
    unittest.main()
