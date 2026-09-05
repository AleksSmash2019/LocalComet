import { invoke } from '@tauri-apps/api/core';

/**
 * Read-only hardware snapshot for fit verdicts. Mirrors the Rust RawHardware
 * contract (hardware.rs): system disk (C:) carries the managed model root, so
 * its free space decides whether a download fits.
 */
export interface DiskPart {
  readonly free_bytes: number;
  readonly total_bytes: number;
  readonly kind: string | null;
  readonly is_system: boolean;
}

export interface RawHardware {
  readonly os: Record<string, unknown>;
  readonly cpu: Record<string, unknown>;
  readonly memory: { readonly total_bytes: number; readonly available_bytes: number };
  readonly gpus: ReadonlyArray<{ readonly name: string; readonly vram_mb: number | null; readonly integrated: boolean | null }>;
  readonly disks: readonly DiskPart[];
}

export async function scanHardwareSnapshot(): Promise<RawHardware> {
  return validateHardware(await invoke<unknown>('scan_hardware'));
}

function validateHardware(value: unknown): RawHardware {
  if (typeof value !== 'object' || value === null) throw new Error('invalid hardware payload');
  const record = value as Record<string, unknown>;
  const disks = record.disks;
  if (!Array.isArray(disks)) throw new Error('invalid hardware payload');
  return value as RawHardware;
}

export function systemDiskFreeBytes(hardware: RawHardware): number | null {
  const system = hardware.disks.find((disk) => disk.is_system) ?? hardware.disks[0];
  return system ? system.free_bytes : null;
}
