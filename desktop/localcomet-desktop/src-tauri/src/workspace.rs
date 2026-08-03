use crate::approval::ApprovalRegistry;
use crate::control_plane::BridgeError;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct WorkspaceIdentity {
    pub canonical_path: String,
    pub digest: String,
}

#[derive(Clone, Debug)]
pub enum WorkspaceError {
    InvalidPath(String),
    SymlinkEscape(String),
    /// Reserved for the workspace.set IPC round-trip (INV-WORKSPACE-001). The
    /// desktop sidecar currently performs no filesystem tool execution, so this
    /// variant is not yet constructed; it is retained for the future sidecar
    /// workspace-propagation path.
    #[allow(dead_code)]
    SidecarRejected(String),
    NotADirectory(String),
    DoesNotExist(String),
}

impl std::fmt::Display for WorkspaceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::InvalidPath(msg) => write!(f, "invalid workspace path: {msg}"),
            Self::SymlinkEscape(msg) => write!(f, "symlink escape detected: {msg}"),
            Self::SidecarRejected(msg) => write!(f, "sidecar rejected workspace: {msg}"),
            Self::NotADirectory(msg) => write!(f, "not a directory: {msg}"),
            Self::DoesNotExist(msg) => write!(f, "path does not exist: {msg}"),
        }
    }
}

impl From<WorkspaceError> for BridgeError {
    fn from(value: WorkspaceError) -> Self {
        BridgeError {
            code: "workspace_error".into(),
            message: value.to_string(),
        }
    }
}

pub fn validate_workspace_path(raw: &Path) -> Result<PathBuf, WorkspaceError> {
    if raw.as_os_str().is_empty() {
        return Err(WorkspaceError::InvalidPath("empty path".into()));
    }
    // Inspect the caller-supplied path before canonicalization. Canonicalization
    // resolves a link, so checking its metadata afterwards only examines the
    // target and cannot enforce the no-link workspace boundary.
    reject_raw_path_links(raw)?;

    let canonical = raw
        .canonicalize()
        .map_err(|e| WorkspaceError::InvalidPath(e.to_string()))?;

    if !canonical.exists() {
        return Err(WorkspaceError::DoesNotExist(
            canonical.display().to_string(),
        ));
    }

    if !canonical.is_dir() {
        return Err(WorkspaceError::NotADirectory(
            canonical.display().to_string(),
        ));
    }

    Ok(canonical)
}

fn reject_raw_path_links(raw: &Path) -> Result<(), WorkspaceError> {
    for component in raw.ancestors() {
        let metadata = match std::fs::symlink_metadata(component) {
            Ok(metadata) => metadata,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => continue,
            Err(error) => return Err(WorkspaceError::InvalidPath(error.to_string())),
        };
        #[cfg(windows)]
        {
            use std::os::windows::fs::MetadataExt;
            const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
            if metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
                return Err(WorkspaceError::SymlinkEscape(
                    component.display().to_string(),
                ));
            }
        }
        #[cfg(not(windows))]
        if metadata.file_type().is_symlink() {
            return Err(WorkspaceError::SymlinkEscape(
                component.display().to_string(),
            ));
        }
    }
    Ok(())
}

pub fn workspace_digest(path: &Path) -> String {
    use sha2::{Digest, Sha256};
    let mut hasher = Sha256::new();
    hasher.update(path.to_string_lossy().as_bytes());
    let result = hasher.finalize();
    result.iter().map(|b| format!("{b:02x}")).collect()
}

