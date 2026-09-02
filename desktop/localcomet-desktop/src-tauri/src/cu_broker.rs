//! Narrow Computer Use spawn broker.
//!
//! The Python sidecar runs inside a job object with `ActiveProcessLimit=1`
//! (containment invariant), so GUI-spawn actions such as `open_app` can never
//! be executed there — every child spawn fails with WinError 1816. This broker
//! runs in the Tauri host process and performs only strictly allowlisted
//! launch operations:
//!
//! * no arbitrary executable paths — only entries of the built-in app registry
//!   (resolved from System32 or the App Paths registration);
//! * no shell, no arbitrary command-line arguments; browser navigation passes
//!   exactly one validated HTTP(S) URL (plus harness-owned isolation flags);
//! * the execution grant consumed by `run_tool_call` is RE-VERIFIED here
//!   against the exact canonical input bytes before anything is launched;
//! * HIDDEN MODE: when the harness provides a hidden desktop name, every
//!   spawn is bound to `winsta0\<desktop>` via CreateProcessW STARTUPINFO
//!   BEFORE process creation — the child can never appear on the user's
//!   interactive desktop. Missing/invalid/unavailable binding in hidden mode
//!   means BLOCKED/FAILED, never a silent fallback;
//! * every outcome is returned as a truthful `computer_use.result.v1`
//!   envelope: `blocked` instead of fallbacks, `launch_pending` when the
//!   postcondition has not been observed yet, never an optimistic PASS.

use reqwest::Url;
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::process::Command;
use std::sync::Mutex;
use std::time::{Duration, Instant};

pub const ENVELOPE_SCHEMA: &str = "computer_use.result.v1";
const POSTCONDITION_TIMEOUT: Duration = Duration::from_secs(5);
const POSTCONDITION_POLL: Duration = Duration::from_millis(250);
/// How long a spawned launch stays observable for continuation checks.
const CONTINUATION_TTL: Duration = Duration::from_secs(600);

/// Test-only readiness fault injection for the canonical hidden desktop harness.
/// This function is compiled only when the harness explicitly builds the
/// dedicated `isolated-cu-test-hook` Cargo feature. Normal product builds do
/// not contain an environment-driven continuation-forcing path at all.
#[cfg(feature = "isolated-cu-test-hook")]
fn isolated_pending_fault_injection_enabled(action: &str, hidden_desktop: Option<&str>) -> bool {
    matches!(action, "open_app" | "open_url")
        && hidden_desktop.is_some()
        && std::env::var("LOCALCOMET_ISOLATED_CU_CAPABILITIES")
            .ok()
            .as_deref()
            == Some(crate::permission_context::ISOLATED_TEST_SENTINEL)
        && std::env::var("LC_FORCE_BROKER_CONTINUATION_PENDING")
            .ok()
            .as_deref()
            == Some("1")
}

#[cfg(not(feature = "isolated-cu-test-hook"))]
fn isolated_pending_fault_injection_enabled(_action: &str, _hidden_desktop: Option<&str>) -> bool {
    false
}

#[cfg(target_os = "windows")]
use windows_sys::Win32::{
    Foundation::{CloseHandle, FILETIME, HANDLE},
    System::Threading::{
        CreateProcessW, GetProcessTimes, OpenProcess, PROCESS_INFORMATION,
        PROCESS_QUERY_LIMITED_INFORMATION, STARTUPINFOW,
    },
    UI::WindowsAndMessaging::{GetForegroundWindow, GetWindowThreadProcessId, IsWindowVisible},
};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct ProcessIdentity {
    pid: u32,
    creation_time_100ns: u64,
}

fn process_identity_matches(expected: Option<u64>, observed: Option<u64>) -> bool {
    matches!((expected, observed), (Some(expected), Some(observed)) if expected == observed)
}

struct AppEntry {
    /// Static path relative to `%SystemRoot%`, when the app lives there.
    system32_exe: Option<&'static str>,
    /// App Paths registration file name (e.g. `chrome.exe`), resolved via the
    /// registry when no static path exists.
    app_paths_exe: Option<&'static str>,
    /// Process image names accepted by the readiness postcondition. The first
    /// entry also covers stub-relaunch flows (calc.exe -> CalculatorApp.exe).
    process_names: &'static [&'static str],
    /// Some Windows UWP launchers reparent the real app outside the broker's
    /// process tree. This is opt-in per registry entry and still requires a
    /// new PID absent from both hidden and input-desktop baselines.
    allow_reparented_process: bool,
}

const APP_REGISTRY: &[(&str, AppEntry)] = &[
    (
        "notepad",
        AppEntry {
            system32_exe: Some("notepad.exe"),
            app_paths_exe: None,
            process_names: &["notepad.exe"],
            allow_reparented_process: false,
        },
    ),
    (
        "calc",
        AppEntry {
            system32_exe: Some("calc.exe"),
            app_paths_exe: None,
            process_names: &["calculatorapp.exe"],
            allow_reparented_process: true,
        },
    ),
    (
        "mspaint",
        AppEntry {
            system32_exe: Some("mspaint.exe"),
            app_paths_exe: None,
            process_names: &["mspaint.exe"],
            allow_reparented_process: false,
        },
    ),
    (
        "explorer",
        AppEntry {
            system32_exe: None, // resolved as %SystemRoot%\explorer.exe
            app_paths_exe: None,
            process_names: &["explorer.exe"],
            allow_reparented_process: false,
        },
    ),
    (
        "chrome",
        AppEntry {
            system32_exe: None,
            app_paths_exe: Some("chrome.exe"),
            process_names: &["chrome.exe"],
            allow_reparented_process: false,
        },
    ),
    (
        "msedge",
        AppEntry {
            system32_exe: None,
            app_paths_exe: Some("msedge.exe"),
            process_names: &["msedge.exe"],
            allow_reparented_process: false,
        },
    ),
    (
        "firefox",
        AppEntry {
            system32_exe: None,
            app_paths_exe: Some("firefox.exe"),
            process_names: &["firefox.exe"],
            allow_reparented_process: false,
        },
    ),
    (
        "vscode",
        AppEntry {
            system32_exe: None,
            app_paths_exe: Some("code.exe"),
            process_names: &["code.exe"],
            allow_reparented_process: false,
        },
    ),
    (
        "steam",
        AppEntry {
            system32_exe: None,
            app_paths_exe: Some("steam.exe"),
            process_names: &["steam.exe"],
            allow_reparented_process: false,
        },
    ),
];

fn app_entry(canonical: &str) -> Option<&'static AppEntry> {
    APP_REGISTRY
        .iter()
        .find(|(id, _)| *id == canonical)
        .map(|(_, entry)| entry)
}

fn normalize_target(raw: &Value) -> Option<String> {
    let text = raw.as_str()?.trim().to_ascii_lowercase();
    // Models frequently emit the executable form ("calc.exe"); strip the
    // suffix so it maps onto the same registry entry.
    let stripped = text.strip_suffix(".exe").unwrap_or(&text);
    let canonical = match stripped {
        "notepad" | "блокнот" => "notepad",
        "calc" | "калькулятор" | "calculator" => "calc",
        "mspaint" | "paint" | "пейнт" | "рисование" => "mspaint",
        "explorer" | "проводник" | "файлы" => "explorer",
        "chrome" | "хром" => "chrome",
        "msedge" | "edge" => "msedge",
        "firefox" | "мозилла" => "firefox",
        "browser" | "браузер" => "browser",
        "vscode" | "code" | "вс код" => "vscode",
        "steam" | "стим" => "steam",
        other => other,
    };
    if app_entry(canonical).is_some() {
        Some(canonical.to_owned())
    } else {
        None
    }
}

/// Returns the broker-managed action key when the computer_use input belongs
/// to the spawn class handled by this broker. Everything else (wait, click,
/// type, screenshot, ...) stays on the sidecar execution path. `open_url` is
/// broker-only so a URL can never fall through to an interactive sidecar spawn.
pub fn broker_action(input: &Value) -> Option<&'static str> {
    let action = input.get("action")?.as_str()?.trim().to_ascii_lowercase();
    match action.as_str() {
        "open_app" => Some("open_app"),
        "open_folder" => Some("open_folder"),
        "open_url" => Some("open_url"),
        "close_owned" => Some("close_owned"),
        _ => None,
    }
}

fn system_root() -> String {
    std::env::var("SystemRoot").unwrap_or_else(|_| r"C:\Windows".to_owned())
}

fn join_dir(base: &str, child: &str) -> String {
    format!("{base}\\{child}")
}

fn resolve_folder(target: &str, workspace_path: Option<&str>) -> Option<String> {
    let profile = std::env::var("USERPROFILE").ok()?;
    match target {
        "downloads" | "загрузки" => Some(join_dir(&profile, "Downloads")),
        "documents" | "документы" => Some(join_dir(&profile, "Documents")),
        "pictures" | "изображения" => Some(join_dir(&profile, "Pictures")),
        "workspace" | "проект" | "рабочая папка" => {
            workspace_path.map(str::to_owned)
        }
        _ => None,
    }
}

struct ResolvedLaunch {
    program: String,
    args: Vec<String>,
    process_names: &'static [&'static str],
    allow_reparented_process: bool,
    /// Folder launches reuse the running shell process, so a NEW-pid
    /// postcondition would never fire; presence of the shell counts instead.
    shell_reused: bool,
    browser_url: Option<String>,
    browser_cdp_port: Option<u16>,
}

fn validate_browser_url(raw: &str) -> Result<String, String> {
    let raw = raw.trim();
    if raw.is_empty() || raw.len() > 2048 {
        return Err("URL must be non-empty and at most 2048 characters".into());
    }
    if raw
        .chars()
        .any(|character| character.is_ascii_control() || character.is_whitespace())
    {
        return Err("URL must not contain whitespace or control characters".into());
    }
    let authority = raw
        .strip_prefix("http://")
        .or_else(|| raw.strip_prefix("https://"))
        .and_then(|rest| rest.split(['/', '?', '#']).next())
        .unwrap_or_default();
    if authority.contains('@') || authority.contains(':') {
        return Err("URL credentials, explicit ports, and IPv6 literals are not allowed".into());
    }
    let parsed = Url::parse(raw).map_err(|_| "URL is not valid".to_owned())?;
    if !matches!(parsed.scheme(), "http" | "https") {
        return Err("only HTTP and HTTPS URLs are allowed".into());
    }
    if parsed.username() != "" || parsed.password().is_some() || parsed.port().is_some() {
        return Err("URL credentials and explicit ports are not allowed".into());
    }
    parsed
        .host_str()
        .filter(|host| !host.trim().is_empty())
        .ok_or_else(|| "URL host is missing".to_owned())?;
    Ok(parsed.to_string())
}

