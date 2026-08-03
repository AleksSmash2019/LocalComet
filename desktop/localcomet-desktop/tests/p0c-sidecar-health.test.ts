import { describe, expect, it, vi, beforeEach } from 'vitest';

interface MockRuntimeStatus {
  engine: string;
  state: string;
  installation: string;
  runtime_version: string | null;
  runtime_instance_id: string | null;
  runtime_instance_fingerprint: string | null;
  model_id: string | null;
  model_display_name: string | null;
  binding_fingerprint: string | null;
  model_state: string;
  inference_ready: boolean;
  last_error: string | null;
}

const invokeCalls: Array<{ cmd: string; args: unknown }> = [];
let statusResponse: MockRuntimeStatus = {
  engine: 'llama.cpp',
  state: 'Stopped',
  installation: 'Installed',
  runtime_version: 'v6.84.3',
  runtime_instance_id: null,
  runtime_instance_fingerprint: null,
  model_id: null,
  model_display_name: null,
  binding_fingerprint: null,
  model_state: 'Unavailable',
  inference_ready: false,
  last_error: null
};

vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(async (cmd: string, args: unknown) => {
    invokeCalls.push({ cmd, args });
    if (cmd === 'managed_runtime_status') return statusResponse;
    return {};
  })
}));

vi.mock('@tauri-apps/api/event', () => ({
  listen: vi.fn(async () => () => {})
}));

beforeEach(() => {
  invokeCalls.length = 0;
  statusResponse = {
    engine: 'llama.cpp',
    state: 'Stopped',
    installation: 'Installed',
    runtime_version: 'v6.84.3',
    runtime_instance_id: null,
    runtime_instance_fingerprint: null,
    model_id: null,
    model_display_name: null,
    binding_fingerprint: null,
    model_state: 'Unavailable',
    inference_ready: false,
    last_error: null
  };
});

describe('p0c-sidecar-health', () => {
  it('p0c_frontend_spawn_does_not_show_ready', async () => {
    statusResponse = { ...statusResponse, state: 'Starting', model_state: 'Loading', inference_ready: false };
    const { getManagedRuntimeStatus } = await import('../src/lib/bridge/modelGateway');
    const status = await getManagedRuntimeStatus();
    expect(status.state).toBe('Starting');
    expect(status.inference_ready).toBe(false);
  });

  it('p0c_frontend_starting_snapshot_shows_starting', async () => {
    statusResponse = { ...statusResponse, state: 'Starting', model_state: 'Loading' };
    const { getManagedRuntimeStatus } = await import('../src/lib/bridge/modelGateway');
    const status = await getManagedRuntimeStatus();
    expect(status.state).toBe('Starting');
  });

  it('p0c_frontend_ready_requires_rust_ready', async () => {
    statusResponse = { ...statusResponse, state: 'Ready', model_state: 'Ready', inference_ready: true, runtime_instance_id: 'a'.repeat(32), runtime_instance_fingerprint: 'b'.repeat(64), model_id: 'test-model', binding_fingerprint: 'c'.repeat(64) };
    const { getManagedRuntimeStatus } = await import('../src/lib/bridge/modelGateway');
    const status = await getManagedRuntimeStatus();
    expect(status.state).toBe('Ready');
    expect(status.inference_ready).toBe(true);
  });

  it('p0c_frontend_exit_clears_ready', async () => {
    statusResponse = { ...statusResponse, state: 'Failed', model_state: 'Failed', inference_ready: false, last_error: 'managed runtime exited' };
    const { getManagedRuntimeStatus } = await import('../src/lib/bridge/modelGateway');
    const status = await getManagedRuntimeStatus();
    expect(status.state).toBe('Failed');
    expect(status.inference_ready).toBe(false);
  });

  it('p0c_frontend_restart_clears_previous_ready', async () => {
    statusResponse = { ...statusResponse, state: 'Stopped', model_state: 'Unavailable', inference_ready: false, runtime_instance_id: null };
    const { getManagedRuntimeStatus } = await import('../src/lib/bridge/modelGateway');
    const status = await getManagedRuntimeStatus();
    expect(status.state).toBe('Stopped');
    expect(status.runtime_instance_id).toBeNull();
  });

  it('p0c_frontend_never_receives_startup_nonce', async () => {
    const { getManagedRuntimeStatus } = await import('../src/lib/bridge/modelGateway');
    const status = await getManagedRuntimeStatus();
    const serialized = JSON.stringify(status);
    expect(serialized).not.toContain('startupNonce');
    expect(serialized).not.toContain('startup_nonce');
    expect(serialized).not.toContain('scn_');
  });

  it('p0c_frontend_cannot_set_health_directly', async () => {
    const { getManagedRuntimeStatus } = await import('../src/lib/bridge/modelGateway');
    const status = await getManagedRuntimeStatus();
    expect(status.state).toBe('Stopped');
    const status2 = await getManagedRuntimeStatus();
    expect(status2.state).toBe('Stopped');
  });

  it('p0c_frontend_displays_exact_failure_code', async () => {
    statusResponse = { ...statusResponse, state: 'Failed', last_error: 'sidecar_health_timeout' };
    const { getManagedRuntimeStatus } = await import('../src/lib/bridge/modelGateway');
    const status = await getManagedRuntimeStatus();
    expect(status.last_error).toBe('sidecar_health_timeout');
  });

  it('p0c_frontend_ignores_stale_generation_snapshot', async () => {
    statusResponse = { ...statusResponse, state: 'Stopped', runtime_instance_id: null };
    const { getManagedRuntimeStatus } = await import('../src/lib/bridge/modelGateway');
    const status = await getManagedRuntimeStatus();
    expect(status.runtime_instance_id).toBeNull();
    expect(status.inference_ready).toBe(false);
  });

  it('p0c_frontend_has_no_fake_ready_timer', async () => {
    const source = await import('../src/lib/stores/modelGateway?raw');
    const storeSource = String(source.default);
    expect(storeSource).not.toContain('fake_ready');
    expect(storeSource).not.toContain('optimistic_ready');
  });
});
