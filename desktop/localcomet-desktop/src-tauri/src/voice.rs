use std::path::PathBuf;
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
const PIPER_LENGTH_SCALE: &str = "1.04";
static TTS_LOCK: OnceLock<Mutex<()>> = OnceLock::new();
static TTS_CANCEL_GENERATION: AtomicU64 = AtomicU64::new(0);
#[cfg(target_os = "windows")]
static ACTIVE_PIPER_CHILD: OnceLock<Mutex<Option<Child>>> = OnceLock::new();

fn tts_lock() -> &'static Mutex<()> {
    TTS_LOCK.get_or_init(|| Mutex::new(()))
}

#[cfg(target_os = "windows")]
fn active_piper_child() -> &'static Mutex<Option<Child>> {
    ACTIVE_PIPER_CHILD.get_or_init(|| Mutex::new(None))
}

#[cfg(target_os = "windows")]
fn cancel_active_piper() {
    if let Ok(mut active) = active_piper_child().lock() {
        if let Some(child) = active.as_mut() {
            let _ = child.kill();
        }
    }
}

#[cfg(target_os = "windows")]
fn wait_for_piper(generation: u64) -> Result<std::process::ExitStatus, String> {
    loop {
        if TTS_CANCEL_GENERATION.load(Ordering::SeqCst) != generation {
            cancel_active_piper();
        }
        let status = {
            let mut active = active_piper_child()
                .lock()
                .map_err(|_| "Локальный Piper lock повреждён".to_string())?;
            let child = active
                .as_mut()
                .ok_or_else(|| "Активный Piper process отсутствует".to_string())?;
            child
                .try_wait()
                .map_err(|error| format!("Piper не завершился: {error}"))?
        };
        if let Some(status) = status {
            if let Ok(mut active) = active_piper_child().lock() {
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
fn speak_with_piper(text: String, generation: u64) -> Result<(), String> {
    if TTS_CANCEL_GENERATION.load(Ordering::SeqCst) != generation {
        return Ok(());
    }

    let root = piper_root();
    let piper = root.join("piper.exe");
    let voice = root.join("ru_RU-denis-medium.onnx");
    if !piper.is_file() || !voice.is_file() {
        return Err("Локальный русский Piper Denis не найден".to_string());
    }

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
        .stdin(Stdio::piped())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|error| format!("Не удалось запустить Piper: {error}"))?;

    {
        let mut active = active_piper_child()
            .lock()
            .map_err(|_| "Локальный Piper lock повреждён".to_string())?;
        *active = Some(child);
    }

    if let Ok(mut active) = active_piper_child().lock() {
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

    let status = wait_for_piper(generation)?;
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

#[cfg(not(target_os = "windows"))]
fn speak_with_piper(_text: String, _generation: u64) -> Result<(), String> {
    Err("Локальная Piper озвучка доступна только в Windows desktop build".to_string())
}

#[tauri::command]
pub async fn speak_local_text(text: String, language: Option<String>) -> Result<(), String> {
    if language.as_deref().unwrap_or("ru-RU") != "ru-RU" {
        return Ok(());
    }
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
        speak_with_piper(text, generation)
    })
    .await
    .map_err(|error| format!("Локальный TTS worker завершился с ошибкой: {error}"))?
}

#[tauri::command]
pub fn stop_local_text() -> Result<(), String> {
    TTS_CANCEL_GENERATION.fetch_add(1, Ordering::SeqCst);
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
    use super::normalized_text;

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
}