fn hidden_browser_launch_options(
    hidden_desktop: Option<&str>,
    canonical: &str,
) -> Result<(Vec<String>, Option<u16>), String> {
    if hidden_desktop.is_none() || !matches!(canonical, "chrome" | "msedge" | "firefox") {
        return Ok((Vec::new(), None));
    }
    let profile = std::env::var("LC_HIDDEN_BROWSER_PROFILE_DIR")
        .map_err(|_| "hidden browser profile is not configured".to_owned())?;
    validate_hidden_browser_profile(&profile)?;
    let port = std::env::var("LC_HIDDEN_BROWSER_CDP_PORT")
        .map_err(|_| "hidden browser CDP port is not configured".to_owned())?
        .parse::<u16>()
        .map_err(|_| "hidden browser CDP port is invalid".to_owned())?;
    if !(1024..=65535).contains(&port) {
        return Err("hidden browser CDP port is outside the user-port range".into());
    }
    if std::net::TcpListener::bind(("127.0.0.1", port)).is_err() {
        return Err("hidden browser CDP port is already in use".into());
    }
    let mut args = Vec::new();
    if canonical == "firefox" {
        args.push("--profile".into());
        args.push(profile);
        args.push("--no-remote".into());
    } else {
        args.push(format!("--user-data-dir={profile}"));
        args.push("--no-first-run".into());
        args.push("--no-default-browser-check".into());
    }
    args.push(format!("--remote-debugging-port={port}"));
    if canonical != "firefox" {
        // An explicit blank document makes open_app observable through the
        // broker-owned CDP endpoint before any user-driven navigation. It is a
        // fixed internal argument, never model-controlled URL data.
        args.push("--new-window".into());
        args.push("about:blank".into());
    }
    Ok((args, Some(port)))
}

fn plan_launch_with(
    action: &str,
    target_raw: &Value,
    url_raw: &Value,
    workspace_path: Option<&str>,
    hidden_desktop: Option<&str>,
    registry: &dyn Fn(&str) -> Option<String>,
) -> Result<ResolvedLaunch, String> {
    let target_value = target_raw.as_str().map(str::trim).unwrap_or_default();
    if target_value.is_empty() || target_value.len() > 200 {
        return Err("broker target must be a short non-empty string".into());
    }
    if target_value.contains('\\')
        || target_value.contains('/')
        || target_value.contains(':')
        || target_value.contains('"')
        || target_value.contains('&')
        || target_value.contains('|')
        || target_value.contains('^')
        || target_value.contains('%')
    {
        return Err("broker target must be a registry id, not a path".into());
    }
    let lowered = target_value.to_ascii_lowercase();
    match action {
        "open_app" => {
            // Strict separation: open_app must not carry a URL. If the planner
            // sent a URL, the typed contract requires open_url instead.
            if let Some(url_str) = url_raw.as_str() {
                if !url_str.trim().is_empty() {
                    return Err(
                        "open_app must not include a URL; use open_url for browser navigation"
                            .into(),
                    );
                }
            } else if !url_raw.is_null() && url_raw != &Value::Null {
                // Non-string URL payload is a schema violation.
                if !url_raw.is_null() {
                    return Err("open_app URL field must be absent or empty".into());
                }
            }
            let Some(canonical) = normalize_target(&Value::String(lowered.clone())) else {
                return Err("target app is not in the broker allowlist".into());
            };
            if hidden_desktop.is_some() && canonical == "calc" {
                return Err("calculator launch is disabled in hidden/automatic mode".into());
            }
            let entry =
                app_entry(&canonical).expect("normalized target must have a registry entry");
            let program = resolve_program_with(entry, registry).ok_or_else(|| {
                "allowlisted app executable was not found on this system".to_owned()
            })?;
            let (args, browser_cdp_port) =
                hidden_browser_launch_options(hidden_desktop, &canonical)?;
            Ok(ResolvedLaunch {
                program,
                args,
                process_names: entry.process_names,
                allow_reparented_process: entry.allow_reparented_process,
                shell_reused: canonical == "explorer",
                browser_url: None,
                browser_cdp_port,
            })
        }
        "open_folder" => {
            let Some(path) = resolve_folder(&lowered, workspace_path) else {
                return Err("target folder is not in the broker allowlist".into());
            };
            Ok(ResolvedLaunch {
                program: format!("{}\\explorer.exe", system_root()),
                args: vec![path],
                process_names: &["explorer.exe"],
                allow_reparented_process: false,
                shell_reused: true,
                browser_url: None,
                browser_cdp_port: None,
            })
        }
        "open_url" => {
            let canonical = if lowered == "browser" || lowered == "браузер" {
                ["chrome", "msedge", "firefox"]
                    .into_iter()
                    .find(|candidate| {
                        resolve_program_with(
                            app_entry(candidate).expect("browser candidate must be registered"),
                            registry,
                        )
                        .is_some()
                    })
                    .ok_or_else(|| {
                        "no allowlisted browser executable was found on this system".to_owned()
                    })?
                    .to_owned()
            } else {
                let Some(normalized) = normalize_target(&Value::String(lowered.clone())) else {
                    return Err("target browser is not in the broker allowlist".into());
                };
                normalized
            };
            if !matches!(canonical.as_str(), "chrome" | "msedge" | "firefox") {
                return Err("open_url supports only Chrome, Edge, or Firefox".into());
            }
            let entry =
                app_entry(&canonical).expect("normalized browser must have a registry entry");
            let program = resolve_program_with(entry, registry).ok_or_else(|| {
                "allowlisted browser executable was not found on this system".to_owned()
            })?;
            let url = url_raw
                .as_str()
                .ok_or_else(|| "open_url requires a URL string".to_owned())?;
            let validated_url = validate_browser_url(url)?;
            let (mut args, browser_cdp_port) =
                hidden_browser_launch_options(hidden_desktop, &canonical)?;
            args.push(validated_url.clone());
            Ok(ResolvedLaunch {
                program,
                args,
                process_names: entry.process_names,
                allow_reparented_process: entry.allow_reparented_process,
                shell_reused: false,
                browser_url: Some(validated_url),
                browser_cdp_port,
            })
        }
        other => Err(format!("unsupported broker action: {other}")),
    }
}

fn plan_launch(
    action: &str,
    target_raw: &Value,
    url_raw: &Value,
    workspace_path: Option<&str>,
    hidden_desktop: Option<&str>,
) -> Result<ResolvedLaunch, String> {
    plan_launch_with(
        action,
        target_raw,
        url_raw,
        workspace_path,
        hidden_desktop,
        &registry_lookup,
    )
}

/// Test-only seam for sibling modules (intent_compiler): same preflight as
/// `plan_launch`, but with a fixed fake App Paths registry so browser
/// resolution never depends on the host. Not part of the production surface.
#[cfg(test)]
pub(crate) fn plan_launch_with_for_test(
    action: &str,
    target_raw: &Value,
    url_raw: &Value,
    workspace_path: Option<&str>,
    hidden_desktop: Option<&str>,
) -> Result<(), String> {
    plan_launch_with(
        action,
        target_raw,
        url_raw,
        workspace_path,
        hidden_desktop,
        &|subkey: &str| {
            const BROWSER_EXES: [&str; 3] = ["chrome.exe", "msedge.exe", "firefox.exe"];
            if BROWSER_EXES
                .iter()
                .any(|exe| subkey.ends_with(&format!("\\{exe}")))
            {
                return Some(format!("{}\\System32\\notepad.exe", system_root()));
            }
            None
        },
    )
    .map(|_: ResolvedLaunch| ())
}

fn validate_hidden_browser_profile(raw: &str) -> Result<(), String> {
    let profile = raw.trim();
    if profile.is_empty() || profile.len() > 240 {
        return Err("hidden browser profile path is invalid".into());
    }
    let local_appdata = std::env::var("LOCALAPPDATA")
        .map_err(|_| "LOCALAPPDATA is unavailable for hidden browser profile".to_owned())?;
    let root = format!(
        "{}\\localcomethiddencu",
        local_appdata.trim_end_matches(['\\', '/'])
    );
    let normalized_profile = profile.replace('/', "\\").to_ascii_lowercase();
    let normalized_root = root.replace('/', "\\").to_ascii_lowercase();
    if !normalized_profile.starts_with(&(normalized_root + "\\")) {
        return Err("hidden browser profile must stay under LocalCometHiddenCU".into());
    }
    if !std::path::Path::new(profile).is_dir() {
        return Err("hidden browser profile directory is unavailable".into());
    }
    Ok(())
}

fn resolve_program_with(
    entry: &AppEntry,
    resolve_registry: &dyn Fn(&str) -> Option<String>,
) -> Option<String> {
    if let Some(exe) = entry.system32_exe {
        let path = format!("{}\\System32\\{exe}", system_root());
        if std::path::Path::new(&path).is_file() {
            return Some(path);
        }
    }
    if entry.process_names.contains(&"explorer.exe") {
        let path = format!("{}\\explorer.exe", system_root());
        if std::path::Path::new(&path).is_file() {
            return Some(path);
        }
    }
    if let Some(exe) = entry.app_paths_exe {
        for root_key in [
            r"HKCU\Software\Microsoft\Windows\CurrentVersion\App Paths",
            r"HKLM\Software\Microsoft\Windows\CurrentVersion\App Paths",
        ] {
            if let Some(path) = resolve_registry(&format!("{root_key}\\{exe}")) {
                let cleaned = path.trim_matches('"').to_owned();
                if std::path::Path::new(&cleaned).is_file() {
                    return Some(cleaned);
                }
            }
        }
    }
    None
}

/// The registry lookup seam for program resolution. Production always uses
/// `registry_default_value` (reg.exe); tests substitute a fixed fake so the
/// allowlisted-browser paths never depend on the host's installed browsers.
fn registry_lookup(subkey: &str) -> Option<String> {
    registry_default_value(subkey)
}

