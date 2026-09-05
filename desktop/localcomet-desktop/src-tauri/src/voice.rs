use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};

#[cfg(target_os = "windows")]
use std::ffi::OsStr;
#[cfg(target_os = "windows")]
use std::os::windows::ffi::OsStrExt;
#[cfg(target_os = "windows")]
use windows_sys::Win32::Media::Audio::{PlaySoundW, SND_FILENAME, SND_PURGE, SND_SYNC};

const MAX_TTS_CHARS: usize = 8_192;
const PIPER_LENGTH_SCALE: &str = "0.96";
static TTS_LOCK: OnceLock<Mutex<()>> = OnceLock::new();
static TTS_CANCEL_GENERATION: AtomicU64 = AtomicU64::new(0);
#[cfg(target_os = "windows")]
static ACTIVE_TTS_CHILD: OnceLock<Mutex<Option<Child>>> = OnceLock::new();

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum TtsVoiceProfile {
    Female,
    Male,
    Dmitri,
    Denis,
}

impl TtsVoiceProfile {
    fn parse(value: Option<&str>) -> Result<Self, String> {
        match value.unwrap_or("female") {
            "female" => Ok(Self::Female),
            "male" => Ok(Self::Male),
            "dmitri" => Ok(Self::Dmitri),
            "denis" => Ok(Self::Denis),
            _ => Err("Неподдерживаемый профиль локального TTS-голоса".to_string()),
        }
    }

    fn model_filename(self) -> &'static str {
        match self {
            Self::Female => "ru_RU-irina-medium.onnx",
            Self::Male => "ru_RU-ruslan-medium.onnx",
            Self::Dmitri => "ru_RU-dmitri-medium.onnx",
            Self::Denis => "ru_RU-denis-medium.onnx",
        }
    }

    fn display_name(self) -> &'static str {
        match self {
            Self::Female => "женский",
            Self::Male => "мужской",
            Self::Dmitri => "мужской Дмитрий",
            Self::Denis => "мужской Денис",
        }
    }
}

fn resolve_voice_files(
    root: &Path,
    profile: TtsVoiceProfile,
) -> Result<(PathBuf, PathBuf), String> {
    let piper = root.join("piper.exe");
    let model = root.join(profile.model_filename());
    let config = root.join(format!("{}.json", profile.model_filename()));
    if !piper.is_file() {
        return Err("Локальный Piper не найден".to_string());
    }
    if !model.is_file() || !config.is_file() {
        return Err(format!(
            "Локальный {} TTS-голос не найден вместе с конфигурацией",
            profile.display_name()
        ));
    }
    Ok((piper, model))
}

fn tts_lock() -> &'static Mutex<()> {
    TTS_LOCK.get_or_init(|| Mutex::new(()))
}

#[cfg(target_os = "windows")]
fn active_tts_child() -> &'static Mutex<Option<Child>> {
    ACTIVE_TTS_CHILD.get_or_init(|| Mutex::new(None))
}

#[cfg(target_os = "windows")]
fn cancel_active_tts() {
    if let Ok(mut active) = active_tts_child().lock() {
        if let Some(child) = active.as_mut() {
            let _ = child.kill();
        }
    }
}

#[cfg(target_os = "windows")]
fn wait_for_tts_child(generation: u64) -> Result<std::process::ExitStatus, String> {
    loop {
        if TTS_CANCEL_GENERATION.load(Ordering::SeqCst) != generation {
            cancel_active_tts();
        }
        let status = {
            let mut active = active_tts_child()
                .lock()
                .map_err(|_| "Локальный TTS lock повреждён".to_string())?;
            let child = active
                .as_mut()
                .ok_or_else(|| "Активный локальный TTS process отсутствует".to_string())?;
            child
                .try_wait()
                .map_err(|error| format!("Локальный TTS процесс не завершился: {error}"))?
        };
        if let Some(status) = status {
            if let Ok(mut active) = active_tts_child().lock() {
                active.take();
            }
            return Ok(status);
        }
        std::thread::sleep(std::time::Duration::from_millis(20));
    }
}

fn piper_root() -> PathBuf {
    std::env::var_os("LOCALCOMET_PIPER_DIR")
        .map(PathBuf::from)
        .or_else(|| {
            std::env::var_os("USERPROFILE")
                .map(PathBuf::from)
                .map(|home| home.join("Documents").join("piper"))
        })
        .unwrap_or_else(|| PathBuf::from("piper"))
}

#[cfg(target_os = "windows")]
const RHVOICE_FEMALE_VOICE_NAME: &str = "Elena";
#[cfg(target_os = "windows")]
const RHVOICE_MALE_VOICE_NAME: &str = "Aleksandr";

