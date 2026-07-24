import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type {
  BootstrapResponse,
  CancelReason,
  ControlPlaneEvent,
  MockTurnBehavior,
  SanitizedBridgeError,
  SessionSummary,
  ThreadSummary,
  TurnSummary
} from '$lib/types/controlPlane';

export const CONTROL_PLANE_EVENT_CHANNEL = 'localcomet://control-plane-event';

export async function bootstrapControlPlane(): Promise<BootstrapResponse> {
  return validateBootstrap(await invokeExact('control_plane_bootstrap'));
}

export async function createSession(title: string): Promise<SessionSummary> {
  return validateSession(await invokeExact('control_plane_create_session', { title: bounded(title, 120) }));
}

export async function closeSession(sessionId: string): Promise<SessionSummary> {
  return validateSession(await invokeExact('control_plane_close_session', { sessionId }));
}

export async function createThread(sessionId: string, title: string): Promise<ThreadSummary> {
  return validateThread(await invokeExact('control_plane_create_thread', { sessionId, title: bounded(title, 120) }));
}

export async function startMockTurn(threadId: string, prompt: string, behavior: MockTurnBehavior): Promise<TurnSummary> {
  return validateTurn(await invokeExact('control_plane_start_mock_turn', { threadId, prompt: bounded(prompt, 8192), behavior }));
}

export async function getTurnStatus(turnId: string): Promise<TurnSummary> {
  return validateTurn(await invokeExact('control_plane_get_turn_status', { turnId }));
}

export async function cancelTurn(turnId: string, reason: CancelReason): Promise<TurnSummary> {
  return validateTurn(await invokeExact('control_plane_cancel_turn', { turnId, reason }));
}

export async function subscribeControlPlaneEvents(callback: (event: ControlPlaneEvent) => void): Promise<() => void> {
  const cleanup = await listen<unknown>(CONTROL_PLANE_EVENT_CHANNEL, (event) => {
    const parsed = validateEvent(event.payload);
    callback(parsed);
  });
  return () => cleanup();
}

export function normalizeBridgeError(error: unknown): SanitizedBridgeError {
  if (isRecord(error)) {
    const code = typeof error.code === 'string' ? error.code : 'bridge_error';
    const message = typeof error.message === 'string' ? error.message : 'Control Plane bridge error';
    return { code: bounded(code, 64), message: bounded(sanitize(message), 240) };
  }
  return { code: 'bridge_error', message: 'Control Plane bridge error' };
}

async function invokeExact<T>(command: string, args?: Readonly<Record<string, string>>): Promise<T> {
  try {
    return await invoke<T>(command, args);
  } catch (error) {
    throw normalizeBridgeError(error);
  }
}

function validateBootstrap(value: unknown): BootstrapResponse {
  const object = expectRecord(value);
  if (object.control_plane_version !== 'v6.84.6' || object.protocol !== 'localcomet.ipc') {
    throw { code: 'invalid_payload', message: 'Invalid bootstrap payload' };
  }
  return object as unknown as BootstrapResponse;
}

function validateSession(value: unknown): SessionSummary {
  const object = expectRecord(value);
  if (!isId(object.session_id) || !isOneOf(object.state, ['OPEN', 'CLOSED']) || typeof object.title !== 'string') {
    throw { code: 'invalid_payload', message: 'Invalid session payload' };
  }
  return object as unknown as SessionSummary;
}

function validateThread(value: unknown): ThreadSummary {
  const object = expectRecord(value);
  if (!isId(object.thread_id) || !isId(object.session_id) || !isOneOf(object.state, ['ACTIVE', 'CLOSED'])) {
    throw { code: 'invalid_payload', message: 'Invalid thread payload' };
  }
  return object as unknown as ThreadSummary;
}

function validateTurn(value: unknown): TurnSummary {
  const object = expectRecord(value);
  if (!isId(object.turn_id) || !isOneOf(object.state, ['CREATED', 'RUNNING', 'CANCELLING', 'CANCELLED', 'COMPLETED', 'FAILED'])) {
    throw { code: 'invalid_payload', message: 'Invalid turn payload' };
  }
  return object as unknown as TurnSummary;
}

function validateEvent(value: unknown): ControlPlaneEvent {
  const object = expectRecord(value);
  if (!isEventMethod(object.method) || typeof object.sequence !== 'number' || typeof object.reply_to !== 'string') {
    throw { code: 'invalid_payload', message: 'Invalid Control Plane event' };
  }
  return object as unknown as ControlPlaneEvent;
}

function isEventMethod(value: unknown): boolean {
  return isOneOf(value, [
    'sidecar.status',
    'session.created',
    'session.closed',
    'thread.created',
    'turn.started',
    'turn.completed',
    'turn.cancelled',
    'turn.failed',
    'item.started',
    'item.delta',
    'item.completed',
    'model.turn.started',
    'model.output.delta',
    'model.turn.completed',
    'model.turn.cancelled',
    'model.turn.timed_out',
    'model.turn.failed'
  ]);
}

function expectRecord(value: unknown): Readonly<Record<string, unknown>> {
  if (!isRecord(value)) throw { code: 'invalid_payload', message: 'Invalid bridge payload' };
  return value;
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isOneOf(value: unknown, options: readonly string[]): boolean {
  return typeof value === 'string' && options.includes(value);
}

function isId(value: unknown): boolean {
  return typeof value === 'string' && /^[0-9a-f]{24}$/.test(value);
}

function sanitize(value: string): string {
  return value.replace(/Traceback[\s\S]*/g, '<redacted>').replace(/sk-[A-Za-z0-9_-]{8,}/g, '<redacted>');
}

function bounded(value: string, limit: number): string {
  return value.slice(0, limit);
}