/// Registry default-value lookup via reg.exe (same pattern as hardware.rs).
/// The broker runs in the host process outside the sidecar job, so spawning
/// reg.exe here is safe and does not touch the confined sidecar.
fn registry_default_value(subkey: &str) -> Option<String> {
    let output = Command::new(r"C:\Windows\System32\reg.exe")
        .args(["query", subkey, "/ve"])
        .output()
        .ok()?;
    if !output.status.success() || output.stdout.len() > 8192 {
        return None;
    }
    let text = String::from_utf8_lossy(&output.stdout);
    text.lines().find_map(|line| {
        let trimmed = line.trim();
        let idx = trimmed.find("REG_SZ")?;
        let value = trimmed[idx + "REG_SZ".len()..].trim();
        (!value.is_empty()).then(|| value.to_owned())
    })
}

fn snapshot_pids() -> HashSet<u32> {
    let mut system = sysinfo::System::new();
    system.refresh_processes(sysinfo::ProcessesToUpdate::All);
    system.processes().keys().map(|pid| pid.as_u32()).collect()
}

fn process_name(pid: u32) -> Option<String> {
    let mut system = sysinfo::System::new();
    system.refresh_processes(sysinfo::ProcessesToUpdate::Some(&[sysinfo::Pid::from_u32(
        pid,
    )]));
    let process = system.process(sysinfo::Pid::from_u32(pid))?;
    Some(process.name().to_string_lossy().to_ascii_lowercase())
}

fn process_descends_from(candidate_pid: u32, ancestor_pid: u32) -> bool {
    if candidate_pid == ancestor_pid {
        return true;
    }
    let mut system = sysinfo::System::new();
    system.refresh_processes(sysinfo::ProcessesToUpdate::All);
    let mut current = sysinfo::Pid::from_u32(candidate_pid);
    let mut visited = HashSet::new();
    loop {
        if !visited.insert(current.as_u32()) {
            return false;
        }
        let Some(process) = system.process(current) else {
            return false;
        };
        let Some(parent) = process.parent() else {
            return false;
        };
        if parent.as_u32() == ancestor_pid {
            return true;
        }
        current = parent;
    }
}

#[cfg(target_os = "windows")]
fn hidden_process_observation(
    root_pid: u32,
    names: &[&str],
    desktop: &str,
    allow_reparented_process: bool,
    baseline_hidden_pids: &HashSet<u32>,
    baseline_user_pids: &HashSet<u32>,
) -> (Option<u32>, bool, bool, Value) {
    let Some(hidden_pids) = desktop_query::pids_with_windows(Some(desktop)) else {
        return (
            None,
            false,
            true,
            json!({"observation_error": "hidden_desktop_query_unavailable"}),
        );
    };
    let Some(user_pids) = desktop_query::pids_with_windows(None) else {
        return (
            None,
            false,
            true,
            json!({"observation_error": "user_desktop_query_unavailable"}),
        );
    };
    let is_spawned_allowlisted = |pid: u32, baseline: &HashSet<u32>| {
        let has_provenance = process_descends_from(pid, root_pid)
            || (allow_reparented_process && pid != root_pid && !baseline.contains(&pid));
        has_provenance
            && process_name(pid).is_some_and(|name| {
                names
                    .iter()
                    .any(|allowed| name == allowed.to_ascii_lowercase())
            })
    };
    let matching_hidden: Vec<u32> = hidden_pids
        .iter()
        .copied()
        .filter(|pid| !user_pids.contains(pid))
        .filter(|pid| is_spawned_allowlisted(*pid, baseline_hidden_pids))
        .collect();
    let matching_user: Vec<u32> = user_pids
        .iter()
        .copied()
        .filter(|pid| is_spawned_allowlisted(*pid, baseline_user_pids))
        .collect();
    let diagnostics = json!({
        "hidden_window_pid_count": hidden_pids.len(),
        "user_window_pid_count": user_pids.len(),
        "matching_hidden_pids": matching_hidden,
        "matching_user_pids": matching_user,
        "allow_reparented_process": allow_reparented_process,
        "expected_process_names": names,
    });
    let observed_pid = diagnostics
        .get("matching_hidden_pids")
        .and_then(Value::as_array)
        .and_then(|pids| pids.first())
        .and_then(Value::as_u64)
        .and_then(|pid| u32::try_from(pid).ok());
    let leaked_to_user = diagnostics
        .get("matching_user_pids")
        .and_then(Value::as_array)
        .is_some_and(|pids| !pids.is_empty());
    (observed_pid, leaked_to_user, false, diagnostics)
}

/// Defined MVP readiness signal: the spawned PID is still alive, or a NEW
/// process appeared whose image name belongs to the registry entry (covers
/// stub-relaunch flows such as calc.exe -> CalculatorApp.exe).
fn postcondition_reached(
    child_pid: u32,
    names: &[&str],
    baseline: &HashSet<u32>,
    budget: Duration,
) -> bool {
    let deadline = Instant::now() + budget;
    loop {
        if let Some(name) = process_name(child_pid) {
            if names
                .iter()
                .any(|allowed| name == allowed.to_ascii_lowercase())
            {
                return true;
            }
        }
        let fresh = snapshot_pids();
        for pid in fresh.difference(baseline) {
            if let Some(name) = process_name(*pid) {
                if names
                    .iter()
                    .any(|allowed| name == allowed.to_ascii_lowercase())
                {
                    return true;
                }
            }
        }
        if Instant::now() >= deadline {
            return false;
        }
        std::thread::sleep(POSTCONDITION_POLL);
    }
}

// ---------------------------------------------------------------------------
// Hidden-desktop support
// ---------------------------------------------------------------------------

/// Validate a desktop name supplied by the isolated harness. Only the exact
/// character class used by this harness is accepted; anything else fails the
/// action instead of falling back to the interactive desktop.
pub fn validate_hidden_desktop_name(name: &str) -> Result<String, String> {
    let trimmed = name.trim_start_matches("winsta0\\").trim();
    if trimmed.is_empty() || trimmed.len() > 80 {
        return Err("hidden desktop name length out of range".into());
    }
    if !trimmed
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '_')
    {
        return Err("hidden desktop name contains unsupported characters".into());
    }
    Ok(trimmed.to_owned())
}

fn to_wide(value: &str) -> Vec<u16> {
    value.encode_utf16().chain(std::iter::once(0)).collect()
}

/// Create the allowlisted program, optionally bound to a specific desktop via
/// STARTUPINFO.lpDesktop — the binding happens BEFORE process creation, so the
/// child can never flash on the interactive desktop in hidden mode.
#[cfg(target_os = "windows")]
fn create_process_on(
    program: &str,
    args: &[String],
    desktop: Option<&str>,
) -> Result<ProcessIdentity, String> {
    use windows_sys::Win32::System::Threading::CREATE_UNICODE_ENVIRONMENT;

    let mut command_line = format!("\"{program}\"");
    for arg in args {
        command_line.push_str(&format!(" \"{arg}\""));
    }
    let mut command_w = to_wide(&command_line);
    let mut program_w = to_wide(program);

    let mut startup: STARTUPINFOW = unsafe { std::mem::zeroed() };
    startup.cb = std::mem::size_of::<STARTUPINFOW>() as u32;
    let mut desktop_wide = desktop.map(|name| to_wide(&format!("winsta0\\{name}")));
    if let Some(wide) = desktop_wide.as_mut() {
        startup.lpDesktop = wide.as_mut_ptr();
    }

    let mut process_info: PROCESS_INFORMATION = unsafe { std::mem::zeroed() };
    let flags = CREATE_UNICODE_ENVIRONMENT;
    crate::startup::record_runtime("broker_create_process", "enter", "open_app");
    let ok = unsafe {
        CreateProcessW(
            program_w.as_mut_ptr(),
            command_w.as_mut_ptr(),
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            0,
            flags,
            std::ptr::null_mut(),
            std::ptr::null(),
            &startup,
            &mut process_info,
        )
    };
    crate::startup::record_runtime(
        "broker_create_process",
        "return",
        if ok == 0 { "failed" } else { "success" },
    );
    if ok == 0 {
        return Err(format!(
            "CreateProcessW failed (desktop={:?}): error {}",
            desktop,
            unsafe { windows_sys::Win32::Foundation::GetLastError() }
        ));
    }
    let pid = process_info.dwProcessId;
    crate::startup::record_runtime("broker_create_process", "identity_start", "open_app");
    let mut creation_time = FILETIME {
        dwLowDateTime: 0,
        dwHighDateTime: 0,
    };
    // GetProcessTimes requires valid writable buffers for all four FILETIME
    // outputs. Passing NULL for the unused exit/kernel/user times is an invalid
    // Win32 FFI contract and can surface as an access violation in the host
    // process immediately after CreateProcessW succeeds.
    let mut exit_time = FILETIME {
        dwLowDateTime: 0,
        dwHighDateTime: 0,
    };
    let mut kernel_time = FILETIME {
        dwLowDateTime: 0,
        dwHighDateTime: 0,
    };
    let mut user_time = FILETIME {
        dwLowDateTime: 0,
        dwHighDateTime: 0,
    };
    let queried = unsafe {
        GetProcessTimes(
            process_info.hProcess as HANDLE,
            &mut creation_time,
            &mut exit_time,
            &mut kernel_time,
            &mut user_time,
        )
    };
    crate::startup::record_runtime(
        "broker_create_process",
        "identity_return",
        if queried == 0 { "failed" } else { "success" },
    );
    unsafe {
        if queried == 0 {
            // The process is ours and has not been exposed to the registry yet;
            // terminate it before returning a failed launch so identity-query
            // failure cannot leak a broker-owned child.
            let _ = windows_sys::Win32::System::Threading::TerminateProcess(
                process_info.hProcess as HANDLE,
                1,
            );
        }
        CloseHandle(process_info.hThread as HANDLE);
        CloseHandle(process_info.hProcess as HANDLE);
    }
    crate::startup::record_runtime("broker_create_process", "handles_closed", "open_app");
    if queried == 0 {
        return Err("GetProcessTimes failed; refusing to register an unidentifiable child".into());
    }
    Ok(ProcessIdentity {
        pid,
        creation_time_100ns: ((creation_time.dwHighDateTime as u64) << 32)
            | creation_time.dwLowDateTime as u64,
    })
}

#[cfg(not(target_os = "windows"))]
fn create_process_on(
    _program: &str,
    _args: &[String],
    _desktop: Option<&str>,
) -> Result<ProcessIdentity, String> {
    Err("broker spawn requires Windows".into())
}

