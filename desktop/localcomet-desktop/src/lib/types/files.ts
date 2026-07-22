export const FILE_ID_PATTERN = /^[0-9a-f]{64}$/;

export type SelectedFileStatus = 'ready' | 'missing' | 'changed' | 'reparse_point' | 'unreadable';

export interface FilesCapabilityStatus {
  readonly available: boolean;
  readonly read_only: true;
  readonly selection: 'native_system_file_picker_only';
  readonly persistence: 'current_process_memory_only';
  readonly supported_extensions: readonly ['txt', 'md', 'json', 'yaml', 'yml', 'csv', 'log'];
  readonly maximum_file_bytes: number;
  readonly maximum_active_context_bytes: number;
  readonly maximum_selected_files: number;
  readonly preview_maximum_characters: number;
}

export interface SelectedFileSummary {
  readonly file_id: string;
  readonly filename: string;
  readonly extension: string;
  readonly media_type: string;
  readonly byte_size: number;
  readonly character_count: number;
  readonly readable: boolean;
  readonly status: SelectedFileStatus;
  readonly added_at_unix_ms: number;
  readonly display_location: string;
}

export interface FileSelectionResponse {
  readonly cancelled: boolean;
  readonly files: readonly SelectedFileSummary[];
}

export interface SelectedFilePreview {
  readonly file_id: string;
  readonly filename: string;
  readonly content: string;
  readonly original_bytes: number;
  readonly original_characters: number;
  readonly displayed_bytes: number;
  readonly displayed_characters: number;
  readonly truncated: boolean;
}

export interface FileCapabilityError {
  readonly code: string;
  readonly message: string;
}

export interface FileContextInclusion {
  readonly file_id: string;
  readonly filename: string;
  readonly original_bytes: number;
  readonly original_characters: number;
  readonly included_bytes: number;
  readonly included_characters: number;
  readonly inclusion: 'full' | 'bounded_excerpt';
}

export interface FilesContextReport {
  readonly source_bytes: number;
  readonly source_characters: number;
  readonly included_bytes: number;
  readonly included_characters: number;
  readonly truncated: boolean;
  readonly files: readonly FileContextInclusion[];
}
