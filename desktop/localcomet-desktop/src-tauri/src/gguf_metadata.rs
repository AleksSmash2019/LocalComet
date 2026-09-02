//! Bounded GGUF header reader and hardware-fit launch recommendations.
//!
//! The reader intentionally extracts only what launch fitting needs
//! (`general.architecture`, `{arch}.block_count`, `{arch}.context_length`)
//! and never trusts header-declared sizes for allocation: every read and
//! skip is bounds-checked against a fixed read buffer, so a malformed or
//! adversarial GGUF can only ever yield `None`, never a panic or an
//! unbounded allocation. The recommendation is advisory: the engine's own
//! `--fit` remains the final authority at load time.

use serde::Serialize;
use std::fs::File;
use std::io::Read;
use std::path::Path;

const HEADER_BYTES: usize = 24;
const MAX_READ_BYTES: usize = 32 * 1024 * 1024;
const MAX_KV_PAIRS: u64 = 16_384;
const MAX_KEY_BYTES: u64 = 4096;
const MAX_STRING_BYTES: u64 = 4 * 1024 * 1024;
const MAX_ARRAY_ITEMS: u64 = 4 * 1024 * 1024;

/// The subset of GGUF metadata used for launch fitting. All fields optional:
/// any parse shortfall degrades to an estimated recommendation instead of
/// blocking a launch.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct GgufMetadata {
    pub architecture: Option<String>,
    pub block_count: Option<u32>,
    pub context_length: Option<u32>,
}

struct Cursor<'a> {
    data: &'a [u8],
    pos: usize,
}

impl<'a> Cursor<'a> {
    fn take(&mut self, count: usize) -> Option<&'a [u8]> {
        let end = self.pos.checked_add(count)?;
        if end > self.data.len() {
            return None;
        }
        let slice = &self.data[self.pos..end];
        self.pos = end;
        Some(slice)
    }

    fn read_u32(&mut self) -> Option<u32> {
        let bytes = self.take(4)?;
        Some(u32::from_le_bytes([bytes[0], bytes[1], bytes[2], bytes[3]]))
    }

    fn read_u64(&mut self) -> Option<u64> {
        let bytes = self.take(8)?;
        Some(u64::from_le_bytes([
            bytes[0], bytes[1], bytes[2], bytes[3], bytes[4], bytes[5], bytes[6], bytes[7],
        ]))
    }

    fn read_string(&mut self, max_bytes: u64) -> Option<String> {
        let len = self.read_u64()?;
        if len > max_bytes {
            return None;
        }
        let bytes = self.take(usize::try_from(len).ok()?)?;
        String::from_utf8(bytes.to_vec()).ok()
    }

    fn skip(&mut self, count: u64) -> Option<()> {
        let count = usize::try_from(count).ok()?;
        self.take(count).map(|_| ())
    }
}

fn scalar_byte_size(value_type: u32) -> Option<u64> {
    match value_type {
        0 | 1 | 7 => Some(1),
        2 | 3 => Some(2),
        4..=6 => Some(4),
        10..=12 => Some(8),
        _ => None,
    }
}

fn numeric_from_le(raw: &[u8]) -> Option<u64> {
    match raw.len() {
        4 => Some(u32::from_le_bytes([raw[0], raw[1], raw[2], raw[3]]) as u64),
        8 => Some(u64::from_le_bytes(raw.try_into().ok()?)),
        _ => None,
    }
}

fn arch_key_matches(key: &str, architecture: Option<&str>, suffix: &str) -> bool {
    match architecture {
        Some(arch) => key == format!("{arch}.{suffix}"),
        // Before the architecture key is seen, accept the first well-known
        // suffix. llama.cpp conversions always write general.architecture
        // first, so this fallback only covers exotic writers.
        None => key.ends_with(&format!(".{suffix}")),
    }
}

