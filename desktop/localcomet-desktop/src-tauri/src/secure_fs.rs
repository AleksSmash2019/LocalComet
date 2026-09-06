//! TOCTOU-safe workspace filesystem mutations for the files.* tool family.
//!
//! The desktop sidecar (Python) has no portable no-reparse, handle-relative
//! primitive, so `files.write` / `files.create_folder` / `files.delete` failed
//! closed there (`feature_disabled`): a junction could replace a path component
//! between validation and mkdir/write. These mutations now execute in this host
//! process through the control-plane broker seam in
//! `approval_commands::run_tool_call_inner` (the same seam the computer_use
//! cu_broker uses), strictly AFTER the one-time approval token has been
//! consumed and with the grant material re-verified against the exact input
//! bytes.
//!
//! Security design (why the TOCTOU is closed):
//! 1. The workspace root is opened once and its final path is compared against
//!    the confirmed canonical workspace identity; the handle pins the anchor.
//! 2. Every intermediate path component is opened RELATIVE to the verified
//!    parent handle (NtCreateFile with RootDirectory) with OBJ_DONT_REPARSE, so
//!    the OS itself refuses any reparse traversal, and the returned handle is
//!    attribute-checked and final-path-checked. The handle chain pins the
//!    directory objects: a later path-level swap of a component cannot
//!    redirect subsequent name resolution.
//! 3. The leaf is created/opened relative to the verified parent handle:
//!    - folders via FILE_DIRECTORY_FILE | FILE_OPEN_IF;
//!    - files via FILE_NON_DIRECTORY_FILE | FILE_OPEN_REPARSE_POINT |
//!      FILE_OPEN_IF. An existing reparse-point leaf is captured AS ITSELF
//!      (never followed) and rejected via its attributes BEFORE any truncation
//!      or write happens on the handle.
//! 4. Deleting opens the leaf with FILE_OPEN_REPARSE_POINT and DELETE access;
//!    a reparse leaf is never deleted (links are not removed), and a
//!    non-empty directory fails with STATUS_DIRECTORY_NOT_EMPTY. Recursive
//!    deletion is not part of the tool contract and is not implemented
//!    anywhere in this module.
//! 5. Hardlinked leaves (nNumberOfLinks > 1) are refused for write and
//!    delete: a link planted before the operation passes every path-level
//!    verification above (it is a plain file whose name resolves inside the
//!    workspace) yet shares its inode with an object outside the verified
//!    chain, so a mutation through it would leak bytes or link-count changes
//!    to that other name.
//! 6. Name resolution never goes through Win32 path normalization: components
//!    are passed as NT object names relative to the parent handle, so
//!    `.`/`..` traversal, drive-relative and UNC forms are structurally
//!    impossible after validation.
//! 7. Non-Windows builds keep the fail-closed `feature_disabled` contract
//!    (docs/porting/PORTING_PLAN_LINUX.md).

use serde_json::Value;
use std::path::{Component, Path, PathBuf};

/// Parity with MAX_TOOL_FILE_BYTES in modules/tool_execution_ru.py (bounded by
/// the IPC per-string payload limit): file content travels inside the tool
/// input, so the broker enforces the same writable-size limit.
pub(crate) const MAX_TOOL_WRITE_BYTES: usize = 1_000_000;

const MAX_RELATIVE_PATH_CHARS: usize = 1024;
const MAX_COMPONENT_CHARS: usize = 255;

/// Error codes are a strict subset of the tool-execution error dictionary
/// (modules/tool_execution_ru.py): invalid_payload / policy_blocked /
/// feature_disabled / internal_error. CODE_FEATURE_DISABLED is only produced
/// by the non-Windows fail-closed stubs.
pub(crate) const CODE_INVALID_PAYLOAD: &str = "invalid_payload";
pub(crate) const CODE_POLICY_BLOCKED: &str = "policy_blocked";
#[cfg_attr(windows, allow(dead_code))]
pub(crate) const CODE_FEATURE_DISABLED: &str = "feature_disabled";
pub(crate) const CODE_INTERNAL_ERROR: &str = "internal_error";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SecureFsError {
    pub code: &'static str,
    pub message: String,
}

impl SecureFsError {
    fn new(code: &'static str, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
        }
    }

    fn invalid_payload(message: impl Into<String>) -> Self {
        Self::new(CODE_INVALID_PAYLOAD, message)
    }

    fn policy_blocked(message: impl Into<String>) -> Self {
        Self::new(CODE_POLICY_BLOCKED, message)
    }

    #[cfg_attr(windows, allow(dead_code))]
    fn feature_disabled(message: impl Into<String>) -> Self {
        Self::new(CODE_FEATURE_DISABLED, message)
    }

    fn internal_error(message: impl Into<String>) -> Self {
        Self::new(CODE_INTERNAL_ERROR, message)
    }

    /// Map a SecureFsError onto the BridgeError wire shape so broker-stage
    /// failures behave exactly like a sidecar tool rejection (code + message).
    pub(crate) fn into_bridge_error(self) -> crate::control_plane::BridgeError {
        crate::control_plane::BridgeError::new(self.code, &self.message)
    }
}

type SecureFsResult<T> = Result<T, SecureFsError>;

/// Outcome of `secure_create_folder`: the created flag is honest state — an
/// already-existing folder is not reported as a fresh creation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CreateFolderOutcome {
    pub path: PathBuf,
    pub created: bool,
}

/// Outcome of `secure_write_file`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WriteOutcome {
    pub path: PathBuf,
    pub bytes_written: usize,
}

/// Outcome of `secure_delete`.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DeleteOutcome {
    pub path: PathBuf,
}

// ---------------------------------------------------------------------------
// Shared path validation (both platforms)
// ---------------------------------------------------------------------------

