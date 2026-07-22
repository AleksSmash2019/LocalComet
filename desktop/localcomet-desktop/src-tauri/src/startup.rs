use crate::app_data_root::{self, ApplicationDataRootError, APPLICATION_DATA_ROOT_OVERRIDE};
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

pub const STARTUP_LOG_DISPLAY_PATH: &str = r"<LocalComet application-data root>\logs\startup.log";

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

pub fn record(phase: StartupPhase, status: &str, code: &str) {
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

pub fn report_failure_with_reason(phase: StartupPhase, code: &'static str, reason: &'static str) {
    record(phase, &failure_status(reason), code);
    show_native_failure(&failure_message(phase, code));
}

pub fn report_application_data_root_failure(error: ApplicationDataRootError) {
    show_native_failure(&application_data_root_failure_message(error));
}

fn application_data_root_failure_message(error: ApplicationDataRootError) -> String {
    format!(
        "LocalComet could not start.\n\nPhase: packaged application-data root validation\nCode: {}\n\n{} must be a nonempty absolute local directory path. LocalComet did not fall back to the normal profile.\n\nClose safely: Select OK, correct the launch environment, and try LocalComet again.",
        error.code(),
        APPLICATION_DATA_ROOT_OVERRIDE,
    )
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
    app_data_root::resolve_startup_application_data_root()
        .ok()
        .flatten()
        .map(|root| root.join("logs").join("startup.log"))
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

fn failure_status(reason: &str) -> String {
    format!("failure.{}", safe_token(reason))
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

    #[test]
    fn diagnostic_failure_reason_is_stable_and_sanitized() {
        assert_eq!(
            failure_status("sidecar_unavailable"),
            "failure.sidecar_unavailable"
        );
        assert_eq!(
            failure_status("sidecar\r\nC:\\private"),
            "failure.sidecarCprivate"
        );
    }

    #[test]
    fn application_data_root_failure_is_explicit_and_does_not_echo_paths() {
        let message = application_data_root_failure_message(ApplicationDataRootError::Relative);
        assert!(message.contains("LOCALCOMET_APP_DATA_ROOT"));
        assert!(message.contains("relative_app_data_root_override"));
        assert!(!message.contains("C:\\Users"));
    }
}
