use std::io;

const INSTANCE_MUTEX_NAME: &str = r"Local\com.localcomet.desktop";

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
        acquire_named(INSTANCE_MUTEX_NAME)
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

        #[test]
        fn named_mutex_rejects_a_second_instance() {
            let name = format!(r"Local\com.localcomet.desktop.test.{}", std::process::id());
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