pub fn change_workspace(
    raw_path: &Path,
    approval_registry: &mut ApprovalRegistry,
    current_workspace: &Option<WorkspaceIdentity>,
) -> Result<WorkspaceIdentity, WorkspaceError> {
    let canonical = validate_workspace_path(raw_path)?;

    if let Some(current) = current_workspace {
        approval_registry.invalidate_workspace(&current.canonical_path);
    }

    let identity = WorkspaceIdentity {
        canonical_path: canonical.display().to_string(),
        digest: workspace_digest(&canonical),
    };

    Ok(identity)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn valid_directory_passes_validation() {
        let temp = std::env::temp_dir();
        let result = validate_workspace_path(&temp);
        assert!(result.is_ok());
    }

    #[test]
    fn empty_path_is_rejected() {
        let result = validate_workspace_path(Path::new(""));
        assert!(matches!(result, Err(WorkspaceError::InvalidPath(_))));
    }

    #[test]
    fn nonexistent_path_is_rejected() {
        let result =
            validate_workspace_path(Path::new(r"Z:\nonexistent_localcomet_test_path_12345"));
        assert!(result.is_err());
    }

    #[test]
    fn file_path_is_rejected_as_not_directory() {
        let temp = std::env::temp_dir();
        let file_path = temp.join("localcomet_ws_test_file.txt");
        fs::write(&file_path, "test").unwrap();
        let result = validate_workspace_path(&file_path);
        let _ = fs::remove_file(&file_path);
        assert!(matches!(result, Err(WorkspaceError::NotADirectory(_))));
    }

    #[test]
    fn supplied_symlink_workspace_is_rejected_before_canonicalization() {
        let root =
            std::env::temp_dir().join(format!("localcomet_workspace_link_{}", std::process::id()));
        let target = root.join("target");
        let link = root.join("link");
        fs::create_dir_all(&target).unwrap();
        #[cfg(windows)]
        let created = std::os::windows::fs::symlink_dir(&target, &link);
        #[cfg(not(windows))]
        let created = std::os::unix::fs::symlink(&target, &link);
        if let Err(error) = created {
            let _ = fs::remove_dir_all(&root);
            panic!("cannot create symlink fixture: {error}");
        }
        let result = validate_workspace_path(&link);
        let _ = fs::remove_dir_all(&root);
        assert!(matches!(result, Err(WorkspaceError::SymlinkEscape(_))));
    }

    #[test]
    fn workspace_change_invalidates_old_tokens() {
        let mut registry = ApprovalRegistry::new();
        let ws_a = WorkspaceIdentity {
            canonical_path: "/workspace-a".into(),
            digest: workspace_digest(Path::new("/workspace-a")),
        };

        use crate::approval::{canonical_input_digest, ApprovalScope, CommandFamily, RiskLevel};
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: canonical_input_digest(&serde_json::json!({"x": 1})),
            workspace: "/workspace-a".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
            command_family: CommandFamily::ToolFilesystemWrite,
            approval_id: "appr_00000000000000000000000000000000".to_owned(),
            call_id: "call_00000000000000000000000000000000".to_owned(),
        };
        let token = registry.issue(scope).unwrap();
        assert_eq!(registry.active_count(), 1);

        let new_identity =
            change_workspace(&std::env::temp_dir(), &mut registry, &Some(ws_a)).unwrap();

        assert_eq!(registry.active_count(), 0);
        assert!(!new_identity.canonical_path.is_empty());
        assert!(!new_identity.digest.is_empty());

        let digest = canonical_input_digest(&serde_json::json!({"x": 1}));
        let err = registry
            .execute_approved(
                &token,
                "files.patch",
                &digest,
                "/workspace-a",
                "appr_00000000000000000000000000000000",
                "call_00000000000000000000000000000000",
                RiskLevel::Guarded,
                CommandFamily::ToolFilesystemWrite,
            )
            .unwrap_err();
        assert!(matches!(err, crate::approval::ApprovalError::TokenNotFound));
    }

    #[test]
    fn workspace_digest_is_deterministic() {
        let d1 = workspace_digest(Path::new("/some/path"));
        let d2 = workspace_digest(Path::new("/some/path"));
        assert_eq!(d1, d2);
        assert_eq!(d1.len(), 64);
    }

    #[test]
    fn different_paths_produce_different_digests() {
        let d1 = workspace_digest(Path::new("/path/a"));
        let d2 = workspace_digest(Path::new("/path/b"));
        assert_ne!(d1, d2);
    }
}