fn read_kv_value(
    cursor: &mut Cursor<'_>,
    value_type: u32,
    key: &str,
    metadata: &mut GgufMetadata,
) -> Option<()> {
    match value_type {
        8 => {
            let value = cursor.read_string(MAX_STRING_BYTES)?;
            if key == "general.architecture" && !value.is_empty() && value.len() <= 64 {
                metadata.architecture = Some(value);
            }
        }
        9 => {
            let element_type = cursor.read_u32()?;
            let count = cursor.read_u64()?;
            if count > MAX_ARRAY_ITEMS {
                return None;
            }
            if element_type == 8 {
                for _ in 0..count {
                    cursor.read_string(MAX_STRING_BYTES)?;
                }
            } else if element_type == 9 {
                // Nested arrays do not occur in practice; fail safe.
                return None;
            } else {
                let size = scalar_byte_size(element_type)?;
                cursor.skip(count.checked_mul(size)?)?;
            }
        }
        _ => {
            let size = scalar_byte_size(value_type)?;
            let raw = cursor.take(usize::try_from(size).ok()?)?.to_vec();
            if value_type == 4 || value_type == 10 {
                let wants_block_count =
                    arch_key_matches(key, metadata.architecture.as_deref(), "block_count")
                        && metadata.block_count.is_none();
                let wants_context_length =
                    arch_key_matches(key, metadata.architecture.as_deref(), "context_length")
                        && metadata.context_length.is_none();
                if wants_block_count || wants_context_length {
                    if let Some(value) = numeric_from_le(&raw) {
                        if wants_block_count && value > 0 && value <= 1024 {
                            metadata.block_count = u32::try_from(value).ok();
                        } else if wants_context_length && (256..=10_000_000).contains(&value) {
                            metadata.context_length = u32::try_from(value).ok();
                        }
                    }
                }
            }
        }
    }
    Some(())
}

/// Reads the launch-fit subset of a GGUF header. Returns `None` for any
/// malformed, truncated, or unsupported input.
pub fn read_gguf_metadata(path: &Path) -> Option<GgufMetadata> {
    let file_size = std::fs::metadata(path).ok()?.len();
    if file_size < HEADER_BYTES as u64 {
        return None;
    }
    let read_len = file_size.min(MAX_READ_BYTES as u64) as usize;
    let mut data = vec![0_u8; read_len];
    File::open(path).ok()?.read_exact(&mut data).ok()?;
    let mut cursor = Cursor {
        data: &data,
        pos: 0,
    };
    let magic = cursor.read_u32()?;
    if magic.to_le_bytes() != *b"GGUF" {
        return None;
    }
    let version = cursor.read_u32()?;
    if !(2..=3).contains(&version) {
        return None;
    }
    let _tensor_count = cursor.read_u64()?;
    let kv_count = cursor.read_u64()?;
    if kv_count > MAX_KV_PAIRS {
        return None;
    }

    let mut metadata = GgufMetadata::default();
    for _ in 0..kv_count {
        let key = cursor.read_string(MAX_KEY_BYTES)?;
        let value_type = cursor.read_u32()?;
        read_kv_value(&mut cursor, value_type, &key, &mut metadata)?;
        if metadata.architecture.is_some()
            && metadata.block_count.is_some()
            && metadata.context_length.is_some()
        {
            break;
        }
    }
    Some(metadata)
}

/// Parses the bounded device summary emitted by `--list-devices`, e.g.
/// `NVIDIA GeForce RTX 5070 (11943 MiB, 11175 MiB free)` into
/// `(total_mib, free_mib)`. Returns `None` when the summary carries no
/// parseable VRAM numbers; absence degrades to a non-VRAM recommendation.
pub fn parse_device_vram(summary: &str) -> Option<(u64, u64)> {
    let open = summary.rfind('(')?;
    let inner = summary.get(open + 1..)?.strip_suffix(')')?;
    let mut total_mib = None;
    let mut free_mib = None;
    for part in inner.split(',') {
        let part = part.trim();
        let is_free = part.ends_with("free");
        let value_part = if is_free {
            part.strip_suffix("free")?.trim().strip_suffix("MiB")
        } else {
            part.strip_suffix("MiB")
        };
        let Some(value_part) = value_part else {
            continue;
        };
        let value: u64 = value_part.trim().parse().ok()?;
        if is_free {
            free_mib = Some(value);
        } else {
            total_mib = total_mib.or(Some(value));
        }
    }
    let total = total_mib?;
    Some((total, free_mib.unwrap_or(total)))
}

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct LaunchRecommendationReport {
    /// "gpu" (full offload, engine auto-fit), "hybrid" (explicit layer split),
    /// or "cpu" (no practical VRAM path for this model on this machine).
    pub mode: &'static str,
    /// Explicit layer count for hybrid only; gpu/cpu leave the engine auto.
    pub gpu_layers: Option<u32>,
    pub ctx_size: u32,
    pub architecture: Option<String>,
    pub block_count: Option<u32>,
    pub model_context_length: Option<u32>,
    /// True when the GGUF header could not be read and the layer estimate
    /// used a default block count.
    pub estimated: bool,
}