#[cfg(target_os = "windows")]
mod desktop_query {
    use super::*;

    struct Collected {
        pids_with_windows: HashSet<u32>,
    }

    unsafe extern "system" fn collect_cb(hwnd: *mut core::ffi::c_void, lparam: isize) -> i32 {
        let collected = &mut *(lparam as *mut Collected);
        if IsWindowVisible(hwnd) != 0 {
            let mut pid: u32 = 0;
            GetWindowThreadProcessId(hwnd, &mut pid);
            if pid != 0 {
                collected.pids_with_windows.insert(pid);
            }
        }
        1
    }

    pub fn desktop_exists(name: &str) -> bool {
        use windows_sys::Win32::System::StationsAndDesktops::{
            CloseDesktop, OpenDesktopW, DESKTOP_ENUMERATE, DESKTOP_READOBJECTS,
        };
        let wide = to_wide(name);
        let handle =
            unsafe { OpenDesktopW(wide.as_ptr(), 0, 0, DESKTOP_ENUMERATE | DESKTOP_READOBJECTS) };
        if handle.is_null() {
            return false;
        }
        unsafe { CloseDesktop(handle) };
        true
    }

    pub fn pids_with_windows(desktop: Option<&str>) -> Option<HashSet<u32>> {
        use windows_sys::Win32::System::StationsAndDesktops::{
            CloseDesktop, EnumDesktopWindows, OpenDesktopW, OpenInputDesktop, DESKTOP_ENUMERATE,
            DESKTOP_READOBJECTS,
        };
        let mut collected = Collected {
            pids_with_windows: HashSet::new(),
        };
        unsafe {
            match desktop {
                Some(name) => {
                    let wide = to_wide(name);
                    let handle =
                        OpenDesktopW(wide.as_ptr(), 0, 0, DESKTOP_ENUMERATE | DESKTOP_READOBJECTS);
                    if handle.is_null() {
                        return None;
                    }
                    EnumDesktopWindows(
                        handle,
                        Some(collect_cb),
                        &mut collected as *mut Collected as isize,
                    );
                    CloseDesktop(handle);
                }
                None => {
                    // The broker process may itself run on the named hidden
                    // desktop. EnumWindows would then enumerate that hidden
                    // desktop again and falsely classify the valid browser as
                    // an interactive leak. Open the real input desktop
                    // explicitly for the independent user-desktop check.
                    let handle = OpenInputDesktop(0, 0, DESKTOP_ENUMERATE | DESKTOP_READOBJECTS);
                    if handle.is_null() {
                        return None;
                    }
                    EnumDesktopWindows(
                        handle,
                        Some(collect_cb),
                        &mut collected as *mut Collected as isize,
                    );
                    CloseDesktop(handle);
                }
            }
        }
        Some(collected.pids_with_windows)
    }
}

// ---------------------------------------------------------------------------
// Spawn registry for continuation observation
// ---------------------------------------------------------------------------

#[derive(Clone)]
struct SpawnRecord {
    pid: u32,
    action: String,
    browser_url: Option<String>,
    browser_cdp_port: Option<u16>,
    process_names: &'static [&'static str],
    allow_reparented_process: bool,
    baseline_hidden_pids: HashSet<u32>,
    baseline_user_pids: HashSet<u32>,
    shell_reused: bool,
    expires_at: Instant,
    desktop: Option<String>,
    /// Exact approval call identity of the spawn (plan P0.2): a continuation
    /// observation must stay bound to the SAME approved request/action/input
    /// bytes and can never be reused for a different turn.
    action_id: String,
    /// One-time approval identities are evidence only; the grant token itself
    /// is never returned to the frontend or stored in this continuation record.
    approval_id: String,
    approval_call_id: String,
    input_digest: [u8; 32],
    /// Stable OS process creation identity used to reject same-image PID reuse.
    creation_time_100ns: Option<u64>,
}

static SPAWN_REGISTRY: Mutex<Option<HashMap<String, SpawnRecord>>> = Mutex::new(None);

fn registry() -> std::sync::MutexGuard<'static, Option<HashMap<String, SpawnRecord>>> {
    SPAWN_REGISTRY
        .lock()
        .expect("cu_broker spawn registry poisoned")
}

fn register_spawn(request_id: &str, record: SpawnRecord) {
    let mut guard = registry();
    let map = guard.get_or_insert_with(HashMap::new);
    let now = Instant::now();
    map.retain(|_, record| record.expires_at > now);
    map.insert(request_id.to_owned(), record);
}

#[allow(clippy::too_many_arguments)]
fn envelope(
    status: &str,
    terminal: bool,
    succeeded: bool,
    verification: &str,
    action: &str,
    reason: &str,
    execution: Value,
    request_id: &str,
    action_id: &str,
) -> Value {
    let mut payload = json!({
        "schema_version": ENVELOPE_SCHEMA,
        "tool": "computer_use",
        "action": action,
        "status": status,
        "terminal": terminal,
        "succeeded": succeeded,
        "verification": verification,
        "execution": execution,
    });
    if !reason.is_empty() {
        payload["reason"] = json!(reason);
    }
    if !request_id.is_empty() {
        payload["request_id"] = json!(request_id);
    }
    if !action_id.is_empty() {
        payload["action_id"] = json!(action_id);
    }
    payload
}

fn blocked_envelope(action: &str, reason: &str, request_id: &str, action_id: &str) -> Value {
    envelope(
        "blocked",
        true,
        false,
        "failed",
        action,
        reason,
        json!({"mode": "cu_broker_spawn", "backend": "rust-host"}),
        request_id,
        action_id,
    )
}

fn blocked_envelope_with_grant(
    action: &str,
    reason: &str,
    request_id: &str,
    action_id: &str,
    grant: &crate::approval::ExecutionGrant,
) -> Value {
    envelope(
        "blocked",
        true,
        false,
        "failed",
        action,
        reason,
        json!({
            "mode": "cu_broker_spawn",
            "backend": "rust-host",
            "approval_id": grant.approval_id,
            "approval_call_id": grant.call_id,
            "input_digest": hex_digest(&grant.input_digest),
        }),
        request_id,
        action_id,
    )
}

/// Validate a broker-managed action without spawning. This is used before
/// approval issuance so an unallowlisted target is reported as blocked rather
/// than shown as an approval candidate. It performs only registry/path
/// resolution; actual process creation remains in `execute_broker_action`.
pub fn validate_broker_action(
    action: &'static str,
    input: &Value,
    workspace_path: Option<&str>,
) -> Result<(), String> {
    if action == "close_owned" {
        let target = input
            .get("target")
            .and_then(Value::as_str)
            .map(str::trim)
            .unwrap_or_default();
        let ownership_request_id = input
            .get("ownership_request_id")
            .and_then(Value::as_str)
            .map(str::trim)
            .unwrap_or_default();
        if target.is_empty()
            || normalize_target(&Value::String(target.to_ascii_lowercase())).is_none()
        {
            return Err("close_owned target must be an allowlisted application".to_owned());
        }
        if !valid_request_id(ownership_request_id) {
            return Err("close_owned ownership_request_id is invalid".to_owned());
        }
        return Ok(());
    }
    let target = input.get("target").cloned().unwrap_or(Value::Null);
    let url = input.get("url").cloned().unwrap_or(Value::Null);
    plan_launch(action, &target, &url, workspace_path, None).map(|_| ())
}

