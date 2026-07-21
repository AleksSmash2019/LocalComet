use std::env;
use std::path::{Path, PathBuf};

pub(crate) const APPLICATION_DATA_ROOT_OVERRIDE: &str = "LOCALCOMET_APP_DATA_ROOT";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum ApplicationDataRootError {
    Empty,
    Relative,
    NonLocal,
}

impl ApplicationDataRootError {
    pub(crate) fn code(self) -> &'static str {
        match self {
            Self::Empty => "empty_app_data_root_override",
            Self::Relative => "relative_app_data_root_override",
            Self::NonLocal => "nonlocal_app_data_root_override",
        }
    }
}

pub(crate) fn resolve_application_data_root(
    default_local_data_dir: &Path,
) -> Result<PathBuf, ApplicationDataRootError> {
    match explicit_application_data_root()? {
        Some(root) => Ok(root),
        None => Ok(default_local_data_dir.join("LocalComet")),
    }
}

pub(crate) fn resolve_startup_application_data_root(
) -> Result<Option<PathBuf>, ApplicationDataRootError> {
    match explicit_application_data_root()? {
        Some(root) => Ok(Some(root)),
        None => Ok(env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .map(|base| base.join("LocalComet"))),
    }
}

fn explicit_application_data_root() -> Result<Option<PathBuf>, ApplicationDataRootError> {
    let Some(value) = env::var_os(APPLICATION_DATA_ROOT_OVERRIDE) else {
        return Ok(None);
    };
    if value.is_empty() {
        return Err(ApplicationDataRootError::Empty);
    }
    let root = PathBuf::from(value);
    if !root.is_absolute() {
        return Err(ApplicationDataRootError::Relative);
    }
    if !is_local_filesystem_path(&root) {
        return Err(ApplicationDataRootError::NonLocal);
    }
    Ok(Some(root))
}

#[cfg(windows)]
fn is_local_filesystem_path(path: &Path) -> bool {
    use std::path::{Component, Prefix};

    !path.components().any(|component| {
        matches!(
            component,
            Component::Prefix(prefix)
                if matches!(prefix.kind(), Prefix::UNC(_, _) | Prefix::VerbatimUNC(_, _))
        )
    })
}

#[cfg(not(windows))]
fn is_local_filesystem_path(_path: &Path) -> bool {
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::OsString;
    use std::sync::{Mutex, OnceLock};

    static OVERRIDE_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

    struct OverrideGuard {
        previous: Option<OsString>,
    }

    impl OverrideGuard {
        fn set(value: Option<OsString>) -> Self {
            let previous = env::var_os(APPLICATION_DATA_ROOT_OVERRIDE);
            match value {
                Some(value) => env::set_var(APPLICATION_DATA_ROOT_OVERRIDE, value),
                None => env::remove_var(APPLICATION_DATA_ROOT_OVERRIDE),
            }
            Self { previous }
        }
    }

    impl Drop for OverrideGuard {
        fn drop(&mut self) {
            match &self.previous {
                Some(value) => env::set_var(APPLICATION_DATA_ROOT_OVERRIDE, value),
                None => env::remove_var(APPLICATION_DATA_ROOT_OVERRIDE),
            }
        }
    }

    fn isolated_root(label: &str) -> PathBuf {
        env::temp_dir().join(format!(
            "localcomet-app-data-root-{label}-{}",
            std::process::id()
        ))
    }

    #[test]
    fn default_resolution_preserves_the_existing_localcomet_path() {
        let _lock = OVERRIDE_LOCK
            .get_or_init(|| Mutex::new(()))
            .lock()
            .expect("override lock");
        let _override = OverrideGuard::set(None);
        let local_data_dir = isolated_root("default-parent");

        let root = resolve_application_data_root(&local_data_dir).expect("default root");

        assert_eq!(root, local_data_dir.join("LocalComet"));
    }

    #[test]
    fn absolute_override_selects_the_exact_isolated_application_root() {
        let _lock = OVERRIDE_LOCK
            .get_or_init(|| Mutex::new(()))
            .lock()
            .expect("override lock");
        let expected = isolated_root("explicit");
        let _override = OverrideGuard::set(Some(expected.clone().into_os_string()));

        assert_eq!(
            resolve_application_data_root(&isolated_root("default-parent")).expect("explicit root"),
            expected
        );
        assert_eq!(
            resolve_startup_application_data_root().expect("startup root"),
            Some(expected)
        );
    }

    #[test]
    fn empty_and_relative_overrides_are_rejected_without_default_fallback() {
        let _lock = OVERRIDE_LOCK
            .get_or_init(|| Mutex::new(()))
            .lock()
            .expect("override lock");
        let default_parent = isolated_root("default-parent");

        let _empty = OverrideGuard::set(Some(OsString::new()));
        assert_eq!(
            resolve_application_data_root(&default_parent).expect_err("empty override rejected"),
            ApplicationDataRootError::Empty
        );
        drop(_empty);

        let _relative = OverrideGuard::set(Some(OsString::from("relative\\LocalComet")));
        assert_eq!(
            resolve_application_data_root(&default_parent).expect_err("relative override rejected"),
            ApplicationDataRootError::Relative
        );
    }

    #[cfg(windows)]
    #[test]
    fn network_share_override_is_rejected_as_nonlocal() {
        let _lock = OVERRIDE_LOCK
            .get_or_init(|| Mutex::new(()))
            .lock()
            .expect("override lock");
        let _override = OverrideGuard::set(Some(OsString::from(r"\\server\share\LocalComet")));

        assert_eq!(
            resolve_application_data_root(&isolated_root("default-parent"))
                .expect_err("network share rejected"),
            ApplicationDataRootError::NonLocal
        );
    }
}
