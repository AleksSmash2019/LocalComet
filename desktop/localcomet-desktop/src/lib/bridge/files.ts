import { invoke } from '@tauri-apps/api/core';
import type {
  FileCapabilityError,
  FileSelectionResponse,
  FilesCapabilityStatus,
  SelectedFilePreview,
  SelectedFileStatus,
  SelectedFileSummary
} from '$lib/types/files';
import { FILE_ID_PATTERN } from '$lib/types/files';

const MAX_FILE_BYTES = 2 * 1024 * 1024;
const MAX_ACTIVE_CONTEXT_BYTES = 5 * 1024 * 1024;
const MAX_SELECTED_FILES = 32;
const PREVIEW_MAX_CHARACTERS = 16_000;
const EXTENSIONS = ['txt', 'md', 'json', 'yaml', 'yml', 'csv', 'log'] as const;
const STATUSES: readonly SelectedFileStatus[] = ['ready', 'missing', 'changed', 'reparse_point', 'unreadable'];
const ABSOLUTE_PATH_RE = /(?:[A-Za-z]:[\\/]|\\\\|\/[A-Za-z0-9._-]+\/)/;

export async function getFilesCapabilityStatus(): Promise<FilesCapabilityStatus> {
  return validateCapabilityStatus(await invokeFiles('files_capability_status'));
}

export async function selectFiles(): Promise<FileSelectionResponse> {
  return validateSelection(await invokeFiles('select_files'));
}

export async function listSelectedFiles(): Promise<readonly SelectedFileSummary[]> {
  return validateFileList(await invokeFiles('list_selected_files'));
}

export async function previewSelectedFile(fileId: string): Promise<SelectedFilePreview> {
  return validatePreview(
    await invokeFiles('preview_selected_file', { fileId: validateFileId(fileId) })
  );
}

export async function forgetSelectedFile(fileId: string): Promise<readonly SelectedFileSummary[]> {
  return validateFileList(
    await invokeFiles('forget_selected_file', { fileId: validateFileId(fileId) })
  );
}

export function normalizeFileError(error: unknown): FileCapabilityError {
  if (isRecord(error)) {
    const code = safeErrorText(error.code, 64, 'LC_FILE_UNREADABLE');
    const message = safeErrorText(error.message, 240, 'Selected file operation failed');
    return { code, message };
  }
  return { code: 'LC_FILE_UNREADABLE', message: 'Selected file operation failed' };
}

async function invokeFiles(command: string, args?: Readonly<Record<string, string>>): Promise<unknown> {
  try {
    return await invoke(command, args);
  } catch (error) {
    throw normalizeFileError(error);
  }
}

function validateCapabilityStatus(value: unknown): FilesCapabilityStatus {
  const object = exactRecord(value, [
    'available',
    'read_only',
    'selection',
    'persistence',
    'supported_extensions',
    'maximum_file_bytes',
    'maximum_active_context_bytes',
    'maximum_selected_files',
    'preview_maximum_characters'
  ]);
  if (
    typeof object.available !== 'boolean' ||
    object.read_only !== true ||
    object.selection !== 'native_system_file_picker_only' ||
    object.persistence !== 'current_process_memory_only' ||
    JSON.stringify(object.supported_extensions) !== JSON.stringify(EXTENSIONS) ||
    object.maximum_file_bytes !== MAX_FILE_BYTES ||
    object.maximum_active_context_bytes !== MAX_ACTIVE_CONTEXT_BYTES ||
    object.maximum_selected_files !== MAX_SELECTED_FILES ||
    object.preview_maximum_characters !== PREVIEW_MAX_CHARACTERS
  ) throw invalidPayload();
  return object as unknown as FilesCapabilityStatus;
}

function validateSelection(value: unknown): FileSelectionResponse {
  const object = exactRecord(value, ['cancelled', 'files']);
  if (typeof object.cancelled !== 'boolean') throw invalidPayload();
  const files = validateFileList(object.files);
  return { cancelled: object.cancelled, files };
}

function validateFileList(value: unknown): readonly SelectedFileSummary[] {
  if (!Array.isArray(value) || value.length > MAX_SELECTED_FILES) throw invalidPayload();
  const ids = new Set<string>();
  return value.map((item) => {
    const file = validateSummary(item);
    if (ids.has(file.file_id)) throw invalidPayload();
    ids.add(file.file_id);
    return file;
  });
}