#[cfg(target_os = "windows")]
const SAPI_SCRIPT: &str = r#"
$ErrorActionPreference = 'Stop'
try {
    $voice = New-Object -ComObject SAPI.SpVoice
    $target = $env:LOCALCOMET_TTS_VOICE
    $match = $voice.GetVoices() | Where-Object { $_.GetDescription() -eq $target } | Select-Object -First 1
    if ($null -eq $match) { exit 3 }
    $voice.Voice = $match
    $voice.Rate = 0
    $voice.Volume = 100
    [Console]::InputEncoding = [System.Text.Encoding]::UTF8
    $text = [Console]::In.ReadToEnd()
    if (-not [string]::IsNullOrWhiteSpace($text)) { [void]$voice.Speak($text) }
    exit 0
} catch {
    exit 3
}
"#;

#[cfg(target_os = "windows")]
fn powershell_path() -> Option<PathBuf> {
    let root = std::env::var_os("WINDIR").map(PathBuf::from)?;
    let path = root
        .join("System32")
        .join("WindowsPowerShell")
        .join("v1.0")
        .join("powershell.exe");
    path.is_file().then_some(path)
}

#[cfg(target_os = "windows")]
fn speak_with_sapi(
    text: String,
    generation: u64,
    voice_name: &'static str,
) -> Result<bool, String> {
    if TTS_CANCEL_GENERATION.load(Ordering::SeqCst) != generation {
        return Ok(true);
    }
    let Some(powershell) = powershell_path() else {
        return Ok(false);
    };
    let child = Command::new(powershell)
        .args([
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-WindowStyle",
            "Hidden",
            "-Command",
            SAPI_SCRIPT,
        ])
        .env("LOCALCOMET_TTS_VOICE", voice_name)
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("Не удалось запустить Windows SAPI: {error}"))?;
    {
        let mut active = active_tts_child()
            .lock()
            .map_err(|_| "Локальный TTS lock повреждён".to_string())?;
        *active = Some(child);
    }
    if let Ok(mut active) = active_tts_child().lock() {
        if let Some(child) = active.as_mut() {
            if let Some(mut stdin) = child.stdin.take() {
                use std::io::Write;
                if let Err(error) = stdin.write_all(text.as_bytes()) {
                    let _ = child.kill();
                    active.take();
                    return Err(format!("Не удалось передать текст в Windows SAPI: {error}"));
                }
            }
        }
    }
    let status = wait_for_tts_child(generation)?;
    if TTS_CANCEL_GENERATION.load(Ordering::SeqCst) != generation {
        return Ok(true);
    }
    if status.code() == Some(3) {
        return Ok(false);
    }
    if !status.success() {
        return Err("Windows SAPI не смогла озвучить текст".to_string());
    }
    Ok(true)
}

fn normalized_text(text: String) -> Option<String> {
    let mut spoken = String::new();
    let mut in_code_block = false;

    for raw_line in text.lines() {
        let trimmed = raw_line.trim();
        if trimmed.starts_with("```") {
            in_code_block = !in_code_block;
            continue;
        }
        if in_code_block || trimmed.is_empty() {
            continue;
        }

        let mut line = trimmed.to_string();
        for prefix in ["### ", "## ", "# ", "- ", "* "] {
            if let Some(stripped) = line.strip_prefix(prefix) {
                line = stripped.trim().to_string();
                break;
            }
        }
        for token in ["**", "__", "~~", "`"] {
            line = line.replace(token, "");
        }
        line = line
            .split_whitespace()
            .filter(|word| !word.starts_with("http://") && !word.starts_with("https://"))
            .collect::<Vec<_>>()
            .join(" ");
        if line.is_empty() {
            continue;
        }
        if !spoken.is_empty() {
            spoken.push_str(". ");
        }
        spoken.push_str(&line);
    }

    let compact = spoken.split_whitespace().collect::<Vec<_>>().join(" ");
    if compact.is_empty() {
        return None;
    }
    Some(compact.chars().take(MAX_TTS_CHARS).collect())
}