/// Context tiers considered for GPU recommendations, largest first. The
/// engine's `--fit` still reduces the real context when VRAM runs out; these
/// targets only pick where the fit should aim.
pub const RECOMMEND_CTX_TIERS: [u32; 5] = [32768, 16384, 8192, 4096, 2048];

/// Weights plus compute-buffer headroom, relative to GGUF bytes.
const MODEL_VRAM_FACTOR: f64 = 1.25;
/// Desktop, display and driver reserve on the GPU.
const VRAM_RESERVE_MIB: f64 = 1024.0;
/// f16 KV cache for a GQA block with ~1024 kv dim is ~4 MiB per 1k tokens.
const KV_MIB_PER_1K_TOKENS_PER_BLOCK: f64 = 4.0;
const MAX_KV_BLOCKS: u32 = 64;
/// Layer-count stand-in when the GGUF header could not be read.
const DEFAULT_BLOCK_COUNT: u32 = 32;
/// Below this free VRAM even a small partial offload is not practical.
const HYBRID_MIN_FREE_MIB: f64 = 1536.0;

fn kv_mib(ctx: u32, blocks: u32) -> f64 {
    (ctx as f64 / 1000.0) * (blocks.min(MAX_KV_BLOCKS) as f64) * KV_MIB_PER_1K_TOKENS_PER_BLOCK
}

/// Mirrors the CPU context table in `managed_runtime::runtime_args` so a CPU
/// recommendation never promises more context than a real CPU launch selects.
fn cpu_ctx_size(model_size_gb: f64, available_ram_gb: f64) -> u32 {
    let mut ctx = 8192_u32;
    if model_size_gb > 3.0 {
        if available_ram_gb < 4.5 {
            ctx = 2048;
        } else if available_ram_gb < 6.5 {
            ctx = 4096;
        }
    } else if available_ram_gb < 3.0 {
        ctx = 4096;
    }
    ctx
}

