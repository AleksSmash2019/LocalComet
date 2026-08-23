use std::io;

const INSTANCE_MUTEX_NAME: &str = r"Local\com.localcomet.desktop";

/// Hidden Computer Use workers run on a separate desktop and need to coexist
/// with the user's normal LocalComet window. Only the harness-owned, strictly
/// validated desktop prefix gets a scoped mutex; normal launches keep the
/// global single-instance boundary.
#[cfg(windows)]
fn instance_mutex_name(hidden_desktop: Option<&str>) -> String {
    let Some(name) = hidden_desktop
        .map(str::trim)
        .filter(|name| !name.is_empty())
    else {
        return INSTANCE_MUTEX_NAME.to_owned();
    };
    let valid_hidden_name = name.starts_with("LocalCometHiddenCU_")
        && name.len() <= 96
        && name
            .chars()
            .all(|character| character.is_ascii_alphanumeric() || matches!(character, '_' | '-'));
    if valid_hidden_name {
        format!(r"Local\com.localcomet.desktop.hidden.{name}")
    } else {
        INSTANCE_MUTEX_NAME.to_owned()
    }
}

#[cfg(windows)]
mod platform {
    use super::*;
    use std::ffi::OsStr;
    use std::os::windows::ffi::OsStrExt;
    use std::ptr::null;
    use windows_sys::Win32::Foundation::{CloseHandle, GetLastError, ERROR_ALREADY_EXISTS, HANDLE};
    use windows_sys::Win32::System::Threading::CreateMutexW;

    pub struct SingleInstanceGuard {
        handle: HANDLE,
    }

    unsafe impl Send for SingleInstanceGuard {}

    pub fn acquire() -> io::Result<Option<SingleInstanceGuard>> {
        let name = instance_mutex_name(std::env::var("LC_HIDDEN_DESKTOP_NAME").ok().as_deref());
        acquire_named(&name)
    }

    fn acquire_named(name: &str) -> io::Result<Option<SingleInstanceGuard>> {
        let mut wide_name: Vec<u16> = OsStr::new(name).encode_wide().collect();
        wide_name.push(0);
        let handle = unsafe { CreateMutexW(null(), 0, wide_name.as_ptr()) };
        if handle.is_null() {
            return Err(io::Error::last_os_error());
        }
        if unsafe { GetLastError() } == ERROR_ALREADY_EXISTS {
            unsafe {
                CloseHandle(handle);
            }
            return Ok(None);
        }
        Ok(Some(SingleInstanceGuard { handle }))
    }

    impl Drop for SingleInstanceGuard {
        fn drop(&mut self) {
            if !self.handle.is_null() {
                unsafe {
                    CloseHandle(self.handle);
                }
                self.handle = std::ptr::null_mut();
            }
        }
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        use windows_sys::Win32::System::Threading::GetCurrentProcessId;

        #[test]
        fn hidden_desktop_uses_scoped_mutex_without_changing_normal_name() {
            let hidden = instance_mutex_name(Some("LocalCometHiddenCU_test-01"));
            assert!(hidden.starts_with(r"Local\com.localcomet.desktop.hidden."));
            assert_eq!(instance_mutex_name(None), INSTANCE_MUTEX_NAME);
            assert_eq!(
                instance_mutex_name(Some("not-a-harness-desktop")),
                INSTANCE_MUTEX_NAME
            );
        }

        #[test]
        fn named_mutex_rejects_a_second_instance() {
            let name = format!(r"Local\com.localcomet.desktop.test.{}", unsafe {
                GetCurrentProcessId()
            });
            let first = acquire_named(&name).unwrap();
            assert!(first.is_some());
            let second = acquire_named(&name).unwrap();
            assert!(second.is_none());
        }
    }
}

#[cfg(not(windows))]
mod platform {
    use super::*;

    pub struct SingleInstanceGuard;

    pub fn acquire() -> io::Result<Option<SingleInstanceGuard>> {
        Ok(Some(SingleInstanceGuard))
    }
}

pub use platform::{acquire, SingleInstanceGuard};

#[cfg(test)]
mod portable_tests {
    #[cfg(windows)]
    use super::instance_mutex_name;

    #[cfg(windows)]
    #[test]
    fn invalid_hidden_name_falls_back_to_global_mutex() {
        assert_eq!(
            instance_mutex_name(Some("LocalCometHiddenCU_unsafe\\name")),
            super::INSTANCE_MUTEX_NAME
        );
    }
}