#[cfg(target_os = "windows")]
fn speak_with_piper(
    text: String,
    generation: u64,
    voice_profile: TtsVoiceProfile,
) -> Result<(), String> {
    if TTS_CANCEL_GENERATION.load(Ordering::SeqCst) != generation {
        return Ok(());
    }

    let root = piper_root();
    let (piper, voice) = resolve_voice_files(&root, voice_profile)?;

    let output = std::env::temp_dir().join(format!(
        "localcomet-tts-{}-{}.wav",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|_| "Не удалось подготовить временный audio-файл".to_string())?
            .as_nanos()
    ));

    let child = Command::new(&piper)
        .arg("--model")
        .arg(&voice)
        .arg("--length_scale")
        .arg(PIPER_LENGTH_SCALE)
        .arg("--output_file")
        .arg(&output)
        // piper resolves espeak-ng-data (and its other DLL/model resources)
        // relative to the CURRENT process directory. Inherited launch dirs
        // make it abort before writing audio, and the SAPI fallback then
        // announces every profile with the same RHVoice. Anchoring the child
        // to the piper root keeps the neural voice selection real.
        .current_dir(&root)
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("Не удалось запустить Piper: {error}"))?;

    {
        let mut active = active_tts_child()
            .lock()
            .map_err(|_| "Локальный TTS lock повреждён".to_string())?;
        *active = Some(child);
    }

    if let Ok(mut active) = active_tts_child().lock() {
        if let Some(child) = active.as_mut() {
            if let Some(mut stdin) = child.stdin.take() {
                use std::io::Write;
                if let Err(error) = stdin.write_all(text.as_bytes()) {
                    let _ = child.kill();
                    active.take();
                    return Err(format!("Не удалось передать текст в Piper: {error}"));
                }
            }
        }
    }

    let status = wait_for_tts_child(generation)?;
    if TTS_CANCEL_GENERATION.load(Ordering::SeqCst) != generation {
        let _ = std::fs::remove_file(&output);
        return Ok(());
    }
    if !status.success() || !output.is_file() {
        let _ = std::fs::remove_file(&output);
        return Err("Piper не создал audio-файл".to_string());
    }

    let wide_path: Vec<u16> = OsStr::new(&output)
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let played = unsafe {
        PlaySoundW(
            wide_path.as_ptr(),
            std::ptr::null_mut(),
            SND_FILENAME | SND_SYNC,
        )
    };
    let cancelled = TTS_CANCEL_GENERATION.load(Ordering::SeqCst) != generation;
    let _ = std::fs::remove_file(&output);
    if cancelled {
        return Ok(());
    }
    if played == 0 {
        return Err("Windows не смогла воспроизвести Piper audio-файл".to_string());
    }
    Ok(())
}

#[cfg(target_os = "windows")]
fn rhvoice_voice_name(profile: TtsVoiceProfile) -> &'static str {
    match profile {
        TtsVoiceProfile::Female => RHVOICE_FEMALE_VOICE_NAME,
        TtsVoiceProfile::Male | TtsVoiceProfile::Dmitri | TtsVoiceProfile::Denis => {
            RHVOICE_MALE_VOICE_NAME
        }
    }
}

#[cfg(target_os = "windows")]
fn speak_with_selected_voice(
    text: String,
    generation: u64,
    voice_profile: TtsVoiceProfile,
    language: &str,
) -> Result<(), String> {
    if language != "ru-RU" {
        return Err("Локальная озвучка сейчас поддерживает только русский язык".to_string());
    }
    // Piper neural voices sound clearly better than the SAPI/RHVoice formant
    // voices, so the local Piper bundle is the primary engine and SAPI/RHVoice
    // is only the fallback when the bundle is missing or fails.
    if let Err(piper_error) = speak_with_piper(text.clone(), generation, voice_profile) {
        let rhvoice_name = rhvoice_voice_name(voice_profile);
        if !speak_with_sapi(text, generation, rhvoice_name)? {
            return Err(piper_error);
        }
    }
    Ok(())
}

#[cfg(not(target_os = "windows"))]
fn speak_with_selected_voice(
    text: String,
    generation: u64,
    voice_profile: TtsVoiceProfile,
    _language: &str,
) -> Result<(), String> {
    speak_with_piper(text, generation, voice_profile)
}

#[tauri::command]
pub async fn speak_local_text(
    text: String,
    language: Option<String>,
    voice_profile: Option<String>,
) -> Result<(), String> {
    let language = language.unwrap_or_else(|| "ru-RU".to_string());
    if language != "ru-RU" {
        return Err("Неподдерживаемый язык локального TTS-голоса".to_string());
    }
    let voice_profile = TtsVoiceProfile::parse(voice_profile.as_deref())?;
    let Some(text) = normalized_text(text) else {
        return Ok(());
    };
    let generation = TTS_CANCEL_GENERATION.load(Ordering::SeqCst);
    tauri::async_runtime::spawn_blocking(move || {
        let _guard = tts_lock()
            .lock()
            .map_err(|_| "Локальный TTS lock повреждён".to_string())?;
        if TTS_CANCEL_GENERATION.load(Ordering::SeqCst) != generation {
            return Ok(());
        }
        speak_with_selected_voice(text, generation, voice_profile, &language)
    })
    .await
    .map_err(|error| format!("Локальный TTS worker завершился с ошибкой: {error}"))?
}

