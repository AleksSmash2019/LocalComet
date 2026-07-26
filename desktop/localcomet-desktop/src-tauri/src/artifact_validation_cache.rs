use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};

const CACHE_FORMAT_VERSION: u32 = 1;
const CACHE_RELATIVE_PATH: &str = "state/artifact-validation-cache.json";

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub(crate) struct ArtifactValidationCacheEntry {
    pub path_canonical: String,
    pub file_size: u64,
    pub mtime_unix_nanos: u128,
    pub expected_sha256: String,
    pub observed_sha256: String,
    pub catalog_digest: String,
    pub verified_at_unix: u64,
    pub cache_format_version: u32,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum ValidationSource {
    Cached,
    Hashed,
}

impl ValidationSource {
    pub(crate) fn combine(self, other: Self) -> Self {
        if self == Self::Hashed || other == Self::Hashed {
            Self::Hashed
        } else {
            Self::Cached
        }
    }
}

#[derive(Debug)]
pub(crate) struct ValidatedHash {
    pub observed_sha256: String,
    pub source: ValidationSource,
}

#[derive(Debug)]
pub(crate) struct ArtifactValidationCache {
    path: PathBuf,
    entries: Mutex<Vec<ArtifactValidationCacheEntry>>,
}

impl ArtifactValidationCache {
    pub(crate) fn new(application_data_root: &Path, catalog_digest: &str) -> Self {
        let path = application_data_root.join(CACHE_RELATIVE_PATH);
        let mut entries = load_entries(&path);
        let original_len = entries.len();
        entries.retain(|entry| entry.catalog_digest == catalog_digest);
        let cache = Self {
            path,
            entries: Mutex::new(entries),
        };
        if original_len != cache.entries().len() {
            cache.persist();
        }
        cache
    }

    pub(crate) fn hash_or_reuse<E, F>(
        &self,
        path: &Path,
        expected_sha256: &str,
        catalog_digest: &str,
        force_full_validation: bool,
        hasher: F,
    ) -> Result<ValidatedHash, E>
    where
        F: FnOnce(&Path) -> Result<String, E>,
    {
        let identity = file_identity(path);
        if !force_full_validation {
            if let Some(identity) = identity.as_ref() {
                if let Some(entry) = self.entries().iter().find(|entry| {
                    entry.cache_format_version == CACHE_FORMAT_VERSION
                        && entry.catalog_digest == catalog_digest
                        && entry.path_canonical == identity.path_canonical
                        && entry.file_size == identity.file_size
                        && entry.mtime_unix_nanos == identity.mtime_unix_nanos
                        && entry.expected_sha256 == expected_sha256
                        && entry.observed_sha256 == expected_sha256
                }) {
                    return Ok(ValidatedHash {
                        observed_sha256: entry.observed_sha256.clone(),
                        source: ValidationSource::Cached,
                    });
                }
            }
        }

        let observed_sha256 = hasher(path)?;
        if let (Some(before), Some(after)) = (identity, file_identity(path)) {
            if before == after {
                let mut entries = self.entries();
                entries.retain(|entry| entry.path_canonical != after.path_canonical);
                entries.push(ArtifactValidationCacheEntry {
                    path_canonical: after.path_canonical,
                    file_size: after.file_size,
                    mtime_unix_nanos: after.mtime_unix_nanos,
                    expected_sha256: expected_sha256.to_string(),
                    observed_sha256: observed_sha256.clone(),
                    catalog_digest: catalog_digest.to_string(),
                    verified_at_unix: now_unix(),
                    cache_format_version: CACHE_FORMAT_VERSION,
                });
                drop(entries);
                self.persist();
            }
        }
        Ok(ValidatedHash {
            observed_sha256,
            source: ValidationSource::Hashed,
        })
    }

    pub(crate) fn invalidate_path(&self, path: &Path) {
        let Some(path_canonical) = canonical_path_for_cache(path) else {
            return;
        };
        let mut entries = self.entries();
        let original_len = entries.len();
        entries.retain(|entry| entry.path_canonical != path_canonical);
        let changed = original_len != entries.len();
        drop(entries);
        if changed {
            self.persist();
        }
    }

    fn entries(&self) -> std::sync::MutexGuard<'_, Vec<ArtifactValidationCacheEntry>> {
        self.entries
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    fn persist(&self) {
        let entries = self.entries().clone();
        let Ok(bytes) = serde_json::to_vec(&entries) else {
            return;
        };
        let Some(parent) = self.path.parent() else {
            return;
        };
        if fs::create_dir_all(parent).is_err() {
            return;
        }
        let temp = self.path.with_extension("json.tmp");
        if fs::write(&temp, bytes).is_err() {
            return;
        }
        if replace_file(&temp, &self.path).is_err() {
            let _ = fs::remove_file(&temp);
        }
    }
}

#[derive(Debug, Eq, PartialEq)]
struct FileIdentity {
    path_canonical: String,
    file_size: u64,
    mtime_unix_nanos: u128,
}

fn file_identity(path: &Path) -> Option<FileIdentity> {
    let path_canonical = canonical_path_for_cache(path)?;
    let metadata = fs::metadata(path).ok()?;
    if !metadata.is_file() {
        return None;
    }
    let mtime_unix_nanos = metadata
        .modified()
        .ok()?
        .duration_since(UNIX_EPOCH)
        .ok()?
        .as_nanos();
    Some(FileIdentity {
        path_canonical,
        file_size: metadata.len(),
        mtime_unix_nanos,
    })
}

fn canonical_path_for_cache(path: &Path) -> Option<String> {
    if let Ok(canonical) = fs::canonicalize(path) {
        return canonical.to_str().map(str::to_string);
    }
    let parent = fs::canonicalize(path.parent()?).ok()?;
    parent.join(path.file_name()?).to_str().map(str::to_string)
}

fn load_entries(path: &Path) -> Vec<ArtifactValidationCacheEntry> {
    let Ok(bytes) = fs::read(path) else {
        return Vec::new();
    };
    let Ok(entries) = serde_json::from_slice::<Vec<ArtifactValidationCacheEntry>>(&bytes) else {
        return Vec::new();
    };
    if entries
        .iter()
        .any(|entry| entry.cache_format_version != CACHE_FORMAT_VERSION)
    {
        return Vec::new();
    }
    entries
}

fn now_unix() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_secs())
        .unwrap_or(0)
}

