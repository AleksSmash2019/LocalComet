// Unfinished, unreferenced prototype; deliberately NOT part of the production launch path.
// No module declares this file, so Cargo does not compile it. It fabricates model
// metadata from filenames and defaults; real GGUF metadata must be read and
// validated before this prototype can be wired into production.
// Known prototype/integration defects: fabricated metadata; CPU-mode GPU layers;
// --fit on combined with explicit --gpu-layers; unbounded --fit-ctx fallback;
// rejected CLI flags (--keep-in-ctx, --pool, --n-lookahead); duplicate argv builder;
// sys.cpus()[0] panic on empty CPU inventory; MiB/GiB mixing; unchecked subtraction.

use serde::{Deserialize, Serialize};
use std::fs::File;
use std::io::Read;
use std::path::Path;
use sysinfo::System;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct HardwareInfo {
    pub ram_total: u64,
    pub ram_available: u64,
    pub ram_percent: f32,
    pub cpu_physical_cores: u32,
    pub cpu_logical_cores: u32,
    pub cpu_freq_max: f32,
    pub gpu_brand: String,
    pub gpu_name: String,
    pub vram_total: u32,
    pub vram_available: u32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ModelInfo {
    pub architecture: String,
    pub name: String,
    pub parameter_count: u64,
    pub file_size_bytes: u64,
    pub context_length: u32,
    pub embedding_length: u32,
    pub attention_head_count: u32,
    pub rope_freq_base: f32,
    pub rope_scaling_factor: f32,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AdaptiveParams {
    pub n_gpu_layers: u32,
    pub ctx_size: u32,
    pub batch_size: u32,
    pub n_threads: u32,
    pub memory_limit_bytes: u64,
    pub rope_freq_base: f32,
    pub rope_freq_scale: f32,
}

pub fn detect_hardware_info() -> HardwareInfo {
    let mut sys = System::new_all();
    sys.refresh_all();

    // GPU detection - в реальной реализации нужно использовать конкретные библиотеки
    // или вызывать nvidia-smi/rocm-smi через subprocess
    let (gpu_brand, gpu_name, vram_total, vram_available) = detect_gpu_info();

    HardwareInfo {
        ram_total: sys.total_memory(),
        ram_available: sys.available_memory(),
        ram_percent: (sys.used_memory() as f32) / (sys.total_memory() as f32) * 100.0,
        cpu_physical_cores: sys.physical_core_count().unwrap_or(4) as u32,
        cpu_logical_cores: sys.cpus().len() as u32,
        cpu_freq_max: sys.cpus()[0].frequency() as f32, // Use the first CPU frequency as max
        gpu_brand,
        gpu_name,
        vram_total,
        vram_available,
    }
}

fn detect_gpu_info() -> (String, String, u32, u32) {
    #[cfg(windows)]
    {
        use std::process::Command;

        // Пробуем nvidia-smi
        if let Ok(output) = Command::new("nvidia-smi")
            .args([
                "--query-gpu=name,memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ])
            .output()
        {
            if !output.stdout.is_empty() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                let lines: Vec<&str> = stdout.trim().split('\n').collect();
                if !lines.is_empty() {
                    let parts: Vec<&str> = lines[0].split(',').map(|s| s.trim()).collect();
                    if parts.len() >= 3 {
                        let name = parts[0].to_string();
                        let total_mb = parts[1].parse::<u32>().unwrap_or(0);
                        let used_mb = parts[2].parse::<u32>().unwrap_or(0);
                        return ("NVIDIA".to_string(), name, total_mb, total_mb - used_mb);
                    }
                }
            }
        }
    }

    // Linux GPU detection
    #[cfg(target_os = "linux")]
    {
        use std::process::Command;

        // nvidia-smi
        if let Ok(output) = Command::new("nvidia-smi")
            .args([
                "--query-gpu=name,memory.total,memory.used",
                "--format=csv,noheader,nounits",
            ])
            .output()
        {
            if !output.stdout.is_empty() {
                let stdout = String::from_utf8_lossy(&output.stdout);
                let lines: Vec<&str> = stdout.trim().split('\n').collect();
                if !lines.is_empty() {
                    let parts: Vec<&str> = lines[0].split(',').map(|s| s.trim()).collect();
                    if parts.len() >= 3 {
                        let name = parts[0].to_string();
                        let total_mb = parts[1].parse::<u32>().unwrap_or(0);
                        let used_mb = parts[2].parse::<u32>().unwrap_or(0);
                        return ("NVIDIA".to_string(), name, total_mb, total_mb - used_mb);
                    }
                }
            }
        }

        // AMD GPU detection через rocm-smi (если установлен)
        if let Ok(output) = Command::new("rocm-smi")
            .args(&["--showmeminfo", "vram"])
            .output()
        {
            // Реализация для AMD GPU
        }
    }

    // Если GPU не обнаружен
    ("CPU_ONLY".to_string(), "None".to_string(), 0, 0)
}

pub fn analyze_gguf_model(model_path: &Path) -> Result<ModelInfo, String> {
    let mut file = File::open(model_path).map_err(|e| format!("Cannot open model file: {}", e))?;

    // Читаем GGUF заголовок
    let mut magic = [0u8; 4];
    file.read_exact(&mut magic)
        .map_err(|e| format!("Cannot read model header: {}", e))?;

    if &magic != b"GGUF" {
        return Err("Model file is not in GGUF format".to_string());
    }

    // Читаем версию GGUF
    let mut version_bytes = [0u8; 4];
    file.read_exact(&mut version_bytes)
        .map_err(|e| format!("Cannot read GGUF version: {}", e))?;
    let _version = u32::from_le_bytes(version_bytes);

    // Читаем количество тензоров и KV пар
    let mut tensor_count_bytes = [0u8; 8];
    let mut kv_count_bytes = [0u8; 8];
    file.read_exact(&mut tensor_count_bytes)
        .map_err(|e| format!("Cannot read tensor count: {}", e))?;
    file.read_exact(&mut kv_count_bytes)
        .map_err(|e| format!("Cannot read KV count: {}", e))?;

    let _tensor_count = u64::from_le_bytes(tensor_count_bytes);
    let _kv_count = u64::from_le_bytes(kv_count_bytes);

    let file_size = std::fs::metadata(model_path)
        .map_err(|e| format!("Cannot get model file size: {}", e))?
        .len();

    // Базовые параметры, которые мы можем определить из имени файла
    let model_name = model_path
        .file_stem()
        .and_then(|name| name.to_str())
        .unwrap_or("unknown")
        .to_lowercase();

    // Определяем архитектуру по имени
    let architecture = if model_name.contains("llama") {
        "llama".to_string()
    } else if model_name.contains("mistral") || model_name.contains("mixtral") {
        "mistral".to_string()
    } else if model_name.contains("qwen") {
        "qwen".to_string()
    } else if model_name.contains("phi") {
        "phi".to_string()
    } else if model_name.contains("gemma") {
        "gemma".to_string()
    } else {
        "unknown".to_string()
    };

    Ok(ModelInfo {
        architecture,
        name: model_path
            .file_stem()
            .and_then(|name| name.to_str())
            .unwrap_or("unknown")
            .to_string(),
        parameter_count: 0, // для полного определения нужно читать GGUF метаданные
        file_size_bytes: file_size,
        context_length: 2048,     // стандартное значение
        embedding_length: 4096,   // стандартное значение
        attention_head_count: 32, // стандартное значение
        rope_freq_base: 10000.0,
        rope_scaling_factor: 1.0,
    })
}

pub fn compute_adaptive_params(
    model_info: &ModelInfo,
    hardware_info: &HardwareInfo,
) -> AdaptiveParams {
    let model_size_gb = model_info.file_size_bytes as f64 / (1024.0 * 1024.0 * 1024.0);
    let available_ram_gb = hardware_info.ram_available as f64 / (1024.0 * 1024.0 * 1024.0);
    let has_gpu = hardware_info.gpu_brand != "CPU_ONLY";
    let vram_gb = hardware_info.vram_available as f64 / 1000.0; // Convert from MB to GB

    // Базовые параметры
    let mut params = AdaptiveParams {
        n_gpu_layers: 0,
        ctx_size: 2048,
        batch_size: 512,
        n_threads: hardware_info.cpu_logical_cores.min(12), // не более 12 потоков
        memory_limit_bytes: (available_ram_gb * 0.8 * 1024.0 * 1024.0 * 1024.0) as u64, // 80% RAM
        rope_freq_base: model_info.rope_freq_base,
        rope_freq_scale: model_info.rope_scaling_factor,
    };

    // Адаптация под GPU
    if has_gpu {
        if model_size_gb < 3.0 {
            // <3B
            params.ctx_size = 8192;
            params.batch_size = 1024;

            if vram_gb > 4.0 {
                params.n_gpu_layers = 99; // почти вся модель на GPU
            } else if vram_gb > 2.0 {
                params.n_gpu_layers = 33; // частичная выгрузка
            }
        } else if model_size_gb < 8.0 {
            // 3-8B
            params.ctx_size = 4096;
            params.batch_size = 512;

            if vram_gb > 8.0 {
                params.n_gpu_layers = 99; // значительная выгрузка
            } else if vram_gb > 6.0 {
                params.n_gpu_layers = 33; // частичная выгрузка
            } else if vram_gb > 4.0 {
                params.n_gpu_layers = 20; // ограниченная выгрузка
            }
        } else {
            // >8B
            params.ctx_size = 2048; // экономия памяти
            params.batch_size = 256; // экономия памяти

            if vram_gb > 10.0 {
                params.n_gpu_layers = 27; // для больших моделей
            } else if vram_gb > 8.0 {
                params.n_gpu_layers = 15; // минимальная выгрузка
            }
        }
    } else {
        // CPU-only настройки
        params.ctx_size = if model_size_gb < 3.0 {
            4096
        } else if model_size_gb < 8.0 {
            2048
        } else {
            1024 // экономия памяти для больших моделей
        };

        params.batch_size = if model_size_gb < 3.0 {
            512
        } else if model_size_gb < 8.0 {
            256
        } else {
            128 // минимизация для больших моделей
        };

        params.n_gpu_layers = 0;
    }

    // Адаптация под архитектуру
    let arch = &model_info.architecture;
    if arch.contains("moe") || arch.contains("mixtral") {
        // MoE - особые ограничения
        params.ctx_size = params.ctx_size.min(2048);
        params.n_gpu_layers = params.n_gpu_layers.min(20);
    } else if arch.contains("qwen") {
        // Qwen - расширенные контексты
        if model_info.name.contains("3.8") {
            params.ctx_size = params.ctx_size.max(32768);
            params.rope_freq_base = 1000000.0; // Qwen3.8 специфичный RoPE
        } else {
            params.ctx_size = params.ctx_size.max(8192);
        }
    } else if arch.contains("gemma") {
        // Gemma - оптимизации для Google моделей
        params.ctx_size = params.ctx_size.min(8192);
        params.batch_size = params.batch_size.min(512);
    } else if arch.contains("phi") {
        // Phi - компактные и быстрые
        params.ctx_size = params.ctx_size.min(2048);
        params.batch_size = params.batch_size.min(256);
        if params.n_gpu_layers > 0 {
            params.n_gpu_layers = params.n_gpu_layers.min(10); // Phi не нуждается в полной выгрузке
        }
    } else if arch.contains("deepseek") {
        // DeepSeek - специфичные параметры
        params.ctx_size = params.ctx_size.max(16384);
        if arch.contains("r1") {
            // DeepSeek R1 - режим reasoning
            params.ctx_size = params.ctx_size.min(8192);
            if has_gpu && vram_gb > 6.0 {
                params.n_gpu_layers = params.n_gpu_layers.min(30);
            }
        }
    }

    // Проверка на достаточную память
    let estimated_model_ram_gb = model_size_gb * 1.2; // +20% overhead
    if available_ram_gb < estimated_model_ram_gb {
        // Снижаем параметры для экономии памяти
        params.ctx_size = (params.ctx_size as f64 * 0.5) as u32;
        params.batch_size = (params.batch_size as f64 * 0.5) as u32;
        params.n_threads = (params.n_threads as f64 * 0.5) as u32;
    }

    params
}

pub fn build_adaptive_runtime_args(
    model_path: &Path,
    mmproj_path: Option<&Path>,
    port: u16,
    api_key_file: &Path,
    _alias: &str,
    _runtime_id: &str,
    _package_dir: &str,
) -> Result<Vec<String>, String> {
    let model_info = analyze_gguf_model(model_path)?;
    let hardware_info = detect_hardware_info();
    let adaptive_params = compute_adaptive_params(&model_info, &hardware_info);

    let mut args = vec![
        "--model".to_string(),
        model_path.to_string_lossy().to_string(),
        "--host".to_string(),
        "127.0.0.1".to_string(),
        "--port".to_string(),
        port.to_string(),
        "--api-key-file".to_string(),
        api_key_file.to_string_lossy().to_string(),
        "--ctx-size".to_string(),
        adaptive_params.ctx_size.to_string(),
        "--batch-size".to_string(),
        adaptive_params.batch_size.to_string(),
        "--threads".to_string(),
        adaptive_params.n_threads.to_string(),
    ];

    // GPU слои
    if adaptive_params.n_gpu_layers > 0 {
        args.push("--n-gpu-layers".to_string());
        args.push(adaptive_params.n_gpu_layers.to_string());
    }

    // MMProj для vision моделей
    if let Some(proj_path) = mmproj_path {
        args.push("--mmproj".to_string());
        args.push(proj_path.to_string_lossy().to_string());
    }

    // Параметры для стабильности
    args.push("--temp".to_string());
    args.push("0.8".to_string());
    args.push("--top-p".to_string());
    args.push("0.95".to_string());
    args.push("--repeat-penalty".to_string());
    args.push("1.1".to_string());

    // RoPE параметры
    args.push("--rope-freq-base".to_string());
    args.push(adaptive_params.rope_freq_base.to_string());
    args.push("--rope-freq-scale".to_string());
    args.push(adaptive_params.rope_freq_scale.to_string());

    // Параметры кэширования
    if adaptive_params.n_gpu_layers > 0 {
        args.push("--cache-type-k".to_string());
        args.push("f16".to_string());
        args.push("--cache-type-v".to_string());
        args.push("f16".to_string());
    } else {
        args.push("--cache-type-k".to_string());
        args.push("q8_0".to_string());
        args.push("--cache-type-v".to_string());
        args.push("q8_0".to_string());
    }

    // Адаптивные параметры для специфичных архитектур
    let arch = &model_info.architecture;
    if arch.contains("moe") || arch.contains("mixtral") {
        args.push("--keep-in-ctx".to_string());
        args.push("128".to_string());
    } else if arch.contains("qwen") && model_info.name.contains("3.8") {
        args.push("--rope-scaling".to_string());
        args.push("linear".to_string());
        args.push("--pool".to_string());
        args.push("none".to_string());
    } else if arch.contains("deepseek") && arch.contains("r1") {
        args.push("--n-lookahead".to_string());
        args.push("256".to_string());
    }

    Ok(args)
}
