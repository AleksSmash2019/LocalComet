use std::ffi::OsString;
use std::fs::File;
use std::io::{self, Write};
use std::path::{Path, PathBuf};

#[derive(Clone, Debug)]
pub struct SidecarLaunchSpec {
    pub executable: PathBuf,
    pub args: Vec<OsString>,
    pub current_dir: PathBuf,
    pub env: Vec<(OsString, OsString)>,
}

#[derive(Clone, Debug)]
pub struct ManagedRuntimeLaunchSpec {
    pub executable: PathBuf,
    pub args: Vec<OsString>,
    pub current_dir: PathBuf,
    pub env: Vec<(OsString, OsString)>,
}

#[cfg(windows)]
mod platform {
    use super::*;
    use std::ffi::{c_void, OsStr};
    use std::mem::{size_of, zeroed};
    use std::os::windows::ffi::OsStrExt;
    use std::os::windows::io::{FromRawHandle, RawHandle};
    use std::ptr::{null, null_mut};
    use windows_sys::Win32::Foundation::{
        CloseHandle, GetLastError, SetHandleInformation, HANDLE, HANDLE_FLAG_INHERIT,
        INVALID_HANDLE_VALUE, WAIT_TIMEOUT,
    };
    use windows_sys::Win32::Security::SECURITY_ATTRIBUTES;
    use windows_sys::Win32::System::JobObjects::{
        AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
        SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
        JOB_OBJECT_LIMIT_ACTIVE_PROCESS, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    };
    use windows_sys::Win32::System::Pipes::CreatePipe;
    use windows_sys::Win32::System::Threading::{
        CreateProcessW, DeleteProcThreadAttributeList, InitializeProcThreadAttributeList,
        ResumeThread, TerminateProcess, UpdateProcThreadAttribute, WaitForSingleObject,
        CREATE_NO_WINDOW, CREATE_SUSPENDED, CREATE_UNICODE_ENVIRONMENT,
        EXTENDED_STARTUPINFO_PRESENT, LPPROC_THREAD_ATTRIBUTE_LIST, PROCESS_INFORMATION,
        PROC_THREAD_ATTRIBUTE_HANDLE_LIST, STARTF_USESTDHANDLES, STARTUPINFOEXW, STARTUPINFOW,
    };

    pub struct ContainedSidecarProcess {
        process: OwnedHandle,
        job: OwnedHandle,
        stdin: File,
        stdout: Option<File>,
        stderr: Option<File>,
    }

    pub struct ContainedManagedRuntimeProcess {
        process: OwnedHandle,
        job: OwnedHandle,
        stdout: Option<File>,
        stderr: Option<File>,
    }

    impl ContainedSidecarProcess {
        pub fn spawn(spec: &SidecarLaunchSpec) -> io::Result<Self> {
            spawn_contained(spec)
        }

        pub fn take_stdout(&mut self) -> Option<File> {
            self.stdout.take()
        }

        pub fn take_stderr(&mut self) -> Option<File> {
            self.stderr.take()
        }

        pub fn is_running(&self) -> bool {
            let _job_handle = self.job.raw();
            unsafe { WaitForSingleObject(self.process.raw(), 0) == WAIT_TIMEOUT }
        }

        pub fn terminate(&self, exit_code: u32) {
            unsafe {
                TerminateProcess(self.process.raw(), exit_code);
            }
        }

        pub fn wait_bounded(&self, millis: u32) -> bool {
            unsafe { WaitForSingleObject(self.process.raw(), millis) != WAIT_TIMEOUT }
        }
    }

    impl ContainedManagedRuntimeProcess {
        pub fn spawn(spec: &ManagedRuntimeLaunchSpec) -> io::Result<Self> {
            spawn_managed_contained(spec)
        }

        pub fn take_stdout(&mut self) -> Option<File> {
            self.stdout.take()
        }

        pub fn take_stderr(&mut self) -> Option<File> {
            self.stderr.take()
        }

        pub fn is_running(&self) -> bool {
            let _job_handle = self.job.raw();
            unsafe { WaitForSingleObject(self.process.raw(), 0) == WAIT_TIMEOUT }
        }

        pub fn terminate(&self, exit_code: u32) {
            unsafe {
                TerminateProcess(self.process.raw(), exit_code);
            }
        }

        pub fn wait_bounded(&self, millis: u32) -> bool {
            unsafe { WaitForSingleObject(self.process.raw(), millis) != WAIT_TIMEOUT }
        }
    }

