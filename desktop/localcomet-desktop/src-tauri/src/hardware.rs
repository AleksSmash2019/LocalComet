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
        out
    }
    #[cfg(not(any(target_arch = "x86", target_arch = "x86_64")))]
    {
        Vec::new()
    }
}

fn detect_gpus() -> Vec<GpuPart> {
    let mut gpus = Vec::new();

    if let Ok(output) = std::process::Command::new("nvidia-smi")
        .args([
            "--query-gpu=name,memory.total",
            "--format=csv,noheader,nounits",
        ])
        .output()
    {
        if output.status.success() {
            for line in String::from_utf8_lossy(&output.stdout).lines() {
                let parts: Vec<&str> = line.split(',').map(|s| s.trim()).collect();
                if parts.len() == 2 {
                    gpus.push(GpuPart {
                        name: parts[0].to_string(),
                        vram_mb: parts[1].parse::<u64>().ok(),
                        integrated: Some(false),
                    });
                }
            }
        }
    }

    #[cfg(target_os = "macos")]
    {
        if gpus.is_empty() && std::env::consts::ARCH == "aarch64" {
            gpus.push(GpuPart {
                name: format!(
                    "Apple Silicon GPU ({})",
                    System::cpu_arch().unwrap_or_else(|| "arm64".into())
                ),
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

    let family = std::env::consts::OS;

    let disks = Disks::new_with_refreshed_list();
    let disk_parts: Vec<DiskPart> = disks
        .iter()
        .map(|d| DiskPart {
            free_bytes: d.available_space(),
            total_bytes: d.total_space(),
            kind: Some(format!("{:?}", d.kind()).to_lowercase()),
            is_system: d.mount_point() == std::path::Path::new("/")
                || d.mount_point().to_string_lossy().starts_with("C:"),
        })
        .collect();

    let cpus = sys.cpus();
    Ok(RawHardware {
        os: OsPart {
            family: family.to_string(),
            version: System::os_version(),
            arch: System::cpu_arch(),
        },
        cpu: CpuPart {
            brand: cpus
                .first()
                .map(|c| c.brand().to_string())
                .unwrap_or_default(),
            physical_cores: sys.physical_core_count(),
            logical_cores: Some(cpus.len()),
            frequency_mhz: cpus.first().map(|c| c.frequency()),
            features: cpu_features(),
        },
        memory: MemoryPart {
            total_bytes: sys.total_memory(),
            available_bytes: sys.available_memory(),
        },
        gpus: detect_gpus(),
        disks: disk_parts,
    })
}
