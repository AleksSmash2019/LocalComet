//! Hugging Face catalog browsing, proxied through the Rust backend.
//!
//! The frontend must never call huggingface.co directly: browser `fetch` from
//! the webview would bypass the vetted network boundary (fixed host allowlist,
//! no redirects, no proxy, bounded response size) that `artifact_acquisition`
//! already enforces for downloads.
//!
//! These commands are read-only metadata lookups. Actual model downloads still
//! go through `start_approved_artifact_download`, which requires an approval
//! token and verifies SHA-256 plus GGUF magic bytes.

use std::io::Read;
use std::sync::OnceLock;
use std::time::Duration;

use reqwest::blocking::Client;
use reqwest::redirect::Policy;
use reqwest::Url;
use serde::Serialize;

/// Only the canonical API host is reachable. Redirects are disabled entirely.
const API_HOST: &str = "huggingface.co";
const MAX_RESPONSE_BYTES: usize = 4 * 1024 * 1024;
const MAX_RESULTS: usize = 30;
const MAX_FILES: usize = 64;
const MAX_QUERY_CHARS: usize = 96;
const MAX_MODEL_ID_CHARS: usize = 128;

#[derive(Debug, Serialize)]
pub struct HfModelSummary {
    pub id: String,
    pub downloads: u64,
    pub tags: Vec<String>,
    pub last_modified: String,
    pub pipeline_tag: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct HfRepoFile {
    pub filename: String,
    pub size: Option<u64>,
}

fn client() -> Result<&'static Client, String> {
    static CLIENT: OnceLock<Result<Client, String>> = OnceLock::new();
    CLIENT
        .get_or_init(|| {
            Client::builder()
                .redirect(Policy::none())
                .no_proxy()
                .connect_timeout(Duration::from_secs(15))
                .timeout(Duration::from_secs(30))
                .build()
                .map_err(|_| "hf_client_unavailable".to_string())
        })
        .as_ref()
        .map_err(Clone::clone)
}

/// Reject anything that is not a plain search term.
fn sanitize_query(raw: &str) -> Result<String, String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() || trimmed.chars().count() > MAX_QUERY_CHARS {
        return Err("invalid_query".into());
    }
    if trimmed
        .chars()
        .any(|c| c.is_control() || c == '/' || c == '\\' || c == '?' || c == '#' || c == '&')
    {
        return Err("invalid_query".into());
    }
    Ok(trimmed.to_string())
}

/// A model id is exactly `owner/name`, both restricted to safe characters.
fn sanitize_model_id(raw: &str) -> Result<String, String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() || trimmed.chars().count() > MAX_MODEL_ID_CHARS {
        return Err("invalid_model_id".into());
    }
    let parts: Vec<&str> = trimmed.split('/').collect();
    if parts.len() != 2 {
        return Err("invalid_model_id".into());
    }
    let valid = |s: &str| {
        !s.is_empty()
            && s != "."
            && s != ".."
            && s.chars()
                .all(|c| c.is_ascii_alphanumeric() || matches!(c, '-' | '_' | '.'))
    };
    if !parts.iter().all(|p| valid(p)) {
        return Err("invalid_model_id".into());
    }
    Ok(trimmed.to_string())
}

/// Fetch a URL that is already known to target the canonical API host.
fn get_json(url: Url) -> Result<serde_json::Value, String> {
    if url.scheme() != "https" || url.host_str() != Some(API_HOST) || url.port().is_some() {
        return Err("host_rejected".into());
    }
    let response = client()?
        .get(url)
        .header(reqwest::header::ACCEPT, "application/json")
        .send()
        .map_err(|_| "hf_request_failed".to_string())?;
    if !response.status().is_success() {
        return Err(format!("hf_http_{}", response.status().as_u16()));
    }
    if response
        .content_length()
        .is_some_and(|length| length > MAX_RESPONSE_BYTES as u64)
    {
        return Err("hf_response_too_large".to_string());
    }
    let bytes = read_bounded(response)?;
    serde_json::from_slice(&bytes).map_err(|_| "hf_response_invalid".to_string())
}

fn read_bounded(reader: impl Read) -> Result<Vec<u8>, String> {
    let mut bytes = Vec::new();
    reader
        .take(MAX_RESPONSE_BYTES as u64 + 1)
        .read_to_end(&mut bytes)
        .map_err(|_| "hf_request_failed".to_string())?;
    if bytes.len() > MAX_RESPONSE_BYTES {
        return Err("hf_response_too_large".to_string());
    }
    Ok(bytes)
}

#[tauri::command]
pub async fn hf_search_models(query: String) -> Result<Vec<HfModelSummary>, String> {
    // The network call is blocking; run it off the async runtime via spawn_blocking
    // so the webview thread never stalls on HF latency (up to 30s).
    tauri::async_runtime::spawn_blocking(move || hf_search_models_blocking(query))
        .await
        .map_err(|_| "hf_request_failed".to_string())?
}

