use serde::Deserialize;
use std::io::{self, Read};

pub const IPC_PROTOCOL: &str = "localcomet.ipc";
pub const IPC_PROTOCOL_VERSION: &str = "1.0";
pub const MAX_FRAME_BYTES: usize = 4_194_304;
#[allow(dead_code)]
pub const MAX_HEALTH_JSON_DEPTH: usize = 16;
const FRAME_PREFIX_BYTES: usize = 4;

pub fn desktop_hello_frame(message_id: &str, session_nonce: &str) -> io::Result<Vec<u8>> {
    json_frame(&format!(
        "{{\"id\":\"{}\",\"method\":null,\"payload\":{{\"capabilities\":[\"lifecycle\"],\"role\":\"desktop_bridge\",\"session_nonce\":\"{}\",\"supported_versions\":[\"{}\"]}},\"protocol\":\"{}\",\"reply_to\":null,\"run_id\":null,\"sequence\":0,\"type\":\"hello\",\"version\":\"{}\"}}",
        escape_json(message_id),
        escape_json(session_nonce),
        IPC_PROTOCOL_VERSION,
        IPC_PROTOCOL,
        IPC_PROTOCOL_VERSION
    ))
}

pub fn lifecycle_request_frame(
    message_id: &str,
    method: &str,
    sequence: u64,
) -> io::Result<Vec<u8>> {
    json_frame(&format!(
        "{{\"id\":\"{}\",\"method\":\"{}\",\"payload\":{{}},\"protocol\":\"{}\",\"reply_to\":null,\"run_id\":null,\"sequence\":{},\"type\":\"request\",\"version\":\"{}\"}}",
        escape_json(message_id),
        escape_json(method),
        IPC_PROTOCOL,
        sequence,
        IPC_PROTOCOL_VERSION
    ))
}

/// Build the MVP-P0-C-R1 health request: existing localcomet.ipc/1.0 request
/// envelope with `method = app.health` and a typed `health.check` payload.
/// The outer `id` and `payload.requestId` are the same `hreq_` value.
pub fn health_check_request_frame(
    request_id: &str,
    generation_id: u64,
    startup_nonce: &str,
    runtime_instance_id: &str,
    sent_at_unix_ms: i64,
    sequence: u64,
) -> io::Result<Vec<u8>> {
    let envelope = serde_json::json!({
        "protocol": IPC_PROTOCOL,
        "version": IPC_PROTOCOL_VERSION,
        "type": "request",
        "id": request_id,
        "method": "app.health",
        "run_id": serde_json::Value::Null,
        "sequence": sequence,
        "reply_to": serde_json::Value::Null,
        "payload": {
            "type": "health.check",
            "protocolVersion": 1,
            "requestId": request_id,
            "generationId": generation_id,
            "startupNonce": startup_nonce,
            "runtimeInstanceId": runtime_instance_id,
            "sentAtUnixMs": sent_at_unix_ms,
        },
    });
    let body = serde_json::to_string(&envelope)
        .map_err(|error| io::Error::new(io::ErrorKind::InvalidInput, error))?;
    json_frame(&body)
}

pub fn json_frame(body: &str) -> io::Result<Vec<u8>> {
    let bytes = body.as_bytes();
    if bytes.is_empty() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "empty IPC frame",
        ));
    }
    if bytes.len() > MAX_FRAME_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "IPC frame too large",
        ));
    }
    let mut frame = Vec::with_capacity(FRAME_PREFIX_BYTES + bytes.len());
    frame.extend_from_slice(&(bytes.len() as u32).to_be_bytes());
    frame.extend_from_slice(bytes);
    Ok(frame)
}

pub fn read_frame(reader: &mut impl Read) -> io::Result<Vec<u8>> {
    let mut prefix = [0_u8; FRAME_PREFIX_BYTES];
    reader.read_exact(&mut prefix)?;
    let length = u32::from_be_bytes(prefix) as usize;
    if length == 0 {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "empty IPC frame",
        ));
    }
    if length > MAX_FRAME_BYTES {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "IPC frame too large",
        ));
    }
    let mut body = vec![0_u8; length];
    reader.read_exact(&mut body)?;
    Ok(body)
}

fn escape_json(value: &str) -> String {
    let mut escaped = String::with_capacity(value.len());
    for ch in value.chars() {
        match ch {
            '"' => escaped.push_str("\\\""),
            '\\' => escaped.push_str("\\\\"),
            '\n' => escaped.push_str("\\n"),
            '\r' => escaped.push_str("\\r"),
            '\t' => escaped.push_str("\\t"),
            ch if ch.is_control() => escaped.push_str(&format!("\\u{:04x}", ch as u32)),
            ch => escaped.push(ch),
        }
    }
    escaped
}