/// Execute a broker-managed computer_use action. The caller has already
/// consumed the one-time approval token and holds the minted grant; this
/// boundary re-verifies the grant material before touching the OS.
///
/// `hidden_desktop`: Some(validated name) switches the broker into mandatory
/// desktop-bound mode (isolated harness runs). None = normal user mode where
/// the child inherits the interactive desktop by explicit user request.
pub fn execute_broker_action(
    action: &'static str,
    input: &Value,
    grant: Option<&crate::approval::ExecutionGrant>,
    request_id: Option<&str>,
    action_id: Option<&str>,
    workspace_path: Option<&str>,
    hidden_desktop: Option<&str>,
) -> Value {
    // Correlation is transport metadata. It is deliberately not read from
    // `input`, because the exact raw tool arguments are schema-validated and
    // hashed into the approval grant. Adding request_id/action_id there would
    // reject valid model calls and invalidate the grant digest.
    let request_id = request_id.unwrap_or_default().to_owned();
    let action_id = action_id.unwrap_or_default().to_owned();
    if !valid_request_id(&request_id) || !valid_action_id(&action_id) {
        return blocked_envelope(
            action,
            "out-of-band broker correlation is missing or invalid",
            "",
            "",
        );
    }

    let Some(grant) = grant else {
        return blocked_envelope(
            action,
            "dangerous action requires an execution grant",
            &request_id,
            &action_id,
        );
    };
    if grant.tool != "computer_use" {
        return blocked_envelope(
            action,
            "grant was issued for a different tool",
            &request_id,
            &action_id,
        );
    }
    if grant.is_expired() {
        return blocked_envelope(action, "execution grant expired", &request_id, &action_id);
    }
    if crate::approval::canonical_input_digest(input) != grant.input_digest {
        return blocked_envelope(
            action,
            "grant input digest does not match the broker input",
            &request_id,
            &action_id,
        );
    }

    // Hidden-mode binding is validated BEFORE anything else touches the OS.
    let validated_desktop: Option<String> = match hidden_desktop {
        Some(name) => match validate_hidden_desktop_name(name) {
            Ok(valid) => {
                // The desktop must be openable NOW: without this probe we
                // cannot guarantee the binding, and an unbindable spawn is
                // BLOCKED instead of silently landing elsewhere.
                if !desktop_query::desktop_exists(&valid) {
                    return blocked_envelope(
                        action,
                        "hidden desktop is unavailable; refusing to spawn unbound",
                        &request_id,
                        &action_id,
                    );
                }
                Some(valid)
            }
            Err(reason) => {
                return blocked_envelope(
                    action,
                    &format!("hidden desktop binding rejected: {reason}"),
                    &request_id,
                    &action_id,
                );
            }
        },
        None => None,
    };

    if action == "close_owned" {
        return close_owned_process(
            input,
            grant,
            &request_id,
            &action_id,
            validated_desktop.as_deref(),
        );
    }

    let launch = match plan_launch(
        action,
        &input.get("target").cloned().unwrap_or(Value::Null),
        &input.get("url").cloned().unwrap_or(Value::Null),
        workspace_path,
        validated_desktop.as_deref(),
    ) {
        Ok(launch) => launch,
        Err(reason) => {
            return blocked_envelope_with_grant(action, &reason, &request_id, &action_id, grant)
        }
    };

    let (baseline_hidden_pids, baseline_user_pids) = match validated_desktop.as_deref() {
        Some(name) => match (
            desktop_query::pids_with_windows(Some(name)),
            desktop_query::pids_with_windows(None),
        ) {
            (Some(hidden), Some(user)) => (
                hidden.into_iter().collect::<HashSet<_>>(),
                user.into_iter().collect::<HashSet<_>>(),
            ),
            _ => {
                return blocked_envelope_with_grant(
                    action,
                    "hidden desktop baseline observation unavailable; refusing to spawn",
                    &request_id,
                    &action_id,
                    grant,
                )
            }
        },
        None => (HashSet::new(), HashSet::new()),
    };

    let foreground_before = current_foreground();

    crate::startup::record_runtime("broker_dispatch", "pre_spawn", action);
    let identity =
        match create_process_on(&launch.program, &launch.args, validated_desktop.as_deref()) {
            Ok(identity) => identity,
            Err(error) => {
                return envelope(
                    "failed",
                    true,
                    false,
                    "failed",
                    action,
                    &error,
                    json!({
                        "mode": "cu_broker_spawn",
                        "backend": "rust-host",
                        "program": launch.program,
                        "desktop": validated_desktop,
                        "pid": Value::Null,
                        "url": launch.browser_url.clone(),
                        "cdp_port": launch.browser_cdp_port,
                        "approval_id": grant.approval_id,
                        "approval_call_id": grant.call_id,
                        "input_digest": hex_digest(&grant.input_digest),
                    }),
                    &request_id,
                    &action_id,
                );
            }
        };
    let pid = identity.pid;
    crate::startup::record_runtime("broker_dispatch", "spawn_return", action);

    // Postcondition differs by mode:
    // hidden  — a visible window owned by the expected image MUST exist on the
    //           hidden desktop AND MUST NOT exist on the interactive desktop;
    // user    — legacy liveness/name signal (explicitly requested user mode).
    crate::startup::record_runtime("broker_dispatch", "postcondition_start", action);
    let (postcondition_verified, mut window_evidence): (bool, Value) =
        match validated_desktop.as_deref() {
            Some(name) => {
                let deadline = Instant::now() + POSTCONDITION_TIMEOUT;
                loop {
                    let (observed_pid, leaked_to_user, observation_unavailable, observation_debug) =
                        hidden_process_observation(
                            pid,
                            launch.process_names,
                            name,
                            launch.allow_reparented_process,
                            &baseline_hidden_pids,
                            &baseline_user_pids,
                        );
                    if observation_unavailable {
                        break (
                            false,
                            json!({
                                "on_hidden_desktop": false,
                                "on_user_desktop": false,
                                "observation_error": "desktop_observation_unavailable",
                                "spawned_pid": pid,
                                "observation": observation_debug,
                            }),
                        );
                    }
                    if let Some(observed_pid) = observed_pid {
                        if !leaked_to_user {
                            break (
                                true,
                                json!({
                                    "on_hidden_desktop": true,
                                    "on_user_desktop": false,
                                    "observed_pid": observed_pid,
                                    "spawned_pid": pid,
                                    "observation": observation_debug,
                                }),
                            );
                        }
                    }
                    if leaked_to_user {
                        break (
                            false,
                            json!({
                                "on_hidden_desktop": false,
                                "on_user_desktop": true,
                                "spawned_pid": pid,
                                "observation": observation_debug,
                            }),
                        );
                    }
                    if Instant::now() >= deadline {
                        break (
                            false,
                            json!({
                                "on_hidden_desktop": false,
                                "on_user_desktop": false,
                                "spawned_pid": pid,
                                "observation": observation_debug,
                            }),
                        );
                    }
                    std::thread::sleep(POSTCONDITION_POLL);
                }
            }
            None => {
                let reached = launch.shell_reused
                    || postcondition_reached(
                        pid,
                        launch.process_names,
                        &snapshot_pids(),
                        POSTCONDITION_TIMEOUT,
                    );
                (reached, json!({"mode": "process_liveness"}))
            }
        };
    let forced_pending =
        isolated_pending_fault_injection_enabled(action, validated_desktop.as_deref());
    let verified = if forced_pending {
        if let Value::Object(details) = &mut window_evidence {
            details.insert(
                "isolated_pending_fault_injection".to_owned(),
                Value::Bool(true),
            );
        }
        false
    } else {
        postcondition_verified
    };

    crate::startup::record_runtime(
        "broker_dispatch",
        "postcondition_return",
        if verified { "verified" } else { "pending" },
    );
    let foreground_after = current_foreground();
    let focus_unchanged = foreground_before == foreground_after;
    let reported_pid = window_evidence
        .get("observed_pid")
        .and_then(Value::as_u64)
        .and_then(|value| u32::try_from(value).ok())
        .unwrap_or(pid);

    let (status, terminal, succeeded, verification, reason) = match verified {
        true => ("completed", true, true, "verified", ""),
        false => (
            "launch_pending",
            false,
            false,
            "pending",
            "spawn accepted but the readiness postcondition has not been observed yet",
        ),
    };

    if !request_id.is_empty() {
        register_spawn(
            &request_id,
            SpawnRecord {
                pid,
                action: action.to_owned(),
                browser_url: launch.browser_url.clone(),
                browser_cdp_port: launch.browser_cdp_port,
                process_names: launch.process_names,
                allow_reparented_process: launch.allow_reparented_process,
                baseline_hidden_pids,
                baseline_user_pids,
                shell_reused: launch.shell_reused,
                expires_at: Instant::now() + CONTINUATION_TTL,
                desktop: validated_desktop.clone(),
                action_id: action_id.clone(),
                approval_id: grant.approval_id.clone(),
                approval_call_id: grant.call_id.clone(),
                input_digest: grant.input_digest,
                creation_time_100ns: Some(identity.creation_time_100ns),
            },
        );
    }

    crate::startup::record_runtime("broker_dispatch", "continuation_start", action);
    // Broker-owned one-time continuation capability (master prompt Part I):
    // issued by Rust only, bound to this exact approved spawn correlation.
    // Raw token lives only inside this response envelope; the registry keeps
    // solely its SHA-256 hash. Duplicate issue for the same correlation does
    // not re-reveal the token.
    let mut continuation_json = Value::Null;
    if !request_id.is_empty() {
        // F-02 honesty contract: advertise ONLY actions the host runtime can
        // actually verify. The broker implements exactly one continuation
        // primitive today (bounded readiness observation); wait/wait_for_window
        // have no host-side postcondition executor and must not be promised.
        let allowed_next: Vec<String> = crate::cu_continuation::HOST_IMPLEMENTED_NEXT_ACTIONS
            .iter()
            .map(|kind| (*kind).to_owned())
            .collect();
        let idempotency_key = format!(
            "{}:{}:{}",
            hex_digest(&grant.input_digest),
            request_id,
            action_id
        );
        let task_id = format!("task_{request_id}");
        let step_id = format!("step_{action_id}");
        let postcondition_kind = if launch.browser_url.is_some() {
            "browser_readiness"
        } else {
            "process_liveness"
        };
        // ExecutionGrant.workspace is the canonical path used by the approval
        // scope, not its digest. Recompute the digest from that Rust-validated
        // path here; consume validates against the confirmed WorkspaceIdentity
        // digest. Passing the path into `workspace_digest` was a latent binding
        // bug that made every real continuation consume fail closed.
        let continuation_workspace_digest =
            crate::workspace::workspace_digest(std::path::Path::new(&grant.workspace));
        if let Ok(receipt) = crate::cu_continuation::issue_continuation_grant(
            &crate::cu_continuation::ContinuationIssueRequest {
                task_id: &task_id,
                step_id: &step_id,
                parent_request_id: &request_id,
                parent_action_id: &action_id,
                parent_input_digest: &grant.input_digest,
                session_id: &grant.session,
                workspace_digest: &continuation_workspace_digest,
                hidden_desktop: validated_desktop.as_deref(),
                target: input
                    .get("target")
                    .and_then(Value::as_str)
                    .unwrap_or_default(),
                allowed_next_actions: &allowed_next,
                expected_postcondition_kind: postcondition_kind,
                step_index: 0,
                remaining_steps: 2,
                ttl_ms: crate::cu_continuation::default_ttl_ms(),
                idempotency_key: &idempotency_key,
            },
        ) {
            continuation_json = json!({
                "schema_version": receipt.schema_version,
                "grant_ref": receipt.grant_ref,
                "grant_state": receipt.grant_state,
                "allowed_next_actions": receipt.allowed_next_actions,
                "step_index": receipt.step_index,
                "remaining_steps": receipt.remaining_steps,
                "expires_at_unix_ms": receipt.expires_at_unix_ms,
            });
        }
    }

    crate::startup::record_runtime("broker_dispatch", "envelope", action);
    envelope(
        status,
        terminal,
        succeeded,
        verification,
        action,
        reason,
        json!({
            "mode": "cu_broker_spawn",
            "backend": "rust-host",
            "program": launch.program,
            "pid": reported_pid,
            "spawn_pid": pid,
            "desktop": validated_desktop,
            "url": launch.browser_url,
            "cdp_port": launch.browser_cdp_port,
            "window_station": "winsta0",
            "window_evidence": window_evidence,
            "foreground_unchanged": focus_unchanged,
            "approval_id": grant.approval_id,
            "approval_call_id": grant.call_id,
            "input_digest": hex_digest(&grant.input_digest),
            "continuation": continuation_json,
        }),
        &request_id,
        &action_id,
    )
}