/// Split a workspace-relative tool path into strict single components.
///
/// Rejects the whole hostile-input class before any filesystem call: embedded
/// NUL, absolute/drive-relative/UNC forms, `..` traversal, stream separators
/// and overlong names. Only plain Normal components survive.
fn validated_components(relative: &str) -> SecureFsResult<Vec<String>> {
    if relative.contains('\0') {
        return Err(SecureFsError::invalid_payload(
            "path contains an embedded null character",
        ));
    }
    if relative.chars().count() > MAX_RELATIVE_PATH_CHARS {
        return Err(SecureFsError::invalid_payload(
            "path exceeds the maximum relative length",
        ));
    }
    if relative.contains(':') {
        return Err(SecureFsError::invalid_payload(
            "path contains a drive or stream separator",
        ));
    }
    let candidate = Path::new(relative);
    if candidate.is_absolute() || candidate.has_root() {
        return Err(SecureFsError::invalid_payload(
            "absolute paths are not allowed; use a workspace-relative path",
        ));
    }
    let mut components = Vec::new();
    for component in candidate.components() {
        let name = match component {
            Component::Normal(value) => value,
            Component::ParentDir => {
                return Err(SecureFsError::invalid_payload(
                    "path traversal is not allowed inside the workspace",
                ));
            }
            // Drive-relative ("C:foo") and UNC forms surface as a Prefix
            // component, so this arm covers every non-relative shape.
            Component::RootDir | Component::Prefix(_) => {
                return Err(SecureFsError::invalid_payload(
                    "absolute paths are not allowed; use a workspace-relative path",
                ));
            }
            Component::CurDir => {
                return Err(SecureFsError::invalid_payload(
                    "path components must be plain names",
                ));
            }
        };
        let name = match name.to_str() {
            Some(name) if !name.is_empty() => name,
            Some(_) => {
                return Err(SecureFsError::invalid_payload(
                    "path components must be non-empty",
                ));
            }
            None => {
                return Err(SecureFsError::invalid_payload(
                    "path component is not valid Unicode",
                ));
            }
        };
        if name.chars().count() > MAX_COMPONENT_CHARS {
            return Err(SecureFsError::invalid_payload(
                "path component exceeds the maximum name length",
            ));
        }
        components.push(name.to_owned());
    }
    if components.is_empty() {
        return Err(SecureFsError::invalid_payload(
            "path must name an object inside the workspace",
        ));
    }
    Ok(components)
}

fn display_path(root: &Path, components: &[String]) -> PathBuf {
    let mut path = root.to_path_buf();
    for component in components {
        path.push(component);
    }
    path
}

// ---------------------------------------------------------------------------
// Public platform dispatch
// ---------------------------------------------------------------------------

/// Create the final folder of `relative` inside `root` (intermediate
/// directories must already exist). Returns the verified absolute path and
/// whether this call created the folder (FILE_OPEN_IF: an existing folder is
/// not an error and is reported with created=false).
pub fn secure_create_folder(root: &Path, relative: &str) -> SecureFsResult<CreateFolderOutcome> {
    #[cfg(windows)]
    {
        windows_impl::create_folder(root, relative)
    }
    #[cfg(not(windows))]
    {
        let _ = (root, relative);
        Err(SecureFsError::feature_disabled(
            "files.create_folder requires the Windows no-reparse broker primitive",
        ))
    }
}

/// Create-or-overwrite the final file of `relative` inside `root` (intermediate
/// directories must already exist) and write `content` through the verified
/// handle. Existing reparse-point leaves are rejected before any byte is
/// written.
pub fn secure_write_file(
    root: &Path,
    relative: &str,
    content: &[u8],
) -> SecureFsResult<WriteOutcome> {
    #[cfg(windows)]
    {
        windows_impl::write_file(root, relative, content)
    }
    #[cfg(not(windows))]
    {
        let _ = (root, relative, content);
        Err(SecureFsError::feature_disabled(
            "files.write requires the Windows no-reparse broker primitive",
        ))
    }
}

/// Delete the file or EMPTY folder at `relative` inside `root`. Reparse-point
/// leaves are never deleted (links are not removed); a non-empty directory is
/// refused. Recursive deletion is not implemented.
pub fn secure_delete(root: &Path, relative: &str) -> SecureFsResult<DeleteOutcome> {
    #[cfg(windows)]
    {
        windows_impl::delete(root, relative)
    }
    #[cfg(not(windows))]
    {
        let _ = (root, relative);
        Err(SecureFsError::feature_disabled(
            "files.delete requires the Windows no-reparse broker primitive",
        ))
    }
}

// ---------------------------------------------------------------------------
// Windows implementation
// ---------------------------------------------------------------------------

#[cfg(windows)]
mod windows_impl {
    use super::{
        display_path, validated_components, CreateFolderOutcome, DeleteOutcome, SecureFsError,
        SecureFsResult, WriteOutcome, MAX_TOOL_WRITE_BYTES,
    };
    use std::ffi::OsString;
    use std::fs::File;
    use std::io::{Seek, SeekFrom, Write};
    use std::os::windows::ffi::{OsStrExt, OsStringExt};
    use std::os::windows::io::{FromRawHandle, RawHandle};
    use std::path::{Path, PathBuf};
    use windows_sys::Wdk::Foundation::OBJECT_ATTRIBUTES;
    use windows_sys::Wdk::Storage::FileSystem::{
        NtCreateFile, FILE_DIRECTORY_FILE, FILE_OPEN, FILE_OPEN_FOR_BACKUP_INTENT, FILE_OPEN_IF,
        FILE_OPEN_REPARSE_POINT, FILE_SYNCHRONOUS_IO_NONALERT, NTCREATEFILE_CREATE_DISPOSITION,
        NTCREATEFILE_CREATE_OPTIONS,
    };
    use windows_sys::Win32::Foundation::{
        CloseHandle, HANDLE, INVALID_HANDLE_VALUE, NTSTATUS, OBJ_CASE_INSENSITIVE,
        OBJ_DONT_REPARSE, STATUS_ACCESS_DENIED, STATUS_CANNOT_DELETE, STATUS_DIRECTORY_NOT_EMPTY,
        STATUS_FILE_IS_A_DIRECTORY, STATUS_NOT_A_DIRECTORY, STATUS_OBJECT_NAME_COLLISION,
        STATUS_OBJECT_NAME_INVALID, STATUS_OBJECT_NAME_NOT_FOUND, STATUS_OBJECT_PATH_NOT_FOUND,
        STATUS_REPARSE_POINT_ENCOUNTERED, STATUS_REPARSE_POINT_NOT_RESOLVED,
        STATUS_SHARING_VIOLATION, UNICODE_STRING,
    };
    use windows_sys::Win32::Storage::FileSystem::{
        CreateFileW, FileDispositionInfo, GetFileInformationByHandle, GetFinalPathNameByHandleW,
        SetFileInformationByHandle, BY_HANDLE_FILE_INFORMATION, DELETE, FILE_ACCESS_RIGHTS,
        FILE_ADD_FILE, FILE_ADD_SUBDIRECTORY, FILE_ATTRIBUTE_DIRECTORY, FILE_ATTRIBUTE_NORMAL,
        FILE_ATTRIBUTE_OFFLINE, FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS,
        FILE_ATTRIBUTE_RECALL_ON_OPEN, FILE_ATTRIBUTE_REPARSE_POINT, FILE_DISPOSITION_INFO,
        FILE_FLAG_BACKUP_SEMANTICS, FILE_LIST_DIRECTORY, FILE_READ_ATTRIBUTES, FILE_SHARE_DELETE,
        FILE_SHARE_MODE, FILE_SHARE_READ, FILE_SHARE_WRITE, FILE_TRAVERSE, FILE_WRITE_ATTRIBUTES,
        FILE_WRITE_DATA, OPEN_EXISTING, SYNCHRONIZE,
    };
    use windows_sys::Win32::System::WindowsProgramming::FILE_CREATED;
    use windows_sys::Win32::System::IO::IO_STATUS_BLOCK;

