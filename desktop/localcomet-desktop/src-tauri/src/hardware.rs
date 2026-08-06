use serde::Serialize;
use sysinfo::{Disks, System};

#[derive(Serialize)]
pub struct OsPart {
    pub family: String,
    pub version: Option<String>,
    pub arch: Option<String>,
}

#[derive(Serialize)]
pub struct CpuPart {
    pub brand: String,
    pub physical_cores: Option<usize>,
    pub logical_cores: Option<usize>,
    pub frequency_mhz: Option<u64>,
    pub features: Vec<String>,
}

#[derive(Serialize)]
pub struct MemoryPart {
    pub total_bytes: u64,
    pub available_bytes: u64,
}

#[derive(Serialize)]
pub struct GpuPart {
    pub name: String,
    pub vram_mb: Option<u64>,
    pub integrated: Option<bool>,
}

#[derive(Serialize)]
pub struct DiskPart {
    pub free_bytes: u64,
    pub total_bytes: u64,
    pub kind: Option<String>,
    pub is_system: bool,
}

#[derive(Serialize)]
pub struct RawHardware {
    pub os: OsPart,
    pub cpu: CpuPart,
    pub memory: MemoryPart,
    pub gpus: Vec<GpuPart>,
    pub disks: Vec<DiskPart>,
}

fn sanitize_name(input: &str) -> String {
    let filtered: String = input.chars().filter(|c| !c.is_control()).collect();
    let trimmed = filtered.trim();
    if trimmed.len() > 128 {
        trimmed[..128].to_string()
    } else {
        trimmed.to_string()
    }
}

fn cpu_brand_fallback() -> String {
    #[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
    {
        let cpuid = raw_cpuid::CpuId::new();
        if let Some(brand) = cpuid.get_processor_brand_string() {
            let s = sanitize_name(brand.as_str());
            if !s.is_empty() {
                return s;
            }
        }
    }
    String::new()
}

fn cpu_features() -> Vec<String> {
    #[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
    {
        let cpuid = raw_cpuid::CpuId::new();
        let mut out = Vec::new();
        if let Some(f) = cpuid.get_feature_info() {
            if f.has_avx() {
                out.push("avx".into());
            }
        }
        if let Some(f) = cpuid.get_extended_feature_info() {
            if f.has_avx2() {
                out.push("avx2".into());
            }
            if f.has_avx512f() {
                out.push("avx512f".into());
            }
        }
        // Also check extended state for AVX512 variants via raw_cpuid if available
        out
    }
    #[cfg(not(any(target_arch = "x86", target_arch = "x86_64")))]
    {
        Vec::new()
    }
}

fn detect_gpus() -> Vec<GpuPart> {
    let mut gpus = Vec::new();
    // Bounded, no shell, fixed args, output capped 8 KiB
    let candidates = ["nvidia-smi", "C:\\Windows\\System32\\nvidia-smi.exe"];
    for bin in candidates {
        if gpus.len() >= 4 {
            break;
        }
        let output = match std::process::Command::new(bin)
            .args([
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ])
            .output()
        {
            Ok(o) => o,
            Err(_) => continue,
        };
        if !output.status.success() {
            continue;
        }
        if output.stdout.len() > 8192 || output.stdout.is_empty() {
            continue;
        }
        for line in String::from_utf8_lossy(&output.stdout).lines().take(4) {
            let parts: Vec<&str> = line.split(',').map(|s| s.trim()).collect();
            if parts.len() != 2 {
                continue;
            }
            let raw_name = sanitize_name(parts[0]);
            if raw_name.is_empty() || raw_name.len() > 128 {
                continue;
            }
            let vram_mb = parts[1]
                .parse::<u64>()
                .ok()
                .filter(|v| *v > 0 && *v < 262144);
            // Deduplicate by name
            if gpus.iter().any(|g: &GpuPart| g.name == raw_name) {
                continue;
            }
            gpus.push(GpuPart {
                name: raw_name,
                vram_mb,
                integrated: Some(false),
            });
        }
        if !gpus.is_empty() {
            break;
        }
    }

    #[cfg(target_os = "macos")]
    {
        if gpus.is_empty() && std::env::consts::ARCH == "aarch64" {
            gpus.push(GpuPart {
                name: sanitize_name(&format!(
                    "Apple Silicon GPU ({})",
                    System::cpu_arch().unwrap_or_else(|| "arm64".into())
                )),
                vram_mb: None,
                integrated: Some(true),
            });
        }
    }

    gpus
}

#[tauri::command]
pub fn scan_hardware() -> Result<RawHardware, String> {
    let mut sys = System::new_all();
    sys.refresh_all();
    // Extra refresh for CPU frequency which may be 0 on first refresh on Windows
    std::thread::sleep(std::time::Duration::from_millis(50));
    sys.refresh_cpu_all();

    let family = std::env::consts::OS.to_string();

    let disks = Disks::new_with_refreshed_list();
    let disk_parts: Vec<DiskPart> = disks
        .iter()
        .take(8)
        .map(|d| {
            let kind_raw = format!("{:?}", d.kind()).to_lowercase();
            let kind = if kind_raw == "unknown" || kind_raw.is_empty() {
                None
            } else {
                Some(kind_raw)
            };
            let mp = d.mount_point().to_string_lossy().to_lowercase();
            let is_system = mp == "/"
                || mp == "c:\\"
                || mp == "c:/"
                || mp.starts_with("c:\\")
                || mp.starts_with("c:/");
            DiskPart {
                free_bytes: d.available_space(),
                total_bytes: d.total_space(),
                kind,
                is_system,
            }
        })
        .collect();

    let cpus = sys.cpus();
    let raw_brand = cpus
        .first()
        .map(|c| c.brand().to_string())
        .unwrap_or_default();
    let brand = {
        let s = sanitize_name(&raw_brand);
        if s.is_empty() {
            let fb = cpu_brand_fallback();
            if fb.is_empty() {
                "Unknown CPU".to_string()
            } else {
                fb
            }
        } else {
            s
        }
    };
    let physical_cores = sys.physical_core_count();
    let logical_cores = Some(cpus.len().max(1));
    let frequency_mhz = cpus
        .first()
        .map(|c| c.frequency())
        .filter(|f| *f > 0 && *f < 10000);
    let features = cpu_features();

    // OS version: prefer long_os_version, fallback to os_version
    let os_version = System::long_os_version()
        .or_else(System::os_version)
        .map(|v| sanitize_name(&v))
        .filter(|v| !v.is_empty());
    let arch = System::cpu_arch()
        .map(|v| sanitize_name(&v))
        .filter(|v| !v.is_empty())
        .or_else(|| Some(std::env::consts::ARCH.to_string()));

    let mem_total = sys.total_memory();
    let mem_avail = sys.available_memory();
    // sysinfo 0.31 returns bytes, clamp to sane range
    let total_bytes = mem_total.clamp(0, 1u64 << 47);
    let available_bytes = mem_avail.min(total_bytes);

    Ok(RawHardware {
        os: OsPart {
            family,
            version: os_version,
            arch,
        },
        cpu: CpuPart {
            brand,
            physical_cores,
            logical_cores,
            frequency_mhz,
            features,
        },
        memory: MemoryPart {
            total_bytes,
            available_bytes,
        },
        gpus: detect_gpus(),
        disks: disk_parts,
    })
}
