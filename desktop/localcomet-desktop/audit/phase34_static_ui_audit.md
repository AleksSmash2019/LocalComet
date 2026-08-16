# Phase 34 static UI audit

Components scanned: 50
Buttons scanned: 110
Fields scanned: 23
Buttons with click/change handlers: 108

## Buttons without a direct handler
- src/lib/components/common/CommandPalette.svelte:182 class='' type='button'

## Icon/toggle buttons without aria-label/title
- src/lib/components/chat/MessageComposer.svelte:133 class='composer-icon-button'
- src/lib/components/chat/MessageComposer.svelte:137 class='composer-icon-button'
- src/lib/components/chat/MessageComposer.svelte:157 class='composer-icon-button'
- src/lib/components/model/ModelSetupDrawer.svelte:148 class='icon-button'
- src/lib/components/shell/ChatHeader.svelte:35 class='icon-button sidebar-toggle'
- src/lib/components/shell/ChatHeader.svelte:68 class='icon-button'
- src/lib/components/shell/PermissionsSection.svelte:45 class='toggle-switch'
- src/lib/components/shell/PermissionsSection.svelte:68 class='toggle-switch'
- src/lib/components/shell/PermissionsSection.svelte:91 class='toggle-switch'
- src/lib/components/shell/PermissionsSection.svelte:114 class='toggle-switch'
- src/lib/components/shell/PermissionsSection.svelte:137 class='toggle-switch'
- src/lib/components/shell/SettingsPanel.svelte:153 class='diagnostics-toggle'
