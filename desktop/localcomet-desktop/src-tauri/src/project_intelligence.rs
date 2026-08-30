//! Project Intelligence MVP — workspace inventory, repo map, context manifest.
//! Deterministic, .gitignore-aware, secret-excluded.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

pub const MANIFEST_SCHEMA: &str = "localcomet.context-manifest.v2";
const INDEXER_VERSION: &str = "project-intelligence-v2";
pub(crate) const MAX_CONTEXT_BUDGET: usize = 256 * 1024;
const MAX_SUMMARY_ITEMS: usize = 32;
const MAX_INVENTORY_FILES: usize = 4_096;
const MAX_SOURCE_FILE_BYTES: u64 = 8 * 1024 * 1024;
const MAX_INVENTORY_BYTES: u64 = 64 * 1024 * 1024;
const MAX_SUMMARY_ITEM_LENGTH: usize = 128;
const MAX_EXCLUSION_LENGTH: usize = 256;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct FileSummary {
    pub parse_mode: String,
    pub symbols: Vec<String>,
    pub imports: Vec<String>,
    pub dependencies: Vec<String>,
}

impl Default for FileSummary {
    fn default() -> Self {
        Self {
            parse_mode: "path_only".to_string(),
            symbols: Vec::new(),
            imports: Vec::new(),
            dependencies: Vec::new(),
        }
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct FileMeta {
    pub rel_path: String, // canonical workspace-relative, forward slashes
    pub hash: String,     // sha256 hex
    pub size: u64,
    #[serde(default)]
    pub summary: FileSummary,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ManifestProvenance {
    pub indexer_version: String,
    pub exclusions: Vec<String>,
    pub tree_digest: String,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContextManifest {
    pub schema_version: String,
    pub workspace_digest: String,
    pub inventory_digest: String,
    pub content_digest: String,
    pub task_id: String,
    pub step_id: Option<String>,
    pub generation: u64,
    pub files: Vec<FileMeta>,
    pub repo_map: String,
    pub token_budget: usize,
    pub context_manifest_hash: String,
    /// Kept as a compatibility alias for consumers of v1 manifests.
    pub manifest_hash: String,
    pub provenance: ManifestProvenance,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ContextError {
    InvalidBudget,
    InvalidWorkspace,
    TraversalRejected,
    ReadFailed,
    InventoryLimitExceeded,
    ContextBudgetExceeded { budget: usize, required: usize },
    InvalidBinding,
}

impl std::fmt::Display for ContextError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidBudget => write!(f, "context_budget_invalid"),
            Self::InvalidWorkspace => write!(f, "workspace_invalid"),
            Self::TraversalRejected => write!(f, "workspace_traversal_rejected"),
            Self::ReadFailed => write!(f, "workspace_read_failed"),
            Self::InventoryLimitExceeded => write!(f, "workspace_inventory_limit_exceeded"),
            Self::ContextBudgetExceeded { budget, required } => {
                write!(f, "context_budget_exceeded:{required}>{budget}")
            }
            Self::InvalidBinding => write!(f, "context_binding_invalid"),
        }
    }
}

impl std::error::Error for ContextError {}

fn sha256_hex(data: &[u8]) -> String {
    let mut h = Sha256::new();
    h.update(data);
    format!("{:x}", h.finalize())
}

fn bounded_items(items: BTreeSet<String>) -> Vec<String> {
    items
        .into_iter()
        .filter(|item| {
            !item.is_empty()
                && item.len() <= MAX_SUMMARY_ITEM_LENGTH
                && !item.chars().any(|character| character.is_control())
        })
        .take(MAX_SUMMARY_ITEMS)
        .collect()
}

fn identifier_after(line: &str, keyword: &str) -> Option<String> {
    let remainder = line.strip_prefix(keyword)?.trim_start();
    let identifier: String = remainder
        .chars()
        .take_while(|character| character.is_ascii_alphanumeric() || *character == '_')
        .collect();
    (!identifier.is_empty()).then_some(identifier)
}

fn quoted_module(line: &str) -> Option<String> {
    let (start, quote) = line.char_indices().find_map(|(index, character)| {
        (character == '"' || character == 39 as char).then_some((index, character))
    })?;
    let rest = &line[start + quote.len_utf8()..];
    let end = rest.find(quote)?;
    let module = &rest[..end];
    (!module.is_empty()).then_some(module.to_string())
}

fn normalize_dependency(module: &str) -> String {
    module
        .trim_start_matches('@')
        .split(['/', '\\'])
        .take(2)
        .collect::<Vec<_>>()
        .join("/")
}

fn source_summary(rel_path: &str, data: &[u8]) -> FileSummary {
    let lower = rel_path.to_ascii_lowercase();
    let is_rust = lower.ends_with(".rs");
    let is_typescript =
        lower.ends_with(".ts") || lower.ends_with(".tsx") || lower.ends_with(".svelte");
    let is_python = lower.ends_with(".py");
    if !is_rust && !is_typescript && !is_python {
        return FileSummary::default();
    }
    let Ok(text) = std::str::from_utf8(data) else {
        return FileSummary::default();
    };
    let mut symbols = BTreeSet::new();
    let mut imports = BTreeSet::new();
    let mut dependencies = BTreeSet::new();
    for raw_line in text.lines().take(16_384) {
        let line = raw_line.trim();
        if is_rust {
            for keyword in [
                "pub fn ",
                "fn ",
                "pub struct ",
                "struct ",
                "pub enum ",
                "enum ",
                "pub trait ",
                "trait ",
                "pub type ",
                "type ",
                "pub const ",
                "const ",
                "pub static ",
                "static ",
                "mod ",
            ] {
                if let Some(name) = identifier_after(line, keyword) {
                    symbols.insert(name);
                    break;
                }
            }
            if line.starts_with("use ") || line.starts_with("extern crate ") {
                if let Some(module) = line.split_whitespace().nth(1) {
                    let module = module.trim_end_matches(';');
                    imports.insert(module.to_string());
                    dependencies.insert(normalize_dependency(module));
                }
            }
        } else if is_python {
            for keyword in ["def ", "class "] {
                if let Some(name) = identifier_after(line, keyword) {
                    symbols.insert(name);
                    break;
                }
            }
            if line.starts_with("import ") {
                if let Some(module) = line.split_whitespace().nth(1) {
                    imports.insert(module.trim_end_matches(',').to_string());
                    dependencies.insert(normalize_dependency(module));
                }
            } else if line.starts_with("from ") {
                if let Some(module) = line.split_whitespace().nth(1) {
                    imports.insert(module.to_string());
                    dependencies.insert(normalize_dependency(module));
                }
            }
        } else {
            for keyword in [
                "export function ",
                "function ",
                "export class ",
                "class ",
                "export interface ",
                "interface ",
                "export type ",
                "type ",
                "export const ",
                "const ",
            ] {
                if let Some(name) = identifier_after(line, keyword) {
                    symbols.insert(name);
                    break;
                }
            }
            if line.starts_with("import ") || line.starts_with("export ") {
                if let Some(module) = line
                    .split(" from ")
                    .nth(1)
                    .and_then(quoted_module)
                    .or_else(|| quoted_module(line))
                {
                    imports.insert(module.clone());
                    dependencies.insert(normalize_dependency(&module));
                }
            }
        }
    }
    FileSummary {
        parse_mode: "heuristic".to_string(),
        symbols: bounded_items(symbols),
        imports: bounded_items(imports),
        dependencies: bounded_items(dependencies),
    }
}

fn load_gitignore_patterns(root: &Path) -> Vec<String> {
    let p = root.join(".gitignore");
    if let Ok(content) = fs::read_to_string(&p) {
        content
            .lines()
            .map(|l| l.trim().to_string())
            .filter(|l| !l.is_empty() && !l.starts_with('#'))
            .collect()
    } else {
        Vec::new()
    }
}

fn is_secret_or_build(rel: &str) -> bool {
    let lower = rel.to_ascii_lowercase();
    lower == ".env"
        || lower == ".gitignore"
        || lower.ends_with(".env")
        || lower.contains(".env.")
        || lower.ends_with(".key")
        || lower.ends_with(".pem")
        || lower.ends_with(".secret")
        || lower.contains("__pycache__")
        || lower.contains(".vscode")
        || lower.contains("devruntime")
}

fn is_build_artifact_dir(name: &str) -> bool {
    matches!(
        name,
        ".git" | "target" | "node_modules" | "dist" | "build" | ".vscode" | "__pycache__" | "audit"
    )
}

fn matches_gitignore(rel: &str, patterns: &[String]) -> bool {
    for pat in patterns {
        let p = pat.trim();
        if p.is_empty() || p.starts_with('#') || p.starts_with('!') {
            continue;
        }
        // simple: * and prefix
        if p.contains('*') {
            let prefix = p.split('*').next().unwrap_or("");
            if !prefix.is_empty() && rel.starts_with(prefix.trim_end_matches('/')) {
                return true;
            }
            // suffix * like *.log
            if p.starts_with("*.") {
                let ext = p.trim_start_matches('*');
                if rel.ends_with(ext) {
                    return true;
                }
            }
        } else if rel == p || rel.starts_with(&format!("{}/", p)) {
            return true;
        }
    }
    false
}

fn inventory_inner(
    root: &Path,
    cur: &Path,
    patterns: &[String],
    out: &mut Vec<FileMeta>,
    total_bytes: &mut u64,
) -> Result<(), ContextError> {
    let entries = fs::read_dir(cur).map_err(|_| ContextError::ReadFailed)?;
    for entry in entries {
        let entry = entry.map_err(|_| ContextError::ReadFailed)?;
        let path = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        if is_build_artifact_dir(&name) {
            continue;
        }
        let metadata = fs::symlink_metadata(&path).map_err(|_| ContextError::ReadFailed)?;
        if metadata.file_type().is_symlink() {
            return Err(ContextError::TraversalRejected);
        }
        let rel = path
            .strip_prefix(root)
            .map_err(|_| ContextError::TraversalRejected)?
            .to_string_lossy()
            .replace('\\', "/");
        if is_secret_or_build(&rel) || matches_gitignore(&rel, patterns) {
            continue;
        }
        if metadata.is_dir() {
            inventory_inner(root, &path, patterns, out, total_bytes)?;
        } else if metadata.is_file() {
            if out.len() >= MAX_INVENTORY_FILES
                || metadata.len() > MAX_SOURCE_FILE_BYTES
                || total_bytes.saturating_add(metadata.len()) > MAX_INVENTORY_BYTES
            {
                return Err(ContextError::InventoryLimitExceeded);
            }
            let data = fs::read(&path).map_err(|_| ContextError::ReadFailed)?;
            *total_bytes = total_bytes.saturating_add(data.len() as u64);
            let hash = sha256_hex(&data);
            out.push(FileMeta {
                rel_path: rel.clone(),
                hash,
                size: data.len() as u64,
                summary: source_summary(&rel, &data),
            });
        }
    }
    Ok(())
}

pub fn try_inventory_workspace(root: &Path) -> Result<Vec<FileMeta>, ContextError> {
    let root_metadata = fs::symlink_metadata(root).map_err(|_| ContextError::InvalidWorkspace)?;
    if !root_metadata.is_dir() {
        return Err(ContextError::InvalidWorkspace);
    }
    if root_metadata.file_type().is_symlink() {
        return Err(ContextError::TraversalRejected);
    }
    let patterns = load_gitignore_patterns(root);
    let mut files = Vec::new();
    let mut total_bytes = 0;
    inventory_inner(root, root, &patterns, &mut files, &mut total_bytes)?;
    files.sort_by(|a, b| a.rel_path.cmp(&b.rel_path));
    Ok(files)
}

/// Legacy read-only API. New callers should use `try_inventory_workspace` so
/// traversal and read failures are not silently converted into an empty map.
pub fn inventory_workspace(root: &Path) -> Vec<FileMeta> {
    try_inventory_workspace(root).unwrap_or_default()
}

fn digest_files(files: &[FileMeta], include_content: bool) -> String {
    let mut hasher = Sha256::new();
    for file in files {
        hasher.update(file.rel_path.as_bytes());
        hasher.update([0]);
        hasher.update(file.size.to_be_bytes());
        if include_content {
            hasher.update(file.hash.as_bytes());
        }
        hasher.update([0xff]);
    }
    format!("{:x}", hasher.finalize())
}

pub fn workspace_digest(root: &Path) -> String {
    digest_files(&inventory_workspace(root), true)
}

pub fn build_repo_map(files: &[FileMeta], task_keywords: &[String], token_budget: usize) -> String {
    // Deterministic ranking: path, symbols/imports/dependencies, then source kind.
    let mut scored: Vec<(&FileMeta, i32)> = files
        .iter()
        .map(|f| {
            let mut score = 0;
            let lower = f.rel_path.to_ascii_lowercase();
            let summary_text = format!(
                "{} {} {}",
                f.summary.symbols.join(" "),
                f.summary.imports.join(" "),
                f.summary.dependencies.join(" ")
            )
            .to_ascii_lowercase();
            for kw in task_keywords {
                let keyword = kw.to_ascii_lowercase();
                if lower.contains(&keyword) {
                    score += 10;
                }
                if summary_text.contains(&keyword) {
                    score += 6;
                }
            }
            if lower.ends_with(".rs")
                || lower.ends_with(".ts")
                || lower.ends_with(".tsx")
                || lower.ends_with(".svelte")
                || lower.ends_with(".py")
            {
                score += 2;
            }
            if lower.contains("lib.rs") || lower.contains("mod.rs") {
                score += 1;
            }
            (f, score)
        })
        .collect();
    scored.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.rel_path.cmp(&b.0.rel_path)));
    let mut out = String::new();
    let mut used = 0;
    for (f, score) in scored {
        let summary = &f.summary;
        let short_hash = f.hash.get(..8).unwrap_or(&f.hash);
        let line = if summary.symbols.is_empty()
            && summary.imports.is_empty()
            && summary.dependencies.is_empty()
        {
            format!("{} | {} | score {}\n", f.rel_path, short_hash, score)
        } else {
            format!(
                "{} | {} | score {} | symbols:{} | imports:{} | deps:{}\n",
                f.rel_path,
                short_hash,
                score,
                summary.symbols.join(","),
                summary.imports.join(","),
                summary.dependencies.join(",")
            )
        };
        if used + line.len() > token_budget {
            break;
        }
        out.push_str(&line);
        used += line.len();
    }
    out
}