#[cfg(windows)]
fn replace_file(temp: &Path, destination: &Path) -> std::io::Result<()> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::Storage::FileSystem::{
        MoveFileExW, MOVEFILE_REPLACE_EXISTING, MOVEFILE_WRITE_THROUGH,
    };

    let mut temp_wide: Vec<u16> = temp.as_os_str().encode_wide().collect();
    temp_wide.push(0);
    let mut destination_wide: Vec<u16> = destination.as_os_str().encode_wide().collect();
    destination_wide.push(0);
    let result = unsafe {
        MoveFileExW(
            temp_wide.as_ptr(),
            destination_wide.as_ptr(),
            MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH,
        )
    };
    if result == 0 {
        Err(std::io::Error::last_os_error())
    } else {
        Ok(())
    }
}

#[cfg(not(windows))]
fn replace_file(temp: &Path, destination: &Path) -> std::io::Result<()> {
    fs::rename(temp, destination)
}

#[cfg(test)]
mod tests {
    use super::*;
    use sha2::{Digest, Sha256};
    use std::fs::{File, FileTimes};
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::Duration;

    static TEST_SEQUENCE: AtomicU64 = AtomicU64::new(0);

    struct TestWorkspace(PathBuf);

    impl TestWorkspace {
        fn new() -> Self {
            let sequence = TEST_SEQUENCE.fetch_add(1, Ordering::Relaxed);
            let path = std::env::temp_dir().join(format!(
                "localcomet-validation-cache-{}-{sequence}",
                std::process::id()
            ));
            fs::create_dir_all(&path).expect("create cache workspace");
            Self(path)
        }
    }

    impl Drop for TestWorkspace {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn hash(path: &Path) -> Result<String, ()> {
        Ok(format!(
            "{:x}",
            Sha256::digest(fs::read(path).map_err(|_| ())?)
        ))
    }

    #[test]
    fn valid_cache_hit_does_not_invoke_hasher() {
        let workspace = TestWorkspace::new();
        let file = workspace.0.join("model.gguf");
        fs::write(&file, b"GGUF-cache").expect("write fixture");
        let expected = hash(&file).expect("hash fixture");
        let cache = ArtifactValidationCache::new(&workspace.0, "catalog-a");
        let first = cache
            .hash_or_reuse(&file, &expected, "catalog-a", false, hash)
            .expect("populate cache");
        assert_eq!(first.source, ValidationSource::Hashed);

        let calls = AtomicU64::new(0);
        let second = cache
            .hash_or_reuse(&file, &expected, "catalog-a", false, |_| {
                calls.fetch_add(1, Ordering::Relaxed);
                Err::<String, ()>(())
            })
            .expect("cache hit");
        assert_eq!(second.source, ValidationSource::Cached);
        assert_eq!(calls.load(Ordering::Relaxed), 0);
    }

    #[test]
    fn catalog_digest_change_invalidates_all_entries() {
        let workspace = TestWorkspace::new();
        let file = workspace.0.join("model.gguf");
        fs::write(&file, b"GGUF-cache").expect("write fixture");
        let expected = hash(&file).expect("hash fixture");
        ArtifactValidationCache::new(&workspace.0, "catalog-a")
            .hash_or_reuse(&file, &expected, "catalog-a", false, hash)
            .expect("populate cache");

        let cache = ArtifactValidationCache::new(&workspace.0, "catalog-b");
        let calls = AtomicU64::new(0);
        let result = cache
            .hash_or_reuse(&file, &expected, "catalog-b", false, |path| {
                calls.fetch_add(1, Ordering::Relaxed);
                hash(path)
            })
            .expect("rehash after catalog change");
        assert_eq!(result.source, ValidationSource::Hashed);
        assert_eq!(calls.load(Ordering::Relaxed), 1);
    }

