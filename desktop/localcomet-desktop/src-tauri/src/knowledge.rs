use crate::control_plane::{BridgeError, ControlPlaneBridge, ControlPlaneMethod};
use serde_json::{json, Value};
use std::sync::Arc;
use tauri::State;

pub const MAX_KNOWLEDGE_CONTEXT_CHARS: u32 = 12_000;
pub const MAX_KNOWLEDGE_RESULTS: u8 = 8;

#[tauri::command]
pub fn knowledge_turn_preview(
    state: State<'_, Arc<ControlPlaneBridge>>,
    turn_id: String,
    intent: String,
    max_context_chars: u32,
    max_results: u8,
) -> Result<Value, BridgeError> {
    ensure_turn_id(&turn_id)?;
    ensure_intent(&intent)?;
    if !(1..=MAX_KNOWLEDGE_CONTEXT_CHARS).contains(&max_context_chars) {
        return Err(BridgeError::new(
            "invalid_payload",
            "knowledge context limit is invalid",
        ));
    }
    if !(1..=MAX_KNOWLEDGE_RESULTS).contains(&max_results) {
        return Err(BridgeError::new(
            "invalid_payload",
            "knowledge result limit is invalid",
        ));
    }
    state.request(
        ControlPlaneMethod::KnowledgeTurnPreview,
        json!({
            "turn_id": turn_id,
            "intent": intent,
            "max_context_chars": max_context_chars,
            "max_results": max_results,
        }),
    )
}

#[tauri::command]
pub fn knowledge_turn_decide(
    state: State<'_, Arc<ControlPlaneBridge>>,
    turn_id: String,
    injection_id: String,
    expected_preview_hash: String,
    action: String,
) -> Result<Value, BridgeError> {
    ensure_turn_id(&turn_id)?;
    ensure_injection_id(&injection_id)?;
    ensure_sha256(&expected_preview_hash)?;
    if !matches!(
        action.as_str(),
        "INCLUDE_AND_SEND" | "REJECT_AND_SEND_WITHOUT_KNOWLEDGE" | "CANCEL"
    ) {
        return Err(BridgeError::new(
            "invalid_payload",
            "knowledge action is invalid",
        ));
    }
    state.request(
        ControlPlaneMethod::KnowledgeTurnDecide,
        json!({
            "turn_id": turn_id,
            "injection_id": injection_id,
            "expected_preview_hash": expected_preview_hash,
            "action": action,
        }),
    )
}

fn ensure_turn_id(value: &str) -> Result<(), BridgeError> {
    if value.len() == 24
        && value
            .chars()
            .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase())
    {
        Ok(())
    } else {
        Err(BridgeError::new("invalid_payload", "turn_id is invalid"))
    }
}

fn ensure_injection_id(value: &str) -> Result<(), BridgeError> {
    if value.starts_with("kinj:")
        && (6..=128).contains(&value.len())
        && value
            .chars()
            .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, ':' | '-'))
    {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            "injection_id is invalid",
        ))
    }
}

fn ensure_sha256(value: &str) -> Result<(), BridgeError> {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return Err(BridgeError::new(
            "invalid_payload",
            "preview hash is invalid",
        ));
    };
    if hex.len() == 64
        && hex
            .chars()
            .all(|ch| ch.is_ascii_hexdigit() && !ch.is_ascii_uppercase())
    {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            "preview hash is invalid",
        ))
    }
}

fn ensure_intent(value: &str) -> Result<(), BridgeError> {
    if matches!(
        value,
        "AUTO"
            | "CURRENT_STATE"
            | "ARCHITECTURE"
            | "SECURITY"
            | "HISTORY"
            | "FOUNDER_INTENT"
            | "ROADMAP"
            | "RESEARCH"
            | "OPERATIONAL"
            | "INCIDENT"
    ) {
        Ok(())
    } else {
        Err(BridgeError::new(
            "invalid_payload",
            "knowledge intent is invalid",
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounded_identifiers_are_enforced() {
        assert!(ensure_turn_id("a23456789012345678901234").is_ok());
        assert!(ensure_turn_id("not-a-turn").is_err());
        assert!(ensure_injection_id("kinj:00000000-0000-4000-8000-000000000001").is_ok());
        assert!(ensure_injection_id("bundle:forged").is_err());
        assert!(ensure_sha256(&format!("sha256:{}", "a".repeat(64))).is_ok());
        assert!(ensure_sha256("sha256:bad").is_err());
    }

    #[test]
    fn exact_actions_and_intents_are_enforced() {
        assert!(ensure_intent("ARCHITECTURE").is_ok());
        assert!(ensure_intent("ARBITRARY").is_err());
        assert_eq!(MAX_KNOWLEDGE_CONTEXT_CHARS, 12_000);
        assert_eq!(MAX_KNOWLEDGE_RESULTS, 8);
    }
}