    /// Access mask for directory handles used to walk or anchor the path:
    /// listing, attribute reads, traversal and child creation. The user owns
    /// the workspace, so requesting create rights on its directories does not
    /// widen the effective authority beyond the approved operation.
    const DIR_WALK_ACCESS: FILE_ACCESS_RIGHTS = FILE_LIST_DIRECTORY
        | FILE_READ_ATTRIBUTES
        | FILE_TRAVERSE
        | FILE_ADD_FILE
        | FILE_ADD_SUBDIRECTORY
        | SYNCHRONIZE;

    const FILE_LEAF_WRITE_ACCESS: FILE_ACCESS_RIGHTS =
        FILE_READ_ATTRIBUTES | FILE_WRITE_ATTRIBUTES | FILE_WRITE_DATA | SYNCHRONIZE;

    const SHARE_ALL: FILE_SHARE_MODE = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE;

    /// Reparse/offline/cloud-placeholder attributes that must never be trusted
    /// as plain filesystem objects (same class as src/files.rs).
    fn is_indirect_or_cloud_attributes(attributes: u32) -> bool {
        attributes
            & (FILE_ATTRIBUTE_REPARSE_POINT
                | FILE_ATTRIBUTE_OFFLINE
                | FILE_ATTRIBUTE_RECALL_ON_OPEN
                | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS)
            != 0
    }

    /// RAII wrapper: every OS handle is closed exactly once, on error paths too.
    struct OwnedHandle(HANDLE);

    impl Drop for OwnedHandle {
        fn drop(&mut self) {
            unsafe { CloseHandle(self.0) };
        }
    }

    /// Case-insensitive namespace comparison for final-path verification: the
    /// same normalization class as src/files.rs comparable_path (strip the
    /// \\?\ device prefix, fold the case, trim trailing separators).
    fn comparable_path(path: &Path) -> Option<String> {
        let text = path.to_str()?.replace('/', "\\");
        let normalized = if let Some(value) = text.strip_prefix("\\\\?\\UNC\\") {
            format!("\\{value}")
        } else if let Some(value) = text.strip_prefix("\\\\?\\") {
            value.to_owned()
        } else {
            text
        };
        Some(normalized.trim_end_matches('\\').to_lowercase())
    }

    fn final_path_of(handle: HANDLE) -> SecureFsResult<PathBuf> {
        let mut buffer = vec![0_u16; 32_768];
        let length = unsafe {
            GetFinalPathNameByHandleW(handle, buffer.as_mut_ptr(), buffer.len() as u32, 0)
        };
        if length == 0 || length as usize >= buffer.len() {
            return Err(SecureFsError::internal_error(
                "final path of the verified handle is unavailable",
            ));
        }
        buffer.truncate(length as usize);
        Ok(PathBuf::from(OsString::from_wide(&buffer)))
    }

    fn handle_attributes(handle: HANDLE) -> SecureFsResult<u32> {
        let mut information = BY_HANDLE_FILE_INFORMATION::default();
        let result = unsafe { GetFileInformationByHandle(handle, &mut information) };
        if result == 0 {
            return Err(SecureFsError::internal_error(
                "attributes of the verified handle are unavailable",
            ));
        }
        Ok(information.dwFileAttributes)
    }

    /// Number of names referring to the same inode as the verified handle.
    /// A hardlinked leaf passes every path-level verification (it is a plain
    /// file resolving inside the workspace) yet shares its data with another
    /// name outside the verified chain, so mutations must refuse it.
    fn handle_link_count(handle: HANDLE) -> SecureFsResult<u32> {
        let mut information = BY_HANDLE_FILE_INFORMATION::default();
        let result = unsafe { GetFileInformationByHandle(handle, &mut information) };
        if result == 0 {
            return Err(SecureFsError::internal_error(
                "link count of the verified handle is unavailable",
            ));
        }
        Ok(information.nNumberOfLinks)
    }

    /// Open the confirmed workspace root and pin it. The open follows no
    /// reparse flag on purpose: if a link was swapped in above the workspace,
    /// the final path of the opened handle will not match the confirmed
    /// identity and the whole operation is refused.
    fn open_root(root: &Path) -> SecureFsResult<OwnedHandle> {
        let wide: Vec<u16> = root
            .as_os_str()
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();
        let handle = unsafe {
            CreateFileW(
                wide.as_ptr(),
                DIR_WALK_ACCESS,
                SHARE_ALL,
                std::ptr::null(),
                OPEN_EXISTING,
                FILE_ATTRIBUTE_NORMAL | FILE_FLAG_BACKUP_SEMANTICS,
                std::ptr::null_mut(),
            )
        };
        if handle.is_null() || handle == INVALID_HANDLE_VALUE {
            return Err(SecureFsError::policy_blocked(
                "workspace root is unavailable; refusing to operate without a verified anchor",
            ));
        }
        let owned = OwnedHandle(handle);
        if is_indirect_or_cloud_attributes(handle_attributes(handle)?) {
            return Err(SecureFsError::policy_blocked(
                "workspace root is a reparse point or cloud placeholder",
            ));
        }
        let final_path = final_path_of(handle)?;
        if comparable_path(&final_path) != comparable_path(root) {
            return Err(SecureFsError::policy_blocked(
                "workspace root identity does not match the confirmed workspace",
            ));
        }
        Ok(owned)
    }

    struct NtName {
        unicode: UNICODE_STRING,
        // Keeps the allocation `unicode.Buffer` points into alive.
        #[allow(dead_code)]
        buffer: Vec<u16>,
    }

    fn nt_name_for(name: &str) -> NtName {
        let buffer: Vec<u16> = name.encode_utf16().collect();
        let length = (buffer.len() * 2) as u16;
        NtName {
            unicode: UNICODE_STRING {
                Length: length,
                MaximumLength: length,
                Buffer: buffer.as_ptr() as *mut u16,
            },
            buffer,
        }
    }

    /// Open `name` as a single NT object name RELATIVE to the verified parent
    /// handle. The name never re-enters the Win32 path namespace, so a
    /// validated component cannot be re-interpreted or re-resolved elsewhere.
    #[allow(clippy::too_many_arguments)]
    fn nt_open_relative(
        parent: HANDLE,
        name: &str,
        desired_access: FILE_ACCESS_RIGHTS,
        object_attributes_flags: u32,
        create_disposition: NTCREATEFILE_CREATE_DISPOSITION,
        create_options: NTCREATEFILE_CREATE_OPTIONS,
    ) -> SecureFsResult<(OwnedHandle, usize)> {
        let nt_name = nt_name_for(name);
        let object_attributes = OBJECT_ATTRIBUTES {
            Length: std::mem::size_of::<OBJECT_ATTRIBUTES>() as u32,
            RootDirectory: parent,
            ObjectName: &nt_name.unicode,
            Attributes: object_attributes_flags,
            SecurityDescriptor: std::ptr::null(),
            SecurityQualityOfService: std::ptr::null(),
        };
        let mut io_status = IO_STATUS_BLOCK::default();
        let mut handle: HANDLE = std::ptr::null_mut();
        let status = unsafe {
            NtCreateFile(
                &mut handle,
                desired_access,
                &object_attributes,
                &mut io_status,
                std::ptr::null(),
                FILE_ATTRIBUTE_NORMAL,
                SHARE_ALL,
                create_disposition,
                create_options,
                std::ptr::null(),
                0,
            )
        };
        if status != 0 {
            return Err(map_ntstatus(status, name));
        }
        Ok((OwnedHandle(handle), io_status.Information))
    }