    impl Drop for ContainedManagedRuntimeProcess {
        fn drop(&mut self) {
            unsafe {
                if self.is_running() {
                    TerminateProcess(self.process.raw(), 0);
                    WaitForSingleObject(self.process.raw(), 2_000);
                }
            }
        }
    }

    impl Write for ContainedSidecarProcess {
        fn write(&mut self, buf: &[u8]) -> io::Result<usize> {
            self.stdin.write(buf)
        }

        fn flush(&mut self) -> io::Result<()> {
            self.stdin.flush()
        }
    }

    impl Drop for ContainedSidecarProcess {
        fn drop(&mut self) {
            unsafe {
                if self.is_running() {
                    TerminateProcess(self.process.raw(), 0);
                    WaitForSingleObject(self.process.raw(), 2_000);
                }
            }
        }
    }

    struct OwnedHandle {
        handle: HANDLE,
    }

    unsafe impl Send for OwnedHandle {}

    impl OwnedHandle {
        fn new(handle: HANDLE) -> io::Result<Self> {
            if invalid_handle(handle) {
                Err(last_error())
            } else {
                Ok(Self { handle })
            }
        }

        fn raw(&self) -> HANDLE {
            self.handle
        }

        fn into_file(mut self) -> File {
            let handle = self.handle;
            self.handle = null_mut();
            unsafe { File::from_raw_handle(handle as RawHandle) }
        }
    }

    impl Drop for OwnedHandle {
        fn drop(&mut self) {
            if !invalid_handle(self.handle) {
                unsafe {
                    CloseHandle(self.handle);
                }
                self.handle = null_mut();
            }
        }
    }

    struct AttributeList {
        pointer: LPPROC_THREAD_ATTRIBUTE_LIST,
        _buffer: Vec<u8>,
    }

    impl AttributeList {
        fn for_handles(handles: &[HANDLE]) -> io::Result<Self> {
            let mut size = 0_usize;
            unsafe {
                InitializeProcThreadAttributeList(null_mut(), 1, 0, &mut size);
            }
            if size == 0 {
                return Err(last_error());
            }
            let mut buffer = vec![0_u8; size];
            let pointer = buffer.as_mut_ptr() as LPPROC_THREAD_ATTRIBUTE_LIST;
            let initialized =
                unsafe { InitializeProcThreadAttributeList(pointer, 1, 0, &mut size) != 0 };
            if !initialized {
                return Err(last_error());
            }
            let updated = unsafe {
                UpdateProcThreadAttribute(
                    pointer,
                    0,
                    PROC_THREAD_ATTRIBUTE_HANDLE_LIST as usize,
                    handles.as_ptr() as *const c_void,
                    std::mem::size_of_val(handles),
                    null_mut(),
                    null(),
                ) != 0
            };
            if !updated {
                unsafe {
                    DeleteProcThreadAttributeList(pointer);
                }
                return Err(last_error());
            }
            Ok(Self {
                pointer,
                _buffer: buffer,
            })
        }
    }

    impl Drop for AttributeList {
        fn drop(&mut self) {
            unsafe {
                DeleteProcThreadAttributeList(self.pointer);
            }
        }
    }