fn close_owned_process(
    input: &Value,
    grant: &crate::approval::ExecutionGrant,
    request_id: &str,
    action_id: &str,
    hidden_desktop: Option<&str>,
) -> Value {
    let parent_request_id = input
        .get("ownership_request_id")
        .and_then(Value::as_str)
        .map(str::trim)
        .unwrap_or_default();
    let target = input
        .get("target")
        .and_then(Value::as_str)
        .map(str::trim)
        .unwrap_or_default();
    if !valid_request_id(request_id)
        || !valid_action_id(action_id)
        || !valid_request_id(parent_request_id)
        || target.is_empty()
    {
        return blocked_envelope(
            "close_owned",
            "close_owned requires valid current and ownership request ids plus a target",
            request_id,
            action_id,
        );
    }

    let record = {
        let mut guard = registry();
        let map = guard.get_or_insert_with(HashMap::new);
        let now = Instant::now();
        map.retain(|_, record| record.expires_at > now);
        let Some(record) = map.get(parent_request_id) else {
            return blocked_envelope(
                "close_owned",
                "ownership record is missing or expired; refusing to close",
                request_id,
                action_id,
            );
        };
        record.clone()
    };

    if record.action != "open_app" && record.action != "open_url" && record.action != "open_folder"
    {
        return blocked_envelope(
            "close_owned",
            "ownership record is not a broker launch",
            request_id,
            action_id,
        );
    }
    if record.input_digest == grant.input_digest {
        return blocked_envelope(
            "close_owned",
            "close approval must be distinct from the launch approval",
            request_id,
            action_id,
        );
    }
    if let Some(expected_desktop) = record.desktop.as_deref() {
        if hidden_desktop != Some(expected_desktop) {
            return blocked_envelope(
                "close_owned",
                "close desktop binding does not match the owned launch",
                request_id,
                action_id,
            );
        }
    } else if hidden_desktop.is_some() {
        return blocked_envelope(
            "close_owned",
            "hidden close cannot target an interactive-desktop launch",
            request_id,
            action_id,
        );
    }

    let expected_target = normalize_target(&Value::String(target.to_ascii_lowercase()));
    let target_entry = expected_target.and_then(|name| app_entry(&name));
    let Some(target_entry) = target_entry else {
        return blocked_envelope(
            "close_owned",
            "close target is not in the broker allowlist",
            request_id,
            action_id,
        );
    };
    if !target_entry.process_names.iter().any(|expected| {
        record
            .process_names
            .iter()
            .any(|observed| observed == expected)
    }) {
        return blocked_envelope(
            "close_owned",
            "close target does not match the owned launch image",
            request_id,
            action_id,
        );
    }

    let mut system = sysinfo::System::new();
    system.refresh_processes(sysinfo::ProcessesToUpdate::All);
    let process = system.process(sysinfo::Pid::from_u32(record.pid));
    let Some(process) = process else {
        let mut guard = registry();
        if let Some(map) = guard.as_mut() {
            map.remove(parent_request_id);
        }
        return envelope(
            "completed",
            true,
            true,
            "verified",
            "close_owned",
            "",
            json!({
                "mode": "cu_broker_close_owned",
                "backend": "rust-host",
                "ownership_request_id": parent_request_id,
                "pid": record.pid,
                "already_exited": true,
                "approval_id": grant.approval_id,
                "approval_call_id": grant.call_id,
                "input_digest": hex_digest(&grant.input_digest),
            }),
            request_id,
            action_id,
        );
    };
    let process_name = process.name().to_string_lossy().to_ascii_lowercase();
    #[cfg(target_os = "windows")]
    let observed_creation_time = {
        let handle = unsafe { OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, record.pid) };
        if handle.is_null() {
            None
        } else {
            let mut creation = FILETIME {
                dwLowDateTime: 0,
                dwHighDateTime: 0,
            };
            let ok = unsafe {
                GetProcessTimes(
                    handle,
                    &mut creation,
                    std::ptr::null_mut(),
                    std::ptr::null_mut(),
                    std::ptr::null_mut(),
                )
            };
            unsafe {
                CloseHandle(handle);
            }
            (ok != 0)
                .then_some(((creation.dwHighDateTime as u64) << 32) | creation.dwLowDateTime as u64)
        }
    };
    #[cfg(not(target_os = "windows"))]
    let observed_creation_time: Option<u64> = None;
    if !process_identity_matches(record.creation_time_100ns, observed_creation_time) {
        return blocked_envelope(
            "close_owned",
            "owned PID creation identity changed or is unavailable; refusing to terminate",
            request_id,
            action_id,
        );
    }
    if !record
        .process_names
        .iter()
        .any(|expected| *expected == process_name)
    {
        return blocked_envelope(
            "close_owned",
            "owned PID image changed; refusing to terminate a reused PID",
            request_id,
            action_id,
        );
    }
    if record.desktop.is_some() {
        let Some(pids) = desktop_query::pids_with_windows(record.desktop.as_deref()) else {
            return blocked_envelope(
                "close_owned",
                "owned desktop observation unavailable; refusing to close",
                request_id,
                action_id,
            );
        };
        if !pids.contains(&record.pid) {
            return blocked_envelope(
                "close_owned",
                "owned process is not observed on its bound desktop",
                request_id,
                action_id,
            );
        }
    }
    if !process.kill() {
        return blocked_envelope(
            "close_owned",
            "owned process termination was rejected by the OS",
            request_id,
            action_id,
        );
    }

    let deadline = Instant::now() + Duration::from_secs(3);
    loop {
        let mut verify = sysinfo::System::new();
        verify.refresh_processes(sysinfo::ProcessesToUpdate::All);
        if verify.process(sysinfo::Pid::from_u32(record.pid)).is_none() {
            let mut guard = registry();
            if let Some(map) = guard.as_mut() {
                map.remove(parent_request_id);
            }
            return envelope(
                "completed",
                true,
                true,
                "verified",
                "close_owned",
                "",
                json!({
                    "mode": "cu_broker_close_owned",
                    "backend": "rust-host",
                    "ownership_request_id": parent_request_id,
                    "pid": record.pid,
                    "terminated": true,
                    "approval_id": grant.approval_id,
                    "approval_call_id": grant.call_id,
                    "input_digest": hex_digest(&grant.input_digest),
                }),
                request_id,
                action_id,
            );
        }
        if Instant::now() >= deadline {
            return envelope(
                "launch_pending",
                false,
                false,
                "pending",
                "close_owned",
                "termination was requested but the owned process is still alive",
                json!({
                    "mode": "cu_broker_close_owned",
                    "backend": "rust-host",
                    "ownership_request_id": parent_request_id,
                    "pid": record.pid,
                    "terminated": false,
                    "approval_id": grant.approval_id,
                    "approval_call_id": grant.call_id,
                    "input_digest": hex_digest(&grant.input_digest),
                }),
                request_id,
                action_id,
            );
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

fn current_foreground() -> usize {
    #[cfg(target_os = "windows")]
    unsafe {
        GetForegroundWindow() as usize
    }
    #[cfg(not(target_os = "windows"))]
    0
}

/// Continuation observation for a previously spawned launch. NEVER spawns
/// anything: it only re-checks the recorded postcondition within the TTL.
/// Returns None when the request_id has no broker spawn record (the caller
/// then keeps the honest pending state instead of inventing a result).
pub fn observe_broker_action(request_id: &str) -> Option<Value> {
    if !valid_request_id(request_id) {
        return None;
    }
    let record = {
        let mut guard = registry();
        let map = guard.get_or_insert_with(HashMap::new);
        let record = map.get(request_id)?;
        if record.expires_at <= Instant::now() {
            let expired = record.clone();
            map.remove(request_id);
            return Some(envelope(
                "failed",
                true,
                false,
                "failed",
                &expired.action,
                "continuation window expired before readiness was observed",
                json!({
                    "mode": "cu_broker_observe",
                    "backend": "rust-host",
                    "action_id": expired.action_id,
                    "url": expired.browser_url,
                    "cdp_port": expired.browser_cdp_port,
                    "approval_id": expired.approval_id,
                    "approval_call_id": expired.approval_call_id,
                    "input_digest": hex_digest(&expired.input_digest),
                }),
                request_id,
                &expired.action_id,
            ));
        }
        record.clone()
    };
    let (verified_pid, leaked_to_user, observation_unavailable, observation_debug) =
        match record.desktop.as_deref() {
            Some(name) => hidden_process_observation(
                record.pid,
                record.process_names,
                name,
                record.allow_reparented_process,
                &record.baseline_hidden_pids,
                &record.baseline_user_pids,
            ),
            None => (
                (record.shell_reused
                    || postcondition_reached(
                        record.pid,
                        record.process_names,
                        &HashSet::new(),
                        Duration::from_millis(1500),
                    ))
                .then_some(record.pid),
                false,
                false,
                json!({}),
            ),
        };
    if observation_unavailable {
        return Some(envelope(
            "failed",
            true,
            false,
            "failed",
            &record.action,
            "desktop observation was unavailable; refusing to verify the spawn",
            json!({
                "mode": "cu_broker_observe",
                "backend": "rust-host",
                "pid": record.pid,
                "desktop": record.desktop,
                "url": record.browser_url,
                "cdp_port": record.browser_cdp_port,
                "action_id": record.action_id,
                "approval_id": record.approval_id,
                "approval_call_id": record.approval_call_id,
                "input_digest": hex_digest(&record.input_digest),
                "observation": observation_debug,
            }),
            request_id,
            &record.action_id,
        ));
    }
    if leaked_to_user {
        return Some(envelope(
            "failed",
            true,
            false,
            "failed",
            &record.action,
            "spawned process appeared on the interactive desktop",
            json!({
                "mode": "cu_broker_observe",
                "backend": "rust-host",
                "pid": record.pid,
                "spawn_pid": record.pid,
                "desktop": record.desktop,
                "url": record.browser_url,
                "cdp_port": record.browser_cdp_port,
                "action_id": record.action_id,
                "approval_id": record.approval_id,
                "approval_call_id": record.approval_call_id,
                "input_digest": hex_digest(&record.input_digest),
                "observation": observation_debug,
            }),
            request_id,
            &record.action_id,
        ));
    }
    if let Some(observed_pid) = verified_pid {
        return Some(envelope(
            "completed",
            true,
            true,
            "verified",
            &record.action,
            "",
            json!({
                "mode": "cu_broker_observe",
                "backend": "rust-host",
                "pid": observed_pid,
                "spawn_pid": record.pid,
                "desktop": record.desktop,
                "url": record.browser_url,
                "cdp_port": record.browser_cdp_port,
                "action_id": record.action_id,
                "approval_id": record.approval_id,
                "approval_call_id": record.approval_call_id,
                "input_digest": hex_digest(&record.input_digest),
                "observation": observation_debug,
            }),
            request_id,
            &record.action_id,
        ));
    }
    Some(envelope(
        "launch_pending",
        false,
        false,
        "pending",
        &record.action,
        "readiness postcondition has not been observed yet",
        json!({
            "mode": "cu_broker_observe",
            "backend": "rust-host",
            "pid": record.pid,
            "desktop": record.desktop,
            "url": record.browser_url,
            "cdp_port": record.browser_cdp_port,
            "action_id": record.action_id,
            "input_digest": hex_digest(&record.input_digest),
            "observation": observation_debug,
        }),
        request_id,
        &record.action_id,
    ))
}

pub fn valid_request_id(value: &str) -> bool {
    value.len() == 24 && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}

pub(crate) fn valid_action_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 128
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || b"_-.:".contains(&byte))
}