const EXCLUSIONS: &[&str] = &[
    ".env",
    "keys/pem/secrets",
    ".git",
    ".gitignore",
    "target",
    "node_modules",
    "dist/build",
    "DevRuntime",
    ".vscode",
    "__pycache__",
    "audit",
];

pub fn try_build_context_manifest(
    root: &Path,
    task_id: &str,
    step_id: Option<&str>,
    task_keywords: &[String],
    token_budget: usize,
) -> Result<ContextManifest, ContextError> {
    try_build_context_manifest_bound(root, "", task_id, step_id, task_keywords, token_budget)
}

/// Build a manifest bound to the already-confirmed workspace identity.
///
/// The empty digest accepted by the compatibility wrapper intentionally falls
/// back to the content digest. Production callers must pass the digest issued
/// by `workspace::change_workspace`, so a manifest cannot be transplanted to a
/// different confirmed workspace without changing its canonical hash.
pub fn try_build_context_manifest_bound(
    root: &Path,
    workspace_digest: &str,
    task_id: &str,
    step_id: Option<&str>,
    task_keywords: &[String],
    token_budget: usize,
) -> Result<ContextManifest, ContextError> {
    if token_budget == 0 || token_budget > MAX_CONTEXT_BUDGET {
        return Err(ContextError::InvalidBudget);
    }
    if (!workspace_digest.is_empty()
        && (workspace_digest.len() != 64
            || !workspace_digest
                .chars()
                .all(|character| character.is_ascii_hexdigit())
            || workspace_digest
                .chars()
                .any(|character| character.is_ascii_uppercase())))
        || task_id.is_empty()
        || task_id.len() > MAX_SUMMARY_ITEM_LENGTH
        || task_id.chars().any(|character| character.is_control())
        || step_id.is_some_and(|value| {
            value.is_empty()
                || value.len() > MAX_SUMMARY_ITEM_LENGTH
                || value.chars().any(|character| character.is_control())
        })
    {
        return Err(ContextError::InvalidBinding);
    }
    let keywords: Vec<String> = task_keywords
        .iter()
        .filter(|keyword| {
            !keyword.is_empty()
                && keyword.len() <= MAX_SUMMARY_ITEM_LENGTH
                && !keyword.chars().any(|character| character.is_control())
        })
        .take(MAX_SUMMARY_ITEMS)
        .cloned()
        .collect();
    let files = try_inventory_workspace(root)?;
    let inventory_digest = digest_files(&files, false);
    let content_digest = digest_files(&files, true);
    let repo_map = build_repo_map(&files, &keywords, token_budget);
    let context_payload = serde_json::json!({
        "files": &files,
        "repo_map": &repo_map,
    });
    let required = canonical_json(&context_payload).len();
    if required > token_budget {
        return Err(ContextError::ContextBudgetExceeded {
            budget: token_budget,
            required,
        });
    }
    let provenance = ManifestProvenance {
        indexer_version: INDEXER_VERSION.to_string(),
        exclusions: EXCLUSIONS
            .iter()
            .map(|value| (*value).to_string())
            .filter(|value| value.len() <= MAX_EXCLUSION_LENGTH)
            .collect(),
        tree_digest: content_digest.clone(),
    };
    let bound_workspace_digest = if workspace_digest.is_empty() {
        content_digest.clone()
    } else {
        workspace_digest.to_string()
    };
    let mut manifest = ContextManifest {
        schema_version: MANIFEST_SCHEMA.to_string(),
        workspace_digest: bound_workspace_digest,
        inventory_digest,
        content_digest,
        task_id: task_id.to_string(),
        step_id: step_id.map(str::to_string),
        generation: 1,
        files,
        repo_map,
        token_budget,
        context_manifest_hash: String::new(),
        manifest_hash: String::new(),
        provenance,
    };
    let mut unsigned = manifest.clone();
    unsigned.context_manifest_hash.clear();
    unsigned.manifest_hash.clear();
    let data = serde_json::to_value(&unsigned).map_err(|_| ContextError::ReadFailed)?;
    let mut hasher = Sha256::new();
    hasher.update(canonical_json(&data).as_bytes());
    let context_manifest_hash = format!("{:x}", hasher.finalize());
    manifest.context_manifest_hash = context_manifest_hash.clone();
    manifest.manifest_hash = context_manifest_hash;
    Ok(manifest)
}