    fn map_ntstatus(status: NTSTATUS, context: &str) -> SecureFsError {
        let code = status as u32;
        if code == STATUS_OBJECT_NAME_NOT_FOUND as u32
            || code == STATUS_OBJECT_PATH_NOT_FOUND as u32
            || code == STATUS_OBJECT_NAME_INVALID as u32
        {
            return SecureFsError::invalid_payload(format!("path does not exist: {context}"));
        }
        if code == STATUS_OBJECT_NAME_COLLISION as u32 {
            return SecureFsError::policy_blocked(format!("path already exists: {context}"));
        }
        if code == STATUS_FILE_IS_A_DIRECTORY as u32 {
            return SecureFsError::invalid_payload(format!(
                "path exists and is a directory: {context}"
            ));
        }
        if code == STATUS_NOT_A_DIRECTORY as u32 {
            return SecureFsError::invalid_payload(format!(
                "path exists and is not a directory: {context}"
            ));
        }
        // OBJ_DONT_REPARSE resolves to STATUS_REPARSE_POINT_ENCOUNTERED;
        // STATUS_REPARSE_POINT_NOT_RESOLVED covers the follow-refused class.
        if code == STATUS_REPARSE_POINT_ENCOUNTERED as u32
            || code == STATUS_REPARSE_POINT_NOT_RESOLVED as u32
        {
            return SecureFsError::policy_blocked(format!(
                "path component is a reparse point: {context}"
            ));
        }
        if code == STATUS_DIRECTORY_NOT_EMPTY as u32 {
            return SecureFsError::policy_blocked(format!(
                "folder is not empty; recursive delete is not available: {context}"
            ));
        }
        if code == STATUS_ACCESS_DENIED as u32
            || code == STATUS_CANNOT_DELETE as u32
            || code == STATUS_SHARING_VIOLATION as u32
        {
            return SecureFsError::policy_blocked(format!(
                "path is not accessible for this operation: {context}"
            ));
        }
        SecureFsError::internal_error(format!(
            "filesystem operation failed: NTSTATUS 0x{code:08X}: {context}"
        ))
    }

    /// Open one intermediate directory component relative to the pinned
    /// parent. OBJ_DONT_REPARSE makes the OS reject any reparse traversal for
    /// this resolution; the attribute and final-path checks below remain as
    /// defense-in-depth and pin the exact directory object.
    fn open_dir_component(
        parent: &OwnedHandle,
        name: &str,
        expected_comparable: &str,
    ) -> SecureFsResult<OwnedHandle> {
        let (handle, _) = nt_open_relative(
            parent.0,
            name,
            DIR_WALK_ACCESS,
            OBJ_CASE_INSENSITIVE | OBJ_DONT_REPARSE,
            FILE_OPEN,
            FILE_DIRECTORY_FILE | FILE_SYNCHRONOUS_IO_NONALERT,
        )?;
        if is_indirect_or_cloud_attributes(handle_attributes(handle.0)?) {
            return Err(SecureFsError::policy_blocked(
                "path component is a reparse point, junction, or cloud placeholder",
            ));
        }
        let final_path = final_path_of(handle.0)?;
        if comparable_path(&final_path).as_deref() != Some(expected_comparable) {
            return Err(SecureFsError::policy_blocked(
                "path component identity does not match the verified workspace chain",
            ));
        }
        Ok(handle)
    }

    fn comparable_root_prefix(root: &Path) -> SecureFsResult<String> {
        comparable_path(root).ok_or_else(|| {
            SecureFsError::policy_blocked("workspace root is not representable as a local path")
        })
    }

    fn walk_intermediates(
        root: &Path,
        components: &[String],
    ) -> SecureFsResult<(OwnedHandle, String)> {
        let mut parent = open_root(root)?;
        let mut expected = comparable_root_prefix(root)?;
        for component in &components[..components.len() - 1] {
            expected.push('\\');
            expected.push_str(&component.to_lowercase());
            parent = open_dir_component(&parent, component, &expected)?;
        }
        Ok((parent, expected))
    }

    pub(super) fn create_folder(
        root: &Path,
        relative: &str,
    ) -> SecureFsResult<CreateFolderOutcome> {
        let components = validated_components(relative)?;
        let (parent, mut expected) = walk_intermediates(root, &components)?;
        let leaf = components.last().expect("components are non-empty");
        expected.push('\\');
        expected.push_str(&leaf.to_lowercase());
        let (handle, information) = nt_open_relative(
            parent.0,
            leaf,
            FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
            OBJ_CASE_INSENSITIVE,
            FILE_OPEN_IF,
            // FILE_OPEN_REPARSE_POINT captures an existing link AS ITSELF
            // instead of following it: a reparse leaf is rejected below
            // without anything having been created or modified.
            FILE_DIRECTORY_FILE | FILE_OPEN_REPARSE_POINT | FILE_SYNCHRONOUS_IO_NONALERT,
        )?;
        if is_indirect_or_cloud_attributes(handle_attributes(handle.0)?) {
            return Err(SecureFsError::policy_blocked(
                "target is a reparse point, junction, or cloud placeholder",
            ));
        }
        let final_path = final_path_of(handle.0)?;
        if comparable_path(&final_path).as_deref() != Some(&expected) {
            return Err(SecureFsError::policy_blocked(
                "created folder identity does not match the verified workspace chain",
            ));
        }
        Ok(CreateFolderOutcome {
            path: display_path(root, &components),
            created: information == FILE_CREATED as usize,
        })
    }