function validateSummary(value: unknown): SelectedFileSummary {
  const object = exactRecord(value, [
    'file_id',
    'filename',
    'extension',
    'media_type',
    'byte_size',
    'character_count',
    'readable',
    'status',
    'added_at_unix_ms',
    'display_location'
  ]);
  const fileId = validateFileId(object.file_id);
  const filename = safeDisplayText(object.filename, 255);
  const extension = safeDisplayText(object.extension, 8).toLowerCase();
  const mediaType = safeDisplayText(object.media_type, 32);
  const displayLocation = safeDisplayText(object.display_location, 520);
  const byteSize = safeInteger(object.byte_size, 0, MAX_FILE_BYTES);
  const characterCount = safeInteger(object.character_count, 0, MAX_FILE_BYTES);
  const addedAt = safeInteger(object.added_at_unix_ms, 1, Number.MAX_SAFE_INTEGER);
  if (
    !EXTENSIONS.includes(extension as (typeof EXTENSIONS)[number]) ||
    !filename.toLowerCase().endsWith(`.${extension}`) ||
    ABSOLUTE_PATH_RE.test(filename) ||
    ABSOLUTE_PATH_RE.test(displayLocation) ||
    typeof object.readable !== 'boolean' ||
    !STATUSES.includes(object.status as SelectedFileStatus) ||
    (object.readable !== (object.status === 'ready'))
  ) throw invalidPayload();
  return {
    file_id: fileId,
    filename,
    extension,
    media_type: mediaType,
    byte_size: byteSize,
    character_count: characterCount,
    readable: object.readable,
    status: object.status as SelectedFileStatus,
    added_at_unix_ms: addedAt,
    display_location: displayLocation
  };
}

function validatePreview(value: unknown): SelectedFilePreview {
  const object = exactRecord(value, [
    'file_id',
    'filename',
    'content',
    'original_bytes',
    'original_characters',
    'displayed_bytes',
    'displayed_characters',
    'truncated'
  ]);
  const content = typeof object.content === 'string' ? object.content : invalidPayload();
  const displayedBytes = safeInteger(object.displayed_bytes, 0, MAX_FILE_BYTES);
  const displayedCharacters = safeInteger(object.displayed_characters, 0, PREVIEW_MAX_CHARACTERS);
  if (
    new TextEncoder().encode(content).length !== displayedBytes ||
    [...content].length !== displayedCharacters ||
    typeof object.truncated !== 'boolean'
  ) throw invalidPayload();
  const originalBytes = safeInteger(object.original_bytes, displayedBytes, MAX_FILE_BYTES);
  const originalCharacters = safeInteger(object.original_characters, displayedCharacters, MAX_FILE_BYTES);
  if (object.truncated !== (displayedBytes < originalBytes)) throw invalidPayload();
  return {
    file_id: validateFileId(object.file_id),
    filename: safeDisplayText(object.filename, 255),
    content,
    original_bytes: originalBytes,
    original_characters: originalCharacters,
    displayed_bytes: displayedBytes,
    displayed_characters: displayedCharacters,
    truncated: object.truncated
  };
}

function validateFileId(value: unknown): string {
  if (typeof value !== 'string' || !FILE_ID_PATTERN.test(value)) throw invalidPayload();
  return value;
}

function exactRecord(value: unknown, keys: readonly string[]): Readonly<Record<string, unknown>> {
  if (!isRecord(value)) throw invalidPayload();
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    throw invalidPayload();
  }
  return value;
}

function isRecord(value: unknown): value is Readonly<Record<string, unknown>> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function safeDisplayText(value: unknown, maximum: number): string {
  if (typeof value !== 'string' || !value || value.length > maximum || /[\0\r\n]/.test(value)) {
    throw invalidPayload();
  }
  return value;
}

function safeErrorText(value: unknown, maximum: number, fallback: string): string {
  if (typeof value !== 'string') return fallback;
  const clean = value.replace(/[\0\r\n]/g, ' ').trim().slice(0, maximum);
  return clean || fallback;
}

function safeInteger(value: unknown, minimum: number, maximum: number): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < minimum || value > maximum) {
    throw invalidPayload();
  }
  return value;
}

function invalidPayload(): never {
  throw { code: 'invalid_payload', message: 'Invalid Files capability payload' };
}