/// Legacy compatibility wrapper. New product paths must use the fallible API.
pub fn build_context_manifest(
    root: &Path,
    task_id: &str,
    step_id: Option<&str>,
    task_keywords: &[String],
    token_budget: usize,
) -> ContextManifest {
    try_build_context_manifest(root, task_id, step_id, task_keywords, token_budget)
        .unwrap_or_else(|error| panic!("context manifest rejected: {error}"))
}

fn canonical_json(v: &serde_json::Value) -> String {
    match v {
        serde_json::Value::Null => "null".into(),
        serde_json::Value::Bool(b) => b.to_string(),
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::String(s) => {
            serde_json::to_string(s).unwrap_or_else(|_| "\"\"".to_string())
        }
        serde_json::Value::Array(a) => format!(
            "[{}]",
            a.iter().map(canonical_json).collect::<Vec<_>>().join(",")
        ),
        serde_json::Value::Object(m) => {
            let mut keys: Vec<&String> = m.keys().collect();
            keys.sort();
            let pairs: Vec<String> = keys
                .iter()
                .map(|k| format!("\"{}\":{}", k, canonical_json(&m[*k])))
                .collect();
            format!("{{{}}}", pairs.join(","))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    fn tmp_root_with_files(files: &[(&str, &[u8])]) -> PathBuf {
        let base = std::env::temp_dir();
        let uniq = format!(
            "pi_{}_{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_nanos()
        );
        let root = base.join(uniq);
        fs::create_dir_all(&root).unwrap();
        for (rel, data) in files {
            let p = root.join(rel);
            if let Some(parent) = p.parent() {
                fs::create_dir_all(parent).unwrap();
            }
            fs::write(&p, data).unwrap();
        }
        root
    }

    #[test]
    fn inventory_excludes_secrets_and_build() {
        let root = tmp_root_with_files(&[
            ("src/lib.rs", b"fn main(){}"),
            (".env", b"secret=1"),
            ("target/debug/foo", b"bin"),
            ("node_modules/x/index.js", b"js"),
        ]);
        // also create .gitignore
        fs::write(root.join(".gitignore"), b"*.log\n").unwrap();
        fs::write(root.join("a.log"), b"log").unwrap();
        let files = inventory_workspace(&root);
        let rels: Vec<String> = files.iter().map(|f| f.rel_path.clone()).collect();
        assert!(rels.contains(&"src/lib.rs".to_string()));
        assert!(!rels.iter().any(|p| p.contains(".env")));
        assert!(!rels.iter().any(|p| p.contains("target")));
        assert!(!rels.iter().any(|p| p.contains("node_modules")));
        assert!(!rels.iter().any(|p| p.ends_with("a.log")));
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn manifest_hash_changes_after_touch() {
        let root = tmp_root_with_files(&[("a.txt", b"hello")]);
        let m1 = build_context_manifest(&root, "t1", None, &["a".to_string()], 4096);
        fs::write(root.join("a.txt"), b"world").unwrap();
        let m2 = build_context_manifest(&root, "t1", None, &["a".to_string()], 4096);
        assert_ne!(m1.manifest_hash, m2.manifest_hash);
        assert_ne!(m1.files[0].hash, m2.files[0].hash);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn repo_map_ranking_and_budget() {
        let root = tmp_root_with_files(&[
            ("src/lib.rs", b"lib"),
            ("src/task.rs", b"task"),
            ("README.md", b"readme"),
        ]);
        let files = inventory_workspace(&root);
        let map = build_repo_map(&files, &["task".to_string()], 100);
        // task.rs should appear before README due to keyword
        let task_pos = map.find("task.rs").unwrap();
        let readme_pos = map.find("README.md").unwrap();
        assert!(task_pos < readme_pos);
        // budget respected
        let small = build_repo_map(&files, &[], 10);
        assert!(small.len() <= 10);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn deterministic_manifest() {
        let root = tmp_root_with_files(&[("a.txt", b"hello"), ("b.txt", b"world")]);
        let m1 = build_context_manifest(&root, "t1", Some("s1"), &[], 4096);
        let m2 = build_context_manifest(&root, "t1", Some("s1"), &[], 4096);
        assert_eq!(m1.manifest_hash, m2.manifest_hash);
        assert_eq!(m1.context_manifest_hash, m2.context_manifest_hash);
        assert_eq!(m1.files, m2.files);
        assert_eq!(m1.provenance.indexer_version, INDEXER_VERSION);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn source_summary_is_bounded_and_ranks_symbols() {
        let root = tmp_root_with_files(&[
            (
                "src/main.rs",
                b"use crate::policy::Rule;\npub fn execute_task() {}\n",
            ),
            (
                "src/app.ts",
                b"import helper from '@scope/package';\nexport function render() {}\n",
            ),
            (
                "tools/check.py",
                b"from pathlib import Path\ndef verify_bundle():\n    pass\n",
            ),
        ]);
        let files = try_inventory_workspace(&root).unwrap();
        let rust = files
            .iter()
            .find(|file| file.rel_path == "src/main.rs")
            .unwrap();
        assert_eq!(rust.summary.parse_mode, "heuristic");
        assert!(rust.summary.symbols.contains(&"execute_task".to_string()));
        assert!(rust
            .summary
            .imports
            .contains(&"crate::policy::Rule".to_string()));
        let typescript = files
            .iter()
            .find(|file| file.rel_path == "src/app.ts")
            .unwrap();
        assert!(typescript.summary.symbols.contains(&"render".to_string()));
        assert!(typescript
            .summary
            .dependencies
            .contains(&"scope/package".to_string()));
        let python = files
            .iter()
            .find(|file| file.rel_path == "tools/check.py")
            .unwrap();
        assert!(python
            .summary
            .symbols
            .contains(&"verify_bundle".to_string()));
        let map = build_repo_map(&files, &["execute_task".to_string()], 4096);
        assert!(map.starts_with("src/main.rs"));
        assert!(map.len() <= 4096);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn split_digests_change_only_when_expected() {
        let root = tmp_root_with_files(&[("src/lib.rs", b"fn one() {}")]);
        let first = try_build_context_manifest(&root, "t1", None, &[], 4096).unwrap();
        fs::write(root.join("src/lib.rs"), b"fn two() {}").unwrap();
        let second = try_build_context_manifest(&root, "t1", None, &[], 4096).unwrap();
        assert_eq!(first.inventory_digest, second.inventory_digest);
        assert_ne!(first.content_digest, second.content_digest);
        assert_ne!(first.context_manifest_hash, second.context_manifest_hash);
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn production_manifest_uses_confirmed_workspace_digest() {
        let root = tmp_root_with_files(&[("src/lib.rs", b"fn main() {}")]);
        let workspace_digest = "a".repeat(64);
        let manifest = try_build_context_manifest_bound(
            &root,
            &workspace_digest,
            "0123456789abcdef01234567",
            Some("step-1"),
            &[],
            4096,
        )
        .unwrap();
        assert_eq!(manifest.workspace_digest, workspace_digest);
        assert_eq!(manifest.provenance.tree_digest, manifest.content_digest);
        assert_eq!(
            try_build_context_manifest_bound(&root, "ABC", "task", None, &[], 4096),
            Err(ContextError::InvalidBinding)
        );
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn invalid_and_oversized_budgets_are_rejected() {
        let root = tmp_root_with_files(&[("a.txt", b"hello")]);
        assert_eq!(
            try_build_context_manifest(&root, "t1", None, &[], 0),
            Err(ContextError::InvalidBudget)
        );
        assert!(matches!(
            try_build_context_manifest(&root, "t1", None, &[], 1),
            Err(ContextError::ContextBudgetExceeded { .. })
        ));
        assert_eq!(
            try_build_context_manifest(&root, "t1", None, &[], MAX_CONTEXT_BUDGET + 1),
            Err(ContextError::InvalidBudget)
        );
        let _ = fs::remove_dir_all(&root);
    }

    #[test]
    fn invalid_workspace_is_rejected_by_fallible_inventory() {
        let missing = std::env::temp_dir().join("localcomet-project-intelligence-missing");
        assert_eq!(
            try_inventory_workspace(&missing),
            Err(ContextError::InvalidWorkspace)
        );
    }
}