    fn spawn_contained(spec: &SidecarLaunchSpec) -> io::Result<ContainedSidecarProcess> {
        let job = create_single_process_kill_on_close_job()?;
        let mut stdin_read = null_mut();
        let mut stdin_write = null_mut();
        let mut stdout_read = null_mut();
        let mut stdout_write = null_mut();
        let mut stderr_read = null_mut();
        let mut stderr_write = null_mut();
        let security = SECURITY_ATTRIBUTES {
            nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
            lpSecurityDescriptor: null_mut(),
            bInheritHandle: 1,
        };

        unsafe {
            if CreatePipe(&mut stdin_read, &mut stdin_write, &security, 0) == 0 {
                return Err(last_error());
            }
            if CreatePipe(&mut stdout_read, &mut stdout_write, &security, 0) == 0 {
                return Err(last_error());
            }
            if CreatePipe(&mut stderr_read, &mut stderr_write, &security, 0) == 0 {
                return Err(last_error());
            }
        }

        let child_stdin = OwnedHandle::new(stdin_read)?;
        let parent_stdin = OwnedHandle::new(stdin_write)?;
        let parent_stdout = OwnedHandle::new(stdout_read)?;
        let child_stdout = OwnedHandle::new(stdout_write)?;
        let parent_stderr = OwnedHandle::new(stderr_read)?;
        let child_stderr = OwnedHandle::new(stderr_write)?;

        set_parent_only(parent_stdin.raw())?;
        set_parent_only(parent_stdout.raw())?;
        set_parent_only(parent_stderr.raw())?;

        let inheritable_handles = [child_stdin.raw(), child_stdout.raw(), child_stderr.raw()];
        let attributes = AttributeList::for_handles(&inheritable_handles)?;
        let mut startup: STARTUPINFOEXW = unsafe { zeroed() };
        startup.StartupInfo.cb = size_of::<STARTUPINFOEXW>() as u32;
        startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
        startup.StartupInfo.hStdInput = child_stdin.raw();
        startup.StartupInfo.hStdOutput = child_stdout.raw();
        startup.StartupInfo.hStdError = child_stderr.raw();
        startup.lpAttributeList = attributes.pointer;

        let executable_wide = wide_null(spec.executable.as_os_str());
        let current_dir_wide = wide_null(spec.current_dir.as_os_str());
        let mut command_line = build_command_line(&spec.executable, &spec.args);
        let environment = build_environment_block(&spec.env);
        let mut process_info: PROCESS_INFORMATION = unsafe { zeroed() };
        let creation_flags = CREATE_SUSPENDED
            | CREATE_NO_WINDOW
            | CREATE_UNICODE_ENVIRONMENT
            | EXTENDED_STARTUPINFO_PRESENT;

        let created = unsafe {
            CreateProcessW(
                executable_wide.as_ptr(),
                command_line.as_mut_ptr(),
                null(),
                null(),
                1,
                creation_flags,
                environment.as_ptr() as *const c_void,
                current_dir_wide.as_ptr(),
                &startup.StartupInfo as *const STARTUPINFOW,
                &mut process_info,
            ) != 0
        };
        if !created {
            return Err(last_error());
        }

        let process = OwnedHandle::new(process_info.hProcess)?;
        let thread = OwnedHandle::new(process_info.hThread)?;
        let assigned = unsafe { AssignProcessToJobObject(job.raw(), process.raw()) != 0 };
        if !assigned {
            unsafe {
                TerminateProcess(process.raw(), 1);
            }
            return Err(last_error());
        }
        let resumed = unsafe { ResumeThread(thread.raw()) != u32::MAX };
        if !resumed {
            unsafe {
                TerminateProcess(process.raw(), 1);
            }
            return Err(last_error());
        }

        drop(child_stdin);
        drop(child_stdout);
        drop(child_stderr);
        drop(thread);

        Ok(ContainedSidecarProcess {
            process,
            job,
            stdin: parent_stdin.into_file(),
            stdout: Some(parent_stdout.into_file()),
            stderr: Some(parent_stderr.into_file()),
        })
    }