    #[test]
    fn corrupt_json_is_ignored_and_rehashed() {
        let workspace = TestWorkspace::new();
        let cache_path = workspace.0.join(CACHE_RELATIVE_PATH);
        fs::create_dir_all(cache_path.parent().expect("cache parent")).expect("create state");
        fs::write(&cache_path, b"{broken").expect("write corrupt cache");
        let file = workspace.0.join("model.gguf");
        fs::write(&file, b"GGUF-cache").expect("write fixture");
        let expected = hash(&file).expect("hash fixture");
        let calls = AtomicU64::new(0);
        let result = ArtifactValidationCache::new(&workspace.0, "catalog-a")
            .hash_or_reuse(&file, &expected, "catalog-a", false, |path| {
                calls.fetch_add(1, Ordering::Relaxed);
                hash(path)
            })
            .expect("rehash corrupt cache");
        assert_eq!(result.source, ValidationSource::Hashed);
        assert_eq!(calls.load(Ordering::Relaxed), 1);
    }

    #[test]
    fn same_size_changed_mtime_rehashes_and_rejects_tampered_bytes() {
        let workspace = TestWorkspace::new();
        let file = workspace.0.join("model.gguf");
        fs::write(&file, b"GGUF-cache").expect("write fixture");
        let expected = hash(&file).expect("hash fixture");
        let original_mtime = fs::metadata(&file)
            .and_then(|metadata| metadata.modified())
            .expect("fixture mtime");
        let cache = ArtifactValidationCache::new(&workspace.0, "catalog-a");
        cache
            .hash_or_reuse(&file, &expected, "catalog-a", false, hash)
            .expect("populate cache");

        fs::write(&file, b"GGUF-tampr").expect("replace same-size fixture");
        File::options()
            .write(true)
            .open(&file)
            .and_then(|file| {
                file.set_times(
                    FileTimes::new().set_modified(original_mtime + Duration::from_secs(2)),
                )
            })
            .expect("set changed mtime");
        let calls = AtomicU64::new(0);
        let result = cache
            .hash_or_reuse(&file, &expected, "catalog-a", false, |path| {
                calls.fetch_add(1, Ordering::Relaxed);
                hash(path)
            })
            .expect("rehash tampered fixture");

        assert_eq!(result.source, ValidationSource::Hashed);
        assert_eq!(calls.load(Ordering::Relaxed), 1);
        assert_ne!(result.observed_sha256, expected);
    }

    #[test]
    fn same_size_tamper_with_restored_mtime_hits_documented_cache_boundary() {
        let workspace = TestWorkspace::new();
        let file = workspace.0.join("model.gguf");
        fs::write(&file, b"GGUF-cache").expect("write fixture");
        let expected = hash(&file).expect("hash fixture");
        let original_mtime = fs::metadata(&file)
            .and_then(|metadata| metadata.modified())
            .expect("fixture mtime");
        let cache = ArtifactValidationCache::new(&workspace.0, "catalog-a");
        cache
            .hash_or_reuse(&file, &expected, "catalog-a", false, hash)
            .expect("populate cache");

        fs::write(&file, b"GGUF-tampr").expect("replace same-size fixture");
        File::options()
            .write(true)
            .open(&file)
            .and_then(|file| file.set_times(FileTimes::new().set_modified(original_mtime)))
            .expect("restore mtime");
        let calls = AtomicU64::new(0);
        let result = cache
            .hash_or_reuse(&file, &expected, "catalog-a", false, |_| {
                calls.fetch_add(1, Ordering::Relaxed);
                Err::<String, ()>(())
            })
            .expect("metadata-identical cache hit");

        assert_eq!(result.source, ValidationSource::Cached);
        assert_eq!(result.observed_sha256, expected);
        assert_eq!(calls.load(Ordering::Relaxed), 0);
    }

    #[test]
    fn force_full_validation_rehashes_valid_entry() {
        let workspace = TestWorkspace::new();
        let file = workspace.0.join("model.gguf");
        fs::write(&file, b"GGUF-cache").expect("write fixture");
        let expected = hash(&file).expect("hash fixture");
        let cache = ArtifactValidationCache::new(&workspace.0, "catalog-a");
        cache
            .hash_or_reuse(&file, &expected, "catalog-a", false, hash)
            .expect("populate cache");
        let calls = AtomicU64::new(0);
        let result = cache
            .hash_or_reuse(&file, &expected, "catalog-a", true, |path| {
                calls.fetch_add(1, Ordering::Relaxed);
                hash(path)
            })
            .expect("forced rehash");

        assert_eq!(result.source, ValidationSource::Hashed);
        assert_eq!(calls.load(Ordering::Relaxed), 1);
    }
}