pub fn recommend_launch(
    model_size_bytes: u64,
    metadata: Option<&GgufMetadata>,
    device_summary: Option<&str>,
    available_ram_gb: f64,
) -> LaunchRecommendationReport {
    let architecture = metadata.and_then(|meta| meta.architecture.clone());
    let reported_block_count = metadata.and_then(|meta| meta.block_count);
    let model_context_length = metadata.and_then(|meta| meta.context_length);
    let estimated = metadata.is_none();
    let fit_blocks = reported_block_count
        .filter(|count| *count > 0)
        .unwrap_or(DEFAULT_BLOCK_COUNT);
    let model_mib = (model_size_bytes as f64 / (1024.0 * 1024.0)).max(1.0);
    let model_gb = model_size_bytes as f64 / (1024.0 * 1024.0 * 1024.0);
    // A recommendation never exceeds the model's trained context; the engine
    // floor is 1024 (the launch clamp in managed_runtime).
    let ctx_tier =
        |target: u32| model_context_length.map_or(target, |trained| target.min(trained).max(1024));
    let base =
        |mode: &'static str, gpu_layers: Option<u32>, ctx_size: u32| LaunchRecommendationReport {
            mode,
            gpu_layers,
            ctx_size,
            architecture: architecture.clone(),
            block_count: reported_block_count,
            model_context_length,
            estimated,
        };

    let Some((_, free_mib)) = device_summary.and_then(parse_device_vram) else {
        return base(
            "cpu",
            None,
            ctx_tier(cpu_ctx_size(model_gb, available_ram_gb)),
        );
    };
    let free = free_mib as f64;
    let weights_full = model_mib * MODEL_VRAM_FACTOR;

    for &tier in RECOMMEND_CTX_TIERS.iter() {
        if weights_full + kv_mib(tier, fit_blocks) + VRAM_RESERVE_MIB <= free {
            return base("gpu", None, ctx_tier(tier));
        }
    }

    if free >= HYBRID_MIN_FREE_MIB {
        let usable = free - VRAM_RESERVE_MIB;
        let layers = (fit_blocks as f64 * usable / model_mib).floor();
        if layers >= 1.0 {
            let layers = layers.min(fit_blocks as f64).min(99.0) as u32;
            let weights = model_mib * (layers as f64 / fit_blocks as f64);
            let leftover = free - weights;
            for &tier in RECOMMEND_CTX_TIERS.iter() {
                if kv_mib(tier, fit_blocks) + 512.0 <= leftover {
                    return base("hybrid", Some(layers), ctx_tier(tier));
                }
            }
        }
    }

    base(
        "cpu",
        None,
        ctx_tier(cpu_ctx_size(model_gb, available_ram_gb)),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    struct GgufBuilder {
        bytes: Vec<u8>,
    }

    impl GgufBuilder {
        fn new(version: u32, kv_count: u64) -> Self {
            let mut bytes = Vec::new();
            bytes.extend_from_slice(b"GGUF");
            bytes.extend_from_slice(&version.to_le_bytes());
            bytes.extend_from_slice(&0_u64.to_le_bytes()); // tensor count
            bytes.extend_from_slice(&kv_count.to_le_bytes());
            Self { bytes }
        }

        fn string_kv(mut self, key: &str, value: &str) -> Self {
            self.bytes
                .extend_from_slice(&(key.len() as u64).to_le_bytes());
            self.bytes.extend_from_slice(key.as_bytes());
            self.bytes.extend_from_slice(&8_u32.to_le_bytes());
            self.bytes
                .extend_from_slice(&(value.len() as u64).to_le_bytes());
            self.bytes.extend_from_slice(value.as_bytes());
            self
        }

        fn u32_kv(mut self, key: &str, value: u32) -> Self {
            self.bytes
                .extend_from_slice(&(key.len() as u64).to_le_bytes());
            self.bytes.extend_from_slice(key.as_bytes());
            self.bytes.extend_from_slice(&4_u32.to_le_bytes());
            self.bytes.extend_from_slice(&value.to_le_bytes());
            self
        }

        fn string_array_kv(mut self, key: &str, items: &[&str]) -> Self {
            self.bytes
                .extend_from_slice(&(key.len() as u64).to_le_bytes());
            self.bytes.extend_from_slice(key.as_bytes());
            self.bytes.extend_from_slice(&9_u32.to_le_bytes());
            self.bytes.extend_from_slice(&8_u32.to_le_bytes());
            self.bytes
                .extend_from_slice(&(items.len() as u64).to_le_bytes());
            for item in items {
                self.bytes
                    .extend_from_slice(&(item.len() as u64).to_le_bytes());
                self.bytes.extend_from_slice(item.as_bytes());
            }
            self
        }

        fn bytes(self) -> Vec<u8> {
            self.bytes
        }
    }

    fn write_temp(name: &str, bytes: &[u8]) -> PathBuf {
        let path =
            std::env::temp_dir().join(format!("lc_gguf_test_{name}_{:?}.gguf", std::process::id()));
        std::fs::write(&path, bytes).expect("write temp gguf");
        path
    }

    #[test]
    fn gguf_v3_header_parses_core_fields() {
        let bytes = GgufBuilder::new(3, 3)
            .string_kv("general.architecture", "qwen3")
            .u32_kv("qwen3.block_count", 28)
            .u32_kv("qwen3.context_length", 40960)
            .bytes();
        let path = write_temp("v3", &bytes);
        let metadata = read_gguf_metadata(&path).expect("metadata");
        let _ = std::fs::remove_file(&path);
        assert_eq!(metadata.architecture.as_deref(), Some("qwen3"));
        assert_eq!(metadata.block_count, Some(28));
        assert_eq!(metadata.context_length, Some(40960));
    }

    #[test]
    fn gguf_v2_header_and_string_arrays_parse() {
        let bytes = GgufBuilder::new(2, 4)
            .string_kv("general.architecture", "llama")
            .string_array_kv("tokenizer.ggml.tokens", &["<s>", "</s>", "hello"])
            .u32_kv("llama.block_count", 32)
            .u32_kv("llama.context_length", 8192)
            .bytes();
        let path = write_temp("v2", &bytes);
        let metadata = read_gguf_metadata(&path).expect("metadata");
        let _ = std::fs::remove_file(&path);
        assert_eq!(metadata.architecture.as_deref(), Some("llama"));
        assert_eq!(metadata.block_count, Some(32));
        assert_eq!(metadata.context_length, Some(8192));
    }

    #[test]
    fn gguf_rejects_garbage_truncation_and_bad_version() {
        let path = write_temp("garbage", b"NOTG");
        assert!(read_gguf_metadata(&path).is_none());
        let _ = std::fs::remove_file(&path);

        let truncated = GgufBuilder::new(3, 4)
            .string_kv("general.architecture", "qwen3")
            .bytes();
        let path = write_temp("truncated", &truncated);
        assert!(read_gguf_metadata(&path).is_none());
        let _ = std::fs::remove_file(&path);

        let bytes = GgufBuilder::new(1, 1).bytes();
        let path = write_temp("v1", &bytes);
        assert!(read_gguf_metadata(&path).is_none());
        let _ = std::fs::remove_file(&path);

        assert!(read_gguf_metadata(Path::new("Z:/definitely/missing.gguf")).is_none());
    }

    #[test]
    fn device_vram_parses_real_probe_shape() {
        let summary = "NVIDIA GeForce RTX 5070 (11943 MiB, 11175 MiB free)";
        assert_eq!(parse_device_vram(summary), Some((11943, 11175)));
        assert_eq!(
            parse_device_vram("AMD Radeon (8192 MiB)"),
            Some((8192, 8192))
        );
        assert_eq!(parse_device_vram("no numbers here"), None);
        assert_eq!(
            parse_device_vram("Name (huge 99999999999999999999999 MiB, 1 MiB free)"),
            None
        );
        assert_eq!(parse_device_vram("Name (bad 12 GiB, 1 MiB free)"), None);
    }

    #[test]
    fn recommend_full_gpu_on_large_vram_small_model() {
        let metadata = GgufMetadata {
            architecture: Some("qwen3".into()),
            block_count: Some(28),
            context_length: Some(40960),
        };
        let report = recommend_launch(
            1_100_000_000,
            Some(&metadata),
            Some("NVIDIA GeForce RTX 5070 (11943 MiB, 11175 MiB free)"),
            16.0,
        );
        assert_eq!(report.mode, "gpu");
        assert_eq!(report.ctx_size, 32768);
        assert!(!report.estimated);
    }

    #[test]
    fn recommend_context_is_clamped_by_trained_context() {
        let metadata = GgufMetadata {
            architecture: Some("qwen3".into()),
            block_count: Some(28),
            context_length: Some(8192),
        };
        let report = recommend_launch(
            1_100_000_000,
            Some(&metadata),
            Some("GPU (11943 MiB, 11175 MiB free)"),
            16.0,
        );
        assert_eq!(report.mode, "gpu");
        assert_eq!(report.ctx_size, 8192);
    }

    #[test]
    fn recommend_hybrid_for_large_model_on_moderate_vram() {
        let metadata = GgufMetadata {
            architecture: Some("qwen3moe".into()),
            block_count: Some(48),
            context_length: Some(40960),
        };
        let report = recommend_launch(
            17_600_000_000,
            Some(&metadata),
            Some("NVIDIA GeForce RTX 5070 (11943 MiB, 11175 MiB free)"),
            16.0,
        );
        assert_eq!(report.mode, "hybrid");
        let layers = report.gpu_layers.expect("hybrid layers");
        assert!((1..48).contains(&layers));
        // Leftover VRAM after ~29 offloaded blocks fits the 2048 tier, not 4096.
        assert_eq!(report.ctx_size, 2048);
    }

    #[test]
    fn recommend_cpu_when_no_device_or_tiny_vram() {
        let metadata = GgufMetadata {
            architecture: Some("llama".into()),
            block_count: Some(32),
            context_length: Some(4096),
        };
        let cpu_no_device = recommend_launch(5_000_000_000, Some(&metadata), None, 4.0);
        assert_eq!(cpu_no_device.mode, "cpu");
        assert_eq!(cpu_no_device.ctx_size, 2048);

        let cpu_small_vram = recommend_launch(
            17_600_000_000,
            Some(&metadata),
            Some("GPU (1024 MiB, 900 MiB free)"),
            16.0,
        );
        assert_eq!(cpu_small_vram.mode, "cpu");

        // CPU tier mirrors the runtime_args RAM table: <=3 GB model on low RAM.
        let small_model = GgufMetadata::default();
        let cpu_small = recommend_launch(1_000_000_000, Some(&small_model), None, 2.5);
        assert_eq!(cpu_small.mode, "cpu");
        assert_eq!(cpu_small.ctx_size, 4096);
    }

    #[test]
    fn recommend_without_metadata_is_estimated_with_default_blocks() {
        let report = recommend_launch(
            1_100_000_000,
            None,
            Some("NVIDIA GeForce RTX 5070 (11943 MiB, 11175 MiB free)"),
            16.0,
        );
        assert_eq!(report.mode, "gpu");
        assert!(report.estimated);
        assert_eq!(report.block_count, None);
        assert_eq!(report.architecture, None);
    }
}