pub(crate) fn hex_digest(digest: &[u8; 32]) -> String {
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration as StdDuration;

    /// Fixed fake of the App Paths registry: chrome/msedge/firefox resolve to
    /// existing files (System32 notepad.exe is used as a stand-in path), any
    /// other subkey is absent. Makes browser-resolution tests independent of
    /// the host's installed browsers and of reg.exe availability.
    fn fake_registry_lookup(subkey: &str) -> Option<String> {
        const BROWSER_EXES: [&str; 3] = ["chrome.exe", "msedge.exe", "firefox.exe"];
        if BROWSER_EXES
            .iter()
            .any(|exe| subkey.ends_with(&format!("\\{exe}")))
        {
            return Some(format!("{}\\System32\\notepad.exe", system_root()));
        }
        None
    }

    const REQUEST_ID: &str = "0123456789abcdef01234567";
    const ACTION_ID: &str = "call_0123456789abcdef0123456789ab";
    const EXPIRED_REQUEST_ID: &str = "111111111111111111111111";
    const PENDING_REQUEST_ID: &str = "222222222222222222222222";
    const BINDING_REQUEST_ID: &str = "333333333333333333333333";

    // Serialise tests that touch the global SPAWN_REGISTRY. Without this,
    // parallel cargo test interleaves register_spawn retain() (which prunes
    // expired entries) with concurrent observe_broker_action, causing
    // observe_expired_record_returns_honest_failed to flap.
    static REGISTRY_TEST_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    fn clear_registry_for_test() {
        let mut guard = super::SPAWN_REGISTRY
            .lock()
            .expect("cu_broker spawn registry poisoned for test");
        *guard = Some(HashMap::new());
    }

    fn grant_for(input: &Value) -> crate::approval::ExecutionGrant {
        crate::approval::ExecutionGrant {
            grant_id: "g_test".into(),
            tool: "computer_use".into(),
            input_digest: crate::approval::canonical_input_digest(input),
            workspace: "ws".into(),
            session: "session".into(),
            nonce: [0u8; 16],
            valid_until: Instant::now() + StdDuration::from_secs(60),
            approval_id: "appr_test".into(),
            call_id: "call_test".into(),
        }
    }

    #[test]
    fn broker_action_scope_is_exact() {
        assert_eq!(
            broker_action(&json!({"action": "open_app", "target": "notepad"})),
            Some("open_app")
        );
        assert_eq!(
            broker_action(&json!({"action": "open_folder", "target": "downloads"})),
            Some("open_folder")
        );
        assert_eq!(
            broker_action(&json!({
                "action": "open_url",
                "target": "msedge",
                "url": "https://www.youtube.com/"
            })),
            Some("open_url")
        );
        assert_eq!(
            broker_action(&json!({
                "action": "close_owned",
                "target": "notepad",
                "ownership_request_id": REQUEST_ID
            })),
            Some("close_owned")
        );
        assert_eq!(broker_action(&json!({"action": "wait"})), None);
        assert_eq!(broker_action(&json!({"action": "screenshot"})), None);
        assert_eq!(broker_action(&json!({})), None);
    }

    #[test]
    fn close_owned_without_ownership_record_is_blocked() {
        let input = json!({
            "action": "close_owned",
            "target": "notepad",
            "ownership_request_id": REQUEST_ID,
        });
        let result = execute_broker_action(
            "close_owned",
            &input,
            Some(&grant_for(&input)),
            Some(BINDING_REQUEST_ID),
            Some(ACTION_ID),
            None,
            None,
        );
        assert_eq!(result["status"], "blocked");
        assert_eq!(result["terminal"], json!(true));
        assert_eq!(result["succeeded"], json!(false));
        assert!(result["reason"]
            .as_str()
            .unwrap_or_default()
            .contains("ownership"));
    }

    #[test]
    fn browser_url_accepts_http_or_https_without_credentials_or_port() {
        assert_eq!(
            validate_browser_url("https://www.youtube.com/watch?v=abc").unwrap(),
            "https://www.youtube.com/watch?v=abc"
        );
        assert_eq!(
            validate_browser_url("http://example.com/path?q=1").unwrap(),
            "http://example.com/path?q=1"
        );
        for invalid in [
            "javascript:alert(1)",
            "file:///C:/Windows/System32/notepad.exe",
            "https://example.com:443/",
            "https://user:pass@example.com/",
            "https://example.com/with whitespace",
            "https://example.com/\u{0000}",
        ] {
            assert!(
                validate_browser_url(invalid).is_err(),
                "must reject {invalid:?}"
            );
        }
    }

    #[test]
    fn close_owned_preflight_is_allowlisted_and_id_bound() {
        let valid = json!({
            "action": "close_owned",
            "target": "notepad",
            "ownership_request_id": REQUEST_ID,
        });
        assert!(validate_broker_action("close_owned", &valid, None).is_ok());
        let invalid_id = json!({
            "action": "close_owned",
            "target": "notepad",
            "ownership_request_id": "not-a-request",
        });
        assert!(validate_broker_action("close_owned", &invalid_id, None).is_err());
        let path = json!({
            "action": "close_owned",
            "target": "C:\\Windows\\System32\\notepad.exe",
            "ownership_request_id": REQUEST_ID,
        });
        assert!(validate_broker_action("close_owned", &path, None).is_err());
    }

    #[test]
    fn broker_preflight_blocks_unknown_target_without_spawning() {
        let unknown = json!({"action": "open_app", "target": "cmd.exe"});
        assert!(validate_broker_action("open_app", &unknown, None)
            .expect_err("unknown app must be blocked")
            .contains("allowlist"));
        let path = json!({"action": "open_app", "target": "C:\\Windows\\System32\\notepad.exe"});
        assert!(validate_broker_action("open_app", &path, None)
            .expect_err("path target must be blocked")
            .contains("path"));
        assert!(plan_launch_with(
            "open_app",
            &json!("notepad"),
            &Value::Null,
            None,
            None,
            &fake_registry_lookup,
        )
        .is_ok());
        assert!(plan_launch_with(
            "open_url",
            &json!("browser"),
            &json!("https://www.youtube.com/"),
            None,
            None,
            &fake_registry_lookup,
        )
        .is_ok());
        assert!(plan_launch_with(
            "open_url",
            &json!("browser"),
            &json!("https://example.com/"),
            None,
            None,
            &fake_registry_lookup,
        )
        .is_ok());
    }

    #[test]
    fn broker_action_normalizes_action_case() {
        assert_eq!(
            broker_action(&json!({"action": "OPEN_APP"})),
            Some("open_app")
        );
        assert_eq!(
            broker_action(&json!({"action": " Open_Folder "})),
            Some("open_folder")
        );
    }

    #[test]
    fn unknown_target_is_blocked_not_spawned() {
        let input = json!({"action": "open_app", "target": "cmd.exe"});
        let result = execute_broker_action(
            "open_app",
            &input,
            Some(&grant_for(&input)),
            Some(REQUEST_ID),
            Some(ACTION_ID),
            None,
            None,
        );
        assert_eq!(result["status"], "blocked");
        assert_eq!(result["terminal"], json!(true));
        assert_eq!(result["succeeded"], json!(false));
    }

    #[test]
    fn path_like_target_is_blocked() {
        let input = json!({"action": "open_app", "target": "C:\\Windows\\System32\\cmd.exe"});
        let result = execute_broker_action(
            "open_app",
            &input,
            Some(&grant_for(&input)),
            Some(REQUEST_ID),
            Some(ACTION_ID),
            None,
            None,
        );
        assert_eq!(result["status"], "blocked");
    }

    #[test]
    fn digest_mismatch_is_blocked() {
        let input = json!({"action": "open_app", "target": "notepad"});
        let other = json!({"action": "open_app", "target": "mspaint"});
        let result = execute_broker_action(
            "open_app",
            &input,
            Some(&grant_for(&other)),
            Some(REQUEST_ID),
            Some(ACTION_ID),
            None,
            None,
        );
        assert_eq!(result["status"], "blocked");
        assert!(result["reason"]
            .as_str()
            .unwrap_or_default()
            .contains("digest"));
    }

    #[test]
    fn input_correlation_fields_are_ignored_without_transport_metadata() {
        let input = json!({
            "action": "open_app",
            "target": "notepad",
            "request_id": REQUEST_ID,
            "action_id": ACTION_ID,
        });
        let result = execute_broker_action(
            "open_app",
            &input,
            Some(&grant_for(&input)),
            None,
            None,
            None,
            None,
        );
        assert_eq!(result["status"], "blocked");
        assert!(result["reason"]
            .as_str()
            .unwrap_or_default()
            .contains("out-of-band"));
        assert!(result.get("request_id").is_none());
        assert!(result.get("action_id").is_none());
    }

    #[test]
    fn missing_grant_is_blocked() {
        let input = json!({"action": "open_app", "target": "notepad"});
        let result = execute_broker_action(
            "open_app",
            &input,
            None,
            Some(REQUEST_ID),
            Some(ACTION_ID),
            None,
            None,
        );
        assert_eq!(result["status"], "blocked");
    }

    #[test]
    fn calculator_alias_resolves_without_spawn() {
        // Alias normalization is a pure registry contract. Do not call the
        // broker execution path here: that would launch Calculator during a
        // normal cargo test run.
        assert_eq!(
            normalize_target(&json!("calculator")),
            Some("calc".to_owned())
        );
    }

    #[test]
    fn hidden_calculator_is_blocked_before_spawn() {
        let error = match plan_launch(
            "open_app",
            &json!("calculator"),
            &Value::Null,
            None,
            Some("LocalCometHidden_test"),
        ) {
            Ok(_) => panic!("Calculator must be disabled in hidden/automatic mode"),
            Err(error) => error,
        };
        assert!(error.contains("disabled in hidden/automatic mode"));
    }

    #[test]
    fn every_sidecar_open_app_alias_resolves_to_a_registry_entry() {
        // The Python deterministic fallback in local_model_gateway_ru.py
        // (_COMPUTER_USE_SAFE_APP_ALIASES) emits these exact target strings for
        // open_app. Each one must survive normalize_target AND land on a real
        // APP_REGISTRY key, otherwise the broker rejects a launch the sidecar
        // considers valid. "paint" regressed exactly this way: Python emitted
        // "paint" while the registry key was "mspaint" and no alias bridged
        // them, so "открой пейнт" failed as not-allowlisted. Keep this table in
        // sync with the Python tuple; a bare mapping is not enough, the
        // canonical result must exist in the registry.
        const SIDECAR_OPEN_APP_TARGETS: &[&str] = &[
            "calculator",
            "notepad",
            "paint",
            "explorer",
            "firefox",
            "msedge",
            "chrome",
            "steam",
        ];
        for target in SIDECAR_OPEN_APP_TARGETS {
            let canonical = normalize_target(&json!(target)).unwrap_or_else(|| {
                panic!("sidecar alias {target:?} was rejected by normalize_target")
            });
            assert!(
                app_entry(&canonical).is_some(),
                "sidecar alias {target:?} normalized to {canonical:?}, which is not an APP_REGISTRY key"
            );
        }
    }

    #[test]
    fn normalize_target_never_yields_an_unregistered_canonical() {
        // Structural invariant: normalize_target must never return a canonical
        // name that app_entry cannot resolve. Several call sites .expect() on
        // that entry, so a violation is a panic, not a graceful rejection.
        for probe in [
            "calc",
            "calculator",
            "калькулятор",
            "notepad",
            "блокнот",
            "mspaint",
            "paint",
            "пейнт",
            "рисование",
            "explorer",
            "проводник",
            "файлы",
            "chrome",
            "хром",
            "msedge",
            "edge",
            "firefox",
            "мозилла",
            "vscode",
            "code",
            "steam",
            "стим",
            "browser",
            "браузер",
            "totally-unknown-app",
        ] {
            if let Some(canonical) = normalize_target(&json!(probe)) {
                assert!(
                    app_entry(&canonical).is_some(),
                    "normalize_target({probe:?}) returned unregistered canonical {canonical:?}"
                );
            }
        }
    }

    #[test]
    fn exe_suffix_maps_to_registry_entry() {
        // Pure mapping check (no spawn): the model-facing "calc.exe" form
        // must resolve onto the same allowlisted entry as bare "calc".
        assert_eq!(
            normalize_target(&json!("calc.exe")),
            Some("calc".to_owned())
        );
        assert_eq!(
            normalize_target(&json!("notepad.exe")),
            Some("notepad".to_owned())
        );
    }

    #[test]
    fn invalid_hidden_desktop_name_is_blocked_without_spawn() {
        let input = json!({"action": "open_app", "target": "notepad"});
        let result = execute_broker_action(
            "open_app",
            &input,
            Some(&grant_for(&input)),
            Some(REQUEST_ID),
            Some(ACTION_ID),
            None,
            Some("bad desktop!"),
        );
        assert_eq!(result["status"], "blocked");
        assert!(result["reason"]
            .as_str()
            .unwrap_or_default()
            .contains("binding rejected"));
    }

    #[test]
    fn unavailable_hidden_desktop_fails_closed() {
        // A syntactically valid but nonexistent desktop cannot host the
        // process: CreateProcessW must fail → FAILED envelope, never PASS,
        // never a user-desktop leak.
        let input = json!({"action": "open_app", "target": "notepad"});
        let result = execute_broker_action(
            "open_app",
            &input,
            Some(&grant_for(&input)),
            Some(REQUEST_ID),
            Some(ACTION_ID),
            None,
            Some("LocalCometMissingDesktopXYZ"),
        );
        // Pre-spawn probe: an unopenable desktop is refused BEFORE any
        // process exists — BLOCKED is stronger than FAILED here.
        assert_eq!(result["status"], "blocked");
        assert!(result["reason"]
            .as_str()
            .unwrap_or_default()
            .contains("unavailable"));
    }

    #[test]
    fn unknown_folder_is_blocked() {
        let input = json!({"action": "open_folder", "target": "C:\\Windows"});
        let result = execute_broker_action(
            "open_folder",
            &input,
            Some(&grant_for(&input)),
            Some(REQUEST_ID),
            Some(ACTION_ID),
            None,
            None,
        );
        assert_eq!(result["status"], "blocked");
    }

    #[test]
    fn invalid_request_id_is_rejected_before_observation() {
        assert!(!valid_request_id("no-such-request"));
        assert!(observe_broker_action("no-such-request").is_none());
    }

    #[test]
    fn observe_unknown_request_is_none() {
        assert!(observe_broker_action("no-such-request").is_none());
    }

    #[test]
    fn same_image_pid_reuse_is_rejected_without_exact_creation_identity() {
        assert!(!process_identity_matches(Some(100), Some(101)));
        assert!(!process_identity_matches(Some(100), None));
        assert!(!process_identity_matches(None, Some(100)));
        assert!(process_identity_matches(Some(100), Some(100)));
    }

    #[test]
    fn process_descends_from_accepts_the_same_process() {
        let pid = std::process::id();
        assert!(process_descends_from(pid, pid));
    }

    #[test]
    fn observe_expired_record_returns_honest_failed() {
        let _lock = REGISTRY_TEST_LOCK
            .lock()
            .expect("registry test lock poisoned");
        clear_registry_for_test();
        register_spawn(
            EXPIRED_REQUEST_ID,
            SpawnRecord {
                pid: 0,
                action: "open_app".into(),
                browser_url: None,
                browser_cdp_port: None,
                process_names: &["notepad.exe"],
                allow_reparented_process: false,
                baseline_hidden_pids: HashSet::new(),
                baseline_user_pids: HashSet::new(),
                shell_reused: false,
                expires_at: Instant::now() - Duration::from_secs(1),
                desktop: None,
                action_id: String::new(),
                approval_id: String::new(),
                approval_call_id: String::new(),
                input_digest: [0u8; 32],
                creation_time_100ns: None,
            },
        );
        let result =
            observe_broker_action(EXPIRED_REQUEST_ID).expect("record must exist until pruned");
        assert_eq!(result["status"], "failed");
        assert_eq!(result["terminal"], json!(true));
    }

    #[test]
    fn observe_unready_record_stays_pending_without_respawn() {
        let _lock = REGISTRY_TEST_LOCK
            .lock()
            .expect("registry test lock poisoned");
        clear_registry_for_test();
        // pid 0 never matches a real process and the name cannot appear, so
        // the observation must stay pending — proving no respawn happened.
        register_spawn(
            PENDING_REQUEST_ID,
            SpawnRecord {
                pid: 0,
                action: "open_app".into(),
                browser_url: None,
                browser_cdp_port: None,
                process_names: &["definitely-not-running-proc-xyz"],
                allow_reparented_process: false,
                baseline_hidden_pids: HashSet::new(),
                baseline_user_pids: HashSet::new(),
                shell_reused: false,
                expires_at: Instant::now() + Duration::from_secs(600),
                desktop: None,
                action_id: String::new(),
                approval_id: String::new(),
                approval_call_id: String::new(),
                input_digest: [0u8; 32],
                creation_time_100ns: None,
            },
        );
        let result = observe_broker_action(PENDING_REQUEST_ID).expect("record must exist");
        assert_eq!(result["status"], "launch_pending");
        assert_eq!(result["terminal"], json!(false));
        assert_eq!(result["succeeded"], json!(false));
    }

    #[test]
    fn open_app_rejects_url_field_strict_separation() {
        let with_url =
            json!({"action": "open_app", "target": "notepad", "url": "https://example.com"});
        assert!(validate_broker_action("open_app", &with_url, None)
            .expect_err("open_app with URL must be blocked")
            .contains("open_app must not include a URL"));
        assert!(plan_launch_with(
            "open_app",
            &json!("notepad"),
            &Value::Null,
            None,
            None,
            &fake_registry_lookup,
        )
        .is_ok());
        assert!(plan_launch_with(
            "open_url",
            &json!("chrome"),
            &json!("https://example.com"),
            None,
            None,
            &fake_registry_lookup,
        )
        .is_ok());
        let url_missing = json!({"action": "open_url", "target": "chrome"});
        assert!(validate_broker_action("open_url", &url_missing, None)
            .expect_err("open_url missing URL must be blocked")
            .contains("URL"));
    }

    #[test]
    fn observe_envelope_echoes_persisted_binding() {
        let _lock = REGISTRY_TEST_LOCK
            .lock()
            .expect("registry test lock poisoned");
        clear_registry_for_test();
        // Plan P0.2: the continuation record carries request_id, action_id,
        // PID, target input digest and desktop binding; every observation
        // echoes them so UI/acceptance can verify the binding end-to-end.
        let digest = crate::approval::canonical_input_digest(&json!({"target": "notepad"}));
        register_spawn(
            BINDING_REQUEST_ID,
            SpawnRecord {
                pid: 4242,
                action: "open_app".into(),
                browser_url: None,
                browser_cdp_port: None,
                process_names: &["notepad.exe"],
                allow_reparented_process: false,
                baseline_hidden_pids: HashSet::new(),
                baseline_user_pids: HashSet::new(),
                shell_reused: false,
                expires_at: Instant::now() + Duration::from_secs(600),
                desktop: Some("LocalCometHiddenCU_test".to_owned()),
                action_id: "action-1".to_owned(),
                approval_id: "appr_test".to_owned(),
                approval_call_id: "call_test".to_owned(),
                input_digest: digest,
                creation_time_100ns: None,
            },
        );
        let result = observe_broker_action(BINDING_REQUEST_ID).expect("record must exist");
        assert_eq!(result["status"], "failed");
        assert_eq!(result["terminal"], json!(true));
        assert_eq!(result["succeeded"], json!(false));
        assert_eq!(result["request_id"], json!(BINDING_REQUEST_ID));
        assert_eq!(result["action_id"], json!("action-1"));
        assert_eq!(result["execution"]["pid"], json!(4242));
        assert_eq!(
            result["execution"]["input_digest"],
            json!(hex_digest(&digest))
        );
        assert_eq!(
            result["execution"]["desktop"],
            json!("LocalCometHiddenCU_test")
        );
    }
}