    fn spawn_managed_contained(
        spec: &ManagedRuntimeLaunchSpec,
    ) -> io::Result<ContainedManagedRuntimeProcess> {
        let job = create_single_process_kill_on_close_job()?;
        let mut stdout_read = null_mut();
        let mut stdout_write = null_mut();
        let mut stderr_read = null_mut();
        let mut stderr_write = null_mut();
        let security = SECURITY_ATTRIBUTES {
            nLength: size_of::<SECURITY_ATTRIBUTES>() as u32,
            lpSecurityDescriptor: null_mut(),
            bInheritHandle: 1,
        };

        unsafe {
            if CreatePipe(&mut stdout_read, &mut stdout_write, &security, 0) == 0 {
                return Err(last_error());
            }
            if CreatePipe(&mut stderr_read, &mut stderr_write, &security, 0) == 0 {
                return Err(last_error());
            }
        }

        let parent_stdout = OwnedHandle::new(stdout_read)?;
        let child_stdout = OwnedHandle::new(stdout_write)?;
        let parent_stderr = OwnedHandle::new(stderr_read)?;
        let child_stderr = OwnedHandle::new(stderr_write)?;

        set_parent_only(parent_stdout.raw())?;
        set_parent_only(parent_stderr.raw())?;

        let inheritable_handles = [child_stdout.raw(), child_stderr.raw()];
        let attributes = AttributeList::for_handles(&inheritable_handles)?;
        let mut startup: STARTUPINFOEXW = unsafe { zeroed() };
        startup.StartupInfo.cb = size_of::<STARTUPINFOEXW>() as u32;
        startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
        startup.StartupInfo.hStdInput = null_mut();
        startup.StartupInfo.hStdOutput = child_stdout.raw();
        startup.StartupInfo.hStdError = child_stderr.raw();
        startup.lpAttributeList = attributes.pointer;

        let executable_wide = wide_null(spec.executable.as_os_str());
        let current_dir_wide = wide_null(spec.current_dir.as_os_str());
        let mut command_line = build_command_line(&spec.executable, &spec.args);
        let environment = build_environment_block(&spec.env);
        let mut process_info: PROCESS_INFORMATION = unsafe { zeroed() };
        let creation_flags = CREATE_SUSPENDED
            | CREATE_NO_WINDOW
            | CREATE_UNICODE_ENVIRONMENT
            | EXTENDED_STARTUPINFO_PRESENT;

        let created = unsafe {
            CreateProcessW(
                executable_wide.as_ptr(),
                command_line.as_mut_ptr(),
                null(),
                null(),
                1,
                creation_flags,
                environment.as_ptr() as *const c_void,
                current_dir_wide.as_ptr(),
                &startup.StartupInfo as *const STARTUPINFOW,
                &mut process_info,
            ) != 0
        };
        if !created {
            return Err(last_error());
        }

        let process = OwnedHandle::new(process_info.hProcess)?;
        let thread = OwnedHandle::new(process_info.hThread)?;
        let assigned = unsafe { AssignProcessToJobObject(job.raw(), process.raw()) != 0 };
        if !assigned {
            unsafe {
                TerminateProcess(process.raw(), 1);
            }
            return Err(last_error());
        }
        let resumed = unsafe { ResumeThread(thread.raw()) != u32::MAX };
        if !resumed {
            unsafe {
                TerminateProcess(process.raw(), 1);
            }
            return Err(last_error());
        }

        drop(child_stdout);
        drop(child_stderr);
        drop(thread);

        Ok(ContainedManagedRuntimeProcess {
            process,
            job,
            stdout: Some(parent_stdout.into_file()),
            stderr: Some(parent_stderr.into_file()),
        })
    }

    fn create_single_process_kill_on_close_job() -> io::Result<OwnedHandle> {
        let job = OwnedHandle::new(unsafe { CreateJobObjectW(null(), null()) })?;
        let mut limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        limits.BasicLimitInformation.LimitFlags =
            JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_ACTIVE_PROCESS;
        limits.BasicLimitInformation.ActiveProcessLimit = 1;
        let configured = unsafe {
            SetInformationJobObject(
                job.raw(),
                JobObjectExtendedLimitInformation,
                &limits as *const _ as *const c_void,
                size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
            ) != 0
        };
        if !configured {
            return Err(last_error());
        }
        Ok(job)
    }

    fn set_parent_only(handle: HANDLE) -> io::Result<()> {
        let ok = unsafe { SetHandleInformation(handle, HANDLE_FLAG_INHERIT, 0) != 0 };
        if ok {
            Ok(())
        } else {
            Err(last_error())
        }
    }

    fn build_command_line(executable: &Path, args: &[OsString]) -> Vec<u16> {
        let mut parts = Vec::with_capacity(args.len() + 1);
        parts.push(quote_windows_arg(executable.as_os_str()));
        for arg in args {
            parts.push(quote_windows_arg(arg.as_os_str()));
        }
        wide_null(OsString::from(parts.join(" ")).as_os_str())
    }

    fn build_environment_block(env: &[(OsString, OsString)]) -> Vec<u16> {
        let mut pairs: Vec<(OsString, OsString)> = env.to_vec();
        pairs.sort_by(|left, right| {
            left.0
                .to_string_lossy()
                .to_ascii_uppercase()
                .cmp(&right.0.to_string_lossy().to_ascii_uppercase())
        });
        let mut block = Vec::new();
        for (key, value) in pairs {
            block.extend(key.encode_wide());
            block.push('=' as u16);
            block.extend(value.encode_wide());
            block.push(0);
        }
        block.push(0);
        block
    }