fn hf_search_models_blocking(query: String) -> Result<Vec<HfModelSummary>, String> {
    let term = sanitize_query(&query)?;
    let mut url =
        Url::parse("https://huggingface.co/api/models").map_err(|_| "host_rejected".to_string())?;
    url.query_pairs_mut()
        .append_pair("search", &term)
        .append_pair("filter", "gguf")
        .append_pair("sort", "downloads")
        .append_pair("direction", "-1")
        .append_pair("limit", &MAX_RESULTS.to_string());

    let value = get_json(url)?;
    let items = value.as_array().ok_or("hf_response_invalid")?;
    Ok(items
        .iter()
        .take(MAX_RESULTS)
        .filter_map(|item| {
            let id = item
                .get("modelId")
                .or_else(|| item.get("id"))
                .and_then(|v| v.as_str())?;
            let id = sanitize_model_id(id).ok()?;
            Some(HfModelSummary {
                id,
                downloads: item.get("downloads").and_then(|v| v.as_u64()).unwrap_or(0),
                tags: item
                    .get("tags")
                    .and_then(|v| v.as_array())
                    .map(|tags| {
                        tags.iter()
                            .filter_map(|t| t.as_str())
                            .take(24)
                            .map(str::to_string)
                            .collect()
                    })
                    .unwrap_or_default(),
                last_modified: item
                    .get("lastModified")
                    .and_then(|v| v.as_str())
                    .unwrap_or_default()
                    .to_string(),
                pipeline_tag: item
                    .get("pipeline_tag")
                    .and_then(|v| v.as_str())
                    .map(str::to_string),
            })
        })
        .collect())
}

#[tauri::command]
pub async fn hf_list_repo_files(model_id: String) -> Result<Vec<HfRepoFile>, String> {
    tauri::async_runtime::spawn_blocking(move || hf_list_repo_files_blocking(model_id))
        .await
        .map_err(|_| "hf_request_failed".to_string())?
}

fn hf_list_repo_files_blocking(model_id: String) -> Result<Vec<HfRepoFile>, String> {
    let id = sanitize_model_id(&model_id)?;
    let url = Url::parse(&format!("https://huggingface.co/api/models/{id}"))
        .map_err(|_| "host_rejected".to_string())?;

    let value = get_json(url)?;
    let siblings = value
        .get("siblings")
        .and_then(|v| v.as_array())
        .ok_or("hf_response_invalid")?;
    Ok(siblings
        .iter()
        .filter_map(|item| {
            let name = item.get("rfilename").and_then(|v| v.as_str())?;
            // Only GGUF weights, and only plain names: no traversal, no nesting.
            if !name.ends_with(".gguf") || name.contains('/') || name.contains('\\') {
                return None;
            }
            if name.contains("..") || name.chars().any(char::is_control) {
                return None;
            }
            Some(HfRepoFile {
                filename: name.to_string(),
                size: item.get("size").and_then(|v| v.as_u64()),
            })
        })
        .take(MAX_FILES)
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    #[test]
    fn query_rejects_injection_and_overlong_input() {
        assert!(sanitize_query("qwen2.5 gguf").is_ok());
        assert!(sanitize_query("  ").is_err());
        assert!(sanitize_query("a/b").is_err());
        assert!(sanitize_query("x?y=1").is_err());
        assert!(sanitize_query("x&y").is_err());
        assert!(sanitize_query("bad\u{0}query").is_err());
        assert!(sanitize_query(&"z".repeat(MAX_QUERY_CHARS + 1)).is_err());
    }

    #[test]
    fn model_id_requires_exactly_owner_slash_name() {
        assert!(sanitize_model_id("Qwen/Qwen3-1.7B-GGUF").is_ok());
        assert!(sanitize_model_id("no-slash").is_err());
        assert!(sanitize_model_id("a/b/c").is_err());
        assert!(sanitize_model_id("../etc/passwd").is_err());
        assert!(sanitize_model_id("owner/..").is_err());
        assert!(sanitize_model_id("owner/name?x=1").is_err());
        assert!(sanitize_model_id("").is_err());
    }

    #[test]
    fn get_json_rejects_non_canonical_hosts() {
        for bad in [
            "https://huggingface.co.attacker.example/api/models",
            "http://huggingface.co/api/models",
            "https://attacker.example/api/models",
            "https://huggingface.co:8443/api/models",
        ] {
            let url = Url::parse(bad).expect("test url");
            assert_eq!(get_json(url).unwrap_err(), "host_rejected", "{bad}");
        }
    }

    #[test]
    fn bounded_reader_accepts_response_at_limit() {
        let bytes = vec![b'x'; MAX_RESPONSE_BYTES];

        assert_eq!(
            read_bounded(Cursor::new(bytes))
                .expect("bounded response")
                .len(),
            MAX_RESPONSE_BYTES
        );
    }

    #[test]
    fn bounded_reader_rejects_response_over_limit() {
        let bytes = vec![b'x'; MAX_RESPONSE_BYTES + 1];

        assert_eq!(
            read_bounded(Cursor::new(bytes)).expect_err("oversized response"),
            "hf_response_too_large"
        );
    }
}
