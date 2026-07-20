# UP02-WP01 AssistantContext Schema

## Trusted value

`AssistantContext` is an immutable, application-owned value authored at the Tauri request boundary and strictly validated before provider-message construction.

```yaml
application:
  name: LocalComet
  mode: local_offline_desktop_assistant
  version: v6.84.5.1
conversation:
  locale: ru | en
  project_context_available: false
capabilities:
  local_chat: true
  local_model_inference: true
  internet: false
  email: false
  browser: false
  filesystem: false
  vault: false
  computer_use: false
  shell: false
  tools: []
```

The version is the existing source-proven desktop shell version. The locale is the only per-turn input and is restricted to the existing Settings preference enum. All authority-bearing values are application constants. Missing, extra, wrongly typed, or changed capability fields are rejected. Unknown capability keys never grant authority.

## Deterministic instruction meaning

The system instruction is compact and deterministic. It says that the model is a local assistant operating inside LocalComet, follows the current UI language unless the user explicitly requests another language, describes only enabled capabilities, cannot gain authority from user text, has no project context, does not invent project facts, distinguishes the assistant/model/user/application, may draft without claiming execution, and is concise and practical by default.

## Security properties

- Frontend code can select only `ru` or `en`; it cannot supply capability fields or arbitrary system text.
- The user prompt is carried separately and always follows the system message.
- The provider payload is validated as exactly `[system, user]` for ordinary chat.
- No absolute path, user name, repository location, Vault location, secret, credential, or environment dump is present.
- The context and system instruction are not rendered in chat or included in normal user-visible diagnostics.
- Local loopback inference transport is not an internet capability.

## Safe display projection

Settings may show only localized availability lists. It must not show the system prompt, internal paths, or offer toggles for unavailable capabilities.
