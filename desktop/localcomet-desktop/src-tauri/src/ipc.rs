use std::io::{self, Read};

pub const IPC_PROTOCOL: &str = "localcomet.ipc";
pub const IPC_PROTOCOL_VERSION: &str = "1.0";
pub const MAX_FRAME_BYTES: usize = 4_194_304;
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

#[cfg(test)]
mod tests {
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