    pub(super) fn write_file(
        root: &Path,
        relative: &str,
        content: &[u8],
    ) -> SecureFsResult<WriteOutcome> {
        if content.len() > MAX_TOOL_WRITE_BYTES {
            return Err(SecureFsError::invalid_payload(
                "content exceeds the writable size limit",
            ));
        }
        let components = validated_components(relative)?;
        let (parent, mut expected) = walk_intermediates(root, &components)?;
        let leaf = components.last().expect("components are non-empty");
        expected.push('\\');
        expected.push_str(&leaf.to_lowercase());
        let (handle, _) = nt_open_relative(
            parent.0,
            leaf,
            FILE_LEAF_WRITE_ACCESS,
            OBJ_CASE_INSENSITIVE,
            FILE_OPEN_IF,
            // FILE_OPEN_REPARSE_POINT captures an existing reparse leaf AS
            // ITSELF (never followed) so it can be classified honestly below,
            // BEFORE the truncation that the write performs on the handle.
            // Backup intent lets the same open inspect files and directories;
            // FILE_OPEN_IF never truncates on open.
            FILE_OPEN_REPARSE_POINT | FILE_OPEN_FOR_BACKUP_INTENT | FILE_SYNCHRONOUS_IO_NONALERT,
        )?;
        let attributes = handle_attributes(handle.0)?;
        if is_indirect_or_cloud_attributes(attributes) {
            return Err(SecureFsError::policy_blocked(
                "target is a reparse point, junction, or cloud placeholder",
            ));
        }
        if attributes & FILE_ATTRIBUTE_DIRECTORY != 0 {
            return Err(SecureFsError::invalid_payload(
                "path exists and is a directory",
            ));
        }
        if handle_link_count(handle.0)? > 1 {
            return Err(SecureFsError::policy_blocked(
                "hardlinked object is refused",
            ));
        }
        let final_path = final_path_of(handle.0)?;
        if comparable_path(&final_path).as_deref() != Some(&expected) {
            return Err(SecureFsError::policy_blocked(
                "target file identity does not match the verified workspace chain",
            ));
        }
        // Ownership of the raw handle moves to `file` from here on
        // (forget prevents the OwnedHandle drop from double-closing it); the
        // File closes it on every remaining path, including write errors.
        let mut file = unsafe { File::from_raw_handle(handle.0 as RawHandle) };
        std::mem::forget(handle);
        file.seek(SeekFrom::Start(0))
            .map_err(|error| SecureFsError::internal_error(format!("write failed: {error}")))?;
        file.set_len(0)
            .map_err(|error| SecureFsError::internal_error(format!("write failed: {error}")))?;
        file.write_all(content)
            .map_err(|error| SecureFsError::internal_error(format!("write failed: {error}")))?;
        Ok(WriteOutcome {
            path: display_path(root, &components),
            bytes_written: content.len(),
        })
    }

    pub(super) fn delete(root: &Path, relative: &str) -> SecureFsResult<DeleteOutcome> {
        let components = validated_components(relative)?;
        let (parent, mut expected) = walk_intermediates(root, &components)?;
        let leaf = components.last().expect("components are non-empty");
        expected.push('\\');
        expected.push_str(&leaf.to_lowercase());
        let (handle, _) = nt_open_relative(
            parent.0,
            leaf,
            DELETE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
            OBJ_CASE_INSENSITIVE,
            FILE_OPEN,
            // Backup intent lets one open cover both files and directories;
            // the reparse flag captures a link leaf as itself so it can be
            // refused instead of followed or removed.
            FILE_OPEN_FOR_BACKUP_INTENT | FILE_OPEN_REPARSE_POINT | FILE_SYNCHRONOUS_IO_NONALERT,
        )?;
        if is_indirect_or_cloud_attributes(handle_attributes(handle.0)?) {
            return Err(SecureFsError::policy_blocked(
                "reparse points, junctions, and links are never deleted",
            ));
        }
        if handle_link_count(handle.0)? > 1 {
            return Err(SecureFsError::policy_blocked(
                "hardlinked object is refused",
            ));
        }
        let final_path = final_path_of(handle.0)?;
        if comparable_path(&final_path).as_deref() != Some(&expected) {
            return Err(SecureFsError::policy_blocked(
                "delete target identity does not match the verified workspace chain",
            ));
        }
        let disposition = FILE_DISPOSITION_INFO { DeleteFile: true };
        let result = unsafe {
            SetFileInformationByHandle(
                handle.0,
                FileDispositionInfo,
                &disposition as *const FILE_DISPOSITION_INFO as *const core::ffi::c_void,
                std::mem::size_of::<FILE_DISPOSITION_INFO>() as u32,
            )
        };
        if result == 0 {
            // The Win32 error code carries the honest refusal reason: a
            // non-empty directory, incompatible sharing, or an ACL denial.
            let error = std::io::Error::last_os_error();
            match error.raw_os_error() {
                Some(145) => {
                    // ERROR_DIRECTORY_NOT_EMPTY: the classic disposition
                    // refuses non-empty folders, so recursive deletion is
                    // structurally impossible through this primitive.
                    return Err(SecureFsError::policy_blocked(
                        "folder is not empty; recursive delete is not available",
                    ));
                }
                Some(5) | Some(32) => {
                    // ERROR_ACCESS_DENIED / ERROR_SHARING_VIOLATION.
                    return Err(SecureFsError::policy_blocked(format!(
                        "delete was refused: {error}"
                    )));
                }
                _ => {
                    return Err(SecureFsError::internal_error(format!(
                        "delete failed: {error}"
                    )));
                }
            }
        }
        // Deletion happens when the last handle closes; dropping here
        // completes the operation on the verified object only.
        Ok(DeleteOutcome {
            path: display_path(root, &components),
        })
    }
}

// ---------------------------------------------------------------------------
// Control-plane broker seam
// ---------------------------------------------------------------------------