#[tauri::command]
pub fn stop_local_text() -> Result<(), String> {
    TTS_CANCEL_GENERATION.fetch_add(1, Ordering::SeqCst);
    #[cfg(target_os = "windows")]
    cancel_active_tts();
    #[cfg(target_os = "windows")]
    unsafe {
        // Interrupt a synchronous PlaySound call if one is active. The
        // generation check above also prevents a queued Piper result from
        // starting after the user has disabled voice output.
        PlaySoundW(std::ptr::null(), std::ptr::null_mut(), SND_PURGE);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{normalized_text, resolve_voice_files, TtsVoiceProfile};
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn normalized_text_removes_markdown_and_urls() {
        let text = normalized_text(
            "# Заголовок\n\n- **Готово**\nСсылка: https://example.test/page".to_string(),
        );
        assert_eq!(text.as_deref(), Some("Заголовок. Готово. Ссылка:"));
    }

    #[test]
    fn normalized_text_skips_code_blocks() {
        let text = normalized_text("Ответ\n```rust\nfn main() {}\n```\nПродолжение".to_string());
        assert_eq!(text.as_deref(), Some("Ответ. Продолжение"));
    }

    #[test]
    fn voice_profile_defaults_to_female_and_rejects_unknown_values() {
        assert_eq!(TtsVoiceProfile::parse(None), Ok(TtsVoiceProfile::Female));
        assert_eq!(
            TtsVoiceProfile::parse(Some("male")),
            Ok(TtsVoiceProfile::Male)
        );
        assert_eq!(
            TtsVoiceProfile::parse(Some("dmitri")),
            Ok(TtsVoiceProfile::Dmitri)
        );
        assert_eq!(
            TtsVoiceProfile::parse(Some("denis")),
            Ok(TtsVoiceProfile::Denis)
        );
        assert!(TtsVoiceProfile::parse(Some("irina")).is_err());
    }

    #[cfg(target_os = "windows")]
    #[test]
    fn rhvoice_profiles_use_only_expected_local_voice_names() {
        assert_eq!(super::rhvoice_voice_name(TtsVoiceProfile::Female), "Elena");
        assert_eq!(
            super::rhvoice_voice_name(TtsVoiceProfile::Male),
            "Aleksandr"
        );
    }

    #[test]
    fn voice_profile_resolver_uses_only_fixed_model_and_config_names() {
        let suffix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system clock")
            .as_nanos();
        let root = std::env::temp_dir().join(format!("localcomet-tts-test-{suffix}"));
        fs::create_dir_all(&root).expect("test root");
        fs::write(root.join("piper.exe"), b"test").expect("piper marker");
        fs::write(root.join("ru_RU-irina-medium.onnx"), b"test").expect("female model marker");
        fs::write(root.join("ru_RU-irina-medium.onnx.json"), b"{}").expect("female config");
        fs::write(root.join("ru_RU-ruslan-medium.onnx"), b"test").expect("male model marker");
        fs::write(root.join("ru_RU-ruslan-medium.onnx.json"), b"{}").expect("male config");
        fs::write(root.join("ru_RU-dmitri-medium.onnx"), b"test").expect("dmitri model marker");
        fs::write(root.join("ru_RU-dmitri-medium.onnx.json"), b"{}").expect("dmitri config");
        fs::write(root.join("ru_RU-denis-medium.onnx"), b"test").expect("denis model marker");
        fs::write(root.join("ru_RU-denis-medium.onnx.json"), b"{}").expect("denis config");

        let (piper, model) =
            resolve_voice_files(&root, TtsVoiceProfile::Female).expect("female files");
        assert_eq!(piper, root.join("piper.exe"));
        assert_eq!(model, root.join("ru_RU-irina-medium.onnx"));
        let (male_piper, male_model) =
            resolve_voice_files(&root, TtsVoiceProfile::Male).expect("male files");
        assert_eq!(male_piper, root.join("piper.exe"));
        assert_eq!(male_model, root.join("ru_RU-ruslan-medium.onnx"));
        let dmitri_model = resolve_voice_files(&root, TtsVoiceProfile::Dmitri)
            .expect("dmitri files")
            .1;
        assert_eq!(dmitri_model, root.join("ru_RU-dmitri-medium.onnx"));
        let denis_model = resolve_voice_files(&root, TtsVoiceProfile::Denis)
            .expect("denis files")
            .1;
        assert_eq!(denis_model, root.join("ru_RU-denis-medium.onnx"));

        fs::remove_dir_all(root).expect("cleanup");
    }
}