#[allow(dead_code)]
/// Semantic duplicate-key detector (MVP-P0-C-R1).
///
/// Operates on DECODED JSON object keys via a recursive serde visitor with a
/// per-map HashSet, so `"status"` and `"status"` collide, while repeated
/// STRING VALUES inside arrays are never mistaken for object keys.
/// Also enforces max structural depth, rejects non-finite numbers, trailing
/// data and multiple top-level values. No character scanning is used.
pub fn parse_semantic_json(body: &[u8]) -> Result<serde_json::Value, &'static str> {
    let text = std::str::from_utf8(body).map_err(|_| "invalid_utf8")?;
    let mut de = serde_json::Deserializer::from_str(text);
    let value =
        SemanticValue::deserialize(&mut de).map_err(|error| classify_semantic_error(&error))?;
    de.end().map_err(|_| "trailing_data")?;
    Ok(value.0)
}

fn classify_semantic_error(error: &serde_json::Error) -> &'static str {
    let text = error.to_string();
    if text.contains("duplicate_key") {
        "duplicate_key"
    } else if text.contains("max_depth_exceeded") {
        "max_depth_exceeded"
    } else if text.contains("non_finite_number") {
        "non_finite_number"
    } else {
        "invalid_json"
    }
}

struct SemanticValue(serde_json::Value);

impl<'de> serde::Deserialize<'de> for SemanticValue {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        deserializer
            .deserialize_any(SemanticVisitor { depth: 1 })
            .map(SemanticValue)
    }
}

struct SemanticVisitor {
    depth: usize,
}

impl<'de> serde::de::Visitor<'de> for SemanticVisitor {
    type Value = serde_json::Value;

    fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
        formatter.write_str("a bounded JSON value without duplicate object keys")
    }

    fn visit_unit<E: serde::de::Error>(self) -> Result<Self::Value, E> {
        Ok(serde_json::Value::Null)
    }

    fn visit_bool<E: serde::de::Error>(self, value: bool) -> Result<Self::Value, E> {
        Ok(serde_json::Value::Bool(value))
    }

    fn visit_i64<E: serde::de::Error>(self, value: i64) -> Result<Self::Value, E> {
        Ok(serde_json::Value::from(value))
    }

    fn visit_u64<E: serde::de::Error>(self, value: u64) -> Result<Self::Value, E> {
        Ok(serde_json::Value::from(value))
    }

    fn visit_f64<E: serde::de::Error>(self, value: f64) -> Result<Self::Value, E> {
        if !value.is_finite() {
            return Err(serde::de::Error::custom("non_finite_number"));
        }
        Ok(serde_json::Value::from(value))
    }

    fn visit_str<E: serde::de::Error>(self, value: &str) -> Result<Self::Value, E> {
        Ok(serde_json::Value::String(value.to_owned()))
    }

    fn visit_seq<A>(self, mut seq: A) -> Result<Self::Value, A::Error>
    where
        A: serde::de::SeqAccess<'de>,
    {
        if self.depth >= MAX_HEALTH_JSON_DEPTH {
            return Err(serde::de::Error::custom("max_depth_exceeded"));
        }
        let mut items = Vec::new();
        while let Some(item) = seq.next_element_seed(SemanticSeed {
            depth: self.depth + 1,
        })? {
            items.push(item);
        }
        Ok(serde_json::Value::Array(items))
    }

    fn visit_map<A>(self, mut map: A) -> Result<Self::Value, A::Error>
    where
        A: serde::de::MapAccess<'de>,
    {
        if self.depth >= MAX_HEALTH_JSON_DEPTH {
            return Err(serde::de::Error::custom("max_depth_exceeded"));
        }
        let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
        let mut object = serde_json::Map::new();
        while let Some(key) = map.next_key::<String>()? {
            if !seen.insert(key.clone()) {
                return Err(serde::de::Error::custom("duplicate_key"));
            }
            let value = map.next_value_seed(SemanticSeed {
                depth: self.depth + 1,
            })?;
            object.insert(key, value);
        }
        Ok(serde_json::Value::Object(object))
    }
}

struct SemanticSeed {
    depth: usize,
}

impl<'de> serde::de::DeserializeSeed<'de> for SemanticSeed {
    type Value = serde_json::Value;

    fn deserialize<D>(self, deserializer: D) -> Result<Self::Value, D::Error>
    where
        D: serde::Deserializer<'de>,
    {
        deserializer.deserialize_any(SemanticVisitor { depth: self.depth })
    }
}