/// Execute an approved files.* mutation in this host process.
///
/// Contract: the caller (`approval_commands::run_tool_call_inner`) has already
/// required the tool's permission, consumed the one-time approval token and
/// minted the scoped ExecutionGrant. This seam re-verifies the grant material
/// against the exact input bytes (same defense as cu_broker::execute_broker_action)
/// before any filesystem object is touched, then dispatches to the secure
/// primitives with the confirmed workspace as the confinement root.
pub(crate) fn execute_broker_mutation(
    tool: &str,
    input: &Value,
    grant: Option<&crate::approval::ExecutionGrant>,
    workspace_path: &str,
) -> Result<Value, crate::control_plane::BridgeError> {
    let Some(grant) = grant else {
        return Err(crate::control_plane::BridgeError::new(
            "approval_required",
            "guarded filesystem mutation requires an execution grant",
        ));
    };
    if grant.tool != tool {
        return Err(crate::control_plane::BridgeError::new(
            "approval_operation_mismatch",
            "grant was issued for a different tool",
        ));
    }
    // Defense-in-depth: the grant is workspace-bound at issuance, so the
    // caller-passed confinement root must match the notarized grant workspace.
    if grant.workspace != workspace_path {
        return Err(crate::control_plane::BridgeError::new(
            "approval_workspace_mismatch",
            "grant workspace does not match the broker workspace",
        ));
    }
    if grant.is_expired() {
        return Err(crate::control_plane::BridgeError::new(
            "grant_expired",
            "execution grant expired",
        ));
    }
    if crate::approval::canonical_input_digest(input) != grant.input_digest {
        return Err(crate::control_plane::BridgeError::new(
            "approval_arguments_mismatch",
            "grant input digest does not match the broker input",
        ));
    }

    let path = input
        .get("path")
        .and_then(Value::as_str)
        .filter(|value| !value.is_empty())
        .ok_or_else(|| {
            crate::control_plane::BridgeError::new(
                CODE_INVALID_PAYLOAD,
                "path must be a non-empty string",
            )
        })?;
    let root = Path::new(workspace_path);
    if workspace_path.is_empty() || !root.is_absolute() {
        return Err(SecureFsError::policy_blocked(
            "filesystem mutations require a confirmed absolute workspace",
        )
        .into_bridge_error());
    }

    match tool {
        "files.create_folder" => {
            let outcome =
                secure_create_folder(root, path).map_err(SecureFsError::into_bridge_error)?;
            Ok(serde_json::json!({
                "tool": tool,
                "path": outcome.path.to_string_lossy(),
                "created": outcome.created,
                "mode": "rust_control_plane_broker",
            }))
        }
        "files.write" => {
            let content = input
                .get("content")
                .and_then(Value::as_str)
                .ok_or_else(|| {
                    crate::control_plane::BridgeError::new(
                        CODE_INVALID_PAYLOAD,
                        "content must be a string",
                    )
                })?;
            let outcome = secure_write_file(root, path, content.as_bytes())
                .map_err(SecureFsError::into_bridge_error)?;
            Ok(serde_json::json!({
                "tool": tool,
                "path": outcome.path.to_string_lossy(),
                "bytes_written": outcome.bytes_written,
                "mode": "rust_control_plane_broker",
            }))
        }
        "files.delete" => {
            let outcome = secure_delete(root, path).map_err(SecureFsError::into_bridge_error)?;
            Ok(serde_json::json!({
                "tool": tool,
                "path": outcome.path.to_string_lossy(),
                "deleted": true,
                "mode": "rust_control_plane_broker",
            }))
        }
        _ => Err(crate::control_plane::BridgeError::new(
            "unknown_tool",
            "tool is not a broker filesystem mutation",
        )),
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(all(test, windows))]
mod windows_tests {
    use super::windows_impl::{create_folder, delete, write_file};
    use super::{execute_broker_mutation, CODE_INVALID_PAYLOAD, CODE_POLICY_BLOCKED};
    use crate::approval::{canonical_input_digest, ExecutionGrant};
    use std::fs;
    use std::path::{Path, PathBuf};
    use std::time::{SystemTime, UNIX_EPOCH};

    struct TestDirectory {
        root: PathBuf,
    }

    impl TestDirectory {
        fn new(label: &str) -> Self {
            let root = std::env::temp_dir().join(format!(
                "localcomet-secure-fs-{label}-{}-{}",
                std::process::id(),
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map(|duration| duration.as_nanos())
                    .unwrap_or_default()
            ));
            fs::create_dir(&root).expect("create secure-fs test directory");
            Self { root }
        }

        fn path(&self, name: &str) -> PathBuf {
            self.root.join(name)
        }

        fn create_junction(&self, link: &str, target: &Path) -> bool {
            let output = std::process::Command::new("cmd")
                .args(["/c", "mklink", "/J"])
                .arg(self.path(link))
                .arg(target)
                .output()
                .expect("spawn mklink for junction fixture");
            output.status.success()
        }

        /// Create a hard link (`mklink /H`, no admin rights required). The
        /// caller MUST assert on the result: a silently skipped hardlink test
        /// would prove nothing about the hardlink protection.
        fn create_hardlink(&self, link: &str, target: &Path) -> bool {
            let output = std::process::Command::new("cmd")
                .args(["/c", "mklink", "/H"])
                .arg(self.path(link))
                .arg(target)
                .output()
                .expect("spawn mklink for hardlink fixture");
            output.status.success()
        }
    }

    impl Drop for TestDirectory {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.root);
        }
    }

    #[test]
    fn create_folder_happy_path_is_handle_relative_and_honest() {
        let workspace = TestDirectory::new("create-happy");
        fs::create_dir(workspace.path("alpha")).expect("create intermediate");
        let outcome = create_folder(&workspace.root, r"alpha\beta").expect("create nested folder");
        assert!(outcome.created);
        assert!(workspace.path(r"alpha\beta").is_dir());
        assert_eq!(
            outcome.path,
            workspace.path(r"alpha\beta"),
            "echoed path must be the verified absolute workspace path"
        );
        let again = create_folder(&workspace.root, "alpha/beta").expect("reopen folder");
        assert!(!again.created, "existing folder must not report creation");
    }

    #[test]
    fn write_file_creates_overwrites_and_reads_back() {
        let workspace = TestDirectory::new("write-happy");
        fs::create_dir(workspace.path("dir")).expect("create intermediate");
        let written =
            write_file(&workspace.root, r"dir\notes.txt", b"hello").expect("write new file");
        assert_eq!(written.bytes_written, 5);
        assert_eq!(
            fs::read(workspace.path(r"dir\notes.txt")).expect("read back"),
            b"hello"
        );
        // Overwrite with shorter content must fully truncate, not merge.
        let rewritten = write_file(&workspace.root, r"dir\notes.txt", b"hi").expect("overwrite");
        assert_eq!(rewritten.bytes_written, 2);
        assert_eq!(
            fs::read(workspace.path(r"dir\notes.txt")).expect("read back"),
            b"hi"
        );
    }

    #[test]
    fn delete_removes_file_and_empty_folder_but_refuses_non_empty_folder() {
        let workspace = TestDirectory::new("delete-happy");
        let written = write_file(&workspace.root, "victim.txt", b"data").expect("write fixture");
        assert_eq!(written.bytes_written, 4);
        delete(&workspace.root, "victim.txt").expect("delete file");
        assert!(!workspace.path("victim.txt").exists());

        fs::create_dir(workspace.path("empty-dir")).expect("create empty folder");
        delete(&workspace.root, "empty-dir").expect("delete empty folder");
        assert!(!workspace.path("empty-dir").exists());

        fs::create_dir(workspace.path("full-dir")).expect("create folder");
        fs::write(workspace.path(r"full-dir\child.txt"), b"x").expect("fill folder");
        let error = delete(&workspace.root, "full-dir").expect_err("non-empty folder refused");
        assert_eq!(error.code, CODE_POLICY_BLOCKED);
        assert!(error.message.contains("recursive delete is not available"));
        assert!(workspace.path("full-dir").is_dir());
    }

    #[test]
    fn junction_component_is_rejected_for_create_write_and_delete() {
        let workspace = TestDirectory::new("junction-component");
        fs::create_dir(workspace.path("target")).expect("create junction target");
        fs::write(workspace.path(r"target\secret.txt"), b"outside").expect("fill junction target");
        assert!(
            workspace.create_junction("link", &workspace.path("target")),
            "mklink /J is unavailable in this test environment: junction protection must be verified, not skipped"
        );
        // Escalation via a junction component must be refused for every mutation.
        let create_error =
            create_folder(&workspace.root, r"link\sub").expect_err("junction component refused");
        assert_eq!(create_error.code, CODE_POLICY_BLOCKED);
        assert!(!workspace.path(r"target\sub").exists());

        let write_error = write_file(&workspace.root, r"link\escape.txt", b"no")
            .expect_err("junction write refused");
        assert_eq!(write_error.code, CODE_POLICY_BLOCKED);
        assert!(!workspace.path(r"target\escape.txt").exists());

        // A reparse leaf is never deleted: the link itself must survive.
        let delete_error = delete(&workspace.root, "link").expect_err("junction delete refused");
        assert_eq!(delete_error.code, CODE_POLICY_BLOCKED);
        assert!(workspace.path("link").exists());
        assert!(workspace.path(r"target\secret.txt").exists());
    }

    #[test]
    fn junction_leaf_is_refused_for_create_and_write_without_touching_the_target() {
        let workspace = TestDirectory::new("junction-leaf");
        fs::create_dir(workspace.path("outside")).expect("create junction target");
        assert!(
            workspace.create_junction("link-dir", &workspace.path("outside")),
            "mklink /J is unavailable in this test environment: junction protection must be verified, not skipped"
        );
        let create_error =
            create_folder(&workspace.root, "link-dir").expect_err("reparse leaf refused");
        assert_eq!(create_error.code, CODE_POLICY_BLOCKED);
        let write_error =
            write_file(&workspace.root, "link-dir", b"x").expect_err("reparse leaf write refused");
        assert_eq!(write_error.code, CODE_POLICY_BLOCKED);
        // The junction and its target are untouched.
        assert!(workspace.path("link-dir").exists());
        assert_eq!(
            fs::read_dir(workspace.path("outside"))
                .expect("target intact")
                .count(),
            0
        );
    }

    #[test]
    fn hardlinked_leaf_is_refused_for_write_and_external_target_is_untouched() {
        let workspace = TestDirectory::new("hardlink-write");
        let outside = TestDirectory::new("hardlink-write-outside");
        fs::write(outside.path("keep.txt"), b"original").expect("create hardlink target");
        assert!(
            workspace.create_hardlink("leaked.txt", &outside.path("keep.txt")),
            "mklink /H is unavailable in this test environment: hardlink protection must be verified, not skipped"
        );
        assert_eq!(
            fs::read(workspace.path("leaked.txt")).expect("hardlink resolves to shared inode"),
            b"original"
        );
        let error = write_file(&workspace.root, "leaked.txt", b"tampered")
            .expect_err("hardlinked leaf must be refused");
        assert_eq!(error.code, CODE_POLICY_BLOCKED);
        assert!(error.message.contains("hardlinked object is refused"));
        assert_eq!(
            fs::read(outside.path("keep.txt")).expect("external target readable"),
            b"original",
            "write must not reach the shared inode"
        );
        assert_eq!(
            fs::read(workspace.path("leaked.txt")).expect("workspace leaf readable"),
            b"original",
            "leaf must not be truncated before the refusal"
        );
    }

    #[test]
    fn hardlinked_leaf_is_refused_for_delete_and_both_names_survive() {
        let workspace = TestDirectory::new("hardlink-delete");
        let outside = TestDirectory::new("hardlink-delete-outside");
        fs::write(outside.path("keep.txt"), b"original").expect("create hardlink target");
        assert!(
            workspace.create_hardlink("leaked.txt", &outside.path("keep.txt")),
            "mklink /H is unavailable in this test environment: hardlink protection must be verified, not skipped"
        );
        let error =
            delete(&workspace.root, "leaked.txt").expect_err("hardlinked leaf must be refused");
        assert_eq!(error.code, CODE_POLICY_BLOCKED);
        assert!(error.message.contains("hardlinked object is refused"));
        assert!(
            workspace.path("leaked.txt").exists(),
            "workspace link must survive the refusal"
        );
        assert!(
            outside.path("keep.txt").exists(),
            "external link must survive the refusal"
        );
        assert_eq!(
            fs::read(outside.path("keep.txt")).expect("external target readable"),
            b"original"
        );
    }

    #[test]
    fn plain_single_link_file_writes_and_deletes_as_before() {
        let workspace = TestDirectory::new("hardlink-plain");
        let outside = TestDirectory::new("hardlink-plain-outside");
        fs::write(outside.path("keep.txt"), b"anchor").expect("create hardlink target");
        assert!(
            workspace.create_hardlink("leaked.txt", &outside.path("keep.txt")),
            "mklink /H is unavailable in this test environment: hardlink protection must be verified, not skipped"
        );
        // The nLinks=1 contract is unchanged, even next to a hardlink fixture.
        let written = write_file(&workspace.root, "plain.txt", b"fresh").expect("plain file write");
        assert_eq!(written.bytes_written, 5);
        delete(&workspace.root, "plain.txt").expect("plain file delete");
        assert!(!workspace.path("plain.txt").exists());
        assert_eq!(
            fs::read(workspace.path("leaked.txt")).expect("hardlink leaf intact"),
            b"anchor"
        );
    }

    // -- execute_broker_mutation: direct tests of the security seam ----------

    fn broker_grant(tool: &str, input: &serde_json::Value, workspace: &Path) -> ExecutionGrant {
        ExecutionGrant {
            grant_id: "test-grant-id".to_owned(),
            tool: tool.to_owned(),
            input_digest: canonical_input_digest(input),
            workspace: workspace.to_string_lossy().into_owned(),
            session: "test-session".to_owned(),
            nonce: [0u8; 16],
            valid_until: std::time::Instant::now() + std::time::Duration::from_secs(30),
            approval_id: "appr_00000000000000000000000000000000".to_owned(),
            call_id: "call_00000000000000000000000000000000".to_owned(),
        }
    }

    #[test]
    fn broker_mutation_without_grant_requires_approval_and_touches_nothing() {
        let workspace = TestDirectory::new("broker-no-grant");
        let error = execute_broker_mutation(
            "files.create_folder",
            &serde_json::json!({ "path": "alpha" }),
            None,
            workspace.root.to_string_lossy().as_ref(),
        )
        .expect_err("guarded mutation without a grant must be refused");
        assert_eq!(error.code, "approval_required");
        assert_eq!(
            fs::read_dir(&workspace.root)
                .expect("workspace intact")
                .count(),
            0,
            "filesystem must be untouched"
        );
    }

    #[test]
    fn broker_mutation_with_wrong_tool_grant_is_operation_mismatch() {
        let workspace = TestDirectory::new("broker-tool-mismatch");
        let input = serde_json::json!({ "path": "alpha" });
        // Grant minted for files.write must not authorize files.create_folder.
        let grant = broker_grant("files.write", &input, &workspace.root);
        let error = execute_broker_mutation(
            "files.create_folder",
            &input,
            Some(&grant),
            workspace.root.to_string_lossy().as_ref(),
        )
        .expect_err("grant for a different tool must be refused");
        assert_eq!(error.code, "approval_operation_mismatch");
        assert_eq!(
            fs::read_dir(&workspace.root)
                .expect("workspace intact")
                .count(),
            0,
            "filesystem must be untouched"
        );
    }

    #[test]
    fn broker_mutation_with_expired_grant_is_grant_expired() {
        let workspace = TestDirectory::new("broker-expired");
        let input = serde_json::json!({ "path": "alpha" });
        let mut grant = broker_grant("files.create_folder", &input, &workspace.root);
        grant.valid_until = std::time::Instant::now() - std::time::Duration::from_secs(1);
        let error = execute_broker_mutation(
            "files.create_folder",
            &input,
            Some(&grant),
            workspace.root.to_string_lossy().as_ref(),
        )
        .expect_err("expired grant must be refused");
        assert_eq!(error.code, "grant_expired");
        assert_eq!(
            fs::read_dir(&workspace.root)
                .expect("workspace intact")
                .count(),
            0,
            "filesystem must be untouched"
        );
    }

    #[test]
    fn broker_mutation_with_tampered_path_is_arguments_mismatch() {
        let workspace = TestDirectory::new("broker-digest");
        // The grant binds the exact input bytes; swapping the path must fail
        // the digest re-verification before any filesystem object is touched.
        let approved_input = serde_json::json!({ "path": "alpha" });
        let grant = broker_grant("files.create_folder", &approved_input, &workspace.root);
        let tampered_input = serde_json::json!({ "path": "beta" });
        let error = execute_broker_mutation(
            "files.create_folder",
            &tampered_input,
            Some(&grant),
            workspace.root.to_string_lossy().as_ref(),
        )
        .expect_err("digest mismatch must be refused");
        assert_eq!(error.code, "approval_arguments_mismatch");
        assert!(!workspace.path("alpha").exists());
        assert!(!workspace.path("beta").exists());
    }

    #[test]
    fn broker_mutation_happy_path_creates_folder_in_workspace() {
        let workspace = TestDirectory::new("broker-happy");
        let input = serde_json::json!({ "path": "alpha" });
        let grant = broker_grant("files.create_folder", &input, &workspace.root);
        let outcome = execute_broker_mutation(
            "files.create_folder",
            &input,
            Some(&grant),
            workspace.root.to_string_lossy().as_ref(),
        )
        .expect("valid grant must execute the mutation");
        assert_eq!(outcome["tool"], "files.create_folder");
        assert_eq!(outcome["created"], true);
        assert_eq!(outcome["mode"], "rust_control_plane_broker");
        assert!(workspace.path("alpha").is_dir());
    }

    #[test]
    fn traversal_absolute_unc_and_drive_relative_paths_are_rejected() {
        let workspace = TestDirectory::new("hostile-paths");
        for hostile in [
            r"..\escape.txt",
            r"sub\..\escape.txt",
            "C:\\Windows\\escape.txt",
            "C:relative.txt",
            "\\\\server\\share\\escape.txt",
            "sub//..",
        ] {
            let error =
                create_folder(&workspace.root, hostile).expect_err("hostile path must be refused");
            assert_eq!(error.code, CODE_INVALID_PAYLOAD, "create_folder({hostile})");
            let error = write_file(&workspace.root, hostile, b"x")
                .expect_err("hostile path must be refused");
            assert_eq!(error.code, CODE_INVALID_PAYLOAD, "write_file({hostile})");
            let error = delete(&workspace.root, hostile).expect_err("hostile path must be refused");
            assert_eq!(error.code, CODE_INVALID_PAYLOAD, "delete({hostile})");
        }
        // Nothing may have escaped the workspace.
        assert_eq!(
            fs::read_dir(&workspace.root)
                .expect("workspace intact")
                .count(),
            0
        );
    }

    #[test]
    fn embedded_nul_and_stream_separator_paths_are_rejected() {
        let workspace = TestDirectory::new("nul-paths");
        let error =
            create_folder(&workspace.root, "bad\0name").expect_err("embedded NUL must be refused");
        assert_eq!(error.code, CODE_INVALID_PAYLOAD);
        assert!(error.message.contains("null character"));
        let error = write_file(&workspace.root, "file.txt:stream", b"x")
            .expect_err("stream separator must be refused");
        assert_eq!(error.code, CODE_INVALID_PAYLOAD);
        let error = delete(&workspace.root, "a:b").expect_err("drive separator refused");
        assert_eq!(error.code, CODE_INVALID_PAYLOAD);
    }

    #[test]
    fn missing_intermediate_and_missing_leaf_fail_with_honest_codes() {
        let workspace = TestDirectory::new("missing-paths");
        // No auto-mkdir: parents must already exist.
        let error = write_file(&workspace.root, r"no-such-dir\f.txt", b"x")
            .expect_err("missing intermediate refused");
        assert_eq!(error.code, CODE_INVALID_PAYLOAD);
        let error = create_folder(&workspace.root, r"no-such-dir\child")
            .expect_err("missing intermediate refused");
        assert_eq!(error.code, CODE_INVALID_PAYLOAD);
        let error = delete(&workspace.root, "no-such-file.txt").expect_err("missing leaf refused");
        assert_eq!(error.code, CODE_INVALID_PAYLOAD);
    }

    #[test]
    fn create_folder_over_existing_file_and_write_over_directory_are_refused() {
        let workspace = TestDirectory::new("kind-mismatch");
        fs::write(workspace.path("occupied.txt"), b"data").expect("create file fixture");
        let error =
            create_folder(&workspace.root, "occupied.txt").expect_err("folder over file refused");
        assert_eq!(error.code, CODE_INVALID_PAYLOAD);
        assert_eq!(
            fs::read(workspace.path("occupied.txt")).expect("file untouched"),
            b"data"
        );

        fs::create_dir(workspace.path("folder")).expect("create folder fixture");
        let error =
            write_file(&workspace.root, "folder", b"x").expect_err("write over directory refused");
        assert_eq!(error.code, CODE_INVALID_PAYLOAD);
        assert!(workspace.path("folder").is_dir());
    }

    #[test]
    fn missing_workspace_root_fails_closed() {
        let workspace = TestDirectory::new("root-guard");
        let missing_root = workspace.path("does-not-exist");
        let error = create_folder(&missing_root, "child")
            .expect_err("missing workspace root must be refused");
        assert_eq!(error.code, CODE_POLICY_BLOCKED);
    }
}

#[cfg(all(test, not(windows)))]
mod non_windows_tests {
    use super::{secure_create_folder, secure_delete, secure_write_file, CODE_FEATURE_DISABLED};
    use std::path::Path;

    #[test]
    fn every_mutation_stays_feature_disabled_off_windows() {
        let root = Path::new("/tmp");
        assert_eq!(
            secure_create_folder(root, "child").unwrap_err().code,
            CODE_FEATURE_DISABLED
        );
        assert_eq!(
            secure_write_file(root, "child", b"x").unwrap_err().code,
            CODE_FEATURE_DISABLED
        );
        assert_eq!(
            secure_delete(root, "child").unwrap_err().code,
            CODE_FEATURE_DISABLED
        );
    }
}