    fn quote_windows_arg(value: &OsStr) -> String {
        let text = value.to_string_lossy();
        if !text.is_empty() && !text.chars().any(|ch| ch.is_whitespace() || ch == '"') {
            return text.into_owned();
        }
        let mut quoted = String::from("\"");
        let mut backslashes = 0;
        for ch in text.chars() {
            match ch {
                '\\' => backslashes += 1,
                '"' => {
                    quoted.push_str(&"\\".repeat(backslashes * 2 + 1));
                    quoted.push('"');
                    backslashes = 0;
                }
                ch => {
                    quoted.push_str(&"\\".repeat(backslashes));
                    quoted.push(ch);
                    backslashes = 0;
                }
            }
        }
        quoted.push_str(&"\\".repeat(backslashes * 2));
        quoted.push('"');
        quoted
    }

    fn wide_null(value: &OsStr) -> Vec<u16> {
        let mut wide: Vec<u16> = value.encode_wide().collect();
        wide.push(0);
        wide
    }

    fn invalid_handle(handle: HANDLE) -> bool {
        handle.is_null() || handle == INVALID_HANDLE_VALUE
    }

    fn last_error() -> io::Error {
        io::Error::from_raw_os_error(unsafe { GetLastError() } as i32)
    }

    #[cfg(test)]
    mod tests {
        use super::*;
        use std::os::windows::ffi::OsStringExt;

        #[test]
        fn command_line_quotes_python_runner_and_flags() {
            let args = vec![
                OsString::from("-I"),
                OsString::from("-B"),
                OsString::from(r"Local Comet\tools\run_localcomet_desktop_sidecar.py"),
            ];
            let line = build_command_line(&PathBuf::from(r"Python\python.exe"), &args);
            let text = OsString::from_wide(&line[..line.len() - 1])
                .to_string_lossy()
                .into_owned();
            assert!(text.contains("-I"));
            assert!(text.contains("-B"));
            assert!(text.contains("\"Local Comet\\tools\\run_localcomet_desktop_sidecar.py\""));
        }

        #[test]
        fn environment_block_is_double_null_terminated() {
            let block =
                build_environment_block(&[(OsString::from("PYTHONUTF8"), OsString::from("1"))]);
            assert_eq!(&block[block.len() - 2..], &[0, 0]);
        }

        #[test]
        fn source_sets_active_process_limit_to_one() {
            let mut limits = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
            limits.BasicLimitInformation.LimitFlags =
                JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_ACTIVE_PROCESS;
            limits.BasicLimitInformation.ActiveProcessLimit = 1;
            assert_eq!(limits.BasicLimitInformation.ActiveProcessLimit, 1);
            assert!(limits.BasicLimitInformation.LimitFlags & JOB_OBJECT_LIMIT_ACTIVE_PROCESS != 0);
        }
    }
}

#[cfg(not(windows))]
mod platform {
    use super::*;

    pub struct ContainedSidecarProcess;
    pub struct ContainedManagedRuntimeProcess;

    impl ContainedSidecarProcess {
        pub fn spawn(_spec: &SidecarLaunchSpec) -> io::Result<Self> {
            Err(io::Error::other("Windows sidecar containment is required"))
        }

        pub fn take_stdout(&mut self) -> Option<File> {
            None
        }

        pub fn take_stderr(&mut self) -> Option<File> {
            None
        }

        pub fn is_running(&self) -> bool {
            false
        }

        pub fn terminate(&self, _exit_code: u32) {}

        pub fn wait_bounded(&self, _millis: u32) -> bool {
            true
        }
    }

    impl ContainedManagedRuntimeProcess {
        pub fn spawn(_spec: &ManagedRuntimeLaunchSpec) -> io::Result<Self> {
            Err(io::Error::other(
                "Windows managed runtime containment is required",
            ))
        }

        pub fn take_stdout(&mut self) -> Option<File> {
            None
        }

        pub fn take_stderr(&mut self) -> Option<File> {
            None
        }

        pub fn is_running(&self) -> bool {
            false
        }

        pub fn terminate(&self, _exit_code: u32) {}

        pub fn wait_bounded(&self, _millis: u32) -> bool {
            true
        }
    }

    impl Write for ContainedSidecarProcess {
        fn write(&mut self, _buf: &[u8]) -> io::Result<usize> {
            Err(io::Error::other("Windows sidecar containment is required"))
        }

        fn flush(&mut self) -> io::Result<()> {
            Err(io::Error::other("Windows sidecar containment is required"))
        }
    }
}

pub use platform::{ContainedManagedRuntimeProcess, ContainedSidecarProcess};
