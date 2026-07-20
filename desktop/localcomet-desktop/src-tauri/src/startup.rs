use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

pub const STARTUP_LOG_DISPLAY_PATH: &str = r"%LOCALAPPDATA%\LocalComet\logs\startup.log";

#[derive(Clone, Copy, Debug)]
pub enum StartupPhase {
    SingleInstance,
    BackendStart,
    BackendReadiness,
    WindowDisplay,
}

impl StartupPhase {
    fn log_name(self) -> &'static str {
        match self {
            Self::SingleInstance => "single_instance",
            Self::BackendStart => "backend_start",
            Self::BackendReadiness => "backend_readiness",
            Self::WindowDisplay => "window_display",
        }
    }

    fn display_name(self) -> &'static str {
        match self {
            Self::SingleInstance => "single-instance check",
            Self::BackendStart => "packaged backend start",
            Self::BackendReadiness => "packaged backend readiness",
            Self::WindowDisplay => "desktop window display",
        }
    }
}

pub fn record(phase: StartupPhase, status: &'static str, code: &'static str) {
    let Some(path) = startup_log_path() else {
        return;
    };
    let Some(parent) = path.parent() else {
        return;
    };
    if std::fs::create_dir_all(parent).is_err() {
        return;
    }
    let timestamp = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0);
    let row = format!(
        "timestamp_unix={timestamp}\tphase={}\tstatus={}\tcode={}\n",
        phase.log_name(),
        safe_token(status),
        safe_token(code)
    );
    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
        let _ = file.write_all(row.as_bytes());
    }
}

pub fn report_failure(phase: StartupPhase, code: &'static str) {
    record(phase, "failure", code);
    show_native_failure(&failure_message(phase, code));
}

fn failure_message(phase: StartupPhase, code: &str) -> String {
    format!(
        "LocalComet could not start.\n\nPhase: {}\nCode: {}\n\nRetry: It is safe to close this message and try LocalComet again. If the failure repeats, reinstall LocalComet using the approved installer.\n\nLog: {}\n\nClose safely: Select OK. Any managed child process will be stopped before the application exits.",
        phase.display_name(),
        safe_token(code),
        STARTUP_LOG_DISPLAY_PATH
    )
}

fn startup_log_path() -> Option<PathBuf> {
    std::env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .map(|base| base.join("LocalComet").join("logs").join("startup.log"))
}

fn safe_token(value: &str) -> String {
    value
        .chars()
        .filter(|character| {
            character.is_ascii_alphanumeric() || matches!(character, '_' | '-' | '.')
        })
        .take(64)
        .collect()
}

#[cfg(windows)]
fn show_native_failure(message: &str) {
    use std::ffi::OsStr;
    use std::os::windows::ffi::OsStrExt;
    use std::ptr::null_mut;
    use windows_sys::Win32::UI::WindowsAndMessaging::{
        MessageBoxW, MB_ICONERROR, MB_OK, MB_SETFOREGROUND,
    };

    let mut message_wide: Vec<u16> = OsStr::new(message).encode_wide().collect();
    message_wide.push(0);
    let mut title_wide: Vec<u16> = OsStr::new("LocalComet startup").encode_wide().collect();
    title_wide.push(0);
    unsafe {
        MessageBoxW(
            null_mut(),
            message_wide.as_ptr(),
            title_wide.as_ptr(),
            MB_OK | MB_ICONERROR | MB_SETFOREGROUND,
        );
    }
}

#[cfg(not(windows))]
fn show_native_failure(_message: &str) {}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn startup_failure_message_is_actionable_and_path_sanitized() {
        let message = failure_message(StartupPhase::BackendReadiness, "LC_START_102");
        assert!(message.contains("packaged backend readiness"));
        assert!(message.contains("safe to close"));
        assert!(message.contains("reinstall"));
        assert!(message.contains(STARTUP_LOG_DISPLAY_PATH));
        let machine_path_prefix = ["C:", "\\", "Users", "\\"].concat();
        assert!(!message.contains(&machine_path_prefix));
    }

    #[test]
    fn log_tokens_reject_path_and_control_characters() {
        assert_eq!(safe_token("code\r\nC:\\private"), "codeCprivate");
    }
}