#[allow(dead_code)]
pub fn parse_health_frame(body: &[u8]) -> Result<serde_json::Value, &'static str> {
    if body.is_empty() {
        return Err("empty_frame");
    }
    if body.len() > MAX_FRAME_BYTES {
        return Err("frame_too_large");
    }
    parse_semantic_json(body)
}

#[cfg(test)]
mod tests {
    #[test]
    fn p0c_r1_semantic_accepts_repeated_array_values() {
        let v = super::parse_semantic_json(br#"{"tags":["x","x","x"]}"#);
        assert!(v.is_ok(), "repeated array values must be accepted: {v:?}");
    }

    #[test]
    fn p0c_r1_semantic_accepts_array_value_equal_to_sibling_key() {
        let v = super::parse_semantic_json(br#"{"status":"ready","list":[1,"status"]}"#);
        assert!(
            v.is_ok(),
            "array string equal to a key name must be accepted: {v:?}"
        );
    }

    #[test]
    fn p0c_r1_semantic_rejects_decoded_unicode_duplicate() {
        let v = super::parse_semantic_json(br#"{"status":"degraded","st\u0061tus":"ready"}"#);
        assert_eq!(v.unwrap_err(), "duplicate_key");
    }

    #[test]
    fn p0c_r1_semantic_rejects_literal_duplicate() {
        let v = super::parse_semantic_json(br#"{"status":"ready","status":"degraded"}"#);
        assert_eq!(v.unwrap_err(), "duplicate_key");
    }

    #[test]
    fn p0c_r1_semantic_allows_same_key_in_separate_objects() {
        let v =
            super::parse_semantic_json(br#"{"a":{"status":"ready"},"b":{"status":"degraded"}}"#);
        assert!(
            v.is_ok(),
            "same key in sibling objects must be accepted: {v:?}"
        );
    }

    #[test]
    fn p0c_r1_semantic_depth_ignores_braces_inside_strings() {
        let v = super::parse_semantic_json(br#"{"status":"{{{{{{{{{{{{{{{{{{{{ready}}}}}}"}"#);
        assert!(
            v.is_ok(),
            "braces inside a string must not count as depth: {v:?}"
        );
    }

    #[test]
    fn p0c_r1_semantic_rejects_trailing_data() {
        let v = super::parse_semantic_json(br#"{"status":"ready"}garbage"#);
        assert_eq!(v.unwrap_err(), "trailing_data");
    }

    #[test]
    fn p0c_r1_semantic_rejects_multiple_top_level_objects() {
        let v = super::parse_semantic_json(br#"{"a":1}{"b":2}"#);
        assert_eq!(v.unwrap_err(), "trailing_data");
    }

    #[test]
    fn p0c_r1_semantic_rejects_invalid_utf8() {
        let v = super::parse_semantic_json(&[
            0x7b, 0x22, 0x61, 0x22, 0x3a, 0x22, 0xff, 0xfe, 0x22, 0x7d,
        ]);
        assert_eq!(v.unwrap_err(), "invalid_utf8");
    }

    #[test]
    fn p0c_r1_semantic_rejects_excessive_depth() {
        let deep = format!("{}1{}", "[".repeat(40), "]".repeat(40));
        let v = super::parse_semantic_json(deep.as_bytes());
        assert_eq!(v.unwrap_err(), "max_depth_exceeded");
    }

    #[test]
    fn p0c_r1_health_request_frame_has_typed_payload() {
        let f = super::health_check_request_frame(
            "hreq_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            1,
            "scn_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "rti_cccccccccccccccccccccccccccccccc",
            1234,
            7,
        )
        .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&f[4..]).unwrap();
        assert_eq!(body["method"], "app.health");
        assert_eq!(body["payload"]["type"], "health.check");
        assert_eq!(body["id"], body["payload"]["requestId"]);
        assert_eq!(body["payload"]["protocolVersion"], 1);
        assert_eq!(body["payload"]["generationId"], 1);
    }

    use super::*;
    use std::io::Cursor;

    #[test]
    fn frames_are_big_endian_length_prefixed_json() {
        let frame = lifecycle_request_frame("desk-health-1", "app.health", 7).unwrap();
        let length = u32::from_be_bytes(frame[..4].try_into().unwrap()) as usize;
        assert_eq!(length, frame.len() - 4);
        let body = String::from_utf8(frame[4..].to_vec()).unwrap();
        assert!(body.contains("\"method\":\"app.health\""));
        assert!(body.contains("\"sequence\":7"));
    }

    #[test]
    fn reader_rejects_zero_length_frame() {
        let mut reader = Cursor::new([0_u8, 0, 0, 0]);
        let error = read_frame(&mut reader).unwrap_err();
        assert_eq!(error.kind(), io::ErrorKind::InvalidData);
    }
}
