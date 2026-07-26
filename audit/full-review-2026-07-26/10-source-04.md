# Полный исходный код (продолжение)

### ПУТЬ: desktop/localcomet-desktop/src-tauri/gen/schemas/windows-schema.json (2526 строк, 127701 байт)

````json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CapabilityFile",
  "description": "Capability formats accepted in a capability file.",
  "anyOf": [
    {
      "description": "A single capability.",
      "allOf": [
        {
          "$ref": "#/definitions/Capability"
        }
      ]
    },
    {
      "description": "A list of capabilities.",
      "type": "array",
      "items": {
        "$ref": "#/definitions/Capability"
      }
    },
    {
      "description": "A list of capabilities.",
      "type": "object",
      "required": [
        "capabilities"
      ],
      "properties": {
        "capabilities": {
          "description": "The list of capabilities.",
          "type": "array",
          "items": {
            "$ref": "#/definitions/Capability"
          }
        }
      }
    }
  ],
  "definitions": {
    "Capability": {
      "description": "A grouping and boundary mechanism developers can use to isolate access to the IPC layer.\n\nIt controls application windows' and webviews' fine grained access to the Tauri core, application, or plugin commands. If a webview or its window is not matching any capability then it has no access to the IPC layer at all.\n\nThis can be done to create groups of windows, based on their required system access, which can reduce impact of frontend vulnerabilities in less privileged windows. Windows can be added to a capability by exact name (e.g. `main-window`) or glob patterns like `*` or `admin-*`. A Window can have none, one, or multiple associated capabilities.\n\n## Example\n\n```json { \"identifier\": \"main-user-files-write\", \"description\": \"This capability allows the `main` window on macOS and Windows access to `filesystem` write related commands and `dialog` commands to enable programmatic access to files selected by the user.\", \"windows\": [ \"main\" ], \"permissions\": [ \"core:default\", \"dialog:open\", { \"identifier\": \"fs:allow-write-text-file\", \"allow\": [{ \"path\": \"$HOME/test.txt\" }] }, ], \"platforms\": [\"macOS\",\"windows\"] } ```",
      "type": "object",
      "required": [
        "identifier",
        "permissions"
      ],
      "properties": {
        "identifier": {
          "description": "Identifier of the capability.\n\n## Example\n\n`main-user-files-write`",
          "type": "string"
        },
        "description": {
          "description": "Description of what the capability is intended to allow on associated windows.\n\nIt should contain a description of what the grouped permissions should allow.\n\n## Example\n\nThis capability allows the `main` window access to `filesystem` write related commands and `dialog` commands to enable programmatic access to files selected by the user.",
          "default": "",
          "type": "string"
        },
        "remote": {
          "description": "Configure remote URLs that can use the capability permissions.\n\nThis setting is optional and defaults to not being set, as our default use case is that the content is served from our local application.\n\n:::caution Make sure you understand the security implications of providing remote sources with local system access. :::\n\n## Example\n\n```json { \"urls\": [\"https://*.mydomain.dev\"] } ```",
          "anyOf": [
            {
              "$ref": "#/definitions/CapabilityRemote"
            },
            {
              "type": "null"
            }
          ]
        },
        "local": {
          "description": "Whether this capability is enabled for local app URLs or not. Defaults to `true`.",
          "default": true,
          "type": "boolean"
        },
        "windows": {
          "description": "List of windows that are affected by this capability. Can be a glob pattern.\n\nIf a window label matches any of the patterns in this list, the capability will be enabled on all the webviews of that window, regardless of the value of [`Self::webviews`].\n\nOn multiwebview windows, prefer specifying [`Self::webviews`] and omitting [`Self::windows`] for a fine grained access control.\n\n## Example\n\n`[\"main\"]`",
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "webviews": {
          "description": "List of webviews that are affected by this capability. Can be a glob pattern.\n\nThe capability will be enabled on all the webviews whose label matches any of the patterns in this list, regardless of whether the webview's window label matches a pattern in [`Self::windows`].\n\n## Example\n\n`[\"sub-webview-one\", \"sub-webview-two\"]`",
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "permissions": {
          "description": "List of permissions attached to this capability.\n\nMust include the plugin name as prefix in the form of `${plugin-name}:${permission-name}`. For commands directly implemented in the application itself only `${permission-name}` is required.\n\n## Example\n\n```json [ \"core:default\", \"shell:allow-open\", \"dialog:open\", { \"identifier\": \"fs:allow-write-text-file\", \"allow\": [{ \"path\": \"$HOME/test.txt\" }] } ] ```",
          "type": "array",
          "items": {
            "$ref": "#/definitions/PermissionEntry"
          },
          "uniqueItems": true
        },
        "platforms": {
          "description": "Limit which target platforms this capability applies to.\n\nBy default all platforms are targeted.\n\n## Example\n\n`[\"macOS\",\"windows\"]`",
          "type": [
            "array",
            "null"
          ],
          "items": {
            "$ref": "#/definitions/Target"
          }
        }
      }
    },
    "CapabilityRemote": {
      "description": "Configuration for remote URLs that are associated with the capability.",
      "type": "object",
      "required": [
        "urls"
      ],
      "properties": {
        "urls": {
          "description": "Remote domains this capability refers to using the [URLPattern standard](https://urlpattern.spec.whatwg.org/).\n\n## Examples\n\n- \"https://*.mydomain.dev\": allows subdomains of mydomain.dev - \"https://mydomain.dev/api/*\": allows any subpath of mydomain.dev/api",
          "type": "array",
          "items": {
            "type": "string"
          }
        }
      }
    },
    "PermissionEntry": {
      "description": "An entry for a permission value in a [`Capability`] can be either a raw permission [`Identifier`] or an object that references a permission and extends its scope.",
      "anyOf": [
        {
          "description": "Reference a permission or permission set by identifier.",
          "allOf": [
            {
              "$ref": "#/definitions/Identifier"
            }
          ]
        },
        {
          "description": "Reference a permission or permission set by identifier and extends its scope.",
          "type": "object",
          "allOf": [
            {
              "properties": {
                "identifier": {
                  "description": "Identifier of the permission or permission set.",
                  "allOf": [
                    {
                      "$ref": "#/definitions/Identifier"
                    }
                  ]
                },
                "allow": {
                  "description": "Data that defines what is allowed by the scope.",
                  "type": [
                    "array",
                    "null"
                  ],
                  "items": {
                    "$ref": "#/definitions/Value"
                  }
                },
                "deny": {
                  "description": "Data that defines what is denied by the scope. This should be prioritized by validation logic.",
                  "type": [
                    "array",
                    "null"
                  ],
                  "items": {
                    "$ref": "#/definitions/Value"
                  }
                }
              }
            }
          ],
          "required": [
            "identifier"
          ]
        }
      ]
    },
    "Identifier": {
      "description": "Permission identifier",
      "oneOf": [
        {
          "description": "Allow cancelling one bounded LocalComet artifact download.",
          "type": "string",
          "const": "allow-cancel-artifact-download",
          "markdownDescription": "Allow cancelling one bounded LocalComet artifact download."
        },
        {
          "description": "Allow LocalComet control-plane bootstrap.",
          "type": "string",
          "const": "allow-control-plane-bootstrap",
          "markdownDescription": "Allow LocalComet control-plane bootstrap."
        },
        {
          "description": "Allow cancelling a LocalComet control-plane turn.",
          "type": "string",
          "const": "allow-control-plane-cancel-turn",
          "markdownDescription": "Allow cancelling a LocalComet control-plane turn."
        },
        {
          "description": "Allow closing a LocalComet control-plane session.",
          "type": "string",
          "const": "allow-control-plane-close-session",
          "markdownDescription": "Allow closing a LocalComet control-plane session."
        },
        {
          "description": "Allow creating a LocalComet control-plane session.",
          "type": "string",
          "const": "allow-control-plane-create-session",
          "markdownDescription": "Allow creating a LocalComet control-plane session."
        },
        {
          "description": "Allow creating a LocalComet control-plane thread.",
          "type": "string",
          "const": "allow-control-plane-create-thread",
          "markdownDescription": "Allow creating a LocalComet control-plane thread."
        },
        {
          "description": "Allow reading LocalComet control-plane turn status.",
          "type": "string",
          "const": "allow-control-plane-get-turn-status",
          "markdownDescription": "Allow reading LocalComet control-plane turn status."
        },
        {
          "description": "Allow starting a mock LocalComet control-plane turn.",
          "type": "string",
          "const": "allow-control-plane-start-mock-turn",
          "markdownDescription": "Allow starting a mock LocalComet control-plane turn."
        },
        {
          "description": "Allow reading the fixed read-only Files capability contract.",
          "type": "string",
          "const": "allow-files-capability-status",
          "markdownDescription": "Allow reading the fixed read-only Files capability contract."
        },
        {
          "description": "Allow revoking one backend-issued opaque file identity from the current process.",
          "type": "string",
          "const": "allow-forget-selected-file",
          "markdownDescription": "Allow revoking one backend-issued opaque file identity from the current process."
        },
        {
          "description": "Allow reading one bounded LocalComet artifact download state.",
          "type": "string",
          "const": "allow-get-artifact-download-state",
          "markdownDescription": "Allow reading one bounded LocalComet artifact download state."
        },
        {
          "description": "Allow creating one bounded in-memory human review decision artifact.",
          "type": "string",
          "const": "allow-knowledge-review-decision-create",
          "markdownDescription": "Allow creating one bounded in-memory human review decision artifact."
        },
        {
          "description": "Allow reading one exact bounded knowledge review projection.",
          "type": "string",
          "const": "allow-knowledge-review-get",
          "markdownDescription": "Allow reading one exact bounded knowledge review projection."
        },
        {
          "description": "Allow listing bounded read-only knowledge review summaries.",
          "type": "string",
          "const": "allow-knowledge-review-list",
          "markdownDescription": "Allow listing bounded read-only knowledge review summaries."
        },
        {
          "description": "Allow refreshing read-only LocalComet knowledge review freshness state.",
          "type": "string",
          "const": "allow-knowledge-review-refresh",
          "markdownDescription": "Allow refreshing read-only LocalComet knowledge review freshness state."
        },
        {
          "description": "Allow reading the bounded LocalComet knowledge review inbox snapshot.",
          "type": "string",
          "const": "allow-knowledge-review-snapshot",
          "markdownDescription": "Allow reading the bounded LocalComet knowledge review inbox snapshot."
        },
        {
          "description": "Allow one bounded user decision for an exact project-knowledge preview.",
          "type": "string",
          "const": "allow-knowledge-turn-decide",
          "markdownDescription": "Allow one bounded user decision for an exact project-knowledge preview."
        },
        {
          "description": "Allow preparing one bounded project-knowledge preview for an existing Turn.",
          "type": "string",
          "const": "allow-knowledge-turn-preview",
          "markdownDescription": "Allow preparing one bounded project-knowledge preview for an existing Turn."
        },
        {
          "description": "Allow reading the fixed approved LocalComet acquisition catalog projection.",
          "type": "string",
          "const": "allow-list-approved-downloadable-artifacts",
          "markdownDescription": "Allow reading the fixed approved LocalComet acquisition catalog projection."
        },
        {
          "description": "Allow listing sanitized metadata for the current in-memory selected-file registry.",
          "type": "string",
          "const": "allow-list-selected-files",
          "markdownDescription": "Allow listing sanitized metadata for the current in-memory selected-file registry."
        },
        {
          "description": "Allow reading live validation status for one LocalComet catalog artifact ID.",
          "type": "string",
          "const": "allow-managed-artifact-validation-status",
          "markdownDescription": "Allow reading live validation status for one LocalComet catalog artifact ID."
        },
        {
          "description": "Allow reading live validated installed artifact metadata derived from the LocalComet artifact catalog.",
          "type": "string",
          "const": "allow-managed-installed-artifacts",
          "markdownDescription": "Allow reading live validated installed artifact metadata derived from the LocalComet artifact catalog."
        },
        {
          "description": "Allow reading safe approved model metadata from the immutable LocalComet artifact catalog.",
          "type": "string",
          "const": "allow-managed-model-catalog",
          "markdownDescription": "Allow reading safe approved model metadata from the immutable LocalComet artifact catalog."
        },
        {
          "description": "Allow reading runtime compatibility and readiness for one LocalComet catalog model ID.",
          "type": "string",
          "const": "allow-managed-model-readiness",
          "markdownDescription": "Allow reading runtime compatibility and readiness for one LocalComet catalog model ID."
        },
        {
          "description": "Allow reading safe approved runtime metadata from the immutable LocalComet artifact catalog.",
          "type": "string",
          "const": "allow-managed-runtime-catalog",
          "markdownDescription": "Allow reading safe approved runtime metadata from the immutable LocalComet artifact catalog."
        },
        {
          "description": "Allow reading bounded sanitized managed runtime log tails.",
          "type": "string",
          "const": "allow-managed-runtime-logs",
          "markdownDescription": "Allow reading bounded sanitized managed runtime log tails."
        },
        {
          "description": "Allow starting the fixed LocalComet managed llama.cpp runtime.",
          "type": "string",
          "const": "allow-managed-runtime-start",
          "markdownDescription": "Allow starting the fixed LocalComet managed llama.cpp runtime."
        },
        {
          "description": "Allow reading sanitized LocalComet managed runtime status.",
          "type": "string",
          "const": "allow-managed-runtime-status",
          "markdownDescription": "Allow reading sanitized LocalComet managed runtime status."
        },
        {
          "description": "Allow stopping the active LocalComet managed llama.cpp runtime.",
          "type": "string",
          "const": "allow-managed-runtime-stop",
          "markdownDescription": "Allow stopping the active LocalComet managed llama.cpp runtime."
        },
        {
          "description": "Allow confirming an in-memory LocalComet model binding.",
          "type": "string",
          "const": "allow-model-binding-set",
          "markdownDescription": "Allow confirming an in-memory LocalComet model binding."
        },
        {
          "description": "Allow reading the fixed LocalComet model gateway catalog.",
          "type": "string",
          "const": "allow-model-gateway-catalog",
          "markdownDescription": "Allow reading the fixed LocalComet model gateway catalog."
        },
        {
          "description": "Allow listing models from the fixed loopback-only local model gateway.",
          "type": "string",
          "const": "allow-model-gateway-list-models",
          "markdownDescription": "Allow listing models from the fixed loopback-only local model gateway."
        },
        {
          "description": "Allow probing the fixed loopback-only local model gateway.",
          "type": "string",
          "const": "allow-model-gateway-probe",
          "markdownDescription": "Allow probing the fixed loopback-only local model gateway."
        },
        {
          "description": "Allow cancelling the active local text model turn.",
          "type": "string",
          "const": "allow-model-turn-cancel",
          "markdownDescription": "Allow cancelling the active local text model turn."
        },
        {
          "description": "Allow starting one bounded local text model turn.",
          "type": "string",
          "const": "allow-model-turn-start",
          "markdownDescription": "Allow starting one bounded local text model turn."
        },
        {
          "description": "Allow a bounded preview reread through one backend-issued opaque file identity.",
          "type": "string",
          "const": "allow-preview-selected-file",
          "markdownDescription": "Allow a bounded preview reread through one backend-issued opaque file identity."
        },
        {
          "description": "Allow explicitly confirmed removal of one inactive approved managed model.",
          "type": "string",
          "const": "allow-remove-managed-model",
          "markdownDescription": "Allow explicitly confirmed removal of one inactive approved managed model."
        },
        {
          "description": "Allow opening the native picker and registering explicitly selected read-only text files.",
          "type": "string",
          "const": "allow-select-files",
          "markdownDescription": "Allow opening the native picker and registering explicitly selected read-only text files."
        },
        {
          "description": "Allow an explicitly confirmed download of one catalog-approved LocalComet artifact.",
          "type": "string",
          "const": "allow-start-approved-artifact-download",
          "markdownDescription": "Allow an explicitly confirmed download of one catalog-approved LocalComet artifact."
        },
        {
          "description": "Default core plugins set.\n#### This default permission set includes:\n\n- `core:path:default`\n- `core:event:default`\n- `core:window:default`\n- `core:webview:default`\n- `core:app:default`\n- `core:image:default`\n- `core:resources:default`\n- `core:menu:default`\n- `core:tray:default`",
          "type": "string",
          "const": "core:default",
          "markdownDescription": "Default core plugins set.\n#### This default permission set includes:\n\n- `core:path:default`\n- `core:event:default`\n- `core:window:default`\n- `core:webview:default`\n- `core:app:default`\n- `core:image:default`\n- `core:resources:default`\n- `core:menu:default`\n- `core:tray:default`"
        },
        {
          "description": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-version`\n- `allow-name`\n- `allow-tauri-version`\n- `allow-identifier`\n- `allow-bundle-type`\n- `allow-register-listener`\n- `allow-remove-listener`\n- `allow-supports-multiple-windows`",
          "type": "string",
          "const": "core:app:default",
          "markdownDescription": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-version`\n- `allow-name`\n- `allow-tauri-version`\n- `allow-identifier`\n- `allow-bundle-type`\n- `allow-register-listener`\n- `allow-remove-listener`\n- `allow-supports-multiple-windows`"
        },
        {
          "description": "Enables the app_hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-app-hide",
          "markdownDescription": "Enables the app_hide command without any pre-configured scope."
        },
        {
          "description": "Enables the app_show command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-app-show",
          "markdownDescription": "Enables the app_show command without any pre-configured scope."
        },
        {
          "description": "Enables the bundle_type command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-bundle-type",
          "markdownDescription": "Enables the bundle_type command without any pre-configured scope."
        },
        {
          "description": "Enables the default_window_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-default-window-icon",
          "markdownDescription": "Enables the default_window_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the fetch_data_store_identifiers command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-fetch-data-store-identifiers",
          "markdownDescription": "Enables the fetch_data_store_identifiers command without any pre-configured scope."
        },
        {
          "description": "Enables the identifier command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-identifier",
          "markdownDescription": "Enables the identifier command without any pre-configured scope."
        },
        {
          "description": "Enables the name command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-name",
          "markdownDescription": "Enables the name command without any pre-configured scope."
        },
        {
          "description": "Enables the register_listener command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-register-listener",
          "markdownDescription": "Enables the register_listener command without any pre-configured scope."
        },
        {
          "description": "Enables the remove_data_store command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-remove-data-store",
          "markdownDescription": "Enables the remove_data_store command without any pre-configured scope."
        },
        {
          "description": "Enables the remove_listener command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-remove-listener",
          "markdownDescription": "Enables the remove_listener command without any pre-configured scope."
        },
        {
          "description": "Enables the set_app_theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-set-app-theme",
          "markdownDescription": "Enables the set_app_theme command without any pre-configured scope."
        },
        {
          "description": "Enables the set_dock_visibility command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-set-dock-visibility",
          "markdownDescription": "Enables the set_dock_visibility command without any pre-configured scope."
        },
        {
          "description": "Enables the supports_multiple_windows command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-supports-multiple-windows",
          "markdownDescription": "Enables the supports_multiple_windows command without any pre-configured scope."
        },
        {
          "description": "Enables the tauri_version command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-tauri-version",
          "markdownDescription": "Enables the tauri_version command without any pre-configured scope."
        },
        {
          "description": "Enables the version command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:allow-version",
          "markdownDescription": "Enables the version command without any pre-configured scope."
        },
        {
          "description": "Denies the app_hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-app-hide",
          "markdownDescription": "Denies the app_hide command without any pre-configured scope."
        },
        {
          "description": "Denies the app_show command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-app-show",
          "markdownDescription": "Denies the app_show command without any pre-configured scope."
        },
        {
          "description": "Denies the bundle_type command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-bundle-type",
          "markdownDescription": "Denies the bundle_type command without any pre-configured scope."
        },
        {
          "description": "Denies the default_window_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-default-window-icon",
          "markdownDescription": "Denies the default_window_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the fetch_data_store_identifiers command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-fetch-data-store-identifiers",
          "markdownDescription": "Denies the fetch_data_store_identifiers command without any pre-configured scope."
        },
        {
          "description": "Denies the identifier command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-identifier",
          "markdownDescription": "Denies the identifier command without any pre-configured scope."
        },
        {
          "description": "Denies the name command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-name",
          "markdownDescription": "Denies the name command without any pre-configured scope."
        },
        {
          "description": "Denies the register_listener command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-register-listener",
          "markdownDescription": "Denies the register_listener command without any pre-configured scope."
        },
        {
          "description": "Denies the remove_data_store command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-remove-data-store",
          "markdownDescription": "Denies the remove_data_store command without any pre-configured scope."
        },
        {
          "description": "Denies the remove_listener command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-remove-listener",
          "markdownDescription": "Denies the remove_listener command without any pre-configured scope."
        },
        {
          "description": "Denies the set_app_theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-set-app-theme",
          "markdownDescription": "Denies the set_app_theme command without any pre-configured scope."
        },
        {
          "description": "Denies the set_dock_visibility command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-set-dock-visibility",
          "markdownDescription": "Denies the set_dock_visibility command without any pre-configured scope."
        },
        {
          "description": "Denies the supports_multiple_windows command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-supports-multiple-windows",
          "markdownDescription": "Denies the supports_multiple_windows command without any pre-configured scope."
        },
        {
          "description": "Denies the tauri_version command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-tauri-version",
          "markdownDescription": "Denies the tauri_version command without any pre-configured scope."
        },
        {
          "description": "Denies the version command without any pre-configured scope.",
          "type": "string",
          "const": "core:app:deny-version",
          "markdownDescription": "Denies the version command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-listen`\n- `allow-unlisten`\n- `allow-emit`\n- `allow-emit-to`",
          "type": "string",
          "const": "core:event:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-listen`\n- `allow-unlisten`\n- `allow-emit`\n- `allow-emit-to`"
        },
        {
          "description": "Enables the emit command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:allow-emit",
          "markdownDescription": "Enables the emit command without any pre-configured scope."
        },
        {
          "description": "Enables the emit_to command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:allow-emit-to",
          "markdownDescription": "Enables the emit_to command without any pre-configured scope."
        },
        {
          "description": "Enables the listen command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:allow-listen",
          "markdownDescription": "Enables the listen command without any pre-configured scope."
        },
        {
          "description": "Enables the unlisten command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:allow-unlisten",
          "markdownDescription": "Enables the unlisten command without any pre-configured scope."
        },
        {
          "description": "Denies the emit command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:deny-emit",
          "markdownDescription": "Denies the emit command without any pre-configured scope."
        },
        {
          "description": "Denies the emit_to command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:deny-emit-to",
          "markdownDescription": "Denies the emit_to command without any pre-configured scope."
        },
        {
          "description": "Denies the listen command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:deny-listen",
          "markdownDescription": "Denies the listen command without any pre-configured scope."
        },
        {
          "description": "Denies the unlisten command without any pre-configured scope.",
          "type": "string",
          "const": "core:event:deny-unlisten",
          "markdownDescription": "Denies the unlisten command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-from-bytes`\n- `allow-from-path`\n- `allow-rgba`\n- `allow-size`",
          "type": "string",
          "const": "core:image:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-from-bytes`\n- `allow-from-path`\n- `allow-rgba`\n- `allow-size`"
        },
        {
          "description": "Enables the from_bytes command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:allow-from-bytes",
          "markdownDescription": "Enables the from_bytes command without any pre-configured scope."
        },
        {
          "description": "Enables the from_path command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:allow-from-path",
          "markdownDescription": "Enables the from_path command without any pre-configured scope."
        },
        {
          "description": "Enables the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:allow-new",
          "markdownDescription": "Enables the new command without any pre-configured scope."
        },
        {
          "description": "Enables the rgba command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:allow-rgba",
          "markdownDescription": "Enables the rgba command without any pre-configured scope."
        },
        {
          "description": "Enables the size command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:allow-size",
          "markdownDescription": "Enables the size command without any pre-configured scope."
        },
        {
          "description": "Denies the from_bytes command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:deny-from-bytes",
          "markdownDescription": "Denies the from_bytes command without any pre-configured scope."
        },
        {
          "description": "Denies the from_path command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:deny-from-path",
          "markdownDescription": "Denies the from_path command without any pre-configured scope."
        },
        {
          "description": "Denies the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:deny-new",
          "markdownDescription": "Denies the new command without any pre-configured scope."
        },
        {
          "description": "Denies the rgba command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:deny-rgba",
          "markdownDescription": "Denies the rgba command without any pre-configured scope."
        },
        {
          "description": "Denies the size command without any pre-configured scope.",
          "type": "string",
          "const": "core:image:deny-size",
          "markdownDescription": "Denies the size command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-append`\n- `allow-prepend`\n- `allow-insert`\n- `allow-remove`\n- `allow-remove-at`\n- `allow-items`\n- `allow-get`\n- `allow-popup`\n- `allow-create-default`\n- `allow-set-as-app-menu`\n- `allow-set-as-window-menu`\n- `allow-text`\n- `allow-set-text`\n- `allow-is-enabled`\n- `allow-set-enabled`\n- `allow-set-accelerator`\n- `allow-set-as-windows-menu-for-nsapp`\n- `allow-set-as-help-menu-for-nsapp`\n- `allow-is-checked`\n- `allow-set-checked`\n- `allow-set-icon`",
          "type": "string",
          "const": "core:menu:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-append`\n- `allow-prepend`\n- `allow-insert`\n- `allow-remove`\n- `allow-remove-at`\n- `allow-items`\n- `allow-get`\n- `allow-popup`\n- `allow-create-default`\n- `allow-set-as-app-menu`\n- `allow-set-as-window-menu`\n- `allow-text`\n- `allow-set-text`\n- `allow-is-enabled`\n- `allow-set-enabled`\n- `allow-set-accelerator`\n- `allow-set-as-windows-menu-for-nsapp`\n- `allow-set-as-help-menu-for-nsapp`\n- `allow-is-checked`\n- `allow-set-checked`\n- `allow-set-icon`"
        },
        {
          "description": "Enables the append command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-append",
          "markdownDescription": "Enables the append command without any pre-configured scope."
        },
        {
          "description": "Enables the create_default command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-create-default",
          "markdownDescription": "Enables the create_default command without any pre-configured scope."
        },
        {
          "description": "Enables the get command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-get",
          "markdownDescription": "Enables the get command without any pre-configured scope."
        },
        {
          "description": "Enables the insert command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-insert",
          "markdownDescription": "Enables the insert command without any pre-configured scope."
        },
        {
          "description": "Enables the is_checked command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-is-checked",
          "markdownDescription": "Enables the is_checked command without any pre-configured scope."
        },
        {
          "description": "Enables the is_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-is-enabled",
          "markdownDescription": "Enables the is_enabled command without any pre-configured scope."
        },
        {
          "description": "Enables the items command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-items",
          "markdownDescription": "Enables the items command without any pre-configured scope."
        },
        {
          "description": "Enables the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-new",
          "markdownDescription": "Enables the new command without any pre-configured scope."
        },
        {
          "description": "Enables the popup command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-popup",
          "markdownDescription": "Enables the popup command without any pre-configured scope."
        },
        {
          "description": "Enables the prepend command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-prepend",
          "markdownDescription": "Enables the prepend command without any pre-configured scope."
        },
        {
          "description": "Enables the remove command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-remove",
          "markdownDescription": "Enables the remove command without any pre-configured scope."
        },
        {
          "description": "Enables the remove_at command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-remove-at",
          "markdownDescription": "Enables the remove_at command without any pre-configured scope."
        },
        {
          "description": "Enables the set_accelerator command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-accelerator",
          "markdownDescription": "Enables the set_accelerator command without any pre-configured scope."
        },
        {
          "description": "Enables the set_as_app_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-as-app-menu",
          "markdownDescription": "Enables the set_as_app_menu command without any pre-configured scope."
        },
        {
          "description": "Enables the set_as_help_menu_for_nsapp command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-as-help-menu-for-nsapp",
          "markdownDescription": "Enables the set_as_help_menu_for_nsapp command without any pre-configured scope."
        },
        {
          "description": "Enables the set_as_window_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-as-window-menu",
          "markdownDescription": "Enables the set_as_window_menu command without any pre-configured scope."
        },
        {
          "description": "Enables the set_as_windows_menu_for_nsapp command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-as-windows-menu-for-nsapp",
          "markdownDescription": "Enables the set_as_windows_menu_for_nsapp command without any pre-configured scope."
        },
        {
          "description": "Enables the set_checked command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-checked",
          "markdownDescription": "Enables the set_checked command without any pre-configured scope."
        },
        {
          "description": "Enables the set_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-enabled",
          "markdownDescription": "Enables the set_enabled command without any pre-configured scope."
        },
        {
          "description": "Enables the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-icon",
          "markdownDescription": "Enables the set_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the set_text command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-set-text",
          "markdownDescription": "Enables the set_text command without any pre-configured scope."
        },
        {
          "description": "Enables the text command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:allow-text",
          "markdownDescription": "Enables the text command without any pre-configured scope."
        },
        {
          "description": "Denies the append command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-append",
          "markdownDescription": "Denies the append command without any pre-configured scope."
        },
        {
          "description": "Denies the create_default command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-create-default",
          "markdownDescription": "Denies the create_default command without any pre-configured scope."
        },
        {
          "description": "Denies the get command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-get",
          "markdownDescription": "Denies the get command without any pre-configured scope."
        },
        {
          "description": "Denies the insert command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-insert",
          "markdownDescription": "Denies the insert command without any pre-configured scope."
        },
        {
          "description": "Denies the is_checked command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-is-checked",
          "markdownDescription": "Denies the is_checked command without any pre-configured scope."
        },
        {
          "description": "Denies the is_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-is-enabled",
          "markdownDescription": "Denies the is_enabled command without any pre-configured scope."
        },
        {
          "description": "Denies the items command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-items",
          "markdownDescription": "Denies the items command without any pre-configured scope."
        },
        {
          "description": "Denies the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-new",
          "markdownDescription": "Denies the new command without any pre-configured scope."
        },
        {
          "description": "Denies the popup command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-popup",
          "markdownDescription": "Denies the popup command without any pre-configured scope."
        },
        {
          "description": "Denies the prepend command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-prepend",
          "markdownDescription": "Denies the prepend command without any pre-configured scope."
        },
        {
          "description": "Denies the remove command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-remove",
          "markdownDescription": "Denies the remove command without any pre-configured scope."
        },
        {
          "description": "Denies the remove_at command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-remove-at",
          "markdownDescription": "Denies the remove_at command without any pre-configured scope."
        },
        {
          "description": "Denies the set_accelerator command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-accelerator",
          "markdownDescription": "Denies the set_accelerator command without any pre-configured scope."
        },
        {
          "description": "Denies the set_as_app_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-as-app-menu",
          "markdownDescription": "Denies the set_as_app_menu command without any pre-configured scope."
        },
        {
          "description": "Denies the set_as_help_menu_for_nsapp command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-as-help-menu-for-nsapp",
          "markdownDescription": "Denies the set_as_help_menu_for_nsapp command without any pre-configured scope."
        },
        {
          "description": "Denies the set_as_window_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-as-window-menu",
          "markdownDescription": "Denies the set_as_window_menu command without any pre-configured scope."
        },
        {
          "description": "Denies the set_as_windows_menu_for_nsapp command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-as-windows-menu-for-nsapp",
          "markdownDescription": "Denies the set_as_windows_menu_for_nsapp command without any pre-configured scope."
        },
        {
          "description": "Denies the set_checked command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-checked",
          "markdownDescription": "Denies the set_checked command without any pre-configured scope."
        },
        {
          "description": "Denies the set_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-enabled",
          "markdownDescription": "Denies the set_enabled command without any pre-configured scope."
        },
        {
          "description": "Denies the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-icon",
          "markdownDescription": "Denies the set_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the set_text command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-set-text",
          "markdownDescription": "Denies the set_text command without any pre-configured scope."
        },
        {
          "description": "Denies the text command without any pre-configured scope.",
          "type": "string",
          "const": "core:menu:deny-text",
          "markdownDescription": "Denies the text command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-resolve-directory`\n- `allow-resolve`\n- `allow-normalize`\n- `allow-join`\n- `allow-dirname`\n- `allow-extname`\n- `allow-basename`\n- `allow-is-absolute`",
          "type": "string",
          "const": "core:path:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-resolve-directory`\n- `allow-resolve`\n- `allow-normalize`\n- `allow-join`\n- `allow-dirname`\n- `allow-extname`\n- `allow-basename`\n- `allow-is-absolute`"
        },
        {
          "description": "Enables the basename command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-basename",
          "markdownDescription": "Enables the basename command without any pre-configured scope."
        },
        {
          "description": "Enables the dirname command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-dirname",
          "markdownDescription": "Enables the dirname command without any pre-configured scope."
        },
        {
          "description": "Enables the extname command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-extname",
          "markdownDescription": "Enables the extname command without any pre-configured scope."
        },
        {
          "description": "Enables the is_absolute command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-is-absolute",
          "markdownDescription": "Enables the is_absolute command without any pre-configured scope."
        },
        {
          "description": "Enables the join command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-join",
          "markdownDescription": "Enables the join command without any pre-configured scope."
        },
        {
          "description": "Enables the normalize command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-normalize",
          "markdownDescription": "Enables the normalize command without any pre-configured scope."
        },
        {
          "description": "Enables the resolve command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-resolve",
          "markdownDescription": "Enables the resolve command without any pre-configured scope."
        },
        {
          "description": "Enables the resolve_directory command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:allow-resolve-directory",
          "markdownDescription": "Enables the resolve_directory command without any pre-configured scope."
        },
        {
          "description": "Denies the basename command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-basename",
          "markdownDescription": "Denies the basename command without any pre-configured scope."
        },
        {
          "description": "Denies the dirname command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-dirname",
          "markdownDescription": "Denies the dirname command without any pre-configured scope."
        },
        {
          "description": "Denies the extname command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-extname",
          "markdownDescription": "Denies the extname command without any pre-configured scope."
        },
        {
          "description": "Denies the is_absolute command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-is-absolute",
          "markdownDescription": "Denies the is_absolute command without any pre-configured scope."
        },
        {
          "description": "Denies the join command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-join",
          "markdownDescription": "Denies the join command without any pre-configured scope."
        },
        {
          "description": "Denies the normalize command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-normalize",
          "markdownDescription": "Denies the normalize command without any pre-configured scope."
        },
        {
          "description": "Denies the resolve command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-resolve",
          "markdownDescription": "Denies the resolve command without any pre-configured scope."
        },
        {
          "description": "Denies the resolve_directory command without any pre-configured scope.",
          "type": "string",
          "const": "core:path:deny-resolve-directory",
          "markdownDescription": "Denies the resolve_directory command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-close`",
          "type": "string",
          "const": "core:resources:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-close`"
        },
        {
          "description": "Enables the close command without any pre-configured scope.",
          "type": "string",
          "const": "core:resources:allow-close",
          "markdownDescription": "Enables the close command without any pre-configured scope."
        },
        {
          "description": "Denies the close command without any pre-configured scope.",
          "type": "string",
          "const": "core:resources:deny-close",
          "markdownDescription": "Denies the close command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-get-by-id`\n- `allow-remove-by-id`\n- `allow-set-icon`\n- `allow-set-menu`\n- `allow-set-tooltip`\n- `allow-set-title`\n- `allow-set-visible`\n- `allow-set-temp-dir-path`\n- `allow-set-icon-as-template`\n- `allow-set-icon-with-as-template`\n- `allow-set-show-menu-on-left-click`",
          "type": "string",
          "const": "core:tray:default",
          "markdownDescription": "Default permissions for the plugin, which enables all commands.\n#### This default permission set includes:\n\n- `allow-new`\n- `allow-get-by-id`\n- `allow-remove-by-id`\n- `allow-set-icon`\n- `allow-set-menu`\n- `allow-set-tooltip`\n- `allow-set-title`\n- `allow-set-visible`\n- `allow-set-temp-dir-path`\n- `allow-set-icon-as-template`\n- `allow-set-icon-with-as-template`\n- `allow-set-show-menu-on-left-click`"
        },
        {
          "description": "Enables the get_by_id command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-get-by-id",
          "markdownDescription": "Enables the get_by_id command without any pre-configured scope."
        },
        {
          "description": "Enables the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-new",
          "markdownDescription": "Enables the new command without any pre-configured scope."
        },
        {
          "description": "Enables the remove_by_id command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-remove-by-id",
          "markdownDescription": "Enables the remove_by_id command without any pre-configured scope."
        },
        {
          "description": "Enables the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-icon",
          "markdownDescription": "Enables the set_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the set_icon_as_template command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-icon-as-template",
          "markdownDescription": "Enables the set_icon_as_template command without any pre-configured scope."
        },
        {
          "description": "Enables the set_icon_with_as_template command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-icon-with-as-template",
          "markdownDescription": "Enables the set_icon_with_as_template command without any pre-configured scope."
        },
        {
          "description": "Enables the set_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-menu",
          "markdownDescription": "Enables the set_menu command without any pre-configured scope."
        },
        {
          "description": "Enables the set_show_menu_on_left_click command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-show-menu-on-left-click",
          "markdownDescription": "Enables the set_show_menu_on_left_click command without any pre-configured scope."
        },
        {
          "description": "Enables the set_temp_dir_path command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-temp-dir-path",
          "markdownDescription": "Enables the set_temp_dir_path command without any pre-configured scope."
        },
        {
          "description": "Enables the set_title command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-title",
          "markdownDescription": "Enables the set_title command without any pre-configured scope."
        },
        {
          "description": "Enables the set_tooltip command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-tooltip",
          "markdownDescription": "Enables the set_tooltip command without any pre-configured scope."
        },
        {
          "description": "Enables the set_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:allow-set-visible",
          "markdownDescription": "Enables the set_visible command without any pre-configured scope."
        },
        {
          "description": "Denies the get_by_id command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-get-by-id",
          "markdownDescription": "Denies the get_by_id command without any pre-configured scope."
        },
        {
          "description": "Denies the new command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-new",
          "markdownDescription": "Denies the new command without any pre-configured scope."
        },
        {
          "description": "Denies the remove_by_id command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-remove-by-id",
          "markdownDescription": "Denies the remove_by_id command without any pre-configured scope."
        },
        {
          "description": "Denies the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-icon",
          "markdownDescription": "Denies the set_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the set_icon_as_template command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-icon-as-template",
          "markdownDescription": "Denies the set_icon_as_template command without any pre-configured scope."
        },
        {
          "description": "Denies the set_icon_with_as_template command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-icon-with-as-template",
          "markdownDescription": "Denies the set_icon_with_as_template command without any pre-configured scope."
        },
        {
          "description": "Denies the set_menu command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-menu",
          "markdownDescription": "Denies the set_menu command without any pre-configured scope."
        },
        {
          "description": "Denies the set_show_menu_on_left_click command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-show-menu-on-left-click",
          "markdownDescription": "Denies the set_show_menu_on_left_click command without any pre-configured scope."
        },
        {
          "description": "Denies the set_temp_dir_path command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-temp-dir-path",
          "markdownDescription": "Denies the set_temp_dir_path command without any pre-configured scope."
        },
        {
          "description": "Denies the set_title command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-title",
          "markdownDescription": "Denies the set_title command without any pre-configured scope."
        },
        {
          "description": "Denies the set_tooltip command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-tooltip",
          "markdownDescription": "Denies the set_tooltip command without any pre-configured scope."
        },
        {
          "description": "Denies the set_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:tray:deny-set-visible",
          "markdownDescription": "Denies the set_visible command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-get-all-webviews`\n- `allow-webview-position`\n- `allow-webview-size`\n- `allow-internal-toggle-devtools`",
          "type": "string",
          "const": "core:webview:default",
          "markdownDescription": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-get-all-webviews`\n- `allow-webview-position`\n- `allow-webview-size`\n- `allow-internal-toggle-devtools`"
        },
        {
          "description": "Enables the clear_all_browsing_data command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-clear-all-browsing-data",
          "markdownDescription": "Enables the clear_all_browsing_data command without any pre-configured scope."
        },
        {
          "description": "Enables the create_webview command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-create-webview",
          "markdownDescription": "Enables the create_webview command without any pre-configured scope."
        },
        {
          "description": "Enables the create_webview_window command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-create-webview-window",
          "markdownDescription": "Enables the create_webview_window command without any pre-configured scope."
        },
        {
          "description": "Enables the get_all_webviews command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-get-all-webviews",
          "markdownDescription": "Enables the get_all_webviews command without any pre-configured scope."
        },
        {
          "description": "Enables the internal_toggle_devtools command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-internal-toggle-devtools",
          "markdownDescription": "Enables the internal_toggle_devtools command without any pre-configured scope."
        },
        {
          "description": "Enables the print command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-print",
          "markdownDescription": "Enables the print command without any pre-configured scope."
        },
        {
          "description": "Enables the reparent command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-reparent",
          "markdownDescription": "Enables the reparent command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_auto_resize command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-auto-resize",
          "markdownDescription": "Enables the set_webview_auto_resize command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_background_color command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-background-color",
          "markdownDescription": "Enables the set_webview_background_color command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_focus command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-focus",
          "markdownDescription": "Enables the set_webview_focus command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-position",
          "markdownDescription": "Enables the set_webview_position command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-size",
          "markdownDescription": "Enables the set_webview_size command without any pre-configured scope."
        },
        {
          "description": "Enables the set_webview_zoom command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-set-webview-zoom",
          "markdownDescription": "Enables the set_webview_zoom command without any pre-configured scope."
        },
        {
          "description": "Enables the webview_close command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-webview-close",
          "markdownDescription": "Enables the webview_close command without any pre-configured scope."
        },
        {
          "description": "Enables the webview_hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-webview-hide",
          "markdownDescription": "Enables the webview_hide command without any pre-configured scope."
        },
        {
          "description": "Enables the webview_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-webview-position",
          "markdownDescription": "Enables the webview_position command without any pre-configured scope."
        },
        {
          "description": "Enables the webview_show command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-webview-show",
          "markdownDescription": "Enables the webview_show command without any pre-configured scope."
        },
        {
          "description": "Enables the webview_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:allow-webview-size",
          "markdownDescription": "Enables the webview_size command without any pre-configured scope."
        },
        {
          "description": "Denies the clear_all_browsing_data command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-clear-all-browsing-data",
          "markdownDescription": "Denies the clear_all_browsing_data command without any pre-configured scope."
        },
        {
          "description": "Denies the create_webview command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-create-webview",
          "markdownDescription": "Denies the create_webview command without any pre-configured scope."
        },
        {
          "description": "Denies the create_webview_window command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-create-webview-window",
          "markdownDescription": "Denies the create_webview_window command without any pre-configured scope."
        },
        {
          "description": "Denies the get_all_webviews command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-get-all-webviews",
          "markdownDescription": "Denies the get_all_webviews command without any pre-configured scope."
        },
        {
          "description": "Denies the internal_toggle_devtools command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-internal-toggle-devtools",
          "markdownDescription": "Denies the internal_toggle_devtools command without any pre-configured scope."
        },
        {
          "description": "Denies the print command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-print",
          "markdownDescription": "Denies the print command without any pre-configured scope."
        },
        {
          "description": "Denies the reparent command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-reparent",
          "markdownDescription": "Denies the reparent command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_auto_resize command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-auto-resize",
          "markdownDescription": "Denies the set_webview_auto_resize command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_background_color command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-background-color",
          "markdownDescription": "Denies the set_webview_background_color command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_focus command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-focus",
          "markdownDescription": "Denies the set_webview_focus command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-position",
          "markdownDescription": "Denies the set_webview_position command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-size",
          "markdownDescription": "Denies the set_webview_size command without any pre-configured scope."
        },
        {
          "description": "Denies the set_webview_zoom command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-set-webview-zoom",
          "markdownDescription": "Denies the set_webview_zoom command without any pre-configured scope."
        },
        {
          "description": "Denies the webview_close command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-webview-close",
          "markdownDescription": "Denies the webview_close command without any pre-configured scope."
        },
        {
          "description": "Denies the webview_hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-webview-hide",
          "markdownDescription": "Denies the webview_hide command without any pre-configured scope."
        },
        {
          "description": "Denies the webview_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-webview-position",
          "markdownDescription": "Denies the webview_position command without any pre-configured scope."
        },
        {
          "description": "Denies the webview_show command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-webview-show",
          "markdownDescription": "Denies the webview_show command without any pre-configured scope."
        },
        {
          "description": "Denies the webview_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:webview:deny-webview-size",
          "markdownDescription": "Denies the webview_size command without any pre-configured scope."
        },
        {
          "description": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-get-all-windows`\n- `allow-scale-factor`\n- `allow-inner-position`\n- `allow-outer-position`\n- `allow-inner-size`\n- `allow-outer-size`\n- `allow-is-fullscreen`\n- `allow-is-minimized`\n- `allow-is-maximized`\n- `allow-is-focused`\n- `allow-is-decorated`\n- `allow-is-resizable`\n- `allow-is-maximizable`\n- `allow-is-minimizable`\n- `allow-is-closable`\n- `allow-is-visible`\n- `allow-is-enabled`\n- `allow-title`\n- `allow-current-monitor`\n- `allow-primary-monitor`\n- `allow-monitor-from-point`\n- `allow-available-monitors`\n- `allow-cursor-position`\n- `allow-theme`\n- `allow-is-always-on-top`\n- `allow-activity-name`\n- `allow-scene-identifier`\n- `allow-internal-toggle-maximize`",
          "type": "string",
          "const": "core:window:default",
          "markdownDescription": "Default permissions for the plugin.\n#### This default permission set includes:\n\n- `allow-get-all-windows`\n- `allow-scale-factor`\n- `allow-inner-position`\n- `allow-outer-position`\n- `allow-inner-size`\n- `allow-outer-size`\n- `allow-is-fullscreen`\n- `allow-is-minimized`\n- `allow-is-maximized`\n- `allow-is-focused`\n- `allow-is-decorated`\n- `allow-is-resizable`\n- `allow-is-maximizable`\n- `allow-is-minimizable`\n- `allow-is-closable`\n- `allow-is-visible`\n- `allow-is-enabled`\n- `allow-title`\n- `allow-current-monitor`\n- `allow-primary-monitor`\n- `allow-monitor-from-point`\n- `allow-available-monitors`\n- `allow-cursor-position`\n- `allow-theme`\n- `allow-is-always-on-top`\n- `allow-activity-name`\n- `allow-scene-identifier`\n- `allow-internal-toggle-maximize`"
        },
        {
          "description": "Enables the activity_name command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-activity-name",
          "markdownDescription": "Enables the activity_name command without any pre-configured scope."
        },
        {
          "description": "Enables the available_monitors command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-available-monitors",
          "markdownDescription": "Enables the available_monitors command without any pre-configured scope."
        },
        {
          "description": "Enables the center command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-center",
          "markdownDescription": "Enables the center command without any pre-configured scope."
        },
        {
          "description": "Enables the close command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-close",
          "markdownDescription": "Enables the close command without any pre-configured scope."
        },
        {
          "description": "Enables the create command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-create",
          "markdownDescription": "Enables the create command without any pre-configured scope."
        },
        {
          "description": "Enables the current_monitor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-current-monitor",
          "markdownDescription": "Enables the current_monitor command without any pre-configured scope."
        },
        {
          "description": "Enables the cursor_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-cursor-position",
          "markdownDescription": "Enables the cursor_position command without any pre-configured scope."
        },
        {
          "description": "Enables the destroy command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-destroy",
          "markdownDescription": "Enables the destroy command without any pre-configured scope."
        },
        {
          "description": "Enables the get_all_windows command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-get-all-windows",
          "markdownDescription": "Enables the get_all_windows command without any pre-configured scope."
        },
        {
          "description": "Enables the hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-hide",
          "markdownDescription": "Enables the hide command without any pre-configured scope."
        },
        {
          "description": "Enables the inner_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-inner-position",
          "markdownDescription": "Enables the inner_position command without any pre-configured scope."
        },
        {
          "description": "Enables the inner_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-inner-size",
          "markdownDescription": "Enables the inner_size command without any pre-configured scope."
        },
        {
          "description": "Enables the internal_toggle_maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-internal-toggle-maximize",
          "markdownDescription": "Enables the internal_toggle_maximize command without any pre-configured scope."
        },
        {
          "description": "Enables the is_always_on_top command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-always-on-top",
          "markdownDescription": "Enables the is_always_on_top command without any pre-configured scope."
        },
        {
          "description": "Enables the is_closable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-closable",
          "markdownDescription": "Enables the is_closable command without any pre-configured scope."
        },
        {
          "description": "Enables the is_decorated command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-decorated",
          "markdownDescription": "Enables the is_decorated command without any pre-configured scope."
        },
        {
          "description": "Enables the is_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-enabled",
          "markdownDescription": "Enables the is_enabled command without any pre-configured scope."
        },
        {
          "description": "Enables the is_focused command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-focused",
          "markdownDescription": "Enables the is_focused command without any pre-configured scope."
        },
        {
          "description": "Enables the is_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-fullscreen",
          "markdownDescription": "Enables the is_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Enables the is_maximizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-maximizable",
          "markdownDescription": "Enables the is_maximizable command without any pre-configured scope."
        },
        {
          "description": "Enables the is_maximized command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-maximized",
          "markdownDescription": "Enables the is_maximized command without any pre-configured scope."
        },
        {
          "description": "Enables the is_minimizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-minimizable",
          "markdownDescription": "Enables the is_minimizable command without any pre-configured scope."
        },
        {
          "description": "Enables the is_minimized command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-minimized",
          "markdownDescription": "Enables the is_minimized command without any pre-configured scope."
        },
        {
          "description": "Enables the is_resizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-resizable",
          "markdownDescription": "Enables the is_resizable command without any pre-configured scope."
        },
        {
          "description": "Enables the is_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-is-visible",
          "markdownDescription": "Enables the is_visible command without any pre-configured scope."
        },
        {
          "description": "Enables the maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-maximize",
          "markdownDescription": "Enables the maximize command without any pre-configured scope."
        },
        {
          "description": "Enables the minimize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-minimize",
          "markdownDescription": "Enables the minimize command without any pre-configured scope."
        },
        {
          "description": "Enables the monitor_from_point command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-monitor-from-point",
          "markdownDescription": "Enables the monitor_from_point command without any pre-configured scope."
        },
        {
          "description": "Enables the outer_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-outer-position",
          "markdownDescription": "Enables the outer_position command without any pre-configured scope."
        },
        {
          "description": "Enables the outer_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-outer-size",
          "markdownDescription": "Enables the outer_size command without any pre-configured scope."
        },
        {
          "description": "Enables the primary_monitor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-primary-monitor",
          "markdownDescription": "Enables the primary_monitor command without any pre-configured scope."
        },
        {
          "description": "Enables the request_user_attention command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-request-user-attention",
          "markdownDescription": "Enables the request_user_attention command without any pre-configured scope."
        },
        {
          "description": "Enables the scale_factor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-scale-factor",
          "markdownDescription": "Enables the scale_factor command without any pre-configured scope."
        },
        {
          "description": "Enables the scene_identifier command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-scene-identifier",
          "markdownDescription": "Enables the scene_identifier command without any pre-configured scope."
        },
        {
          "description": "Enables the set_always_on_bottom command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-always-on-bottom",
          "markdownDescription": "Enables the set_always_on_bottom command without any pre-configured scope."
        },
        {
          "description": "Enables the set_always_on_top command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-always-on-top",
          "markdownDescription": "Enables the set_always_on_top command without any pre-configured scope."
        },
        {
          "description": "Enables the set_background_color command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-background-color",
          "markdownDescription": "Enables the set_background_color command without any pre-configured scope."
        },
        {
          "description": "Enables the set_badge_count command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-badge-count",
          "markdownDescription": "Enables the set_badge_count command without any pre-configured scope."
        },
        {
          "description": "Enables the set_badge_label command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-badge-label",
          "markdownDescription": "Enables the set_badge_label command without any pre-configured scope."
        },
        {
          "description": "Enables the set_closable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-closable",
          "markdownDescription": "Enables the set_closable command without any pre-configured scope."
        },
        {
          "description": "Enables the set_content_protected command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-content-protected",
          "markdownDescription": "Enables the set_content_protected command without any pre-configured scope."
        },
        {
          "description": "Enables the set_cursor_grab command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-cursor-grab",
          "markdownDescription": "Enables the set_cursor_grab command without any pre-configured scope."
        },
        {
          "description": "Enables the set_cursor_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-cursor-icon",
          "markdownDescription": "Enables the set_cursor_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the set_cursor_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-cursor-position",
          "markdownDescription": "Enables the set_cursor_position command without any pre-configured scope."
        },
        {
          "description": "Enables the set_cursor_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-cursor-visible",
          "markdownDescription": "Enables the set_cursor_visible command without any pre-configured scope."
        },
        {
          "description": "Enables the set_decorations command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-decorations",
          "markdownDescription": "Enables the set_decorations command without any pre-configured scope."
        },
        {
          "description": "Enables the set_effects command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-effects",
          "markdownDescription": "Enables the set_effects command without any pre-configured scope."
        },
        {
          "description": "Enables the set_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-enabled",
          "markdownDescription": "Enables the set_enabled command without any pre-configured scope."
        },
        {
          "description": "Enables the set_focus command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-focus",
          "markdownDescription": "Enables the set_focus command without any pre-configured scope."
        },
        {
          "description": "Enables the set_focusable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-focusable",
          "markdownDescription": "Enables the set_focusable command without any pre-configured scope."
        },
        {
          "description": "Enables the set_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-fullscreen",
          "markdownDescription": "Enables the set_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Enables the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-icon",
          "markdownDescription": "Enables the set_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the set_ignore_cursor_events command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-ignore-cursor-events",
          "markdownDescription": "Enables the set_ignore_cursor_events command without any pre-configured scope."
        },
        {
          "description": "Enables the set_max_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-max-size",
          "markdownDescription": "Enables the set_max_size command without any pre-configured scope."
        },
        {
          "description": "Enables the set_maximizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-maximizable",
          "markdownDescription": "Enables the set_maximizable command without any pre-configured scope."
        },
        {
          "description": "Enables the set_min_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-min-size",
          "markdownDescription": "Enables the set_min_size command without any pre-configured scope."
        },
        {
          "description": "Enables the set_minimizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-minimizable",
          "markdownDescription": "Enables the set_minimizable command without any pre-configured scope."
        },
        {
          "description": "Enables the set_overlay_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-overlay-icon",
          "markdownDescription": "Enables the set_overlay_icon command without any pre-configured scope."
        },
        {
          "description": "Enables the set_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-position",
          "markdownDescription": "Enables the set_position command without any pre-configured scope."
        },
        {
          "description": "Enables the set_progress_bar command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-progress-bar",
          "markdownDescription": "Enables the set_progress_bar command without any pre-configured scope."
        },
        {
          "description": "Enables the set_resizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-resizable",
          "markdownDescription": "Enables the set_resizable command without any pre-configured scope."
        },
        {
          "description": "Enables the set_shadow command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-shadow",
          "markdownDescription": "Enables the set_shadow command without any pre-configured scope."
        },
        {
          "description": "Enables the set_simple_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-simple-fullscreen",
          "markdownDescription": "Enables the set_simple_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Enables the set_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-size",
          "markdownDescription": "Enables the set_size command without any pre-configured scope."
        },
        {
          "description": "Enables the set_size_constraints command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-size-constraints",
          "markdownDescription": "Enables the set_size_constraints command without any pre-configured scope."
        },
        {
          "description": "Enables the set_skip_taskbar command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-skip-taskbar",
          "markdownDescription": "Enables the set_skip_taskbar command without any pre-configured scope."
        },
        {
          "description": "Enables the set_theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-theme",
          "markdownDescription": "Enables the set_theme command without any pre-configured scope."
        },
        {
          "description": "Enables the set_title command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-title",
          "markdownDescription": "Enables the set_title command without any pre-configured scope."
        },
        {
          "description": "Enables the set_title_bar_style command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-title-bar-style",
          "markdownDescription": "Enables the set_title_bar_style command without any pre-configured scope."
        },
        {
          "description": "Enables the set_visible_on_all_workspaces command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-set-visible-on-all-workspaces",
          "markdownDescription": "Enables the set_visible_on_all_workspaces command without any pre-configured scope."
        },
        {
          "description": "Enables the show command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-show",
          "markdownDescription": "Enables the show command without any pre-configured scope."
        },
        {
          "description": "Enables the start_dragging command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-start-dragging",
          "markdownDescription": "Enables the start_dragging command without any pre-configured scope."
        },
        {
          "description": "Enables the start_resize_dragging command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-start-resize-dragging",
          "markdownDescription": "Enables the start_resize_dragging command without any pre-configured scope."
        },
        {
          "description": "Enables the theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-theme",
          "markdownDescription": "Enables the theme command without any pre-configured scope."
        },
        {
          "description": "Enables the title command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-title",
          "markdownDescription": "Enables the title command without any pre-configured scope."
        },
        {
          "description": "Enables the toggle_maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-toggle-maximize",
          "markdownDescription": "Enables the toggle_maximize command without any pre-configured scope."
        },
        {
          "description": "Enables the unmaximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-unmaximize",
          "markdownDescription": "Enables the unmaximize command without any pre-configured scope."
        },
        {
          "description": "Enables the unminimize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:allow-unminimize",
          "markdownDescription": "Enables the unminimize command without any pre-configured scope."
        },
        {
          "description": "Denies the activity_name command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-activity-name",
          "markdownDescription": "Denies the activity_name command without any pre-configured scope."
        },
        {
          "description": "Denies the available_monitors command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-available-monitors",
          "markdownDescription": "Denies the available_monitors command without any pre-configured scope."
        },
        {
          "description": "Denies the center command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-center",
          "markdownDescription": "Denies the center command without any pre-configured scope."
        },
        {
          "description": "Denies the close command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-close",
          "markdownDescription": "Denies the close command without any pre-configured scope."
        },
        {
          "description": "Denies the create command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-create",
          "markdownDescription": "Denies the create command without any pre-configured scope."
        },
        {
          "description": "Denies the current_monitor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-current-monitor",
          "markdownDescription": "Denies the current_monitor command without any pre-configured scope."
        },
        {
          "description": "Denies the cursor_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-cursor-position",
          "markdownDescription": "Denies the cursor_position command without any pre-configured scope."
        },
        {
          "description": "Denies the destroy command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-destroy",
          "markdownDescription": "Denies the destroy command without any pre-configured scope."
        },
        {
          "description": "Denies the get_all_windows command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-get-all-windows",
          "markdownDescription": "Denies the get_all_windows command without any pre-configured scope."
        },
        {
          "description": "Denies the hide command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-hide",
          "markdownDescription": "Denies the hide command without any pre-configured scope."
        },
        {
          "description": "Denies the inner_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-inner-position",
          "markdownDescription": "Denies the inner_position command without any pre-configured scope."
        },
        {
          "description": "Denies the inner_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-inner-size",
          "markdownDescription": "Denies the inner_size command without any pre-configured scope."
        },
        {
          "description": "Denies the internal_toggle_maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-internal-toggle-maximize",
          "markdownDescription": "Denies the internal_toggle_maximize command without any pre-configured scope."
        },
        {
          "description": "Denies the is_always_on_top command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-always-on-top",
          "markdownDescription": "Denies the is_always_on_top command without any pre-configured scope."
        },
        {
          "description": "Denies the is_closable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-closable",
          "markdownDescription": "Denies the is_closable command without any pre-configured scope."
        },
        {
          "description": "Denies the is_decorated command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-decorated",
          "markdownDescription": "Denies the is_decorated command without any pre-configured scope."
        },
        {
          "description": "Denies the is_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-enabled",
          "markdownDescription": "Denies the is_enabled command without any pre-configured scope."
        },
        {
          "description": "Denies the is_focused command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-focused",
          "markdownDescription": "Denies the is_focused command without any pre-configured scope."
        },
        {
          "description": "Denies the is_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-fullscreen",
          "markdownDescription": "Denies the is_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Denies the is_maximizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-maximizable",
          "markdownDescription": "Denies the is_maximizable command without any pre-configured scope."
        },
        {
          "description": "Denies the is_maximized command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-maximized",
          "markdownDescription": "Denies the is_maximized command without any pre-configured scope."
        },
        {
          "description": "Denies the is_minimizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-minimizable",
          "markdownDescription": "Denies the is_minimizable command without any pre-configured scope."
        },
        {
          "description": "Denies the is_minimized command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-minimized",
          "markdownDescription": "Denies the is_minimized command without any pre-configured scope."
        },
        {
          "description": "Denies the is_resizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-resizable",
          "markdownDescription": "Denies the is_resizable command without any pre-configured scope."
        },
        {
          "description": "Denies the is_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-is-visible",
          "markdownDescription": "Denies the is_visible command without any pre-configured scope."
        },
        {
          "description": "Denies the maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-maximize",
          "markdownDescription": "Denies the maximize command without any pre-configured scope."
        },
        {
          "description": "Denies the minimize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-minimize",
          "markdownDescription": "Denies the minimize command without any pre-configured scope."
        },
        {
          "description": "Denies the monitor_from_point command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-monitor-from-point",
          "markdownDescription": "Denies the monitor_from_point command without any pre-configured scope."
        },
        {
          "description": "Denies the outer_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-outer-position",
          "markdownDescription": "Denies the outer_position command without any pre-configured scope."
        },
        {
          "description": "Denies the outer_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-outer-size",
          "markdownDescription": "Denies the outer_size command without any pre-configured scope."
        },
        {
          "description": "Denies the primary_monitor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-primary-monitor",
          "markdownDescription": "Denies the primary_monitor command without any pre-configured scope."
        },
        {
          "description": "Denies the request_user_attention command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-request-user-attention",
          "markdownDescription": "Denies the request_user_attention command without any pre-configured scope."
        },
        {
          "description": "Denies the scale_factor command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-scale-factor",
          "markdownDescription": "Denies the scale_factor command without any pre-configured scope."
        },
        {
          "description": "Denies the scene_identifier command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-scene-identifier",
          "markdownDescription": "Denies the scene_identifier command without any pre-configured scope."
        },
        {
          "description": "Denies the set_always_on_bottom command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-always-on-bottom",
          "markdownDescription": "Denies the set_always_on_bottom command without any pre-configured scope."
        },
        {
          "description": "Denies the set_always_on_top command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-always-on-top",
          "markdownDescription": "Denies the set_always_on_top command without any pre-configured scope."
        },
        {
          "description": "Denies the set_background_color command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-background-color",
          "markdownDescription": "Denies the set_background_color command without any pre-configured scope."
        },
        {
          "description": "Denies the set_badge_count command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-badge-count",
          "markdownDescription": "Denies the set_badge_count command without any pre-configured scope."
        },
        {
          "description": "Denies the set_badge_label command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-badge-label",
          "markdownDescription": "Denies the set_badge_label command without any pre-configured scope."
        },
        {
          "description": "Denies the set_closable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-closable",
          "markdownDescription": "Denies the set_closable command without any pre-configured scope."
        },
        {
          "description": "Denies the set_content_protected command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-content-protected",
          "markdownDescription": "Denies the set_content_protected command without any pre-configured scope."
        },
        {
          "description": "Denies the set_cursor_grab command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-cursor-grab",
          "markdownDescription": "Denies the set_cursor_grab command without any pre-configured scope."
        },
        {
          "description": "Denies the set_cursor_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-cursor-icon",
          "markdownDescription": "Denies the set_cursor_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the set_cursor_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-cursor-position",
          "markdownDescription": "Denies the set_cursor_position command without any pre-configured scope."
        },
        {
          "description": "Denies the set_cursor_visible command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-cursor-visible",
          "markdownDescription": "Denies the set_cursor_visible command without any pre-configured scope."
        },
        {
          "description": "Denies the set_decorations command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-decorations",
          "markdownDescription": "Denies the set_decorations command without any pre-configured scope."
        },
        {
          "description": "Denies the set_effects command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-effects",
          "markdownDescription": "Denies the set_effects command without any pre-configured scope."
        },
        {
          "description": "Denies the set_enabled command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-enabled",
          "markdownDescription": "Denies the set_enabled command without any pre-configured scope."
        },
        {
          "description": "Denies the set_focus command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-focus",
          "markdownDescription": "Denies the set_focus command without any pre-configured scope."
        },
        {
          "description": "Denies the set_focusable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-focusable",
          "markdownDescription": "Denies the set_focusable command without any pre-configured scope."
        },
        {
          "description": "Denies the set_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-fullscreen",
          "markdownDescription": "Denies the set_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Denies the set_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-icon",
          "markdownDescription": "Denies the set_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the set_ignore_cursor_events command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-ignore-cursor-events",
          "markdownDescription": "Denies the set_ignore_cursor_events command without any pre-configured scope."
        },
        {
          "description": "Denies the set_max_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-max-size",
          "markdownDescription": "Denies the set_max_size command without any pre-configured scope."
        },
        {
          "description": "Denies the set_maximizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-maximizable",
          "markdownDescription": "Denies the set_maximizable command without any pre-configured scope."
        },
        {
          "description": "Denies the set_min_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-min-size",
          "markdownDescription": "Denies the set_min_size command without any pre-configured scope."
        },
        {
          "description": "Denies the set_minimizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-minimizable",
          "markdownDescription": "Denies the set_minimizable command without any pre-configured scope."
        },
        {
          "description": "Denies the set_overlay_icon command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-overlay-icon",
          "markdownDescription": "Denies the set_overlay_icon command without any pre-configured scope."
        },
        {
          "description": "Denies the set_position command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-position",
          "markdownDescription": "Denies the set_position command without any pre-configured scope."
        },
        {
          "description": "Denies the set_progress_bar command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-progress-bar",
          "markdownDescription": "Denies the set_progress_bar command without any pre-configured scope."
        },
        {
          "description": "Denies the set_resizable command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-resizable",
          "markdownDescription": "Denies the set_resizable command without any pre-configured scope."
        },
        {
          "description": "Denies the set_shadow command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-shadow",
          "markdownDescription": "Denies the set_shadow command without any pre-configured scope."
        },
        {
          "description": "Denies the set_simple_fullscreen command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-simple-fullscreen",
          "markdownDescription": "Denies the set_simple_fullscreen command without any pre-configured scope."
        },
        {
          "description": "Denies the set_size command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-size",
          "markdownDescription": "Denies the set_size command without any pre-configured scope."
        },
        {
          "description": "Denies the set_size_constraints command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-size-constraints",
          "markdownDescription": "Denies the set_size_constraints command without any pre-configured scope."
        },
        {
          "description": "Denies the set_skip_taskbar command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-skip-taskbar",
          "markdownDescription": "Denies the set_skip_taskbar command without any pre-configured scope."
        },
        {
          "description": "Denies the set_theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-theme",
          "markdownDescription": "Denies the set_theme command without any pre-configured scope."
        },
        {
          "description": "Denies the set_title command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-title",
          "markdownDescription": "Denies the set_title command without any pre-configured scope."
        },
        {
          "description": "Denies the set_title_bar_style command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-title-bar-style",
          "markdownDescription": "Denies the set_title_bar_style command without any pre-configured scope."
        },
        {
          "description": "Denies the set_visible_on_all_workspaces command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-set-visible-on-all-workspaces",
          "markdownDescription": "Denies the set_visible_on_all_workspaces command without any pre-configured scope."
        },
        {
          "description": "Denies the show command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-show",
          "markdownDescription": "Denies the show command without any pre-configured scope."
        },
        {
          "description": "Denies the start_dragging command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-start-dragging",
          "markdownDescription": "Denies the start_dragging command without any pre-configured scope."
        },
        {
          "description": "Denies the start_resize_dragging command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-start-resize-dragging",
          "markdownDescription": "Denies the start_resize_dragging command without any pre-configured scope."
        },
        {
          "description": "Denies the theme command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-theme",
          "markdownDescription": "Denies the theme command without any pre-configured scope."
        },
        {
          "description": "Denies the title command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-title",
          "markdownDescription": "Denies the title command without any pre-configured scope."
        },
        {
          "description": "Denies the toggle_maximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-toggle-maximize",
          "markdownDescription": "Denies the toggle_maximize command without any pre-configured scope."
        },
        {
          "description": "Denies the unmaximize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-unmaximize",
          "markdownDescription": "Denies the unmaximize command without any pre-configured scope."
        },
        {
          "description": "Denies the unminimize command without any pre-configured scope.",
          "type": "string",
          "const": "core:window:deny-unminimize",
          "markdownDescription": "Denies the unminimize command without any pre-configured scope."
        }
      ]
    },
    "Value": {
      "description": "All supported ACL values.",
      "anyOf": [
        {
          "description": "Represents a null JSON value.",
          "type": "null"
        },
        {
          "description": "Represents a [`bool`].",
          "type": "boolean"
        },
        {
          "description": "Represents a valid ACL [`Number`].",
          "allOf": [
            {
              "$ref": "#/definitions/Number"
            }
          ]
        },
        {
          "description": "Represents a [`String`].",
          "type": "string"
        },
        {
          "description": "Represents a list of other [`Value`]s.",
          "type": "array",
          "items": {
            "$ref": "#/definitions/Value"
          }
        },
        {
          "description": "Represents a map of [`String`] keys to [`Value`]s.",
          "type": "object",
          "additionalProperties": {
            "$ref": "#/definitions/Value"
          }
        }
      ]
    },
    "Number": {
      "description": "A valid ACL number.",
      "anyOf": [
        {
          "description": "Represents an [`i64`].",
          "type": "integer",
          "format": "int64"
        },
        {
          "description": "Represents a [`f64`].",
          "type": "number",
          "format": "double"
        }
      ]
    },
    "Target": {
      "description": "Platform target.",
      "oneOf": [
        {
          "description": "MacOS.",
          "type": "string",
          "enum": [
            "macOS"
          ]
        },
        {
          "description": "Windows.",
          "type": "string",
          "enum": [
            "windows"
          ]
        },
        {
          "description": "Linux.",
          "type": "string",
          "enum": [
            "linux"
          ]
        },
        {
          "description": "Android.",
          "type": "string",
          "enum": [
            "android"
          ]
        },
        {
          "description": "iOS.",
          "type": "string",
          "enum": [
            "iOS"
          ]
        }
      ]
    }
  }
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/permissions/control-plane.toml (216 строк, 5998 байт)

````toml
[[permission]]
identifier = "allow-control-plane-bootstrap"
description = "Allow LocalComet control-plane bootstrap."
commands.allow = [
  "control_plane_bootstrap",
]

[[permission]]
identifier = "allow-control-plane-create-session"
description = "Allow creating a LocalComet control-plane session."
commands.allow = [
  "control_plane_create_session",
]

[[permission]]
identifier = "allow-control-plane-close-session"
description = "Allow closing a LocalComet control-plane session."
commands.allow = [
  "control_plane_close_session",
]

[[permission]]
identifier = "allow-control-plane-create-thread"
description = "Allow creating a LocalComet control-plane thread."
commands.allow = [
  "control_plane_create_thread",
]

[[permission]]
identifier = "allow-control-plane-start-mock-turn"
description = "Allow starting a mock LocalComet control-plane turn."
commands.allow = [
  "control_plane_start_mock_turn",
]

[[permission]]
identifier = "allow-control-plane-get-turn-status"
description = "Allow reading LocalComet control-plane turn status."
commands.allow = [
  "control_plane_get_turn_status",
]

[[permission]]
identifier = "allow-control-plane-cancel-turn"
description = "Allow cancelling a LocalComet control-plane turn."
commands.allow = [
  "control_plane_cancel_turn",
]

[[permission]]
identifier = "allow-model-gateway-catalog"
description = "Allow reading the fixed LocalComet model gateway catalog."
commands.allow = [
  "model_gateway_catalog",
]

[[permission]]
identifier = "allow-knowledge-turn-preview"
description = "Allow preparing one bounded project-knowledge preview for an existing Turn."
commands.allow = [
  "knowledge_turn_preview",
]

[[permission]]
identifier = "allow-knowledge-turn-decide"
description = "Allow one bounded user decision for an exact project-knowledge preview."
commands.allow = [
  "knowledge_turn_decide",
]

[[permission]]
identifier = "allow-knowledge-review-list"
description = "Allow listing bounded read-only knowledge review summaries."
commands.allow = [
  "knowledge_review_list",
]

[[permission]]
identifier = "allow-knowledge-review-get"
description = "Allow reading one exact bounded knowledge review projection."
commands.allow = [
  "knowledge_review_get",
]

[[permission]]
identifier = "allow-model-gateway-probe"
description = "Allow probing the fixed loopback-only local model gateway."
commands.allow = [
  "model_gateway_probe",
]

[[permission]]
identifier = "allow-model-gateway-list-models"
description = "Allow listing models from the fixed loopback-only local model gateway."
commands.allow = [
  "model_gateway_list_models",
]

[[permission]]
identifier = "allow-model-binding-set"
description = "Allow confirming an in-memory LocalComet model binding."
commands.allow = [
  "model_binding_set",
]

[[permission]]
identifier = "allow-model-turn-start"
description = "Allow starting one bounded local text model turn."
commands.allow = [
  "model_turn_start",
]

[[permission]]
identifier = "allow-model-turn-cancel"
description = "Allow cancelling the active local text model turn."
commands.allow = [
  "model_turn_cancel",
]

[[permission]]
identifier = "allow-managed-runtime-status"
description = "Allow reading sanitized LocalComet managed runtime status."
commands.allow = [
  "managed_runtime_status",
]

[[permission]]
identifier = "allow-managed-model-catalog"
description = "Allow reading safe approved model metadata from the immutable LocalComet artifact catalog."
commands.allow = [
  "managed_model_catalog",
]

[[permission]]
identifier = "allow-managed-runtime-catalog"
description = "Allow reading safe approved runtime metadata from the immutable LocalComet artifact catalog."
commands.allow = [
  "managed_runtime_catalog",
]

[[permission]]
identifier = "allow-managed-installed-artifacts"
description = "Allow reading live validated installed artifact metadata derived from the LocalComet artifact catalog."
commands.allow = [
  "managed_installed_artifacts",
]

[[permission]]
identifier = "allow-managed-artifact-validation-status"
description = "Allow reading live validation status for one LocalComet catalog artifact ID."
commands.allow = [
  "managed_artifact_validation_status",
]

[[permission]]
identifier = "allow-managed-model-readiness"
description = "Allow reading runtime compatibility and readiness for one LocalComet catalog model ID."
commands.allow = [
  "managed_model_readiness",
]

[[permission]]
identifier = "allow-managed-runtime-start"
description = "Allow starting the fixed LocalComet managed llama.cpp runtime."
commands.allow = [
  "managed_runtime_start",
]

[[permission]]
identifier = "allow-managed-runtime-stop"
description = "Allow stopping the active LocalComet managed llama.cpp runtime."
commands.allow = [
  "managed_runtime_stop",
]

[[permission]]
identifier = "allow-managed-runtime-logs"
description = "Allow reading bounded sanitized managed runtime log tails."
commands.allow = [
  "managed_runtime_logs",
]

[[permission]]
identifier = "allow-list-approved-downloadable-artifacts"
description = "Allow reading the fixed approved LocalComet acquisition catalog projection."
commands.allow = [
  "list_approved_downloadable_artifacts",
]

[[permission]]
identifier = "allow-start-approved-artifact-download"
description = "Allow an explicitly confirmed download of one catalog-approved LocalComet artifact."
commands.allow = [
  "start_approved_artifact_download",
]

[[permission]]
identifier = "allow-get-artifact-download-state"
description = "Allow reading one bounded LocalComet artifact download state."
commands.allow = [
  "get_artifact_download_state",
]

[[permission]]
identifier = "allow-cancel-artifact-download"
description = "Allow cancelling one bounded LocalComet artifact download."
commands.allow = [
  "cancel_artifact_download",
]

[[permission]]
identifier = "allow-remove-managed-model"
description = "Allow explicitly confirmed removal of one inactive approved managed model."
commands.allow = [
  "remove_managed_model",
]
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/permissions/files.toml (34 строк, 989 байт)

````toml
[[permission]]
identifier = "allow-files-capability-status"
description = "Allow reading the fixed read-only Files capability contract."
commands.allow = [
  "files_capability_status",
]

[[permission]]
identifier = "allow-select-files"
description = "Allow opening the native picker and registering explicitly selected read-only text files."
commands.allow = [
  "select_files",
]

[[permission]]
identifier = "allow-list-selected-files"
description = "Allow listing sanitized metadata for the current in-memory selected-file registry."
commands.allow = [
  "list_selected_files",
]

[[permission]]
identifier = "allow-preview-selected-file"
description = "Allow a bounded preview reread through one backend-issued opaque file identity."
commands.allow = [
  "preview_selected_file",
]

[[permission]]
identifier = "allow-forget-selected-file"
description = "Allow revoking one backend-issued opaque file identity from the current process."
commands.allow = [
  "forget_selected_file",
]
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/permissions/knowledge-review-command-center.toml (20 строк, 615 байт)

````toml
[[permission]]
identifier = "allow-knowledge-review-snapshot"
description = "Allow reading the bounded LocalComet knowledge review inbox snapshot."
commands.allow = [
  "knowledge_review_snapshot",
]

[[permission]]
identifier = "allow-knowledge-review-refresh"
description = "Allow refreshing read-only LocalComet knowledge review freshness state."
commands.allow = [
  "knowledge_review_refresh",
]

[[permission]]
identifier = "allow-knowledge-review-decision-create"
description = "Allow creating one bounded in-memory human review decision artifact."
commands.allow = [
  "knowledge_review_decision_create",
]
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/resources/localcomet/approved-artifacts.v1.json (459 строк, 15695 байт)

````json
{
  "schema_version": 1,
  "catalog_id": "localcomet-approved-artifacts",
  "catalog_version": "1.0.0",
  "runtimes": [
    {
      "runtime_id": "llama-cpp-windows-x86-64-cpu-bootstrap",
      "provider": "ggml-org",
      "release_tag": "b10068",
      "platform": "windows",
      "architecture": "x86-64",
      "variant": "cpu",
      "upstream_repository": "ggml-org/llama.cpp",
      "upstream_revision": "571d0d540df04f25298d0e159e520d9fc62ed121",
      "asset_filename": "llama-b10068-bin-win-cpu-x64.zip",
      "asset_bytes": 18007324,
      "asset_sha256": "01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89",
      "acquisition": {
        "artifact_id": "llama-cpp-windows-x86-64-cpu-bootstrap",
        "artifact_kind": "runtime",
        "source_type": "approved_https",
        "primary_url": "https://github.com/ggml-org/llama.cpp/releases/download/b10068/llama-b10068-bin-win-cpu-x64.zip",
        "allowed_redirect_hosts": [
          "github.com",
          "objects.githubusercontent.com",
          "release-assets.githubusercontent.com"
        ],
        "expected_filename": "llama-b10068-bin-win-cpu-x64.zip",
        "expected_bytes": 18007324,
        "expected_sha256": "01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89",
        "content_type": "application/octet-stream",
        "managed_relative_destination": "llama-cpp-windows-x86-64-cpu-bootstrap",
        "public_distribution": false,
        "installer_bundled": false,
        "automatic_download": false,
        "user_confirmation_required": true
      },
      "archive_format": "zip",
      "managed_relative_path": "llama-cpp-windows-x86-64-cpu-bootstrap",
      "executable_relative_path": "llama-server.exe",
      "archive_members": [
        {
          "relative_path": "ggml-base.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-alderlake.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-cannonlake.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-cascadelake.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-cooperlake.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-haswell.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-icelake.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-ivybridge.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-piledriver.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-sandybridge.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-sapphirerapids.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-skylakex.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-sse42.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-x64.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-cpu-zen4.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml-rpc-server.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "ggml-rpc.dll",
          "disposition": "install"
        },
        {
          "relative_path": "ggml.dll",
          "disposition": "install"
        },
        {
          "relative_path": "libomp140.x86_64.dll",
          "disposition": "install"
        },
        {
          "relative_path": "llama-batched-bench-impl.dll",
          "disposition": "install"
        },
        {
          "relative_path": "llama-batched-bench.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-bench-impl.dll",
          "disposition": "install"
        },
        {
          "relative_path": "llama-bench.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-cli-impl.dll",
          "disposition": "install"
        },
        {
          "relative_path": "llama-cli.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-common.dll",
          "disposition": "install"
        },
        {
          "relative_path": "llama-completion-impl.dll",
          "disposition": "install"
        },
        {
          "relative_path": "llama-completion.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-fit-params-impl.dll",
          "disposition": "install"
        },
        {
          "relative_path": "llama-fit-params.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-gemma3-cli.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-gguf-split.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-imatrix.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-llava-cli.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-minicpmv-cli.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-mtmd-cli.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-mtmd-debug.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-perplexity-impl.dll",
          "disposition": "install"
        },
        {
          "relative_path": "llama-perplexity.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-quantize-impl.dll",
          "disposition": "install"
        },
        {
          "relative_path": "llama-quantize.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-qwen2vl-cli.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-results.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-server-impl.dll",
          "disposition": "install"
        },
        {
          "relative_path": "llama-server.exe",
          "disposition": "install"
        },
        {
          "relative_path": "llama-template-analysis.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-tokenize.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama-tts.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "llama.dll",
          "disposition": "install"
        },
        {
          "relative_path": "llama.exe",
          "disposition": "recognized_not_installed"
        },
        {
          "relative_path": "mtmd.dll",
          "disposition": "install"
        }
      ],
      "required_files": [
        {
          "relative_path": "ggml-base.dll",
          "bytes": 772096,
          "sha256": "e82e7cd4ea68e689183308aa58a0273dc98e36cea1a066b0688366c213c32962"
        },
        {
          "relative_path": "ggml-cpu-alderlake.dll",
          "bytes": 1180160,
          "sha256": "c68af2cc231d2c0c1eca5da294efe5dd0dad5e1f3249ad272053be281c1008aa"
        },
        {
          "relative_path": "ggml-cpu-cannonlake.dll",
          "bytes": 1395200,
          "sha256": "fb7ccd4768af2e413d64462f87c27ea4d9b58495db941a914f83ab1fd8b3044e"
        },
        {
          "relative_path": "ggml-cpu-cascadelake.dll",
          "bytes": 1381376,
          "sha256": "1a5e6ee151629c1650a9399b065974511dc3413b52f48f224fe863368fdc33b2"
        },
        {
          "relative_path": "ggml-cpu-cooperlake.dll",
          "bytes": 1382400,
          "sha256": "81ff174a388dadbdc17ad5b5fe7a84f035788679b7e84898871a5ec36a363067"
        },
        {
          "relative_path": "ggml-cpu-haswell.dll",
          "bytes": 1184768,
          "sha256": "8c894b71a068b820393b3b3df688fcde054bbed2431d02e627f9e3227ce2d588"
        },
        {
          "relative_path": "ggml-cpu-icelake.dll",
          "bytes": 1388032,
          "sha256": "8d5e142acbdb02fd8c6a8fdc6e467f1d171f4ffe80079b18ff9f5ee60c9364e9"
        },
        {
          "relative_path": "ggml-cpu-ivybridge.dll",
          "bytes": 1073664,
          "sha256": "43ee5b4682c215c49559cdbc79fe1589d43a446e9c2a6c58461bfac42509fbe6"
        },
        {
          "relative_path": "ggml-cpu-piledriver.dll",
          "bytes": 1077760,
          "sha256": "41337951f86aa6868a2a9ec29e327b4d92fbc14c453a6b5636c2d26cb416eebb"
        },
        {
          "relative_path": "ggml-cpu-sandybridge.dll",
          "bytes": 1053696,
          "sha256": "7041e512ab129cdd9e167a3eece7df60438f5f7e854b0e67278b45c023148d45"
        },
        {
          "relative_path": "ggml-cpu-sapphirerapids.dll",
          "bytes": 1659392,
          "sha256": "f0ffc8feb14ebc39147325132b4d05ae2ab9208fe3e2fb02c02005b4ac251a16"
        },
        {
          "relative_path": "ggml-cpu-skylakex.dll",
          "bytes": 1389056,
          "sha256": "590b982d931061b75a4d2296604f658247e5c039295634b931e3a4101906b105"
        },
        {
          "relative_path": "ggml-cpu-sse42.dll",
          "bytes": 876544,
          "sha256": "9290e8d0eecbbf4f923d26683ffbe36b203ea44e1c029fbf4c8c1968d40516ef"
        },
        {
          "relative_path": "ggml-cpu-x64.dll",
          "bytes": 869376,
          "sha256": "e36d94b4eeb177afc008b3297fec3227433307891051cdda4bad221e1baf1b24"
        },
        {
          "relative_path": "ggml-cpu-zen4.dll",
          "bytes": 1389056,
          "sha256": "8309045a77e98768dfc28b1430b006749ffa52d8dfd02c7fe434eb5adaaf3106"
        },
        {
          "relative_path": "ggml-rpc.dll",
          "bytes": 136192,
          "sha256": "033d36e60a0f6ae93de87ac34be2fcfb46404ae6e7d2cc7ec88e6807b61c20d1"
        },
        {
          "relative_path": "ggml.dll",
          "bytes": 86016,
          "sha256": "a706734f601a98861f88fc42f80ef5dfab3cc6ea8ae17f02c9237521a9755353"
        },
        {
          "relative_path": "libomp140.x86_64.dll",
          "bytes": 661856,
          "sha256": "4a20c1e5c115c29771a12324513eb109badac72180f79481527ad79d996ffb33"
        },
        {
          "relative_path": "llama-batched-bench-impl.dll",
          "bytes": 60928,
          "sha256": "9a41ddde60aadc61f2ca0d3bb6c6853ba6b5312c68694b9030cddb6db1c17fc3"
        },
        {
          "relative_path": "llama-bench-impl.dll",
          "bytes": 392704,
          "sha256": "723bc946d6e4a34903355d40899e60304641eb6c718b39ce279018e8483d5a80"
        },
        {
          "relative_path": "llama-cli-impl.dll",
          "bytes": 3542528,
          "sha256": "15e4a626c28bfe97d234dc7d4399fe9d8d09165499012833bc5284807b2b342b"
        },
        {
          "relative_path": "llama-common.dll",
          "bytes": 7816192,
          "sha256": "3f61aa713effbc40f3a523b9a9d6a00851f1ac2fc1abe65468a4cc4c716f05cc"
        },
        {
          "relative_path": "llama-completion-impl.dll",
          "bytes": 132608,
          "sha256": "906741c65a592d1936098496ce923e26477f5baf400865a7f7b47ccbfbb9acc8"
        },
        {
          "relative_path": "llama-fit-params-impl.dll",
          "bytes": 40448,
          "sha256": "9c495c202b1c1dfe9180d2ef98b04bd37bdf2a060b21c65f52f9291932d1206f"
        },
        {
          "relative_path": "llama-perplexity-impl.dll",
          "bytes": 193536,
          "sha256": "003ada3096ef33b921769add3389af9f01b97c7b7addfa43cd0be2af3946d1f4"
        },
        {
          "relative_path": "llama-quantize-impl.dll",
          "bytes": 136704,
          "sha256": "0538ed8fb46348f33f4e30adac7d2cc5404122ae27b725d9aa53538097198194"
        },
        {
          "relative_path": "llama-server-impl.dll",
          "bytes": 9539072,
          "sha256": "957b3cdeb84d88c09c9d8a0e1a378648a5e7b7624a75eb8b48f16a2238d4c902"
        },
        {
          "relative_path": "llama-server.exe",
          "bytes": 9216,
          "sha256": "3a8aea5f889c4b4c2ec41c98f4e1ed484bb7a40c4096883acb23d3cfe26b59fb"
        },
        {
          "relative_path": "llama.dll",
          "bytes": 2684416,
          "sha256": "2d76f08d5742f8800ef63e4976b26c6a36bb55ad565eb530ba1de570266af3f1"
        },
        {
          "relative_path": "mtmd.dll",
          "bytes": 1250304,
          "sha256": "d912fdd1d0bf17c6ff78214e159604a4b34f000ae240bcfe86bcaab780093ae4"
        }
      ],
      "license_asset": {
        "source_relative_path": "third_party/llama.cpp/LICENSE-MIT.txt",
        "destination_relative_path": "LICENSE-MIT.txt",
        "bytes": 1078,
        "sha256": "94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d"
      },
      "permitted_bind_scope": "loopback-only",
      "supported_api_protocol": "openai-compatible-v1",
      "license_id": "MIT",
      "public_distribution": false,
      "status": "approved_internal_bootstrap"
    }
  ],
  "models": [
    {
      "model_id": "qwen2.5-1.5b-instruct-q4-k-m",
      "provider": "Qwen",
      "family": "Qwen2.5",
      "display_name": "Qwen2.5 1.5B Instruct Q4_K_M",
      "format": "GGUF",
      "quantization": "Q4_K_M",
      "upstream_repository": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
      "upstream_revision": "91cad51170dc346986eccefdc2dd33a9da36ead9",
      "asset_filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
      "asset_bytes": 1117320736,
      "asset_sha256": "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e",
      "acquisition": {
        "artifact_id": "qwen2.5-1.5b-instruct-q4-k-m",
        "artifact_kind": "model",
        "source_type": "approved_https",
        "primary_url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "allowed_redirect_hosts": [
          "cas-bridge.xethub.hf.co",
          "cdn-lfs-us-1.hf.co",
          "cdn-lfs.hf.co",
          "huggingface.co",
          "transfer.xethub.hf.co",
          "us.aws.cdn.hf.co"
        ],
        "expected_filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "expected_bytes": 1117320736,
        "expected_sha256": "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e",
        "content_type": "application/octet-stream",
        "managed_relative_destination": "qwen2.5-1.5b-instruct-q4-k-m/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "public_distribution": false,
        "installer_bundled": false,
        "automatic_download": false,
        "user_confirmation_required": true
      },
      "license_id": "Apache-2.0",
      "compatible_runtime_ids": [
        "llama-cpp-windows-x86-64-cpu-bootstrap"
      ],
      "managed_relative_path": "qwen2.5-1.5b-instruct-q4-k-m/qwen2.5-1.5b-instruct-q4_k_m.gguf",
      "public_distribution": false,
      "installer_bundled": false,
      "bootstrap_purpose": "INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION",
      "status": "approved_internal_bootstrap"
    }
  ]
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/src/app_data_root.rs (186 строк, 5753 байт)

````rust
use std::env;
use std::path::{Path, PathBuf};

pub(crate) const APPLICATION_DATA_ROOT_OVERRIDE: &str = "LOCALCOMET_APP_DATA_ROOT";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum ApplicationDataRootError {
    Empty,
    Relative,
    NonLocal,
}

impl ApplicationDataRootError {
    pub(crate) fn code(self) -> &'static str {
        match self {
            Self::Empty => "empty_app_data_root_override",
            Self::Relative => "relative_app_data_root_override",
            Self::NonLocal => "nonlocal_app_data_root_override",
        }
    }
}

pub(crate) fn resolve_application_data_root(
    default_local_data_dir: &Path,
) -> Result<PathBuf, ApplicationDataRootError> {
    match explicit_application_data_root()? {
        Some(root) => Ok(root),
        None => Ok(default_local_data_dir.join("LocalComet")),
    }
}

pub(crate) fn resolve_startup_application_data_root(
) -> Result<Option<PathBuf>, ApplicationDataRootError> {
    match explicit_application_data_root()? {
        Some(root) => Ok(Some(root)),
        None => Ok(env::var_os("LOCALAPPDATA")
            .map(PathBuf::from)
            .map(|base| base.join("LocalComet"))),
    }
}

fn explicit_application_data_root() -> Result<Option<PathBuf>, ApplicationDataRootError> {
    let Some(value) = env::var_os(APPLICATION_DATA_ROOT_OVERRIDE) else {
        return Ok(None);
    };
    if value.is_empty() {
        return Err(ApplicationDataRootError::Empty);
    }
    let root = PathBuf::from(value);
    if !root.is_absolute() {
        return Err(ApplicationDataRootError::Relative);
    }
    if !is_local_filesystem_path(&root) {
        return Err(ApplicationDataRootError::NonLocal);
    }
    Ok(Some(root))
}

#[cfg(windows)]
fn is_local_filesystem_path(path: &Path) -> bool {
    use std::path::{Component, Prefix};

    !path.components().any(|component| {
        matches!(
            component,
            Component::Prefix(prefix)
                if matches!(prefix.kind(), Prefix::UNC(_, _) | Prefix::VerbatimUNC(_, _))
        )
    })
}

#[cfg(not(windows))]
fn is_local_filesystem_path(_path: &Path) -> bool {
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::ffi::OsString;
    use std::sync::{Mutex, OnceLock};

    static OVERRIDE_LOCK: OnceLock<Mutex<()>> = OnceLock::new();

    struct OverrideGuard {
        previous: Option<OsString>,
    }

    impl OverrideGuard {
        fn set(value: Option<OsString>) -> Self {
            let previous = env::var_os(APPLICATION_DATA_ROOT_OVERRIDE);
            match value {
                Some(value) => env::set_var(APPLICATION_DATA_ROOT_OVERRIDE, value),
                None => env::remove_var(APPLICATION_DATA_ROOT_OVERRIDE),
            }
            Self { previous }
        }
    }

    impl Drop for OverrideGuard {
        fn drop(&mut self) {
            match &self.previous {
                Some(value) => env::set_var(APPLICATION_DATA_ROOT_OVERRIDE, value),
                None => env::remove_var(APPLICATION_DATA_ROOT_OVERRIDE),
            }
        }
    }

    fn isolated_root(label: &str) -> PathBuf {
        env::temp_dir().join(format!(
            "localcomet-app-data-root-{label}-{}",
            std::process::id()
        ))
    }

    #[test]
    fn default_resolution_preserves_the_existing_localcomet_path() {
        let _lock = OVERRIDE_LOCK
            .get_or_init(|| Mutex::new(()))
            .lock()
            .expect("override lock");
        let _override = OverrideGuard::set(None);
        let local_data_dir = isolated_root("default-parent");

        let root = resolve_application_data_root(&local_data_dir).expect("default root");

        assert_eq!(root, local_data_dir.join("LocalComet"));
    }

    #[test]
    fn absolute_override_selects_the_exact_isolated_application_root() {
        let _lock = OVERRIDE_LOCK
            .get_or_init(|| Mutex::new(()))
            .lock()
            .expect("override lock");
        let expected = isolated_root("explicit");
        let _override = OverrideGuard::set(Some(expected.clone().into_os_string()));

        assert_eq!(
            resolve_application_data_root(&isolated_root("default-parent")).expect("explicit root"),
            expected
        );
        assert_eq!(
            resolve_startup_application_data_root().expect("startup root"),
            Some(expected)
        );
    }

    #[test]
    fn empty_and_relative_overrides_are_rejected_without_default_fallback() {
        let _lock = OVERRIDE_LOCK
            .get_or_init(|| Mutex::new(()))
            .lock()
            .expect("override lock");
        let default_parent = isolated_root("default-parent");

        let _empty = OverrideGuard::set(Some(OsString::new()));
        assert_eq!(
            resolve_application_data_root(&default_parent).expect_err("empty override rejected"),
            ApplicationDataRootError::Empty
        );
        drop(_empty);

        let _relative = OverrideGuard::set(Some(OsString::from("relative\\LocalComet")));
        assert_eq!(
            resolve_application_data_root(&default_parent).expect_err("relative override rejected"),
            ApplicationDataRootError::Relative
        );
    }

    #[cfg(windows)]
    #[test]
    fn network_share_override_is_rejected_as_nonlocal() {
        let _lock = OVERRIDE_LOCK
            .get_or_init(|| Mutex::new(()))
            .lock()
            .expect("override lock");
        let _override = OverrideGuard::set(Some(OsString::from(r"\\server\share\LocalComet")));

        assert_eq!(
            resolve_application_data_root(&isolated_root("default-parent"))
                .expect_err("network share rejected"),
            ApplicationDataRootError::NonLocal
        );
    }
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/src/approval.rs (604 строк, 21016 байт)

````rust
use sha2::{Digest, Sha256};
use std::collections::HashMap;
use std::time::{Duration, Instant};
use subtle::ConstantTimeEq;

const TOKEN_ENTROPY_BYTES: usize = 32;
const TOKEN_PREFIX: &str = "lcap_";
const MAX_ACTIVE_TOKENS: usize = 64;
const DEFAULT_TTL: Duration = Duration::from_secs(300);
const GRANT_TTL: Duration = Duration::from_secs(30);

#[derive(Clone, Debug)]
pub struct ApprovalScope {
    pub tool: String,
    pub input_digest: [u8; 32],
    pub workspace: String,
    pub session: String,
    /// Risk classification recorded at issue time (for UI/policy/audit). The
    /// authorization decision is enforced by scope matching in execute_approved;
    /// risk_level is descriptive metadata retained on the scope.
    #[allow(dead_code)]
    pub risk_level: RiskLevel,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum RiskLevel {
    ReadOnly,
    Guarded,
    Dangerous,
}

#[derive(Debug)]
struct ApprovalEntry {
    scope: ApprovalScope,
    nonce: [u8; 16],
    issued_at: Instant,
    ttl: Duration,
}

#[derive(Debug)]
pub enum ApprovalError {
    RegistryFull,
    TokenNotFound,
    ToolMismatch,
    InputDigestMismatch,
    WorkspaceMismatch,
    SessionMismatch,
    Expired,
    /// Reserved for a future soft-consume design that marks tokens consumed
    /// without removing them. The current implementation removes a token on
    /// consume, so a replay surfaces as TokenNotFound; this variant is retained
    /// to keep the error vocabulary stable.
    #[allow(dead_code)]
    AlreadyConsumed,
    InvalidToken,
}

impl std::fmt::Display for ApprovalError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::RegistryFull => write!(f, "approval registry is full"),
            Self::TokenNotFound => write!(f, "approval token not found"),
            Self::ToolMismatch => write!(f, "approval tool mismatch"),
            Self::InputDigestMismatch => write!(f, "approval input digest mismatch"),
            Self::WorkspaceMismatch => write!(f, "approval workspace mismatch"),
            Self::SessionMismatch => write!(f, "approval session mismatch"),
            Self::Expired => write!(f, "approval token expired"),
            Self::AlreadyConsumed => write!(f, "approval token already consumed"),
            Self::InvalidToken => write!(f, "approval token is invalid"),
        }
    }
}

pub struct ApprovalRegistry {
    entries: HashMap<String, ApprovalEntry>,
    session_id: String,
}

impl ApprovalRegistry {
    pub fn new() -> Self {
        let mut session_bytes = [0u8; 16];
        getrandom::getrandom(&mut session_bytes)
            .expect("OS CSPRNG unavailable for session generation");
        Self {
            entries: HashMap::new(),
            session_id: hex_encode(&session_bytes),
        }
    }

    pub fn session_id(&self) -> &str {
        &self.session_id
    }

    pub fn issue(&mut self, scope: ApprovalScope) -> Result<String, ApprovalError> {
        self.issue_with_ttl(scope, DEFAULT_TTL)
    }

    fn issue_with_ttl(
        &mut self,
        scope: ApprovalScope,
        ttl: Duration,
    ) -> Result<String, ApprovalError> {
        // Sweep already-expired entries before the capacity check so stale
        // tokens cannot permanently occupy registry slots. This only removes
        // tokens past their TTL; it never weakens validation (fail-closed).
        self.entries
            .retain(|_, entry| entry.issued_at.elapsed() <= entry.ttl);

        if self.entries.len() >= MAX_ACTIVE_TOKENS {
            return Err(ApprovalError::RegistryFull);
        }

        let mut token_bytes = [0u8; TOKEN_ENTROPY_BYTES];
        getrandom::getrandom(&mut token_bytes).expect("OS CSPRNG unavailable for token generation");

        let mut nonce = [0u8; 16];
        getrandom::getrandom(&mut nonce).expect("OS CSPRNG unavailable for nonce generation");

        let token_string = format!("{}{}", TOKEN_PREFIX, hex_encode(&token_bytes));

        self.entries.insert(
            token_string.clone(),
            ApprovalEntry {
                scope,
                nonce,
                issued_at: Instant::now(),
                ttl,
            },
        );

        Ok(token_string)
    }

    pub fn execute_approved(
        &mut self,
        token: &str,
        tool: &str,
        input_digest: &[u8; 32],
        workspace: &str,
    ) -> Result<ExecutionGrant, ApprovalError> {
        if !token.starts_with(TOKEN_PREFIX) {
            return Err(ApprovalError::InvalidToken);
        }

        let entry = self
            .entries
            .remove(token)
            .ok_or(ApprovalError::TokenNotFound)?;

        if entry.issued_at.elapsed() > entry.ttl {
            return Err(ApprovalError::Expired);
        }

        let scope = &entry.scope;

        if scope.tool.as_bytes().ct_eq(tool.as_bytes()).unwrap_u8() != 1 {
            return Err(ApprovalError::ToolMismatch);
        }

        if scope.input_digest.ct_eq(input_digest).unwrap_u8() != 1 {
            return Err(ApprovalError::InputDigestMismatch);
        }

        if scope
            .workspace
            .as_bytes()
            .ct_eq(workspace.as_bytes())
            .unwrap_u8()
            != 1
        {
            return Err(ApprovalError::WorkspaceMismatch);
        }

        if scope
            .session
            .as_bytes()
            .ct_eq(self.session_id.as_bytes())
            .unwrap_u8()
            != 1
        {
            return Err(ApprovalError::SessionMismatch);
        }

        let mut grant_id = [0u8; 16];
        getrandom::getrandom(&mut grant_id).expect("OS CSPRNG unavailable for grant generation");

        Ok(ExecutionGrant {
            grant_id: hex_encode(&grant_id),
            tool: scope.tool.clone(),
            input_digest: *input_digest,
            workspace: workspace.to_owned(),
            session: self.session_id.clone(),
            nonce: entry.nonce,
            valid_until: Instant::now() + GRANT_TTL,
        })
    }

    pub fn invalidate_workspace(&mut self, old_workspace: &str) {
        self.entries
            .retain(|_, entry| entry.scope.workspace != old_workspace);
    }

    /// Invalidate every active token (e.g. on session reset / restart).
    /// Public API; not invoked internally yet.
    #[allow(dead_code)]
    pub fn invalidate_all(&mut self) {
        self.entries.clear();
    }

    /// Number of active (not yet consumed/expired) tokens. Used by tests and
    /// intended for monitoring/diagnostics.
    #[allow(dead_code)]
    pub fn active_count(&self) -> usize {
        self.entries.len()
    }

    #[cfg(test)]
    fn issue_backdated(
        &mut self,
        scope: ApprovalScope,
        ttl: Duration,
        backdate: Duration,
    ) -> String {
        let mut token_bytes = [0u8; TOKEN_ENTROPY_BYTES];
        getrandom::getrandom(&mut token_bytes).expect("OS CSPRNG unavailable for token generation");
        let mut nonce = [0u8; 16];
        getrandom::getrandom(&mut nonce).expect("OS CSPRNG unavailable for nonce generation");
        let token_string = format!("{}{}", TOKEN_PREFIX, hex_encode(&token_bytes));
        self.entries.insert(
            token_string.clone(),
            ApprovalEntry {
                scope,
                nonce,
                issued_at: Instant::now() - backdate,
                ttl,
            },
        );
        token_string
    }
}

#[derive(Clone, Debug)]
pub struct ExecutionGrant {
    pub grant_id: String,
    pub tool: String,
    // input_digest and nonce are part of the grant's authorization material.
    // They are consumed by a downstream tool-execution path when one exists
    // (the desktop sidecar currently performs no filesystem tool execution);
    // retained so the grant is self-describing and verifiable at that boundary.
    #[allow(dead_code)]
    pub input_digest: [u8; 32],
    pub workspace: String,
    pub session: String,
    #[allow(dead_code)]
    pub nonce: [u8; 16],
    pub valid_until: Instant,
}

impl ExecutionGrant {
    pub fn is_expired(&self) -> bool {
        Instant::now() >= self.valid_until
    }
}

pub fn canonical_input_digest(input: &serde_json::Value) -> [u8; 32] {
    let canonical = canonicalize_json(input);
    let mut hasher = Sha256::new();
    hasher.update(canonical.as_bytes());
    hasher.finalize().into()
}

fn canonicalize_json(value: &serde_json::Value) -> String {
    match value {
        serde_json::Value::Null => "null".to_owned(),
        serde_json::Value::Bool(b) => b.to_string(),
        serde_json::Value::Number(n) => n.to_string(),
        serde_json::Value::String(s) => format!("\"{}\"", escape_json_string(s)),
        serde_json::Value::Array(arr) => {
            let items: Vec<String> = arr.iter().map(canonicalize_json).collect();
            format!("[{}]", items.join(","))
        }
        serde_json::Value::Object(map) => {
            let mut keys: Vec<&String> = map.keys().collect();
            keys.sort();
            let pairs: Vec<String> = keys
                .iter()
                .map(|k| {
                    format!(
                        "\"{}\":{}",
                        escape_json_string(k),
                        canonicalize_json(&map[*k])
                    )
                })
                .collect();
            format!("{{{}}}", pairs.join(","))
        }
    }
}

fn escape_json_string(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if c.is_control() => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn test_scope(tool: &str, workspace: &str, session: &str) -> ApprovalScope {
        ApprovalScope {
            tool: tool.to_owned(),
            input_digest: canonical_input_digest(&json!({"path": "test.txt", "content": "hello"})),
            workspace: workspace.to_owned(),
            session: session.to_owned(),
            risk_level: RiskLevel::Guarded,
        }
    }

    #[test]
    fn issued_tokens_are_unique_and_256_bits() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let mut tokens = Vec::new();
        for _ in 0..MAX_ACTIVE_TOKENS {
            let scope = test_scope("files.patch", "/workspace", &session);
            let token = registry.issue(scope).unwrap();
            tokens.push(token);
        }
        let unique: std::collections::HashSet<&String> = tokens.iter().collect();
        assert_eq!(unique.len(), MAX_ACTIVE_TOKENS);
        for token in &tokens {
            let hex_part = token.strip_prefix(TOKEN_PREFIX).unwrap();
            assert_eq!(hex_part.len(), 64);
        }
    }

    #[test]
    fn two_registries_issue_different_first_tokens() {
        let mut r1 = ApprovalRegistry::new();
        let mut r2 = ApprovalRegistry::new();
        let s1_session = r1.session_id().to_owned();
        let s2_session = r2.session_id().to_owned();
        let t1 = r1
            .issue(test_scope("files.patch", "/w", &s1_session))
            .unwrap();
        let t2 = r2
            .issue(test_scope("files.patch", "/w", &s2_session))
            .unwrap();
        assert_ne!(t1, t2);
    }

    #[test]
    fn execute_approved_succeeds_with_matching_scope() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt", "content": "data"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/workspace".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(&token, "files.patch", &digest, "/workspace")
            .unwrap();
        assert_eq!(grant.tool, "files.patch");
        assert_eq!(grant.workspace, "/workspace");
    }

    #[test]
    fn replay_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let token = registry.issue(scope).unwrap();
        registry
            .execute_approved(&token, "files.patch", &digest, "/w")
            .unwrap();
        let err = registry
            .execute_approved(&token, "files.patch", &digest, "/w")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::TokenNotFound));
    }

    #[test]
    fn wrong_tool_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(&token, "files.delete", &digest, "/w")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::ToolMismatch));
    }

    #[test]
    fn wrong_input_digest_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input_a = json!({"path": "a.txt", "content": "A"});
        let input_b = json!({"path": "a.txt", "content": "B"});
        let digest_a = canonical_input_digest(&input_a);
        let digest_b = canonical_input_digest(&input_b);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest_a,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(&token, "files.patch", &digest_b, "/w")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::InputDigestMismatch));
    }

    #[test]
    fn wrong_workspace_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/workspace-a".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(&token, "files.patch", &digest, "/workspace-b")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::WorkspaceMismatch));
    }

    #[test]
    fn key_reordering_does_not_change_digest() {
        let a = json!({"alpha": 1, "beta": 2});
        let b = json!({"beta": 2, "alpha": 1});
        assert_eq!(canonical_input_digest(&a), canonical_input_digest(&b));
    }

    #[test]
    fn value_change_changes_digest() {
        let a = json!({"key": "value_a"});
        let b = json!({"key": "value_b"});
        assert_ne!(canonical_input_digest(&a), canonical_input_digest(&b));
    }

    #[test]
    fn invalidate_workspace_removes_matching_tokens() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"x": 1});
        let digest = canonical_input_digest(&input);
        let scope_a = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/ws-a".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let scope_b = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/ws-b".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let token_a = registry.issue(scope_a).unwrap();
        let _token_b = registry.issue(scope_b).unwrap();
        assert_eq!(registry.active_count(), 2);
        registry.invalidate_workspace("/ws-a");
        assert_eq!(registry.active_count(), 1);
        let err = registry
            .execute_approved(&token_a, "files.patch", &digest, "/ws-a")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::TokenNotFound));
    }

    #[test]
    fn invalid_prefix_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let digest = [0u8; 32];
        let err = registry
            .execute_approved("apt_fake_token", "files.patch", &digest, "/w")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::InvalidToken));
    }

    #[test]
    fn wrong_session_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        // Token is bound to a forged session that does not match the registry.
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: "00000000000000000000000000000000".to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let token = registry.issue(scope).unwrap();
        let err = registry
            .execute_approved(&token, "files.patch", &digest, "/w")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::SessionMismatch));
    }

    #[test]
    fn expired_token_is_rejected() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        let scope = test_scope("files.patch", "/w", &session);
        let digest = scope.input_digest;
        // Backdate the token so it is already expired (deterministic, no sleep).
        let token =
            registry.issue_backdated(scope, Duration::from_secs(1), Duration::from_secs(10));
        let err = registry
            .execute_approved(&token, "files.patch", &digest, "/w")
            .unwrap_err();
        assert!(matches!(err, ApprovalError::Expired));
    }

    #[test]
    fn ttl_sweep_frees_expired_slots_before_capacity_check() {
        let mut registry = ApprovalRegistry::new();
        let session = registry.session_id().to_owned();
        // Fill the registry to capacity with tokens that are already expired
        // (backdated). This is deterministic and independent of wall-clock timing.
        for _ in 0..MAX_ACTIVE_TOKENS {
            registry.issue_backdated(
                test_scope("files.patch", "/w", &session),
                Duration::from_secs(1),
                Duration::from_secs(10),
            );
        }
        assert_eq!(registry.active_count(), MAX_ACTIVE_TOKENS);
        // Without the sweep this would fail with RegistryFull; the sweep clears
        // the expired entries first, so a fresh issue succeeds.
        let scope = test_scope("files.patch", "/w", &session);
        assert!(registry.issue(scope).is_ok());
        assert_eq!(registry.active_count(), 1);
    }

    #[test]
    fn execution_grant_carries_short_lived_expiry() {
        let mut registry = ApprovalRegistry::new();
        let input = json!({"path": "a.txt"});
        let digest = canonical_input_digest(&input);
        let scope = ApprovalScope {
            tool: "files.patch".to_owned(),
            input_digest: digest,
            workspace: "/w".to_owned(),
            session: registry.session_id().to_owned(),
            risk_level: RiskLevel::Guarded,
        };
        let token = registry.issue(scope).unwrap();
        let grant = registry
            .execute_approved(&token, "files.patch", &digest, "/w")
            .unwrap();
        // A freshly minted grant must not be expired yet.
        assert!(!grant.is_expired());
        // A grant whose deadline is in the past must report expired.
        let stale = ExecutionGrant {
            valid_until: Instant::now() - Duration::from_secs(1),
            ..grant.clone()
        };
        assert!(stale.is_expired());
    }
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/src/approval_commands.rs (158 строк, 5992 байт)

````rust
use crate::approval::{canonical_input_digest, ApprovalRegistry, ApprovalScope, RiskLevel};
use crate::control_plane::BridgeError;
use crate::workspace::WorkspaceIdentity;
use serde_json::{json, Value};
use std::sync::Mutex;
use tauri::State;

/// Managed approval state: the single Rust authority for issuing and consuming
/// scoped one-time approval tokens, plus the currently confirmed workspace.
pub struct ApprovalState {
    registry: Mutex<ApprovalRegistry>,
    workspace: Mutex<Option<WorkspaceIdentity>>,
}

impl Default for ApprovalState {
    fn default() -> Self {
        Self {
            registry: Mutex::new(ApprovalRegistry::new()),
            workspace: Mutex::new(None),
        }
    }
}

impl ApprovalState {
    /// Store a confirmed workspace identity.
    ///
    /// Public API for workspace management. The `set_workspace` Tauri command
    /// updates the guards directly (to avoid re-locking the same mutexes), so
    /// this helper is not yet called internally; it is retained as the
    /// documented entry point for future UI/IPC workspace flows.
    #[allow(dead_code)]
    pub fn set_workspace(&self, identity: WorkspaceIdentity) {
        let mut workspace = self
            .workspace
            .lock()
            .expect("approval workspace lock poisoned");
        *workspace = Some(identity);
    }

    /// Invalidate all approval tokens bound to a previous workspace.
    ///
    /// `workspace::change_workspace` already performs this invalidation; this
    /// helper exposes the same operation for callers that change workspace
    /// outside that path.
    #[allow(dead_code)]
    pub fn invalidate_workspace_tokens(&self, old_workspace: &str) {
        let mut registry = self.registry.lock().expect("approval registry poisoned");
        registry.invalidate_workspace(old_workspace);
    }
}

/// Maps a tool name to its risk level.
///
/// MUST stay in sync with security/invariants/tool_risk_levels.toml. The
/// scripts/check_tool_risk_registry.py gate enforces the Python-side registry;
/// this mirror covers the Rust authorization boundary.
fn risk_level_for_tool(tool: &str) -> RiskLevel {
    match tool {
        "files.delete" | "artifact.remove" => RiskLevel::Dangerous,
        "files.write"
        | "files.create_folder"
        | "artifact.download"
        | "runtime.start"
        | "runtime.stop"
        | "model.binding.set" => RiskLevel::Guarded,
        _ => RiskLevel::ReadOnly,
    }
}

/// Issue a scoped one-time approval token bound to (tool, input digest,
/// workspace, session). Fails closed if no workspace is confirmed.
#[tauri::command]
pub fn request_approval(
    state: State<'_, ApprovalState>,
    tool: String,
    input: Value,
) -> Result<String, BridgeError> {
    let risk_level = risk_level_for_tool(&tool);
    let digest = canonical_input_digest(&input);
    let mut registry = state.registry.lock().expect("approval registry poisoned");
    let workspace_guard = state
        .workspace
        .lock()
        .expect("approval workspace lock poisoned");
    let workspace = workspace_guard.as_ref().ok_or_else(|| {
        BridgeError::new("no_workspace", "approval requires a confirmed workspace")
    })?;
    let scope = ApprovalScope {
        tool,
        input_digest: digest,
        workspace: workspace.canonical_path.clone(),
        session: registry.session_id().to_owned(),
        risk_level,
    };
    registry
        .issue(scope)
        .map_err(|error| BridgeError::new("approval_error", &error.to_string()))
}

/// Atomically validate scope and consume a one-time token, returning an
/// execution grant on success.
///
/// NOTE (honest boundary): the desktop sidecar exposes no tool.call execution
/// path (filesystem methods are explicitly `unsupported_method`), so this
/// command produces the authoritative grant but does not dispatch to the
/// sidecar. A future tool-execution path must present this grant; there is no
/// bypass around execute_approved.
#[tauri::command]
pub fn execute_approved(
    state: State<'_, ApprovalState>,
    token: String,
    tool: String,
    input: Value,
) -> Result<Value, BridgeError> {
    let digest = canonical_input_digest(&input);
    let mut registry = state.registry.lock().expect("approval registry poisoned");
    let workspace_guard = state
        .workspace
        .lock()
        .expect("approval workspace lock poisoned");
    let workspace = workspace_guard.as_ref().ok_or_else(|| {
        BridgeError::new("no_workspace", "approval requires a confirmed workspace")
    })?;
    let grant = registry
        .execute_approved(&token, &tool, &digest, &workspace.canonical_path)
        .map_err(|error| BridgeError::new("approval_denied", &error.to_string()))?;
    if grant.is_expired() {
        return Err(BridgeError::new("grant_expired", "execution grant expired"));
    }
    Ok(json!({
        "grant_id": grant.grant_id,
        "tool": grant.tool,
        "workspace": grant.workspace,
        "session": grant.session,
    }))
}

/// Confirm a workspace: validate the path, invalidate tokens bound to the
/// previous workspace, and store the new identity. Fails closed on invalid
/// paths or symlink/reparse escape.
#[tauri::command]
pub fn set_workspace(state: State<'_, ApprovalState>, path: String) -> Result<Value, BridgeError> {
    let raw = std::path::Path::new(&path);
    let mut registry = state.registry.lock().expect("approval registry poisoned");
    let mut workspace_guard = state
        .workspace
        .lock()
        .expect("approval workspace lock poisoned");
    let current = workspace_guard.clone();
    let identity = crate::workspace::change_workspace(raw, &mut registry, &current)
        .map_err(|error| BridgeError::new("workspace_error", &error.to_string()))?;
    *workspace_guard = Some(identity.clone());
    Ok(json!({
        "status": "ok",
        "canonical_path": identity.canonical_path,
        "workspace_digest": identity.digest,
    }))
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/src/artifact_acquisition.rs (2256 строк, 86877 байт)

````rust
use crate::artifact_trust::{
    source_controlled_runtime_license_bytes, ApprovedDownloadArtifact, ApprovedModelArtifact,
    ApprovedRuntimeArtifact, ArtifactKind, ArtifactTrustService, InstallationStatus,
    RuntimeArchiveMemberDisposition,
};
use crate::control_plane::{BridgeError, ControlPlaneBridge};
use crate::managed_runtime::{ManagedRuntimeState, ManagedRuntimeSupervisor};
use reqwest::blocking::{Client, Response};
use reqwest::redirect::Policy;
use reqwest::Url;
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tauri::State;
use zip::ZipArchive;

#[cfg(windows)]
use std::ffi::OsStr;
#[cfg(windows)]
use std::os::windows::ffi::OsStrExt;
#[cfg(windows)]
use windows_sys::Win32::Storage::FileSystem::GetDiskFreeSpaceExW;

const MAX_REDIRECTS: usize = 5;
const DOWNLOAD_BUFFER_BYTES: usize = 64 * 1024;
const PROGRESS_UPDATE_BYTES: u64 = 512 * 1024;
const DISK_RESERVE_BYTES: u64 = 64 * 1024 * 1024;
const MAX_STALE_PARTIALS: usize = 64;
const MAX_RUNTIME_ARCHIVE_MEMBERS: usize = 128;
const ACQUISITION_EVENT_SCHEMA_VERSION: u32 = 1;

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ArtifactDownloadLifecycle {
    Idle,
    AwaitingConfirmation,
    CheckingDisk,
    Downloading,
    Cancelling,
    Cancelled,
    VerifyingSize,
    VerifyingHash,
    ValidatingArtifact,
    Installing,
    Completed,
    Failed,
}

impl ArtifactDownloadLifecycle {
    fn terminal(&self) -> bool {
        matches!(self, Self::Cancelled | Self::Completed | Self::Failed)
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
enum AcquisitionFailureStage {
    Transfer,
    SizeVerification,
    HashVerification,
    ArchiveValidation,
    StagingExtraction,
    AtomicPromotion,
    PostInstallValidation,
}

#[derive(Serialize)]
struct AcquisitionFailureEvent<'a> {
    schema_version: u32,
    timestamp_utc_ms: u64,
    artifact_kind: &'static str,
    artifact_id: &'a str,
    terminal_status: &'static str,
    stage: AcquisitionFailureStage,
    error_code: &'a str,
    downloaded_bytes: u64,
    expected_bytes: u64,
    archive_member: Option<&'a str>,
    archive_disposition: Option<RuntimeArchiveMemberDisposition>,
    expected_member_count: Option<u64>,
    observed_member_count: Option<u64>,
    cleanup_complete: bool,
    final_artifact_exists: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ArtifactDownloadState {
    pub job_id: String,
    pub artifact_id: String,
    pub lifecycle: ArtifactDownloadLifecycle,
    pub expected_bytes: u64,
    pub received_bytes: u64,
    pub percent: Option<u8>,
    pub started_utc_ms: u64,
    pub updated_utc_ms: u64,
    pub error_code: Option<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ApprovedDownloadableArtifact {
    pub artifact_id: String,
    pub kind: ArtifactKind,
    pub display_name: String,
    pub source_identity: String,
    pub expected_bytes: u64,
    pub license_id: String,
    pub format: Option<String>,
    pub quantization: Option<String>,
    pub user_confirmation_required: bool,
    pub automatic_download: bool,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedModelRemovalResult {
    pub model_id: String,
    pub removed: bool,
}

#[derive(Clone)]
pub struct ArtifactAcquisitionManager {
    artifacts: Arc<ArtifactTrustService>,
    jobs: Arc<Mutex<DownloadRegistry>>,
    job_sequence: Arc<AtomicU64>,
    diagnostic_lock: Arc<Mutex<()>>,
}

#[derive(Default)]
struct DownloadRegistry {
    jobs: HashMap<String, DownloadJob>,
    active_by_artifact: HashMap<String, String>,
}

struct DownloadJob {
    state: ArtifactDownloadState,
    cancel_requested: Arc<AtomicBool>,
}

#[derive(Debug)]
struct AcquisitionError {
    code: &'static str,
    archive_member: Option<String>,
    archive_disposition: Option<RuntimeArchiveMemberDisposition>,
    expected_member_count: Option<u64>,
    observed_member_count: Option<u64>,
}

impl AcquisitionError {
    fn new(code: &'static str) -> Self {
        Self {
            code,
            archive_member: None,
            archive_disposition: None,
            expected_member_count: None,
            observed_member_count: None,
        }
    }

    fn archive_member(
        mut self,
        member: String,
        disposition: Option<RuntimeArchiveMemberDisposition>,
    ) -> Self {
        self.archive_member = Some(member);
        self.archive_disposition = disposition;
        self
    }

    fn archive_member_counts(mut self, expected: usize, observed: usize) -> Self {
        self.expected_member_count = Some(expected as u64);
        self.observed_member_count = Some(observed as u64);
        self
    }
}

impl ArtifactAcquisitionManager {
    pub fn new(artifacts: Arc<ArtifactTrustService>) -> Self {
        let manager = Self {
            artifacts,
            jobs: Arc::new(Mutex::new(DownloadRegistry::default())),
            job_sequence: Arc::new(AtomicU64::new(0)),
            diagnostic_lock: Arc::new(Mutex::new(())),
        };
        manager.cleanup_stale_partials();
        manager
    }

    pub fn approved_artifacts(&self) -> Vec<ApprovedDownloadableArtifact> {
        let mut approved = Vec::new();
        for runtime in self.artifacts.runtime_catalog().runtimes {
            approved.push(ApprovedDownloadableArtifact {
                artifact_id: runtime.runtime_id,
                kind: ArtifactKind::Runtime,
                display_name: format!("llama.cpp {}", runtime.release_tag),
                source_identity: runtime.upstream_repository,
                expected_bytes: runtime.asset_bytes,
                license_id: runtime.license_id,
                format: Some(runtime.archive_format),
                quantization: None,
                user_confirmation_required: true,
                automatic_download: false,
            });
        }
        for model in self.artifacts.model_catalog().models {
            approved.push(ApprovedDownloadableArtifact {
                artifact_id: model.model_id,
                kind: ArtifactKind::Model,
                display_name: model.display_name,
                source_identity: model.upstream_repository,
                expected_bytes: model.asset_bytes,
                license_id: model.license_id,
                format: Some(model.format),
                quantization: Some(model.quantization),
                user_confirmation_required: true,
                automatic_download: false,
            });
        }
        approved
    }

    pub fn start(
        &self,
        artifact_id: &str,
        confirmed: bool,
    ) -> Result<ArtifactDownloadState, BridgeError> {
        if !confirmed {
            return Err(BridgeError::new(
                "confirmation_required",
                "approved artifact download requires confirmation",
            ));
        }
        let artifact = self
            .artifacts
            .approved_download_artifact(artifact_id)
            .map_err(BridgeError::from)?;
        let current = self
            .artifacts
            .artifact_validation_status(artifact_id)
            .map_err(BridgeError::from)?;
        if current.installation_status == InstallationStatus::Valid {
            let mut completed = self.new_state(
                artifact_id,
                current.expected_bytes,
                ArtifactDownloadLifecycle::Completed,
            );
            completed.received_bytes = current.expected_bytes;
            completed.percent = percent(current.expected_bytes, current.expected_bytes);
            let mut registry = self.jobs.lock().expect("download registry poisoned");
            registry.jobs.insert(
                completed.job_id.clone(),
                DownloadJob {
                    state: completed.clone(),
                    cancel_requested: Arc::new(AtomicBool::new(false)),
                },
            );
            return Ok(completed);
        }
        if current.installation_status != InstallationStatus::NotInstalled {
            return Err(BridgeError::new(
                "conflicting_installed_artifact",
                "approved artifact is present but not valid",
            ));
        }
        let destination = self
            .artifacts
            .download_destination(&artifact)
            .map_err(BridgeError::from)?;
        if destination.exists() {
            return Err(BridgeError::new(
                "conflicting_installed_artifact",
                "approved artifact destination already exists",
            ));
        }
        let expected_bytes = expected_bytes(&artifact);
        let mut state =
            self.new_state(artifact_id, expected_bytes, ArtifactDownloadLifecycle::Idle);
        state.lifecycle = ArtifactDownloadLifecycle::AwaitingConfirmation;
        state.updated_utc_ms = now_utc_ms();
        let cancel_requested = Arc::new(AtomicBool::new(false));
        {
            let mut registry = self.jobs.lock().expect("download registry poisoned");
            if let Some(existing_id) = registry.active_by_artifact.get(artifact_id) {
                return registry
                    .jobs
                    .get(existing_id)
                    .map(|job| job.state.clone())
                    .ok_or_else(|| {
                        BridgeError::new("download_conflict", "active download unavailable")
                    });
            }
            registry
                .active_by_artifact
                .insert(artifact_id.to_string(), state.job_id.clone());
            registry.jobs.insert(
                state.job_id.clone(),
                DownloadJob {
                    state: state.clone(),
                    cancel_requested: Arc::clone(&cancel_requested),
                },
            );
        }
        let manager = self.clone();
        let job_id = state.job_id.clone();
        thread::spawn(move || manager.run_job(job_id, artifact, cancel_requested));
        Ok(state)
    }

    pub fn get(&self, job_id: &str) -> Result<ArtifactDownloadState, BridgeError> {
        validate_job_id(job_id)?;
        self.jobs
            .lock()
            .expect("download registry poisoned")
            .jobs
            .get(job_id)
            .map(|job| job.state.clone())
            .ok_or_else(|| BridgeError::new("unknown_download_job", "download job is unavailable"))
    }

    pub fn cancel(&self, job_id: &str) -> Result<ArtifactDownloadState, BridgeError> {
        validate_job_id(job_id)?;
        let mut registry = self.jobs.lock().expect("download registry poisoned");
        let job = registry.jobs.get_mut(job_id).ok_or_else(|| {
            BridgeError::new("unknown_download_job", "download job is unavailable")
        })?;
        if !job.state.lifecycle.terminal() {
            job.cancel_requested.store(true, Ordering::Release);
            job.state.lifecycle = ArtifactDownloadLifecycle::Cancelling;
            job.state.updated_utc_ms = now_utc_ms();
        }
        Ok(job.state.clone())
    }

    pub fn remove_model(
        &self,
        model_id: &str,
        confirmed: bool,
        runtime: &ManagedRuntimeSupervisor,
        bridge: &ControlPlaneBridge,
    ) -> Result<ManagedModelRemovalResult, BridgeError> {
        if !confirmed {
            return Err(BridgeError::new(
                "confirmation_required",
                "managed model removal requires confirmation",
            ));
        }
        let artifact = self
            .artifacts
            .approved_download_artifact(model_id)
            .map_err(BridgeError::from)?;
        let ApprovedDownloadArtifact::Model(_) = artifact else {
            return Err(BridgeError::new(
                "invalid_artifact_kind",
                "managed artifact is not a model",
            ));
        };
        let status = runtime.status(bridge);
        if status.model_id.as_deref() == Some(model_id)
            || matches!(
                status.state,
                ManagedRuntimeState::Validating
                    | ManagedRuntimeState::Starting
                    | ManagedRuntimeState::Ready
                    | ManagedRuntimeState::Stopping
            )
        {
            return Err(BridgeError::new(
                "model_active",
                "disconnect the managed model before removal",
            ));
        }
        let validation = self
            .artifacts
            .artifact_validation_status(model_id)
            .map_err(BridgeError::from)?;
        if validation.installation_status != InstallationStatus::Valid {
            return Err(BridgeError::new(
                "model_not_installed",
                "managed model is not valid",
            ));
        }
        let destination = self
            .artifacts
            .download_destination(&artifact)
            .map_err(BridgeError::from)?;
        fs::remove_file(&destination).map_err(|_| {
            BridgeError::new("model_removal_failed", "managed model removal failed")
        })?;
        self.prune_empty_model_parents(&destination);
        Ok(ManagedModelRemovalResult {
            model_id: model_id.to_string(),
            removed: true,
        })
    }

    fn run_job(
        &self,
        job_id: String,
        artifact: ApprovedDownloadArtifact,
        cancel_requested: Arc<AtomicBool>,
    ) {
        let result = self.download_and_install(&job_id, &artifact, &cancel_requested);
        match result {
            Ok(()) => {
                self.cleanup_job_temporary_resources(&job_id);
                self.complete(&job_id, ArtifactDownloadLifecycle::Completed, None);
            }
            Err(error) if error.code == "cancelled" => {
                self.cleanup_job_temporary_resources(&job_id);
                self.complete(&job_id, ArtifactDownloadLifecycle::Cancelled, None);
            }
            Err(error) => {
                self.persist_terminal_failure_before_cleanup(&job_id, &artifact, &error);
                self.complete(&job_id, ArtifactDownloadLifecycle::Failed, Some(error.code));
            }
        }
    }

    fn download_and_install(
        &self,
        job_id: &str,
        artifact: &ApprovedDownloadArtifact,
        cancel_requested: &AtomicBool,
    ) -> Result<(), AcquisitionError> {
        self.set_lifecycle(job_id, ArtifactDownloadLifecycle::CheckingDisk, None);
        self.require_not_cancelled(cancel_requested)?;
        let destination = self
            .artifacts
            .download_destination(artifact)
            .map_err(|_| AcquisitionError::new("invalid_destination"))?;
        if destination.exists() {
            return Err(AcquisitionError::new("conflicting_installed_artifact"));
        }
        let acquisition_root = self
            .artifacts
            .acquisition_root()
            .map_err(|_| AcquisitionError::new("acquisition_storage_unavailable"))?;
        let partial = acquisition_root.join(format!("{job_id}.partial"));
        if partial.exists() {
            return Err(AcquisitionError::new("partial_name_conflict"));
        }
        let required_space = required_disk_space(artifact)?;
        if available_space(&acquisition_root)? < required_space {
            return Err(AcquisitionError::new("insufficient_disk_space"));
        }
        self.set_lifecycle(job_id, ArtifactDownloadLifecycle::Downloading, None);
        self.download_to_partial(job_id, artifact, &partial, cancel_requested)?;
        self.require_not_cancelled(cancel_requested)?;
        self.set_lifecycle(job_id, ArtifactDownloadLifecycle::VerifyingSize, None);
        let expected = expected_bytes(artifact);
        let actual = fs::metadata(&partial)
            .map_err(|_| AcquisitionError::new("partial_unavailable"))?
            .len();
        if actual != expected {
            return Err(AcquisitionError::new("size_mismatch"));
        }
        self.set_lifecycle(job_id, ArtifactDownloadLifecycle::VerifyingHash, None);
        if sha256_file(&partial, Some(cancel_requested))? != expected_sha256(artifact) {
            return Err(AcquisitionError::new("hash_mismatch"));
        }
        self.set_lifecycle(job_id, ArtifactDownloadLifecycle::ValidatingArtifact, None);
        self.require_not_cancelled(cancel_requested)?;
        match artifact {
            ApprovedDownloadArtifact::Model(model) => {
                validate_model_partial(&partial, model)?;
                self.set_lifecycle(job_id, ArtifactDownloadLifecycle::Installing, None);
                self.require_not_cancelled(cancel_requested)?;
                install_model(&partial, &destination)?;
            }
            ApprovedDownloadArtifact::Runtime(runtime) => {
                self.set_lifecycle(job_id, ArtifactDownloadLifecycle::Installing, None);
                let staging = acquisition_root.join(format!("{job_id}.runtime-staging"));
                extract_and_install_runtime(
                    &partial,
                    &staging,
                    &destination,
                    runtime,
                    cancel_requested,
                )?;
            }
        }
        if let Err(error) = self.require_not_cancelled(cancel_requested) {
            remove_installed_artifact(artifact, &destination);
            return Err(error);
        }
        let validation = self
            .artifacts
            .artifact_validation_status(artifact_id(artifact))
            .map_err(|_| AcquisitionError::new("post_install_validation_failed"))?;
        if validation.installation_status != InstallationStatus::Valid {
            remove_installed_artifact(artifact, &destination);
            return Err(AcquisitionError::new("post_install_validation_failed"));
        }
        remove_owned_file(&partial);
        Ok(())
    }

    fn download_to_partial(
        &self,
        job_id: &str,
        artifact: &ApprovedDownloadArtifact,
        partial: &Path,
        cancel_requested: &AtomicBool,
    ) -> Result<(), AcquisitionError> {
        let mut response = open_approved_response(artifact)?;
        validate_content_type(&response, artifact)?;
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(partial)
            .map_err(|_| AcquisitionError::new("partial_create_failed"))?;
        let expected = expected_bytes(artifact);
        let mut received = 0_u64;
        let mut last_reported = 0_u64;
        let mut buffer = [0_u8; DOWNLOAD_BUFFER_BYTES];
        loop {
            self.require_not_cancelled(cancel_requested)?;
            let read = response
                .read(&mut buffer)
                .map_err(|_| AcquisitionError::new("download_failed"))?;
            if read == 0 {
                break;
            }
            received = received
                .checked_add(read as u64)
                .ok_or_else(|| AcquisitionError::new("size_mismatch"))?;
            if received > expected {
                return Err(AcquisitionError::new("size_mismatch"));
            }
            file.write_all(&buffer[..read])
                .map_err(|_| AcquisitionError::new("partial_write_failed"))?;
            if received.saturating_sub(last_reported) >= PROGRESS_UPDATE_BYTES
                || received == expected
            {
                self.set_progress(job_id, received);
                last_reported = received;
            }
        }
        file.flush()
            .and_then(|_| file.sync_all())
            .map_err(|_| AcquisitionError::new("partial_write_failed"))?;
        self.set_progress(job_id, received);
        Ok(())
    }

    fn set_lifecycle(
        &self,
        job_id: &str,
        lifecycle: ArtifactDownloadLifecycle,
        error_code: Option<&'static str>,
    ) {
        let mut registry = self.jobs.lock().expect("download registry poisoned");
        let Some(job) = registry.jobs.get_mut(job_id) else {
            return;
        };
        if job.state.lifecycle.terminal() {
            return;
        }
        job.state.lifecycle = lifecycle;
        job.state.error_code = error_code.map(str::to_owned);
        job.state.updated_utc_ms = now_utc_ms();
    }

    fn set_progress(&self, job_id: &str, received_bytes: u64) {
        let mut registry = self.jobs.lock().expect("download registry poisoned");
        let Some(job) = registry.jobs.get_mut(job_id) else {
            return;
        };
        if job.state.lifecycle.terminal() {
            return;
        }
        job.state.received_bytes = received_bytes.min(job.state.expected_bytes);
        job.state.percent = percent(job.state.received_bytes, job.state.expected_bytes);
        job.state.updated_utc_ms = now_utc_ms();
    }

    fn complete(
        &self,
        job_id: &str,
        lifecycle: ArtifactDownloadLifecycle,
        error_code: Option<&'static str>,
    ) {
        let mut registry = self.jobs.lock().expect("download registry poisoned");
        let artifact_id = {
            let Some(job) = registry.jobs.get_mut(job_id) else {
                return;
            };
            if job.state.lifecycle.terminal() {
                return;
            }
            job.state.lifecycle = lifecycle;
            job.state.error_code = error_code.map(str::to_owned);
            job.state.updated_utc_ms = now_utc_ms();
            job.state.artifact_id.clone()
        };
        registry.active_by_artifact.remove(&artifact_id);
    }

    fn new_state(
        &self,
        artifact_id: &str,
        expected_bytes: u64,
        lifecycle: ArtifactDownloadLifecycle,
    ) -> ArtifactDownloadState {
        let timestamp = now_utc_ms();
        ArtifactDownloadState {
            job_id: self.next_job_id(),
            artifact_id: artifact_id.to_string(),
            lifecycle,
            expected_bytes,
            received_bytes: 0,
            percent: percent(0, expected_bytes),
            started_utc_ms: timestamp,
            updated_utc_ms: timestamp,
            error_code: None,
        }
    }

    fn next_job_id(&self) -> String {
        let counter = self.job_sequence.fetch_add(1, Ordering::Relaxed);
        let mut hasher = Sha256::new();
        hasher.update(now_utc_ms().to_le_bytes());
        hasher.update(counter.to_le_bytes());
        hasher.update(std::process::id().to_le_bytes());
        format!("{:x}", hasher.finalize())
    }

    fn require_not_cancelled(&self, cancel_requested: &AtomicBool) -> Result<(), AcquisitionError> {
        if cancel_requested.load(Ordering::Acquire) {
            return Err(AcquisitionError::new("cancelled"));
        }
        Ok(())
    }

    fn cleanup_stale_partials(&self) {
        let Ok(root) = self.artifacts.acquisition_root() else {
            return;
        };
        let Ok(entries) = fs::read_dir(root) else {
            return;
        };
        for entry in entries.flatten().take(MAX_STALE_PARTIALS) {
            let path = entry.path();
            let name = entry.file_name();
            let name = name.to_string_lossy();
            if is_owned_partial_name(&name)
                && entry
                    .file_type()
                    .map(|kind| kind.is_file())
                    .unwrap_or(false)
            {
                let _ = fs::remove_file(path);
            } else if is_owned_runtime_staging_name(&name)
                && entry.file_type().map(|kind| kind.is_dir()).unwrap_or(false)
            {
                let _ = fs::remove_dir_all(path);
            }
        }
    }

    fn remove_job_partial(&self, job_id: &str) {
        let Ok(root) = self.artifacts.acquisition_root() else {
            return;
        };
        remove_owned_file(&root.join(format!("{job_id}.partial")));
    }

    fn cleanup_job_temporary_resources(&self, job_id: &str) -> bool {
        let Ok(root) = self.artifacts.acquisition_root() else {
            return false;
        };
        let partial = root.join(format!("{job_id}.partial"));
        let staging = root.join(format!("{job_id}.runtime-staging"));
        self.remove_job_partial(job_id);
        if staging.exists() {
            let _ = fs::remove_dir_all(&staging);
        }
        !partial.exists() && !staging.exists()
    }

    fn persist_terminal_failure_before_cleanup(
        &self,
        job_id: &str,
        artifact: &ApprovedDownloadArtifact,
        error: &AcquisitionError,
    ) {
        let downloaded_bytes = self.current_received_bytes(job_id);
        let expected_bytes = expected_bytes(artifact);
        let stage = acquisition_failure_stage(error.code);
        let final_artifact_exists = self.final_artifact_exists(artifact);
        let before_cleanup = AcquisitionFailureEvent {
            schema_version: ACQUISITION_EVENT_SCHEMA_VERSION,
            timestamp_utc_ms: now_utc_ms(),
            artifact_kind: acquisition_artifact_kind(artifact),
            artifact_id: artifact_id(artifact),
            terminal_status: "failed",
            stage,
            error_code: error.code,
            downloaded_bytes,
            expected_bytes,
            archive_member: error.archive_member.as_deref(),
            archive_disposition: error.archive_disposition,
            expected_member_count: error.expected_member_count,
            observed_member_count: error.observed_member_count,
            cleanup_complete: false,
            final_artifact_exists,
        };
        let _ = self.append_failure_event(&before_cleanup);
        let cleanup_complete = self.cleanup_job_temporary_resources(job_id);
        let after_cleanup = AcquisitionFailureEvent {
            timestamp_utc_ms: now_utc_ms(),
            cleanup_complete,
            final_artifact_exists: self.final_artifact_exists(artifact),
            ..before_cleanup
        };
        let _ = self.append_failure_event(&after_cleanup);
    }

    fn current_received_bytes(&self, job_id: &str) -> u64 {
        self.jobs
            .lock()
            .expect("download registry poisoned")
            .jobs
            .get(job_id)
            .map(|job| job.state.received_bytes)
            .unwrap_or(0)
    }

    fn final_artifact_exists(&self, artifact: &ApprovedDownloadArtifact) -> bool {
        self.artifacts
            .download_destination(artifact)
            .map(|path| path.exists())
            .unwrap_or(false)
    }

    fn append_failure_event(&self, event: &AcquisitionFailureEvent<'_>) -> Result<(), ()> {
        let path = self
            .artifacts
            .acquisition_event_log_path()
            .map_err(|_| ())?;
        let mut bytes = serde_json::to_vec(event).map_err(|_| ())?;
        bytes.push(b'\n');
        let _guard = self.diagnostic_lock.lock().map_err(|_| ())?;
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(path)
            .map_err(|_| ())?;
        file.write_all(&bytes)
            .and_then(|_| file.sync_data())
            .map_err(|_| ())
    }

    fn prune_empty_model_parents(&self, destination: &Path) {
        let root = &self.artifacts.roots().model_root;
        let mut current = destination.parent();
        while let Some(directory) = current {
            if directory == root || !directory.starts_with(root) {
                break;
            }
            if fs::remove_dir(directory).is_err() {
                break;
            }
            current = directory.parent();
        }
    }
}

fn acquisition_artifact_kind(artifact: &ApprovedDownloadArtifact) -> &'static str {
    match artifact {
        ApprovedDownloadArtifact::Runtime(_) => "runtime",
        ApprovedDownloadArtifact::Model(_) => "model",
    }
}

fn acquisition_failure_stage(error_code: &str) -> AcquisitionFailureStage {
    match error_code {
        "size_mismatch" => AcquisitionFailureStage::SizeVerification,
        "hash_mismatch" | "hash_read_failed" => AcquisitionFailureStage::HashVerification,
        "invalid_runtime_archive"
        | "unexpected_runtime_member"
        | "runtime_member_hash_mismatch"
        | "missing_runtime_member"
        | "archive_member_count_mismatch" => AcquisitionFailureStage::ArchiveValidation,
        "staging_create_failed" | "staging_write_failed" | "license_asset_invalid" => {
            AcquisitionFailureStage::StagingExtraction
        }
        "atomic_install_failed" => AcquisitionFailureStage::AtomicPromotion,
        "post_install_validation_failed" => AcquisitionFailureStage::PostInstallValidation,
        _ => AcquisitionFailureStage::Transfer,
    }
}

#[tauri::command]
pub fn list_approved_downloadable_artifacts(
    state: State<'_, Arc<ArtifactAcquisitionManager>>,
) -> Vec<ApprovedDownloadableArtifact> {
    state.approved_artifacts()
}

#[tauri::command]
pub fn start_approved_artifact_download(
    state: State<'_, Arc<ArtifactAcquisitionManager>>,
    artifact_id: String,
    confirmed: bool,
) -> Result<ArtifactDownloadState, BridgeError> {
    state.start(&artifact_id, confirmed)
}

#[tauri::command]
pub fn get_artifact_download_state(
    state: State<'_, Arc<ArtifactAcquisitionManager>>,
    job_id: String,
) -> Result<ArtifactDownloadState, BridgeError> {
    state.get(&job_id)
}

#[tauri::command]
pub fn cancel_artifact_download(
    state: State<'_, Arc<ArtifactAcquisitionManager>>,
    job_id: String,
) -> Result<ArtifactDownloadState, BridgeError> {
    state.cancel(&job_id)
}

#[tauri::command]
pub fn remove_managed_model(
    acquisition: State<'_, Arc<ArtifactAcquisitionManager>>,
    runtime: State<'_, Arc<ManagedRuntimeSupervisor>>,
    bridge: State<'_, Arc<ControlPlaneBridge>>,
    model_id: String,
    confirmed: bool,
) -> Result<ManagedModelRemovalResult, BridgeError> {
    acquisition.remove_model(&model_id, confirmed, &runtime, &bridge)
}

fn artifact_id(artifact: &ApprovedDownloadArtifact) -> &str {
    match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => &runtime.runtime_id,
        ApprovedDownloadArtifact::Model(model) => &model.model_id,
    }
}

fn expected_bytes(artifact: &ApprovedDownloadArtifact) -> u64 {
    match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => runtime.acquisition.expected_bytes,
        ApprovedDownloadArtifact::Model(model) => model.acquisition.expected_bytes,
    }
}

fn expected_sha256(artifact: &ApprovedDownloadArtifact) -> &str {
    match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => &runtime.acquisition.expected_sha256,
        ApprovedDownloadArtifact::Model(model) => &model.acquisition.expected_sha256,
    }
}

fn required_disk_space(artifact: &ApprovedDownloadArtifact) -> Result<u64, AcquisitionError> {
    let downloaded = expected_bytes(artifact);
    let install_reserve = match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => runtime
            .required_files
            .iter()
            .try_fold(0_u64, |total, file| total.checked_add(file.bytes))
            .and_then(|total| total.checked_add(runtime.license_asset.bytes))
            .ok_or_else(|| AcquisitionError::new("disk_requirement_overflow"))?,
        ApprovedDownloadArtifact::Model(_) => DISK_RESERVE_BYTES,
    };
    downloaded
        .checked_add(install_reserve)
        .and_then(|value| value.checked_add(DISK_RESERVE_BYTES))
        .ok_or_else(|| AcquisitionError::new("disk_requirement_overflow"))
}

fn open_approved_response(
    artifact: &ApprovedDownloadArtifact,
) -> Result<Response, AcquisitionError> {
    let acquisition = match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => &runtime.acquisition,
        ApprovedDownloadArtifact::Model(model) => &model.acquisition,
    };
    let client = Client::builder()
        .redirect(Policy::none())
        .no_proxy()
        .connect_timeout(Duration::from_secs(15))
        .build()
        .map_err(|_| AcquisitionError::new("download_client_unavailable"))?;
    let mut current = Url::parse(&acquisition.primary_url)
        .map_err(|_| AcquisitionError::new("invalid_catalog_url"))?;
    for _ in 0..=MAX_REDIRECTS {
        validate_redirect_url(&current, &acquisition.allowed_redirect_hosts)?;
        let response = client
            .get(current.clone())
            .send()
            .map_err(|_| AcquisitionError::new("download_failed"))?;
        if response.status().is_redirection() {
            let location = response
                .headers()
                .get(reqwest::header::LOCATION)
                .and_then(|header| header.to_str().ok())
                .ok_or_else(|| AcquisitionError::new("redirect_rejected"))?;
            let next = current
                .join(location)
                .map_err(|_| AcquisitionError::new("redirect_rejected"))?;
            validate_redirect_url(&next, &acquisition.allowed_redirect_hosts)?;
            current = next;
            continue;
        }
        if !response.status().is_success() {
            return Err(AcquisitionError::new("download_failed"));
        }
        return Ok(response);
    }
    Err(AcquisitionError::new("redirect_limit_exceeded"))
}

fn validate_redirect_url(url: &Url, allowed_hosts: &[String]) -> Result<(), AcquisitionError> {
    let Some(host) = url.host_str() else {
        return Err(AcquisitionError::new("redirect_rejected"));
    };
    if url.scheme() != "https"
        || url.port().is_some()
        || !url.username().is_empty()
        || url.password().is_some()
        || !allowed_hosts.iter().any(|allowed| allowed == host)
    {
        return Err(AcquisitionError::new("redirect_rejected"));
    }
    Ok(())
}

fn validate_content_type(
    response: &Response,
    artifact: &ApprovedDownloadArtifact,
) -> Result<(), AcquisitionError> {
    let expected = match artifact {
        ApprovedDownloadArtifact::Runtime(runtime) => runtime.acquisition.content_type.as_deref(),
        ApprovedDownloadArtifact::Model(model) => model.acquisition.content_type.as_deref(),
    };
    let Some(expected) = expected else {
        return Ok(());
    };
    let Some(actual) = response
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|header| header.to_str().ok())
    else {
        return Ok(());
    };
    let actual = actual.split(';').next().unwrap_or_default().trim();
    if actual.eq_ignore_ascii_case(expected) {
        Ok(())
    } else {
        Err(AcquisitionError::new("content_type_mismatch"))
    }
}

fn validate_model_partial(
    path: &Path,
    model: &ApprovedModelArtifact,
) -> Result<(), AcquisitionError> {
    if !model
        .acquisition
        .expected_filename
        .to_ascii_lowercase()
        .ends_with(".gguf")
    {
        return Err(AcquisitionError::new("invalid_model_format"));
    }
    let mut magic = [0_u8; 4];
    File::open(path)
        .and_then(|mut file| file.read_exact(&mut magic))
        .map_err(|_| AcquisitionError::new("invalid_model_format"))?;
    if &magic != b"GGUF" {
        return Err(AcquisitionError::new("invalid_model_format"));
    }
    Ok(())
}

fn install_model(partial: &Path, destination: &Path) -> Result<(), AcquisitionError> {
    fs::rename(partial, destination).map_err(|_| AcquisitionError::new("atomic_install_failed"))
}

fn extract_and_install_runtime(
    partial: &Path,
    staging: &Path,
    destination: &Path,
    runtime: &ApprovedRuntimeArtifact,
    cancel_requested: &AtomicBool,
) -> Result<(), AcquisitionError> {
    if staging.exists() || destination.exists() {
        return Err(AcquisitionError::new("conflicting_installed_artifact"));
    }
    fs::create_dir(staging).map_err(|_| AcquisitionError::new("staging_create_failed"))?;
    (|| {
        let file =
            File::open(partial).map_err(|_| AcquisitionError::new("invalid_runtime_archive"))?;
        let mut archive =
            ZipArchive::new(file).map_err(|_| AcquisitionError::new("invalid_runtime_archive"))?;
        let envelope = runtime
            .archive_members
            .iter()
            .map(|member| {
                (
                    member.relative_path.to_ascii_lowercase(),
                    member.disposition,
                )
            })
            .collect::<BTreeMap<_, _>>();
        let archive_member_count = archive.len();
        if archive_member_count == 0 || archive_member_count > MAX_RUNTIME_ARCHIVE_MEMBERS {
            return Err(AcquisitionError::new("archive_member_count_mismatch")
                .archive_member_counts(envelope.len(), archive_member_count));
        }
        let required = runtime
            .required_files
            .iter()
            .map(|file| (file.relative_path.to_ascii_lowercase(), file))
            .collect::<BTreeMap<_, _>>();
        let mut seen = BTreeSet::new();
        let mut archive_indexes = BTreeMap::new();
        for index in 0..archive_member_count {
            let member = archive
                .by_index(index)
                .map_err(|_| AcquisitionError::new("invalid_runtime_archive"))?;
            let name = member.name().to_string();
            let folded = safe_zip_member_name(&name)?;
            let disposition = envelope.get(&folded).copied();
            let regular_file = !member.is_dir()
                && member
                    .unix_mode()
                    .is_none_or(|mode| matches!(mode & 0o170000, 0 | 0o100000));
            if !regular_file {
                return Err(AcquisitionError::new("invalid_runtime_archive")
                    .archive_member(folded, disposition)
                    .archive_member_counts(envelope.len(), archive_member_count));
            }
            let Some(disposition) = disposition else {
                return Err(AcquisitionError::new("unexpected_runtime_member")
                    .archive_member(folded, None)
                    .archive_member_counts(envelope.len(), archive_member_count));
            };
            if !seen.insert(folded.clone()) {
                return Err(AcquisitionError::new("invalid_runtime_archive")
                    .archive_member(folded, Some(disposition))
                    .archive_member_counts(envelope.len(), archive_member_count));
            }
            archive_indexes.insert(folded, index);
        }
        if seen.len() != envelope.len() {
            let missing = envelope
                .iter()
                .find(|(name, _)| !seen.contains(*name))
                .map(|(name, disposition)| (name.clone(), *disposition))
                .expect("envelope count mismatch has a missing member");
            return Err(AcquisitionError::new("missing_runtime_member")
                .archive_member(missing.0, Some(missing.1))
                .archive_member_counts(envelope.len(), seen.len()));
        }
        for (folded, expected) in &required {
            if cancel_requested.load(Ordering::Acquire) {
                return Err(AcquisitionError::new("cancelled"));
            }
            if envelope.get(folded) != Some(&RuntimeArchiveMemberDisposition::Install) {
                return Err(AcquisitionError::new("invalid_runtime_archive")
                    .archive_member(folded.clone(), envelope.get(folded).copied()));
            }
            let index = archive_indexes.get(folded).copied().ok_or_else(|| {
                AcquisitionError::new("missing_runtime_member").archive_member(
                    folded.clone(),
                    Some(RuntimeArchiveMemberDisposition::Install),
                )
            })?;
            let mut member = archive
                .by_index(index)
                .map_err(|_| AcquisitionError::new("invalid_runtime_archive"))?;
            let output = contained_staging_path(staging, &expected.relative_path)?;
            let mut output_file = OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(output)
                .map_err(|_| AcquisitionError::new("staging_write_failed"))?;
            std::io::copy(&mut member, &mut output_file)
                .and_then(|_| output_file.sync_all())
                .map_err(|_| AcquisitionError::new("staging_write_failed"))?;
            let path = contained_staging_path(staging, &expected.relative_path)?;
            let metadata =
                fs::metadata(&path).map_err(|_| AcquisitionError::new("staging_write_failed"))?;
            if metadata.len() != expected.bytes
                || sha256_file(&path, Some(cancel_requested))? != expected.sha256
            {
                return Err(AcquisitionError::new("runtime_member_hash_mismatch"));
            }
        }
        let license_bytes = source_controlled_runtime_license_bytes(&runtime.license_asset)
            .map_err(|_| AcquisitionError::new("license_asset_invalid"))?;
        let license_path =
            contained_staging_path(staging, &runtime.license_asset.destination_relative_path)?;
        let mut license_file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&license_path)
            .map_err(|_| AcquisitionError::new("staging_write_failed"))?;
        license_file
            .write_all(license_bytes)
            .and_then(|_| license_file.sync_all())
            .map_err(|_| AcquisitionError::new("staging_write_failed"))?;
        drop(license_file);
        let license_metadata = fs::metadata(&license_path)
            .map_err(|_| AcquisitionError::new("staging_write_failed"))?;
        if license_metadata.len() != runtime.license_asset.bytes
            || sha256_file(&license_path, Some(cancel_requested))? != runtime.license_asset.sha256
        {
            return Err(AcquisitionError::new("license_asset_invalid"));
        }
        fs::rename(staging, destination)
            .map_err(|_| AcquisitionError::new("atomic_install_failed"))?;
        Ok(())
    })()
}

fn safe_zip_member_name(value: &str) -> Result<String, AcquisitionError> {
    if value.is_empty()
        || value.len() > 240
        || value.starts_with('/')
        || value.starts_with('\\')
        || value.contains('\\')
        || value.contains(':')
        || value.contains('\0')
        || value.ends_with('/')
    {
        return Err(AcquisitionError::new("invalid_runtime_archive"));
    }
    for segment in value.split('/') {
        if segment.is_empty() || segment == "." || segment == ".." || segment.ends_with([' ', '.'])
        {
            return Err(AcquisitionError::new("invalid_runtime_archive"));
        }
    }
    Ok(value.to_ascii_lowercase())
}

fn contained_staging_path(root: &Path, member: &str) -> Result<PathBuf, AcquisitionError> {
    safe_zip_member_name(member)?;
    let mut path = root.to_path_buf();
    for segment in member.split('/') {
        path.push(segment);
    }
    if !path.starts_with(root) {
        return Err(AcquisitionError::new("invalid_runtime_archive"));
    }
    Ok(path)
}

fn sha256_file(
    path: &Path,
    cancel_requested: Option<&AtomicBool>,
) -> Result<String, AcquisitionError> {
    let mut file = File::open(path).map_err(|_| AcquisitionError::new("hash_read_failed"))?;
    let mut hasher = Sha256::new();
    let mut buffer = [0_u8; DOWNLOAD_BUFFER_BYTES];
    loop {
        if cancel_requested.is_some_and(|cancel| cancel.load(Ordering::Acquire)) {
            return Err(AcquisitionError::new("cancelled"));
        }
        let read = file
            .read(&mut buffer)
            .map_err(|_| AcquisitionError::new("hash_read_failed"))?;
        if read == 0 {
            break;
        }
        hasher.update(&buffer[..read]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn remove_installed_artifact(artifact: &ApprovedDownloadArtifact, destination: &Path) {
    match artifact {
        ApprovedDownloadArtifact::Runtime(_) if destination.exists() => {
            let _ = fs::remove_dir_all(destination);
        }
        ApprovedDownloadArtifact::Model(_) if destination.exists() => {
            let _ = fs::remove_file(destination);
        }
        _ => {}
    }
}

fn remove_owned_file(path: &Path) {
    if path
        .file_name()
        .and_then(|value| value.to_str())
        .is_some_and(is_owned_partial_name)
    {
        let _ = fs::remove_file(path);
    }
}

fn is_owned_partial_name(value: &str) -> bool {
    value.strip_suffix(".partial").is_some_and(is_opaque_job_id)
}

fn is_owned_runtime_staging_name(value: &str) -> bool {
    value
        .strip_suffix(".runtime-staging")
        .is_some_and(is_opaque_job_id)
}

fn is_opaque_job_id(job_id: &str) -> bool {
    job_id.len() == 64
        && job_id
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn validate_job_id(value: &str) -> Result<(), BridgeError> {
    if value.len() != 64
        || value
            .bytes()
            .any(|byte| !(byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)))
    {
        return Err(BridgeError::new(
            "invalid_download_job",
            "download job id rejected",
        ));
    }
    Ok(())
}

fn percent(received: u64, expected: u64) -> Option<u8> {
    if expected == 0 {
        return None;
    }
    Some(((received.saturating_mul(100) / expected).min(100)) as u8)
}

fn now_utc_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis().min(u64::MAX as u128) as u64)
        .unwrap_or(0)
}

#[cfg(windows)]
fn available_space(path: &Path) -> Result<u64, AcquisitionError> {
    let mut available = 0_u64;
    let mut total = 0_u64;
    let mut free = 0_u64;
    let mut wide: Vec<u16> = OsStr::new(path)
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let result =
        unsafe { GetDiskFreeSpaceExW(wide.as_mut_ptr(), &mut available, &mut total, &mut free) };
    if result == 0 {
        return Err(AcquisitionError::new("disk_space_unavailable"));
    }
    Ok(available)
}

#[cfg(not(windows))]
fn available_space(_path: &Path) -> Result<u64, AcquisitionError> {
    Ok(u64::MAX)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::artifact_trust::{
        AcquisitionArtifactKind, AcquisitionSourceType, ApprovedArtifactAcquisition,
        ApprovedArtifactCatalog, ApprovedRuntimeArchiveMember, ApprovedRuntimeFile,
        ApprovedRuntimeLicenseAsset, CatalogStatus, ManagedArtifactRoots,
    };
    use std::sync::atomic::AtomicU64;
    use zip::write::SimpleFileOptions;

    const TEST_RUNTIME_ID: &str = "test-runtime";
    const TEST_MODEL_ID: &str = "test-model";
    const TEST_RUNTIME_BYTES: &[u8] = b"test-runtime";
    const TEST_MODEL_BYTES: &[u8] = b"GGUFtest-model";

    static TEST_SEQUENCE: AtomicU64 = AtomicU64::new(0);

    struct TestWorkspace {
        root: PathBuf,
    }

    impl TestWorkspace {
        fn new() -> Self {
            let sequence = TEST_SEQUENCE.fetch_add(1, Ordering::Relaxed);
            let root = std::env::temp_dir().join(format!(
                "localcomet-artifact-acquisition-{}-{}-{sequence}",
                std::process::id(),
                now_utc_ms()
            ));
            fs::create_dir_all(&root).expect("create test workspace");
            Self { root }
        }

        fn roots(&self) -> ManagedArtifactRoots {
            ManagedArtifactRoots {
                app_data_root: self.root.clone(),
                runtime_root: self.root.join("runtimes"),
                model_root: self.root.join("models"),
                state_root: self.root.join("state"),
            }
        }
    }

    impl Drop for TestWorkspace {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.root);
        }
    }

    fn sha256_bytes(bytes: &[u8]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(bytes);
        format!("{:x}", hasher.finalize())
    }

    fn test_runtime() -> ApprovedRuntimeArtifact {
        ApprovedRuntimeArtifact {
            runtime_id: TEST_RUNTIME_ID.into(),
            provider: "test-provider".into(),
            release_tag: "b1".into(),
            platform: "windows".into(),
            architecture: "x86-64".into(),
            variant: "cpu".into(),
            upstream_repository: "test/runtime".into(),
            upstream_revision: "1111111111111111111111111111111111111111".into(),
            asset_filename: "test-runtime.zip".into(),
            asset_bytes: 7,
            asset_sha256: sha256_bytes(b"archive"),
            acquisition: ApprovedArtifactAcquisition {
                artifact_id: TEST_RUNTIME_ID.into(),
                artifact_kind: AcquisitionArtifactKind::Runtime,
                source_type: AcquisitionSourceType::ApprovedHttps,
                primary_url: "https://assets.example.test/test-runtime.zip".into(),
                allowed_redirect_hosts: vec!["assets.example.test".into()],
                expected_filename: "test-runtime.zip".into(),
                expected_bytes: 7,
                expected_sha256: sha256_bytes(b"archive"),
                content_type: Some("application/octet-stream".into()),
                managed_relative_destination: TEST_RUNTIME_ID.into(),
                public_distribution: false,
                installer_bundled: false,
                automatic_download: false,
                user_confirmation_required: true,
            },
            archive_format: "zip".into(),
            managed_relative_path: TEST_RUNTIME_ID.into(),
            executable_relative_path: "llama-server.exe".into(),
            archive_members: vec![ApprovedRuntimeArchiveMember {
                relative_path: "llama-server.exe".into(),
                disposition: RuntimeArchiveMemberDisposition::Install,
            }],
            required_files: vec![ApprovedRuntimeFile {
                relative_path: "llama-server.exe".into(),
                bytes: TEST_RUNTIME_BYTES.len() as u64,
                sha256: sha256_bytes(TEST_RUNTIME_BYTES),
            }],
            license_asset: ApprovedRuntimeLicenseAsset {
                source_relative_path: "third_party/llama.cpp/LICENSE-MIT.txt".into(),
                destination_relative_path: "LICENSE-MIT.txt".into(),
                bytes: 1_078,
                sha256: "94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d".into(),
            },
            permitted_bind_scope: "loopback-only".into(),
            supported_api_protocol: "openai-compatible-v1".into(),
            license_id: "MIT".into(),
            public_distribution: false,
            status: CatalogStatus::ApprovedInternalBootstrap,
        }
    }

    fn test_model() -> ApprovedModelArtifact {
        ApprovedModelArtifact {
            model_id: TEST_MODEL_ID.into(),
            provider: "test-provider".into(),
            family: "test-family".into(),
            display_name: "Test model".into(),
            format: "GGUF".into(),
            quantization: "Q4_K_M".into(),
            upstream_repository: "test/model".into(),
            upstream_revision: "2222222222222222222222222222222222222222".into(),
            asset_filename: "test-model.gguf".into(),
            asset_bytes: TEST_MODEL_BYTES.len() as u64,
            asset_sha256: sha256_bytes(TEST_MODEL_BYTES),
            acquisition: ApprovedArtifactAcquisition {
                artifact_id: TEST_MODEL_ID.into(),
                artifact_kind: AcquisitionArtifactKind::Model,
                source_type: AcquisitionSourceType::ApprovedHttps,
                primary_url: "https://assets.example.test/test-model.gguf".into(),
                allowed_redirect_hosts: vec!["assets.example.test".into()],
                expected_filename: "test-model.gguf".into(),
                expected_bytes: TEST_MODEL_BYTES.len() as u64,
                expected_sha256: sha256_bytes(TEST_MODEL_BYTES),
                content_type: Some("application/octet-stream".into()),
                managed_relative_destination: "test-model/test-model.gguf".into(),
                public_distribution: false,
                installer_bundled: false,
                automatic_download: false,
                user_confirmation_required: true,
            },
            license_id: "Apache-2.0".into(),
            compatible_runtime_ids: vec![TEST_RUNTIME_ID.into()],
            managed_relative_path: "test-model/test-model.gguf".into(),
            public_distribution: false,
            installer_bundled: false,
            bootstrap_purpose: "INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION".into(),
            status: CatalogStatus::ApprovedInternalBootstrap,
        }
    }

    fn test_manager() -> (
        TestWorkspace,
        ArtifactAcquisitionManager,
        Arc<ArtifactTrustService>,
    ) {
        let workspace = TestWorkspace::new();
        let catalog = ApprovedArtifactCatalog {
            schema_version: 1,
            catalog_id: "localcomet-approved-artifacts".into(),
            catalog_version: "1.0.0-test".into(),
            runtimes: vec![test_runtime()],
            models: vec![test_model()],
        };
        let mut bytes = serde_json::to_vec_pretty(&catalog).expect("serialize test catalog");
        bytes.push(b'\n');
        let trust = Arc::new(
            ArtifactTrustService::from_catalog_bytes(&bytes, workspace.roots())
                .expect("create test trust service"),
        );
        let manager = ArtifactAcquisitionManager::new(Arc::clone(&trust));
        (workspace, manager, trust)
    }

    fn write_zip(path: &Path, entries: &[(&str, &[u8])]) {
        let file = File::create(path).expect("create archive");
        let mut writer = zip::ZipWriter::new(file);
        let options =
            SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored);
        for (name, bytes) in entries {
            writer
                .start_file(*name, options)
                .expect("start archive entry");
            writer.write_all(bytes).expect("write archive entry");
        }
        writer.finish().expect("finish archive");
    }

    fn write_owned_zip(path: &Path, entries: &[(String, Vec<u8>)]) {
        let file = File::create(path).expect("create archive");
        let mut writer = zip::ZipWriter::new(file);
        let options =
            SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored);
        for (name, bytes) in entries {
            writer
                .start_file(name, options)
                .expect("start archive entry");
            writer.write_all(bytes).expect("write archive entry");
        }
        writer.finish().expect("finish archive");
    }

    fn embedded_runtime() -> ApprovedRuntimeArtifact {
        let catalog: ApprovedArtifactCatalog = serde_json::from_slice(include_bytes!(
            "../resources/localcomet/approved-artifacts.v1.json"
        ))
        .expect("parse embedded approved catalog");
        catalog
            .runtimes
            .into_iter()
            .next()
            .expect("approved runtime fixture")
    }

    fn approved_runtime_envelope_fixture() -> (ApprovedRuntimeArtifact, Vec<(String, Vec<u8>)>) {
        let mut runtime = embedded_runtime();
        let entries = runtime
            .archive_members
            .iter()
            .map(|member| {
                let prefix = match member.disposition {
                    RuntimeArchiveMemberDisposition::Install => "install",
                    RuntimeArchiveMemberDisposition::RecognizedNotInstalled => "recognized",
                };
                (
                    member.relative_path.clone(),
                    format!("{prefix}:{}", member.relative_path).into_bytes(),
                )
            })
            .collect::<Vec<_>>();
        runtime.required_files = runtime
            .archive_members
            .iter()
            .filter(|member| member.disposition == RuntimeArchiveMemberDisposition::Install)
            .map(|member| {
                let bytes = format!("install:{}", member.relative_path).into_bytes();
                ApprovedRuntimeFile {
                    relative_path: member.relative_path.clone(),
                    bytes: bytes.len() as u64,
                    sha256: sha256_bytes(&bytes),
                }
            })
            .collect();
        (runtime, entries)
    }

    fn top_level_names(path: &Path) -> BTreeSet<String> {
        fs::read_dir(path)
            .expect("read final runtime directory")
            .map(|entry| {
                entry
                    .expect("runtime directory entry")
                    .file_name()
                    .to_string_lossy()
                    .to_ascii_lowercase()
            })
            .collect()
    }

    fn register_job(
        manager: &ArtifactAcquisitionManager,
        artifact_id: &str,
        expected_bytes: u64,
        received_bytes: u64,
    ) -> String {
        let mut state = manager.new_state(
            artifact_id,
            expected_bytes,
            ArtifactDownloadLifecycle::Installing,
        );
        state.received_bytes = received_bytes;
        state.percent = percent(received_bytes, expected_bytes);
        let job_id = state.job_id.clone();
        let mut registry = manager.jobs.lock().expect("download registry");
        registry
            .active_by_artifact
            .insert(artifact_id.into(), job_id.clone());
        registry.jobs.insert(
            job_id.clone(),
            DownloadJob {
                state,
                cancel_requested: Arc::new(AtomicBool::new(false)),
            },
        );
        job_id
    }

    fn read_failure_events(trust: &ArtifactTrustService) -> Vec<serde_json::Value> {
        let path = trust.acquisition_event_log_path().expect("diagnostic path");
        let contents = fs::read_to_string(path).expect("read diagnostic events");
        contents
            .lines()
            .map(|line| serde_json::from_str(line).expect("diagnostic event JSON"))
            .collect()
    }

    #[test]
    fn model_redirect_authority_requires_exact_https_host() {
        let allowed = vec![
            "cas-bridge.xethub.hf.co".to_string(),
            "cdn-lfs-us-1.hf.co".to_string(),
            "cdn-lfs.hf.co".to_string(),
            "huggingface.co".to_string(),
            "transfer.xethub.hf.co".to_string(),
            "us.aws.cdn.hf.co".to_string(),
        ];
        assert!(validate_redirect_url(
            &Url::parse(
                "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf",
            )
            .expect("valid primary URL"),
            &allowed,
        )
        .is_ok());
        for host in &allowed {
            assert!(validate_redirect_url(
                &Url::parse(&format!("https://{host}/download")).expect("valid approved URL"),
                &allowed,
            )
            .is_ok());
        }
        for value in [
            "http://us.aws.cdn.hf.co/download",
            "https://us.aws.cdn.hf.co.attacker.example/download",
            "https://attacker-us.aws.cdn.hf.co/download",
            "https://aws.cdn.hf.co/download",
            "https://cdn.hf.co/download",
            "https://us.aws.cdn.hf.co./download",
            "https://us.aws.cdn.hf.co:8443/download",
            "https://user@us.aws.cdn.hf.co/download",
            "https://user:[REDACTED: secret in desktop/localcomet-desktop/src-tauri/src/artifact_acquisition.rs:1600]@us.aws.cdn.hf.co/download",
            "https://127.0.0.1/download",
        ] {
            assert!(
                validate_redirect_url(&Url::parse(value).expect("valid URL"), &allowed).is_err()
            );
        }
    }

    #[test]
    fn runtime_archive_members_reject_windows_and_traversal_forms() {
        assert_eq!(
            safe_zip_member_name("llama-server.exe").expect("safe member"),
            "llama-server.exe"
        );
        for member in [
            "../llama-server.exe",
            "C:/llama-server.exe",
            "a\\b.dll",
            "/root.dll",
        ] {
            assert!(safe_zip_member_name(member).is_err());
        }
    }

    #[test]
    fn stale_cleanup_names_are_limited_to_opaque_job_resources() {
        let job_id = "a".repeat(64);
        assert!(is_owned_partial_name(&format!("{job_id}.partial")));
        assert!(is_owned_runtime_staging_name(&format!(
            "{job_id}.runtime-staging"
        )));
        assert!(!is_owned_partial_name("model.gguf.partial"));
        assert!(!is_owned_runtime_staging_name("runtime-staging"));
    }

    #[test]
    fn model_validation_rejects_bad_gguf_magic_before_installation() {
        let workspace = TestWorkspace::new();
        let partial = workspace.root.join("invalid.partial");
        fs::write(&partial, b"not-a-gguf").expect("write invalid model");

        let error = validate_model_partial(&partial, &test_model()).expect_err("reject bad magic");

        assert_eq!(error.code, "invalid_model_format");
    }

    #[test]
    fn runtime_archive_rejects_traversal_duplicate_and_bad_member_hash() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        for (name, entries, expected_code) in [
            (
                "traversal.zip",
                vec![("../llama-server.exe", TEST_RUNTIME_BYTES)],
                "invalid_runtime_archive",
            ),
            (
                "duplicate.zip",
                vec![
                    ("llama-server.exe", TEST_RUNTIME_BYTES),
                    ("LLAMA-SERVER.EXE", TEST_RUNTIME_BYTES),
                ],
                "invalid_runtime_archive",
            ),
            (
                "bad-hash.zip",
                vec![("llama-server.exe", b"wrong".as_slice())],
                "runtime_member_hash_mismatch",
            ),
        ] {
            let archive = workspace.root.join(name);
            let staging = workspace.root.join(format!("{name}.staging"));
            let destination = workspace.root.join(format!("{name}.destination"));
            write_zip(&archive, &entries);

            let error = extract_and_install_runtime(
                &archive,
                &staging,
                &destination,
                &test_runtime(),
                &cancel,
            )
            .expect_err("reject unsafe archive");

            assert_eq!(error.code, expected_code);
            assert!(staging.exists());
            fs::remove_dir_all(&staging).expect("remove failed staging fixture");
            assert!(!staging.exists());
            assert!(!destination.exists());
        }
    }

    #[test]
    fn runtime_archive_rejects_directory_members_before_staging_them() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        let archive = workspace.root.join("directory-member.zip");
        let staging = workspace.root.join("directory-member.staging");
        let destination = workspace.root.join("directory-member.destination");
        let file = File::create(&archive).expect("create archive");
        let mut writer = zip::ZipWriter::new(file);
        let options =
            SimpleFileOptions::default().compression_method(zip::CompressionMethod::Stored);
        writer
            .add_directory("llama-server.exe/", options)
            .expect("add directory entry");
        writer.finish().expect("finish archive");

        let error =
            extract_and_install_runtime(&archive, &staging, &destination, &test_runtime(), &cancel)
                .expect_err("directory archive member must be rejected");

        assert_eq!(error.code, "invalid_runtime_archive");
        assert!(!destination.exists());
        assert!(top_level_names(&staging).is_empty());
    }

    #[test]
    fn approved_runtime_envelope_installs_only_the_pinned_subset_and_license() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        let (runtime, entries) = approved_runtime_envelope_fixture();
        assert_eq!(runtime.archive_members.len(), 51);
        assert_eq!(runtime.required_files.len(), 30);
        assert_eq!(
            runtime
                .archive_members
                .iter()
                .filter(|member| {
                    member.disposition == RuntimeArchiveMemberDisposition::RecognizedNotInstalled
                })
                .count(),
            21
        );

        let archive = workspace.root.join("approved-runtime.zip");
        let staging = workspace.root.join("approved-runtime.staging");
        let destination = workspace.root.join("approved-runtime.destination");
        write_owned_zip(&archive, &entries);
        extract_and_install_runtime(&archive, &staging, &destination, &runtime, &cancel)
            .expect("approved envelope installs");

        assert!(!staging.exists());
        let mut expected = runtime
            .required_files
            .iter()
            .map(|file| file.relative_path.to_ascii_lowercase())
            .collect::<BTreeSet<_>>();
        expected.insert(
            runtime
                .license_asset
                .destination_relative_path
                .to_ascii_lowercase(),
        );
        assert_eq!(top_level_names(&destination), expected);
        for skipped in runtime.archive_members.iter().filter(|member| {
            member.disposition == RuntimeArchiveMemberDisposition::RecognizedNotInstalled
        }) {
            assert!(
                !destination.join(&skipped.relative_path).exists(),
                "recognized but uninstalled member escaped extraction: {}",
                skipped.relative_path
            );
        }
    }

    #[test]
    fn runtime_envelope_rejects_unknown_executable_library_and_text_members() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        for unknown in ["unknown.exe", "unknown.dll", "manifest.txt"] {
            let (runtime, mut entries) = approved_runtime_envelope_fixture();
            entries.push((unknown.into(), b"unexpected".to_vec()));
            let archive = workspace.root.join(format!("{unknown}.zip"));
            let staging = workspace.root.join(format!("{unknown}.staging"));
            let destination = workspace.root.join(format!("{unknown}.destination"));
            write_owned_zip(&archive, &entries);

            let error =
                extract_and_install_runtime(&archive, &staging, &destination, &runtime, &cancel)
                    .expect_err("unknown envelope member must be rejected");

            assert_eq!(error.code, "unexpected_runtime_member");
            assert_eq!(error.archive_member.as_deref(), Some(unknown));
            assert_eq!(error.expected_member_count, Some(51));
            assert_eq!(error.observed_member_count, Some(52));
            assert!(!destination.exists());
            fs::remove_dir_all(&staging).expect("remove failed staging fixture");
        }
    }

    #[test]
    fn runtime_envelope_rejects_missing_members_and_disposition_drift_before_promotion() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        for (missing_name, expected_disposition) in [
            ("llama-server.exe", RuntimeArchiveMemberDisposition::Install),
            (
                "llama-bench.exe",
                RuntimeArchiveMemberDisposition::RecognizedNotInstalled,
            ),
        ] {
            let (runtime, mut entries) = approved_runtime_envelope_fixture();
            entries.retain(|(name, _)| name != missing_name);
            let archive = workspace.root.join(format!("missing-{missing_name}.zip"));
            let staging = workspace
                .root
                .join(format!("missing-{missing_name}.staging"));
            let destination = workspace
                .root
                .join(format!("missing-{missing_name}.destination"));
            write_owned_zip(&archive, &entries);

            let error =
                extract_and_install_runtime(&archive, &staging, &destination, &runtime, &cancel)
                    .expect_err("missing envelope member must be rejected");

            assert_eq!(error.code, "missing_runtime_member");
            assert_eq!(error.archive_member.as_deref(), Some(missing_name));
            assert_eq!(error.archive_disposition, Some(expected_disposition));
            assert_eq!(error.expected_member_count, Some(51));
            assert_eq!(error.observed_member_count, Some(50));
            assert!(!destination.exists());
            fs::remove_dir_all(&staging).expect("remove failed staging fixture");
        }

        let (mut runtime, entries) = approved_runtime_envelope_fixture();
        runtime
            .archive_members
            .iter_mut()
            .find(|member| member.relative_path == "llama-server.exe")
            .expect("launcher envelope member")
            .disposition = RuntimeArchiveMemberDisposition::RecognizedNotInstalled;
        let archive = workspace.root.join("disposition-drift.zip");
        let staging = workspace.root.join("disposition-drift.staging");
        let destination = workspace.root.join("disposition-drift.destination");
        write_owned_zip(&archive, &entries);

        let error =
            extract_and_install_runtime(&archive, &staging, &destination, &runtime, &cancel)
                .expect_err("installable launcher cannot become recognized-only");

        assert_eq!(error.code, "invalid_runtime_archive");
        assert_eq!(error.archive_member.as_deref(), Some("llama-server.exe"));
        assert_eq!(
            error.archive_disposition,
            Some(RuntimeArchiveMemberDisposition::RecognizedNotInstalled)
        );
        assert!(!destination.exists());
        fs::remove_dir_all(&staging).expect("remove failed staging fixture");
    }

    #[test]
    fn runtime_license_asset_identity_is_checked_before_atomic_promotion() {
        let workspace = TestWorkspace::new();
        let cancel = AtomicBool::new(false);
        for field in ["source_relative_path", "sha256"] {
            let (mut runtime, entries) = approved_runtime_envelope_fixture();
            match field {
                "source_relative_path" => {
                    runtime.license_asset.source_relative_path = "missing.txt".into()
                }
                "sha256" => runtime.license_asset.sha256 = "0".repeat(64),
                _ => unreachable!("fixed test field"),
            }
            let archive = workspace.root.join(format!("license-{field}.zip"));
            let staging = workspace.root.join(format!("license-{field}.staging"));
            let destination = workspace.root.join(format!("license-{field}.destination"));
            write_owned_zip(&archive, &entries);

            let error =
                extract_and_install_runtime(&archive, &staging, &destination, &runtime, &cancel)
                    .expect_err("invalid source-controlled license asset must fail");

            assert_eq!(error.code, "license_asset_invalid");
            assert!(!destination.exists());
            assert!(!staging.join("LICENSE-MIT.txt").exists());
            fs::remove_dir_all(&staging).expect("remove failed staging fixture");
        }
    }

    #[test]
    #[ignore = "requires an explicit operator-provided approved runtime archive path"]
    fn offline_approved_runtime_archive_validates_exact_envelope_and_extraction_plan() {
        let archive = PathBuf::from(
            std::env::var("LOCALCOMET_RUNTIME_ARCHIVE_VALIDATION_PATH")
                .expect("explicit archive validation path"),
        );
        let runtime = embedded_runtime();
        assert_eq!(
            fs::metadata(&archive)
                .expect("runtime archive metadata")
                .len(),
            18_007_324
        );
        assert_eq!(
            sha256_file(&archive, None).expect("hash approved runtime archive"),
            "01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89"
        );
        assert_eq!(runtime.archive_members.len(), 51);
        assert_eq!(runtime.required_files.len(), 30);

        let workspace = TestWorkspace::new();
        let staging = workspace.root.join("approved-runtime.staging");
        let destination = workspace
            .roots()
            .runtime_root
            .join(&runtime.managed_relative_path);
        fs::create_dir_all(destination.parent().expect("runtime destination parent"))
            .expect("create temporary runtime root");
        extract_and_install_runtime(
            &archive,
            &staging,
            &destination,
            &runtime,
            &AtomicBool::new(false),
        )
        .expect("approved runtime archive envelope and extraction plan");

        let mut expected = runtime
            .required_files
            .iter()
            .map(|file| file.relative_path.to_ascii_lowercase())
            .collect::<BTreeSet<_>>();
        expected.insert(
            runtime
                .license_asset
                .destination_relative_path
                .to_ascii_lowercase(),
        );
        assert_eq!(top_level_names(&destination), expected);
        assert!(!staging.exists());
        for skipped in runtime.archive_members.iter().filter(|member| {
            member.disposition == RuntimeArchiveMemberDisposition::RecognizedNotInstalled
        }) {
            assert!(!destination.join(&skipped.relative_path).exists());
        }
    }

    #[test]
    fn runtime_failure_codes_map_to_distinct_bounded_stages() {
        for (code, expected) in [
            ("download_failed", AcquisitionFailureStage::Transfer),
            ("size_mismatch", AcquisitionFailureStage::SizeVerification),
            ("hash_mismatch", AcquisitionFailureStage::HashVerification),
            (
                "invalid_runtime_archive",
                AcquisitionFailureStage::ArchiveValidation,
            ),
            (
                "staging_write_failed",
                AcquisitionFailureStage::StagingExtraction,
            ),
            (
                "atomic_install_failed",
                AcquisitionFailureStage::AtomicPromotion,
            ),
            (
                "post_install_validation_failed",
                AcquisitionFailureStage::PostInstallValidation,
            ),
        ] {
            assert_eq!(
                acquisition_failure_stage(code),
                expected,
                "stage for {code}"
            );
        }
    }

    #[test]
    fn terminal_runtime_failure_is_persisted_before_owned_cleanup() {
        let (_workspace, manager, trust) = test_manager();
        let mut artifact = trust
            .approved_download_artifact(TEST_RUNTIME_ID)
            .expect("approved runtime");
        let expected_bytes = {
            let ApprovedDownloadArtifact::Runtime(runtime) = &mut artifact else {
                panic!("test runtime must be a runtime artifact");
            };
            runtime.acquisition.primary_url =
                "https://assets.example.test/runtime.zip?signed-token=must-not-persist".into();
            runtime.acquisition.expected_bytes
        };

        let job_id = register_job(&manager, TEST_RUNTIME_ID, expected_bytes, expected_bytes);
        let acquisition_root = trust.acquisition_root().expect("acquisition root");
        let partial = acquisition_root.join(format!("{job_id}.partial"));
        let staging = acquisition_root.join(format!("{job_id}.runtime-staging"));
        fs::write(&partial, b"runtime archive").expect("write owned partial");
        fs::create_dir(&staging).expect("create owned staging");
        fs::write(staging.join("member"), b"staging data").expect("write staging data");

        manager.persist_terminal_failure_before_cleanup(
            &job_id,
            &artifact,
            &AcquisitionError::new("staging_write_failed"),
        );

        let events = read_failure_events(&trust);
        assert_eq!(events.len(), 2);
        assert_eq!(events[0]["schema_version"], 1);
        assert_eq!(events[0]["artifact_kind"], "runtime");
        assert_eq!(events[0]["artifact_id"], TEST_RUNTIME_ID);
        assert_eq!(events[0]["terminal_status"], "failed");
        assert_eq!(events[0]["stage"], "staging_extraction");
        assert_eq!(events[0]["error_code"], "staging_write_failed");
        assert_eq!(events[0]["downloaded_bytes"], expected_bytes);
        assert_eq!(events[0]["cleanup_complete"], false);
        assert_eq!(events[0]["final_artifact_exists"], false);
        assert_eq!(events[1]["cleanup_complete"], true);
        assert!(!partial.exists());
        assert!(!staging.exists());
        assert!(!trust
            .download_destination(&artifact)
            .expect("runtime destination")
            .exists());

        let event_text =
            fs::read_to_string(trust.acquisition_event_log_path().expect("diagnostic path"))
                .expect("read diagnostic event text");
        assert!(!event_text.contains("signed-token"));
        assert!(!event_text.contains("assets.example.test"));
    }

    #[test]
    fn runtime_envelope_failure_diagnostic_records_only_bounded_member_context() {
        let (_workspace, manager, trust) = test_manager();
        let artifact = trust
            .approved_download_artifact(TEST_RUNTIME_ID)
            .expect("approved runtime");
        let job_id = register_job(&manager, TEST_RUNTIME_ID, 7, 7);
        manager.persist_terminal_failure_before_cleanup(
            &job_id,
            &artifact,
            &AcquisitionError::new("unexpected_runtime_member")
                .archive_member("unknown.exe".into(), None)
                .archive_member_counts(51, 52),
        );

        let events = read_failure_events(&trust);
        assert_eq!(events[0]["stage"], "archive_validation");
        assert_eq!(events[0]["error_code"], "unexpected_runtime_member");
        assert_eq!(events[0]["archive_member"], "unknown.exe");
        assert!(events[0]["archive_disposition"].is_null());
        assert_eq!(events[0]["expected_member_count"], 51);
        assert_eq!(events[0]["observed_member_count"], 52);
        assert_eq!(events[1]["cleanup_complete"], true);
    }

    #[test]
    fn completed_job_does_not_emit_a_terminal_failure_event() {
        let (_workspace, manager, trust) = test_manager();
        let job_id = register_job(&manager, TEST_RUNTIME_ID, 7, 7);

        manager.complete(&job_id, ArtifactDownloadLifecycle::Completed, None);

        assert!(!trust
            .acquisition_event_log_path()
            .expect("diagnostic path")
            .exists());
    }

    #[test]
    fn terminal_event_uses_catalog_identity_and_backend_failure_values() {
        let (workspace, manager, trust) = test_manager();
        let artifact = trust
            .approved_download_artifact(TEST_RUNTIME_ID)
            .expect("approved runtime");
        let job_id = register_job(&manager, TEST_RUNTIME_ID, 7, 3);
        let normal_profile_event = workspace
            .root
            .join("normal-profile")
            .join("LocalComet")
            .join("logs")
            .join("acquisition-events.jsonl");
        fs::create_dir_all(normal_profile_event.parent().expect("normal log parent"))
            .expect("create normal log parent");
        fs::write(&normal_profile_event, b"normal-profile-sentinel\n")
            .expect("write normal profile sentinel");
        {
            let mut registry = manager.jobs.lock().expect("download registry");
            registry
                .jobs
                .get_mut(&job_id)
                .expect("registered job")
                .state
                .artifact_id = "frontend-forged-artifact".into();
        }

        manager.persist_terminal_failure_before_cleanup(
            &job_id,
            &artifact,
            &AcquisitionError::new("atomic_install_failed"),
        );

        let events = read_failure_events(&trust);
        assert_eq!(events[0]["artifact_id"], TEST_RUNTIME_ID);
        assert_eq!(events[0]["stage"], "atomic_promotion");
        assert_eq!(events[0]["error_code"], "atomic_install_failed");
        assert_eq!(events[0]["downloaded_bytes"], 3);
        assert!(!events[0].to_string().contains("frontend-forged-artifact"));
        assert_eq!(
            fs::read_to_string(normal_profile_event).expect("read normal profile sentinel"),
            "normal-profile-sentinel\n"
        );
    }

    #[test]
    fn owned_partial_cleanup_never_targets_an_unrelated_file() {
        let (workspace, manager, trust) = test_manager();
        let root = trust.acquisition_root().expect("acquisition root");
        let job_id = "a".repeat(64);
        let owned = root.join(format!("{job_id}.partial"));
        let unrelated = root.join("notes.partial");
        fs::write(&owned, b"partial").expect("write owned partial");
        fs::write(&unrelated, b"keep").expect("write unrelated file");

        manager.remove_job_partial(&job_id);

        assert!(!owned.exists());
        assert!(unrelated.exists());
        drop(workspace);
    }

    #[test]
    fn cancellation_removes_only_the_active_job_partial() {
        let (_workspace, manager, trust) = test_manager();
        let root = trust.acquisition_root().expect("acquisition root");
        let job_id = "c".repeat(64);
        let partial = root.join(format!("{job_id}.partial"));
        let unrelated = root.join("user-model.gguf.partial");
        fs::write(&partial, b"partial").expect("write owned partial");
        fs::write(&unrelated, b"keep").expect("write unrelated partial");

        let artifact = trust
            .approved_download_artifact(TEST_MODEL_ID)
            .expect("approved model");
        manager.run_job(job_id, artifact, Arc::new(AtomicBool::new(true)));

        assert!(!partial.exists());
        assert!(unrelated.exists());
    }

    #[test]
    fn stale_cleanup_only_removes_owned_job_partials() {
        let (_workspace, manager, trust) = test_manager();
        let root = trust.acquisition_root().expect("acquisition root");
        let owned = root.join(format!("{}.partial", "b".repeat(64)));
        let unrelated = root.join("user-model.gguf.partial");
        fs::write(&owned, b"stale").expect("write stale partial");
        fs::write(&unrelated, b"keep").expect("write unrelated partial");

        manager.cleanup_stale_partials();

        assert!(!owned.exists());
        assert!(unrelated.exists());
    }

    #[test]
    fn start_reuses_valid_artifact_and_rejects_conflicting_or_unknown_artifacts() {
        let (_workspace, manager, trust) = test_manager();
        let confirmation = manager
            .start(TEST_RUNTIME_ID, false)
            .expect_err("require download confirmation");
        assert_eq!(confirmation.code, "confirmation_required");
        let package = trust.roots().runtime_root.join(TEST_RUNTIME_ID);
        fs::create_dir_all(&package).expect("create runtime package");
        fs::write(package.join("llama-server.exe"), TEST_RUNTIME_BYTES)
            .expect("write validated runtime");
        let runtime = match trust
            .approved_download_artifact(TEST_RUNTIME_ID)
            .expect("approved test runtime")
        {
            ApprovedDownloadArtifact::Runtime(runtime) => runtime,
            ApprovedDownloadArtifact::Model(_) => {
                unreachable!("test runtime must remain a runtime")
            }
        };
        let license_bytes = source_controlled_runtime_license_bytes(&runtime.license_asset)
            .expect("test runtime license asset");
        fs::write(
            package.join(runtime.license_asset.destination_relative_path),
            license_bytes,
        )
        .expect("write validated runtime license");

        let reused = manager
            .start(TEST_RUNTIME_ID, true)
            .expect("reuse valid runtime");
        assert_eq!(reused.lifecycle, ArtifactDownloadLifecycle::Completed);
        assert_eq!(reused.received_bytes, reused.expected_bytes);
        assert_eq!(reused.percent, Some(100));

        let model = trust
            .approved_download_artifact(TEST_MODEL_ID)
            .expect("approved model");
        let model_destination = trust
            .download_destination(&model)
            .expect("model destination");
        fs::create_dir_all(model_destination.parent().expect("model parent"))
            .expect("create model parent");
        fs::write(&model_destination, b"conflicting").expect("write conflicting model");

        let conflict = manager
            .start(TEST_MODEL_ID, true)
            .expect_err("reject conflicting model");
        assert_eq!(conflict.code, "conflicting_installed_artifact");
        let unknown = manager
            .start("unknown-artifact", true)
            .expect_err("reject unknown artifact");
        assert_eq!(unknown.code, "unknown_artifact");
    }

    #[test]
    fn duplicate_job_is_returned_and_terminal_state_is_written_once() {
        let (_workspace, manager, _trust) = test_manager();
        let state = manager.new_state(
            TEST_RUNTIME_ID,
            7,
            ArtifactDownloadLifecycle::AwaitingConfirmation,
        );
        let job_id = state.job_id.clone();
        {
            let mut registry = manager.jobs.lock().expect("download registry");
            registry
                .active_by_artifact
                .insert(TEST_RUNTIME_ID.into(), job_id.clone());
            registry.jobs.insert(
                job_id.clone(),
                DownloadJob {
                    state: state.clone(),
                    cancel_requested: Arc::new(AtomicBool::new(false)),
                },
            );
        }

        let duplicate = manager
            .start(TEST_RUNTIME_ID, true)
            .expect("return existing download job");
        assert_eq!(duplicate.job_id, job_id);
        manager.complete(&job_id, ArtifactDownloadLifecycle::Cancelled, None);
        manager.complete(&job_id, ArtifactDownloadLifecycle::Completed, None);

        assert_eq!(
            manager.get(&job_id).expect("completed job").lifecycle,
            ArtifactDownloadLifecycle::Cancelled
        );
        assert!(!manager
            .jobs
            .lock()
            .expect("download registry")
            .active_by_artifact
            .contains_key(TEST_RUNTIME_ID));
    }
}
````

### ПУТЬ: desktop/localcomet-desktop/src-tauri/src/artifact_trust.rs (3295 строк, 121796 байт)

````rust
use crate::control_plane::BridgeError;
use serde::de::{MapAccess, SeqAccess, Visitor};
use serde::{Deserialize, Deserializer, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::borrow::Cow;
use std::collections::{BTreeMap, BTreeSet};
use std::fmt;
use std::fs::{self, File, OpenOptions};
use std::io::{BufReader, Read};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::State;

#[cfg(windows)]
use std::os::windows::{
    ffi::OsStrExt,
    fs::{MetadataExt, OpenOptionsExt},
    io::FromRawHandle,
};

#[cfg(windows)]
use windows_sys::Win32::Foundation::{GENERIC_READ, INVALID_HANDLE_VALUE};

#[cfg(windows)]
use windows_sys::Win32::Storage::FileSystem::{
    CreateFileW, FILE_FLAG_BACKUP_SEMANTICS, FILE_FLAG_OPEN_REPARSE_POINT, FILE_SHARE_READ,
    FILE_SHARE_WRITE, OPEN_EXISTING,
};

const CATALOG_BYTES: &[u8] = include_bytes!("../resources/localcomet/approved-artifacts.v1.json");
const EMBEDDED_CATALOG_SHA256: &str =
    "29bbbe33c207417415f637bafc4dc3853c04cf68db05d9be2a6e661c5f93c605";
const CATALOG_ID: &str = "localcomet-approved-artifacts";
const SCHEMA_VERSION: u32 = 1;
const MAX_ARTIFACTS: usize = 32;
const MAX_REQUIRED_FILES: usize = 128;
const MAX_RUNTIME_ARCHIVE_MEMBERS: usize = 128;
const MAX_RUNTIME_ARCHIVE_BYTES: u64 = 4 * 1024 * 1024 * 1024;
const MAX_MODEL_BYTES: u64 = 128 * 1024 * 1024 * 1024;
const MODEL_ROOT_SENTINEL: &str = "<MANAGED_MODEL_ROOT>";
const INTERNAL_BOOTSTRAP_PURPOSE: &str = "INTERNAL_BOOTSTRAP_INFERENCE_VALIDATION";
const LLAMA_CPP_LICENSE_SOURCE_PATH: &str = "third_party/llama.cpp/LICENSE-MIT.txt";
const LLAMA_CPP_LICENSE_BYTES: &[u8] =
    include_bytes!("../../../../third_party/llama.cpp/LICENSE-MIT.txt");

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CatalogStatus {
    ApprovedInternalBootstrap,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AcquisitionArtifactKind {
    Runtime,
    Model,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AcquisitionSourceType {
    ApprovedHttps,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedArtifactAcquisition {
    pub artifact_id: String,
    pub artifact_kind: AcquisitionArtifactKind,
    pub source_type: AcquisitionSourceType,
    pub primary_url: String,
    pub allowed_redirect_hosts: Vec<String>,
    pub expected_filename: String,
    pub expected_bytes: u64,
    pub expected_sha256: String,
    pub content_type: Option<String>,
    pub managed_relative_destination: String,
    pub public_distribution: bool,
    pub installer_bundled: bool,
    pub automatic_download: bool,
    pub user_confirmation_required: bool,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedRuntimeFile {
    pub relative_path: String,
    pub bytes: u64,
    pub sha256: String,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum RuntimeArchiveMemberDisposition {
    Install,
    RecognizedNotInstalled,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedRuntimeArchiveMember {
    pub relative_path: String,
    pub disposition: RuntimeArchiveMemberDisposition,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedRuntimeLicenseAsset {
    pub source_relative_path: String,
    pub destination_relative_path: String,
    pub bytes: u64,
    pub sha256: String,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedRuntimeArtifact {
    pub runtime_id: String,
    pub provider: String,
    pub release_tag: String,
    pub platform: String,
    pub architecture: String,
    pub variant: String,
    pub upstream_repository: String,
    pub upstream_revision: String,
    pub asset_filename: String,
    pub asset_bytes: u64,
    pub asset_sha256: String,
    pub acquisition: ApprovedArtifactAcquisition,
    pub archive_format: String,
    pub managed_relative_path: String,
    pub executable_relative_path: String,
    pub archive_members: Vec<ApprovedRuntimeArchiveMember>,
    pub required_files: Vec<ApprovedRuntimeFile>,
    pub license_asset: ApprovedRuntimeLicenseAsset,
    pub permitted_bind_scope: String,
    pub supported_api_protocol: String,
    pub license_id: String,
    pub public_distribution: bool,
    pub status: CatalogStatus,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedModelArtifact {
    pub model_id: String,
    pub provider: String,
    pub family: String,
    pub display_name: String,
    pub format: String,
    pub quantization: String,
    pub upstream_repository: String,
    pub upstream_revision: String,
    pub asset_filename: String,
    pub asset_bytes: u64,
    pub asset_sha256: String,
    pub acquisition: ApprovedArtifactAcquisition,
    pub license_id: String,
    pub compatible_runtime_ids: Vec<String>,
    pub managed_relative_path: String,
    pub public_distribution: bool,
    pub installer_bundled: bool,
    pub bootstrap_purpose: String,
    pub status: CatalogStatus,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ApprovedArtifactCatalog {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub runtimes: Vec<ApprovedRuntimeArtifact>,
    pub models: Vec<ApprovedModelArtifact>,
}

#[derive(Clone, Debug)]
pub(crate) struct ManagedArtifactRoots {
    pub app_data_root: PathBuf,
    pub runtime_root: PathBuf,
    pub model_root: PathBuf,
    pub state_root: PathBuf,
}

impl ManagedArtifactRoots {
    pub(crate) fn from_application_data_root(application_data_root: &Path) -> Self {
        Self {
            app_data_root: application_data_root.to_path_buf(),
            runtime_root: application_data_root.join("runtimes").join("llama.cpp"),
            model_root: application_data_root.join("models"),
            state_root: application_data_root.join("runtime-state"),
        }
    }
}

#[derive(Debug)]
pub struct ArtifactTrustError {
    code: &'static str,
    message: String,
}

impl ArtifactTrustError {
    fn new(code: &'static str, message: impl Into<String>) -> Self {
        let message = message.into();
        let safe: String = message
            .chars()
            .filter(|character| !character.is_control())
            .take(240)
            .collect();
        Self {
            code,
            message: safe,
        }
    }
}

pub(crate) fn source_controlled_runtime_license_bytes(
    asset: &ApprovedRuntimeLicenseAsset,
) -> Result<&'static [u8], ArtifactTrustError> {
    if asset.source_relative_path != LLAMA_CPP_LICENSE_SOURCE_PATH
        || asset.bytes != LLAMA_CPP_LICENSE_BYTES.len() as u64
        || sha256_bytes(LLAMA_CPP_LICENSE_BYTES) != asset.sha256
    {
        return Err(ArtifactTrustError::new(
            "invalid_license_asset",
            "runtime license asset identity rejected",
        ));
    }
    Ok(LLAMA_CPP_LICENSE_BYTES)
}

impl From<ArtifactTrustError> for BridgeError {
    fn from(value: ArtifactTrustError) -> Self {
        BridgeError {
            code: value.code.into(),
            message: value.message,
        }
    }
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ArtifactKind {
    Runtime,
    Model,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum InstallationStatus {
    NotInstalled,
    Valid,
    BytesMismatch,
    HashMismatch,
    InvalidPath,
    InvalidFormat,
    MissingRequiredFile,
    UnexpectedFile,
    IoError,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum CompatibilityStatus {
    Compatible,
    NoCompatibleRuntimeInstalled,
    IncompatibleRuntimeInstalled,
}

#[derive(Clone, Debug, Eq, PartialEq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ModelReadiness {
    Ready,
    ModelNotInstalled,
    ModelInvalid,
    RuntimeNotInstalled,
    RuntimeInvalid,
    Incompatible,
}

#[derive(Clone, Debug, Serialize)]
pub struct ApprovedRuntimeSummary {
    pub runtime_id: String,
    pub provider: String,
    pub release_tag: String,
    pub platform: String,
    pub architecture: String,
    pub variant: String,
    pub upstream_repository: String,
    pub upstream_revision: String,
    pub asset_filename: String,
    pub asset_bytes: u64,
    pub asset_sha256: String,
    pub archive_format: String,
    pub permitted_bind_scope: String,
    pub supported_api_protocol: String,
    pub license_id: String,
    pub public_distribution: bool,
    pub status: CatalogStatus,
}

#[derive(Clone, Debug, Serialize)]
pub struct ApprovedModelSummary {
    pub model_id: String,
    pub provider: String,
    pub family: String,
    pub display_name: String,
    pub format: String,
    pub quantization: String,
    pub upstream_repository: String,
    pub upstream_revision: String,
    pub asset_filename: String,
    pub asset_bytes: u64,
    pub asset_sha256: String,
    pub license_id: String,
    pub compatible_runtime_ids: Vec<String>,
    pub public_distribution: bool,
    pub installer_bundled: bool,
    pub bootstrap_purpose: String,
    pub status: CatalogStatus,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedRuntimeCatalog {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub catalog_digest: String,
    pub runtimes: Vec<ApprovedRuntimeSummary>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedModelCatalog {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub catalog_digest: String,
    pub engine: &'static str,
    pub model_root: &'static str,
    pub models: Vec<ApprovedModelSummary>,
    pub maximum_models: usize,
}

#[derive(Clone, Debug, Serialize)]
pub struct ArtifactValidationSummary {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub catalog_digest: String,
    pub artifact_id: String,
    pub kind: ArtifactKind,
    pub catalog_status: CatalogStatus,
    pub installation_status: InstallationStatus,
    pub expected_bytes: u64,
    pub expected_sha256: String,
    pub observed_bytes: Option<u64>,
    pub observed_sha256: Option<String>,
    pub validation_code: String,
    pub verified_unix_ms: u64,
}

#[derive(Clone, Debug, Serialize)]
pub struct ManagedInstalledArtifacts {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub catalog_digest: String,
    pub artifacts: Vec<ArtifactValidationSummary>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ModelReadinessSummary {
    pub schema_version: u32,
    pub catalog_id: String,
    pub catalog_version: String,
    pub catalog_digest: String,
    pub model_id: String,
    pub model_status: InstallationStatus,
    pub compatible_runtime_ids: Vec<String>,
    pub selected_runtime_id: Option<String>,
    pub runtime_status: Option<InstallationStatus>,
    pub compatibility: CompatibilityStatus,
    pub readiness: ModelReadiness,
    pub launchable: bool,
}

#[derive(Debug)]
struct ValidationOutcome {
    status: InstallationStatus,
    observed_bytes: Option<u64>,
    observed_sha256: Option<String>,
    code: &'static str,
}

impl ValidationOutcome {
    fn not_installed() -> Self {
        Self {
            status: InstallationStatus::NotInstalled,
            observed_bytes: None,
            observed_sha256: None,
            code: "not_installed",
        }
    }
}

#[derive(Debug)]
pub(crate) struct ValidatedRuntimeModel {
    pub runtime_id: String,
    pub runtime_release_tag: String,
    pub package_dir: PathBuf,
    pub executable: PathBuf,
    pub model_id: String,
    pub model_display_name: String,
    pub model_path: PathBuf,
    pub model_handle: File,
    pub runtime_handles: Vec<File>,
    pub directory_handles: Vec<File>,
}

#[derive(Clone, Debug)]
pub(crate) enum ApprovedDownloadArtifact {
    Runtime(ApprovedRuntimeArtifact),
    Model(ApprovedModelArtifact),
}

pub struct ArtifactTrustService {
    catalog: ApprovedArtifactCatalog,
    catalog_digest: String,
    roots: ManagedArtifactRoots,
}

impl ArtifactTrustService {
    pub fn production(application_data_root: &Path) -> Result<Self, ArtifactTrustError> {
        let catalog_bytes = canonical_embedded_catalog_bytes()?;
        Self::from_catalog_bytes(
            catalog_bytes.as_ref(),
            ManagedArtifactRoots::from_application_data_root(application_data_root),
        )
    }

    pub(crate) fn from_catalog_bytes(
        bytes: &[u8],
        roots: ManagedArtifactRoots,
    ) -> Result<Self, ArtifactTrustError> {
        let catalog = parse_catalog(bytes)?;
        validate_catalog(&catalog)?;
        validate_canonical_catalog_bytes(bytes, &catalog)?;
        Ok(Self {
            catalog,
            catalog_digest: sha256_bytes(bytes),
            roots,
        })
    }

    pub(crate) fn roots(&self) -> &ManagedArtifactRoots {
        &self.roots
    }

    pub(crate) fn guard_runtime_state_root(&self) -> Result<Vec<File>, ArtifactTrustError> {
        open_directory_guard_chain(&self.roots.app_data_root, &self.roots.state_root, true)
    }

    pub(crate) fn approved_download_artifact(
        &self,
        artifact_id: &str,
    ) -> Result<ApprovedDownloadArtifact, ArtifactTrustError> {
        validate_artifact_id(artifact_id)?;
        if let Some(runtime) = self
            .catalog
            .runtimes
            .iter()
            .find(|runtime| runtime.runtime_id == artifact_id)
        {
            return Ok(ApprovedDownloadArtifact::Runtime(runtime.clone()));
        }
        if let Some(model) = self
            .catalog
            .models
            .iter()
            .find(|model| model.model_id == artifact_id)
        {
            return Ok(ApprovedDownloadArtifact::Model(model.clone()));
        }
        Err(ArtifactTrustError::new(
            "unknown_artifact",
            "unknown approved artifact id",
        ))
    }

    pub(crate) fn acquisition_root(&self) -> Result<PathBuf, ArtifactTrustError> {
        let root = resolve_contained(&self.roots.app_data_root, "acquisition")?;
        let _guards = open_directory_guard_chain(&self.roots.app_data_root, &root, true)?;
        Ok(root)
    }

    pub(crate) fn acquisition_event_log_path(&self) -> Result<PathBuf, ArtifactTrustError> {
        let path = resolve_contained(&self.roots.app_data_root, "logs/acquisition-events.jsonl")?;
        let parent = path
            .parent()
            .ok_or_else(|| ArtifactTrustError::new("invalid_path", "log parent unavailable"))?;
        let _guards = open_directory_guard_chain(&self.roots.app_data_root, parent, true)?;
        Ok(path)
    }

    pub(crate) fn download_destination(
        &self,
        artifact: &ApprovedDownloadArtifact,
    ) -> Result<PathBuf, ArtifactTrustError> {
        let (root, relative) = match artifact {
            ApprovedDownloadArtifact::Runtime(runtime) => {
                (&self.roots.runtime_root, &runtime.managed_relative_path)
            }
            ApprovedDownloadArtifact::Model(model) => {
                (&self.roots.model_root, &model.managed_relative_path)
            }
        };
        let destination = resolve_contained(root, relative)?;
        let parent = destination
            .parent()
            .ok_or_else(|| ArtifactTrustError::new("invalid_path", "managed parent unavailable"))?;
        let _guards = open_directory_guard_chain(&self.roots.app_data_root, parent, true)?;
        Ok(destination)
    }

    pub fn runtime_catalog(&self) -> ManagedRuntimeCatalog {
        ManagedRuntimeCatalog {
            schema_version: self.catalog.schema_version,
            catalog_id: self.catalog.catalog_id.clone(),
            catalog_version: self.catalog.catalog_version.clone(),
            catalog_digest: self.catalog_digest.clone(),
            runtimes: self
                .catalog
                .runtimes
                .iter()
                .map(|runtime| ApprovedRuntimeSummary {
                    runtime_id: runtime.runtime_id.clone(),
                    provider: runtime.provider.clone(),
                    release_tag: runtime.release_tag.clone(),
                    platform: runtime.platform.clone(),
                    architecture: runtime.architecture.clone(),
                    variant: runtime.variant.clone(),
                    upstream_repository: runtime.upstream_repository.clone(),
                    upstream_revision: runtime.upstream_revision.clone(),
                    asset_filename: runtime.asset_filename.clone(),
                    asset_bytes: runtime.asset_bytes,
                    asset_sha256: runtime.asset_sha256.clone(),
                    archive_format: runtime.archive_format.clone(),
                    permitted_bind_scope: runtime.permitted_bind_scope.clone(),
                    supported_api_protocol: runtime.supported_api_protocol.clone(),
                    license_id: runtime.license_id.clone(),
                    public_distribution: runtime.public_distribution,
                    status: runtime.status.clone(),
                })
                .collect(),
        }
    }

    pub fn model_catalog(&self) -> ManagedModelCatalog {
        ManagedModelCatalog {
            schema_version: self.catalog.schema_version,
            catalog_id: self.catalog.catalog_id.clone(),
            catalog_version: self.catalog.catalog_version.clone(),
            catalog_digest: self.catalog_digest.clone(),
            engine: "llama.cpp",
            model_root: MODEL_ROOT_SENTINEL,
            models: self
                .catalog
                .models
                .iter()
                .map(|model| ApprovedModelSummary {
                    model_id: model.model_id.clone(),
                    provider: model.provider.clone(),
                    family: model.family.clone(),
                    display_name: model.display_name.clone(),
                    format: model.format.clone(),
                    quantization: model.quantization.clone(),
                    upstream_repository: model.upstream_repository.clone(),
                    upstream_revision: model.upstream_revision.clone(),
                    asset_filename: model.asset_filename.clone(),
                    asset_bytes: model.asset_bytes,
                    asset_sha256: model.asset_sha256.clone(),
                    license_id: model.license_id.clone(),
                    compatible_runtime_ids: model.compatible_runtime_ids.clone(),
                    public_distribution: model.public_distribution,
                    installer_bundled: model.installer_bundled,
                    bootstrap_purpose: model.bootstrap_purpose.clone(),
                    status: model.status.clone(),
                })
                .collect(),
            maximum_models: MAX_ARTIFACTS,
        }
    }

    pub fn installed_artifacts(&self) -> ManagedInstalledArtifacts {
        let mut artifacts = Vec::new();
        for runtime in &self.catalog.runtimes {
            artifacts.push(self.runtime_validation_summary(runtime));
        }
        for model in &self.catalog.models {
            artifacts.push(self.model_validation_summary(model));
        }
        ManagedInstalledArtifacts {
            schema_version: self.catalog.schema_version,
            catalog_id: self.catalog.catalog_id.clone(),
            catalog_version: self.catalog.catalog_version.clone(),
            catalog_digest: self.catalog_digest.clone(),
            artifacts,
        }
    }

    pub fn artifact_validation_status(
        &self,
        artifact_id: &str,
    ) -> Result<ArtifactValidationSummary, ArtifactTrustError> {
        validate_artifact_id(artifact_id)?;
        if let Some(runtime) = self
            .catalog
            .runtimes
            .iter()
            .find(|runtime| runtime.runtime_id == artifact_id)
        {
            return Ok(self.runtime_validation_summary(runtime));
        }
        if let Some(model) = self
            .catalog
            .models
            .iter()
            .find(|model| model.model_id == artifact_id)
        {
            return Ok(self.model_validation_summary(model));
        }
        Err(ArtifactTrustError::new(
            "unknown_artifact",
            "unknown approved artifact id",
        ))
    }

    pub fn model_readiness(
        &self,
        model_id: &str,
    ) -> Result<ModelReadinessSummary, ArtifactTrustError> {
        validate_artifact_id(model_id)?;
        let model = self
            .catalog
            .models
            .iter()
            .find(|model| model.model_id == model_id)
            .ok_or_else(|| ArtifactTrustError::new("unknown_artifact", "unknown model id"))?;
        let model_outcome = self.validate_model(model);
        let mut selected_runtime_id = None;
        let mut selected_runtime_status = None;
        let mut saw_invalid_runtime = false;
        for runtime_id in &model.compatible_runtime_ids {
            let runtime = self
                .catalog
                .runtimes
                .iter()
                .find(|runtime| &runtime.runtime_id == runtime_id)
                .ok_or_else(|| {
                    ArtifactTrustError::new("invalid_catalog", "unknown compatible runtime")
                })?;
            let outcome = self.validate_runtime(runtime);
            if outcome.status == InstallationStatus::Valid {
                selected_runtime_id = Some(runtime.runtime_id.clone());
                selected_runtime_status = Some(outcome.status);
                break;
            }
            if outcome.status != InstallationStatus::NotInstalled {
                saw_invalid_runtime = true;
            }
            if selected_runtime_status.is_none()
                || (selected_runtime_status == Some(InstallationStatus::NotInstalled)
                    && outcome.status != InstallationStatus::NotInstalled)
            {
                selected_runtime_status = Some(outcome.status);
            }
        }
        let incompatible_runtime_installed = selected_runtime_id.is_none()
            && self.catalog.runtimes.iter().any(|runtime| {
                !model
                    .compatible_runtime_ids
                    .iter()
                    .any(|runtime_id| runtime_id == &runtime.runtime_id)
                    && self.validate_runtime(runtime).status == InstallationStatus::Valid
            });
        let compatibility = if selected_runtime_id.is_some() {
            CompatibilityStatus::Compatible
        } else if incompatible_runtime_installed {
            CompatibilityStatus::IncompatibleRuntimeInstalled
        } else {
            CompatibilityStatus::NoCompatibleRuntimeInstalled
        };
        let (readiness, launchable) = match model_outcome.status {
            InstallationStatus::NotInstalled => (ModelReadiness::ModelNotInstalled, false),
            InstallationStatus::Valid if selected_runtime_id.is_some() => {
                (ModelReadiness::Ready, true)
            }
            InstallationStatus::Valid if saw_invalid_runtime => {
                (ModelReadiness::RuntimeInvalid, false)
            }
            InstallationStatus::Valid if incompatible_runtime_installed => {
                (ModelReadiness::Incompatible, false)
            }
            InstallationStatus::Valid => (ModelReadiness::RuntimeNotInstalled, false),
            _ => (ModelReadiness::ModelInvalid, false),
        };
        Ok(ModelReadinessSummary {
            schema_version: self.catalog.schema_version,
            catalog_id: self.catalog.catalog_id.clone(),
            catalog_version: self.catalog.catalog_version.clone(),
            catalog_digest: self.catalog_digest.clone(),
            model_id: model.model_id.clone(),
            model_status: model_outcome.status,
            compatible_runtime_ids: model.compatible_runtime_ids.clone(),
            selected_runtime_id,
            runtime_status: selected_runtime_status,
            compatibility,
            readiness,
            launchable,
        })
    }

    pub(crate) fn resolve_launch(
        &self,
        model_id: &str,
    ) -> Result<ValidatedRuntimeModel, ArtifactTrustError> {
        let readiness = self.model_readiness(model_id)?;
        if !readiness.launchable {
            return Err(ArtifactTrustError::new(
                "artifact_not_ready",
                "approved runtime/model pair is not ready",
            ));
        }
        let model = self
            .catalog
            .models
            .iter()
            .find(|model| model.model_id == model_id)
            .ok_or_else(|| ArtifactTrustError::new("unknown_artifact", "unknown model id"))?;
        let runtime_id = readiness
            .selected_runtime_id
            .ok_or_else(|| ArtifactTrustError::new("artifact_not_ready", "runtime unavailable"))?;
        let runtime = self
            .catalog
            .runtimes
            .iter()
            .find(|runtime| runtime.runtime_id == runtime_id)
            .ok_or_else(|| ArtifactTrustError::new("invalid_catalog", "runtime unavailable"))?;
        let package_dir =
            resolve_contained(&self.roots.runtime_root, &runtime.managed_relative_path)?;
        let executable = resolve_contained(&package_dir, &runtime.executable_relative_path)?;
        let model_path = resolve_contained(&self.roots.model_root, &model.managed_relative_path)?;
        let model_parent = model_path
            .parent()
            .ok_or_else(|| ArtifactTrustError::new("invalid_path", "model parent unavailable"))?;
        let mut directory_handles =
            open_directory_guard_chain(&self.roots.app_data_root, &package_dir, false)?;
        directory_handles.extend(open_directory_guard_chain(
            &self.roots.app_data_root,
            model_parent,
            false,
        )?);
        for required in &runtime.required_files {
            let path = resolve_contained(&package_dir, &required.relative_path)?;
            let parent = path.parent().ok_or_else(|| {
                ArtifactTrustError::new("invalid_path", "runtime file parent unavailable")
            })?;
            directory_handles.extend(open_directory_guard_chain(
                &self.roots.app_data_root,
                parent,
                false,
            )?);
        }
        let model_handle = open_model_guard(&model_path)?;
        let mut runtime_handles = Vec::with_capacity(runtime.required_files.len());
        for required in &runtime.required_files {
            let path = resolve_contained(&package_dir, &required.relative_path)?;
            runtime_handles.push(open_runtime_guard(&path)?);
        }
        let model_recheck = self.validate_model(model);
        if model_recheck.status != InstallationStatus::Valid {
            return Err(ArtifactTrustError::new(
                "artifact_changed",
                "model identity changed before launch",
            ));
        }
        let runtime_recheck = self.validate_runtime(runtime);
        if runtime_recheck.status != InstallationStatus::Valid {
            return Err(ArtifactTrustError::new(
                "artifact_changed",
                "runtime identity changed before launch",
            ));
        }
        Ok(ValidatedRuntimeModel {
            runtime_id: runtime.runtime_id.clone(),
            runtime_release_tag: runtime.release_tag.clone(),
            package_dir,
            executable,
            model_id: model.model_id.clone(),
            model_display_name: model.display_name.clone(),
            model_path,
            model_handle,
            runtime_handles,
            directory_handles,
        })
    }

    pub(crate) fn has_valid_runtime(&self) -> bool {
        self.catalog
            .runtimes
            .iter()
            .any(|runtime| self.validate_runtime(runtime).status == InstallationStatus::Valid)
    }

    fn runtime_validation_summary(
        &self,
        runtime: &ApprovedRuntimeArtifact,
    ) -> ArtifactValidationSummary {
        let outcome = self.validate_runtime(runtime);
        self.validation_summary(
            &runtime.runtime_id,
            ArtifactKind::Runtime,
            runtime.status.clone(),
            runtime.asset_bytes,
            &runtime.asset_sha256,
            outcome,
        )
    }

    fn model_validation_summary(&self, model: &ApprovedModelArtifact) -> ArtifactValidationSummary {
        let outcome = self.validate_model(model);
        self.validation_summary(
            &model.model_id,
            ArtifactKind::Model,
            model.status.clone(),
            model.asset_bytes,
            &model.asset_sha256,
            outcome,
        )
    }

    fn validation_summary(
        &self,
        artifact_id: &str,
        kind: ArtifactKind,
        catalog_status: CatalogStatus,
        expected_bytes: u64,
        expected_sha256: &str,
        outcome: ValidationOutcome,
    ) -> ArtifactValidationSummary {
        ArtifactValidationSummary {
            schema_version: self.catalog.schema_version,
            catalog_id: self.catalog.catalog_id.clone(),
            catalog_version: self.catalog.catalog_version.clone(),
            catalog_digest: self.catalog_digest.clone(),
            artifact_id: artifact_id.to_string(),
            kind,
            catalog_status,
            installation_status: outcome.status,
            expected_bytes,
            expected_sha256: expected_sha256.to_string(),
            observed_bytes: outcome.observed_bytes,
            observed_sha256: outcome.observed_sha256,
            validation_code: outcome.code.into(),
            verified_unix_ms: now_unix_ms(),
        }
    }

    fn validate_runtime(&self, runtime: &ApprovedRuntimeArtifact) -> ValidationOutcome {
        let package_dir =
            match resolve_contained(&self.roots.runtime_root, &runtime.managed_relative_path) {
                Ok(path) => path,
                Err(_) => {
                    return ValidationOutcome {
                        status: InstallationStatus::InvalidPath,
                        observed_bytes: None,
                        observed_sha256: None,
                        code: "invalid_path",
                    }
                }
            };
        if !package_dir.exists() {
            return ValidationOutcome::not_installed();
        }
        if ensure_existing_safe_path(
            &self.roots.app_data_root,
            &self.roots.runtime_root,
            &package_dir,
            true,
        )
        .is_err()
        {
            return ValidationOutcome {
                status: InstallationStatus::InvalidPath,
                observed_bytes: None,
                observed_sha256: None,
                code: "invalid_path",
            };
        }
        let mut listed = BTreeSet::new();
        for required in &runtime.required_files {
            listed.insert(required.relative_path.to_ascii_lowercase());
            let file_path = match resolve_contained(&package_dir, &required.relative_path) {
                Ok(path) => path,
                Err(_) => {
                    return ValidationOutcome {
                        status: InstallationStatus::InvalidPath,
                        observed_bytes: None,
                        observed_sha256: None,
                        code: "invalid_path",
                    }
                }
            };
            let metadata = match file_path.metadata() {
                Ok(metadata) if metadata.is_file() => metadata,
                _ => {
                    return ValidationOutcome {
                        status: InstallationStatus::MissingRequiredFile,
                        observed_bytes: None,
                        observed_sha256: None,
                        code: "missing_required_file",
                    }
                }
            };
            if reject_reparse_point(&file_path).is_err() {
                return ValidationOutcome {
                    status: InstallationStatus::InvalidPath,
                    observed_bytes: None,
                    observed_sha256: None,
                    code: "invalid_path",
                };
            }
            if metadata.len() != required.bytes {
                return ValidationOutcome {
                    status: InstallationStatus::BytesMismatch,
                    observed_bytes: Some(metadata.len()),
                    observed_sha256: None,
                    code: "bytes_mismatch",
                };
            }
            match sha256_file(&file_path) {
                Ok(hash) if hash == required.sha256 => {}
                Ok(_) => {
                    return ValidationOutcome {
                        status: InstallationStatus::HashMismatch,
                        observed_bytes: Some(metadata.len()),
                        observed_sha256: None,
                        code: "hash_mismatch",
                    }
                }
                Err(_) => {
                    return ValidationOutcome {
                        status: InstallationStatus::IoError,
                        observed_bytes: Some(metadata.len()),
                        observed_sha256: None,
                        code: "io_error",
                    }
                }
            }
        }
        let license_bytes = match source_controlled_runtime_license_bytes(&runtime.license_asset) {
            Ok(bytes) => bytes,
            Err(_) => {
                return ValidationOutcome {
                    status: InstallationStatus::InvalidPath,
                    observed_bytes: None,
                    observed_sha256: None,
                    code: "invalid_license_asset",
                }
            }
        };
        let license_path = match resolve_contained(
            &package_dir,
            &runtime.license_asset.destination_relative_path,
        ) {
            Ok(path) => path,
            Err(_) => {
                return ValidationOutcome {
                    status: InstallationStatus::InvalidPath,
                    observed_bytes: None,
                    observed_sha256: None,
                    code: "invalid_path",
                }
            }
        };
        listed.insert(
            runtime
                .license_asset
                .destination_relative_path
                .to_ascii_lowercase(),
        );
        let license_metadata = match license_path.metadata() {
            Ok(metadata) if metadata.is_file() => metadata,
            _ => {
                return ValidationOutcome {
                    status: InstallationStatus::MissingRequiredFile,
                    observed_bytes: None,
                    observed_sha256: None,
                    code: "missing_required_file",
                }
            }
        };
        if reject_reparse_point(&license_path).is_err() {
            return ValidationOutcome {
                status: InstallationStatus::InvalidPath,
                observed_bytes: None,
                observed_sha256: None,
                code: "invalid_path",
            };
        }
        if license_metadata.len() != runtime.license_asset.bytes
            || license_bytes.len() as u64 != runtime.license_asset.bytes
        {
            return ValidationOutcome {
                status: InstallationStatus::BytesMismatch,
                observed_bytes: Some(license_metadata.len()),
                observed_sha256: None,
                code: "bytes_mismatch",
            };
        }
        match sha256_file(&license_path) {
            Ok(hash) if hash == runtime.license_asset.sha256 => {}
            Ok(_) => {
                return ValidationOutcome {
                    status: InstallationStatus::HashMismatch,
                    observed_bytes: Some(license_metadata.len()),
                    observed_sha256: None,
                    code: "hash_mismatch",
                }
            }
            Err(_) => {
                return ValidationOutcome {
                    status: InstallationStatus::IoError,
                    observed_bytes: Some(license_metadata.len()),
                    observed_sha256: None,
                    code: "io_error",
                }
            }
        }
        if reject_unlisted_runtime_files(&package_dir, &listed).is_err() {
            return ValidationOutcome {
                status: InstallationStatus::UnexpectedFile,
                observed_bytes: None,
                observed_sha256: None,
                code: "unexpected_file",
            };
        }
        ValidationOutcome {
            status: InstallationStatus::Valid,
            observed_bytes: None,
            observed_sha256: None,
            code: "valid",
        }
    }

    fn validate_model(&self, model: &ApprovedModelArtifact) -> ValidationOutcome {
        let path = match resolve_contained(&self.roots.model_root, &model.managed_relative_path) {
            Ok(path) => path,
            Err(_) => {
                return ValidationOutcome {
                    status: InstallationStatus::InvalidPath,
                    observed_bytes: None,
                    observed_sha256: None,
                    code: "invalid_path",
                }
            }
        };
        if !path.exists() {
            return ValidationOutcome::not_installed();
        }
        if ensure_existing_safe_path(
            &self.roots.app_data_root,
            &self.roots.model_root,
            &path,
            false,
        )
        .is_err()
        {
            return ValidationOutcome {
                status: InstallationStatus::InvalidPath,
                observed_bytes: None,
                observed_sha256: None,
                code: "invalid_path",
            };
        }
        let metadata = match path.metadata() {
            Ok(metadata) if metadata.is_file() => metadata,
            _ => {
                return ValidationOutcome {
                    status: InstallationStatus::InvalidPath,
                    observed_bytes: None,
                    observed_sha256: None,
                    code: "invalid_path",
                }
            }
        };
        if metadata.len() != model.asset_bytes {
            return ValidationOutcome {
                status: InstallationStatus::BytesMismatch,
                observed_bytes: Some(metadata.len()),
                observed_sha256: None,
                code: "bytes_mismatch",
            };
        }
        let mut magic = [0_u8; 4];
        match File::open(&path).and_then(|mut file| file.read_exact(&mut magic)) {
            Ok(()) if &magic == b"GGUF" => {}
            _ => {
                return ValidationOutcome {
                    status: InstallationStatus::InvalidFormat,
                    observed_bytes: Some(metadata.len()),
                    observed_sha256: None,
                    code: "invalid_format",
                }
            }
        }
        match sha256_file(&path) {
            Ok(hash) if hash == model.asset_sha256 => ValidationOutcome {
                status: InstallationStatus::Valid,
                observed_bytes: Some(metadata.len()),
                observed_sha256: Some(hash),
                code: "valid",
            },
            Ok(hash) => ValidationOutcome {
                status: InstallationStatus::HashMismatch,
                observed_bytes: Some(metadata.len()),
                observed_sha256: Some(hash),
                code: "hash_mismatch",
            },
            Err(_) => ValidationOutcome {
                status: InstallationStatus::IoError,
                observed_bytes: Some(metadata.len()),
                observed_sha256: None,
                code: "io_error",
            },
        }
    }
}

fn normalize_catalog_line_endings(bytes: &[u8]) -> Result<Cow<'_, [u8]>, ArtifactTrustError> {
    if !bytes.contains(&b'\r') {
        return Ok(Cow::Borrowed(bytes));
    }

    let mut normalized = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'\r' {
            if bytes.get(index + 1) != Some(&b'\n') {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "catalog line endings rejected",
                ));
            }
            normalized.push(b'\n');
            index += 2;
        } else {
            normalized.push(bytes[index]);
            index += 1;
        }
    }
    Ok(Cow::Owned(normalized))
}

fn canonical_catalog_bytes(bytes: &[u8]) -> Result<Cow<'_, [u8]>, ArtifactTrustError> {
    let normalized = normalize_catalog_line_endings(bytes)?;
    if sha256_bytes(normalized.as_ref()) != EMBEDDED_CATALOG_SHA256 {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "embedded catalog identity rejected",
        ));
    }
    Ok(normalized)
}

fn canonical_embedded_catalog_bytes() -> Result<Cow<'static, [u8]>, ArtifactTrustError> {
    canonical_catalog_bytes(CATALOG_BYTES)
}

#[tauri::command]
pub fn managed_runtime_catalog(
    state: State<'_, Arc<ArtifactTrustService>>,
) -> ManagedRuntimeCatalog {
    state.runtime_catalog()
}

#[tauri::command]
pub fn managed_model_catalog(state: State<'_, Arc<ArtifactTrustService>>) -> ManagedModelCatalog {
    state.model_catalog()
}

#[tauri::command]
pub async fn managed_installed_artifacts(
    state: State<'_, Arc<ArtifactTrustService>>,
) -> Result<ManagedInstalledArtifacts, BridgeError> {
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || {
        let start = std::time::Instant::now();
        let result = state.installed_artifacts();
        let dur_ms = start.elapsed().as_millis();
        if perf_logging_enabled() {
            eprintln!("[PERF] cmd=managed_installed_artifacts dur_ms={dur_ms}");
        }
        result
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "installed artifacts worker failed"))
}

#[tauri::command]
pub async fn managed_artifact_validation_status(
    state: State<'_, Arc<ArtifactTrustService>>,
    artifact_id: String,
) -> Result<ArtifactValidationSummary, BridgeError> {
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || {
        let start = std::time::Instant::now();
        let result = state
            .artifact_validation_status(&artifact_id)
            .map_err(BridgeError::from);
        let dur_ms = start.elapsed().as_millis();
        if perf_logging_enabled() {
            eprintln!(
                "[PERF] cmd=managed_artifact_validation_status artifact={artifact_id} dur_ms={dur_ms}"
            );
        }
        result
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "artifact validation worker failed"))?
}

#[tauri::command]
pub async fn managed_model_readiness(
    state: State<'_, Arc<ArtifactTrustService>>,
    model_id: String,
) -> Result<ModelReadinessSummary, BridgeError> {
    let state = Arc::clone(&state);
    tauri::async_runtime::spawn_blocking(move || {
        let start = std::time::Instant::now();
        let result = state.model_readiness(&model_id).map_err(BridgeError::from);
        let dur_ms = start.elapsed().as_millis();
        if perf_logging_enabled() {
            eprintln!("[PERF] cmd=managed_model_readiness model={model_id} dur_ms={dur_ms}");
        }
        result
    })
    .await
    .map_err(|_| BridgeError::new("runtime_unavailable", "model readiness worker failed"))?
}

fn parse_catalog(bytes: &[u8]) -> Result<ApprovedArtifactCatalog, ArtifactTrustError> {
    if bytes.starts_with(&[0xef, 0xbb, 0xbf]) {
        return Err(ArtifactTrustError::new("invalid_catalog", "BOM rejected"));
    }
    let mut deserializer = serde_json::Deserializer::from_slice(bytes);
    let unique = UniqueValue::deserialize(&mut deserializer)
        .map_err(|_| ArtifactTrustError::new("invalid_catalog", "catalog JSON rejected"))?;
    deserializer
        .end()
        .map_err(|_| ArtifactTrustError::new("invalid_catalog", "catalog trailing data"))?;
    serde_json::from_value(unique.0)
        .map_err(|_| ArtifactTrustError::new("invalid_catalog", "catalog schema rejected"))
}

fn validate_canonical_catalog_bytes(
    bytes: &[u8],
    catalog: &ApprovedArtifactCatalog,
) -> Result<(), ArtifactTrustError> {
    let text = std::str::from_utf8(bytes)
        .map_err(|_| ArtifactTrustError::new("invalid_catalog", "catalog is not UTF-8"))?;
    if text.contains('\r')
        || !text.ends_with('\n')
        || text.ends_with("\n\n")
        || text.lines().any(|line| line.ends_with([' ', '\t']))
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "catalog serialization rejected",
        ));
    }
    let mut canonical = serde_json::to_string_pretty(catalog)
        .map_err(|_| ArtifactTrustError::new("invalid_catalog", "catalog serialization failed"))?;
    canonical.push('\n');
    if canonical.as_bytes() != bytes {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "catalog is not canonical",
        ));
    }
    Ok(())
}

fn validate_catalog(catalog: &ApprovedArtifactCatalog) -> Result<(), ArtifactTrustError> {
    if catalog.schema_version != SCHEMA_VERSION
        || catalog.catalog_id != CATALOG_ID
        || catalog.catalog_version.is_empty()
        || catalog.catalog_version.len() > 64
        || catalog.catalog_version.bytes().any(|byte| {
            !(byte.is_ascii_lowercase() || byte.is_ascii_digit() || matches!(byte, b'.' | b'-'))
        })
        || catalog.runtimes.is_empty()
        || catalog.runtimes.len() > MAX_ARTIFACTS
        || catalog.models.is_empty()
        || catalog.models.len() > MAX_ARTIFACTS
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "catalog header rejected",
        ));
    }
    ensure_sorted_unique(
        catalog
            .runtimes
            .iter()
            .map(|runtime| runtime.runtime_id.as_str()),
    )?;
    ensure_sorted_unique(catalog.models.iter().map(|model| model.model_id.as_str()))?;
    let runtime_ids: BTreeSet<&str> = catalog
        .runtimes
        .iter()
        .map(|runtime| runtime.runtime_id.as_str())
        .collect();
    let mut artifact_ids = BTreeSet::new();
    let mut filenames = BTreeMap::new();
    let mut runtime_locations = BTreeSet::new();
    let mut model_locations = BTreeSet::new();
    let mut acquisition_sources = BTreeSet::new();

    for runtime in &catalog.runtimes {
        validate_artifact_id(&runtime.runtime_id)?;
        if !artifact_ids.insert(runtime.runtime_id.as_str()) {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "duplicate artifact id",
            ));
        }
        validate_required_texts(&[
            &runtime.provider,
            &runtime.release_tag,
            &runtime.upstream_repository,
            &runtime.upstream_revision,
            &runtime.license_id,
        ])?;
        if runtime.platform != "windows"
            || runtime.architecture != "x86-64"
            || runtime.variant != "cpu"
            || runtime.archive_format != "zip"
            || runtime.permitted_bind_scope != "loopback-only"
            || runtime.supported_api_protocol != "openai-compatible-v1"
            || runtime.public_distribution
            || runtime.asset_bytes == 0
            || runtime.asset_bytes > MAX_RUNTIME_ARCHIVE_BYTES
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime policy rejected",
            ));
        }
        validate_sha256(&runtime.asset_sha256)?;
        validate_filename(&runtime.asset_filename)?;
        validate_relative_windows_path(&runtime.managed_relative_path)?;
        validate_acquisition(
            &runtime.acquisition,
            ExpectedAcquisition {
                artifact_id: &runtime.runtime_id,
                artifact_kind: AcquisitionArtifactKind::Runtime,
                filename: &runtime.asset_filename,
                bytes: runtime.asset_bytes,
                sha256: &runtime.asset_sha256,
                destination: &runtime.managed_relative_path,
            },
            &mut acquisition_sources,
        )?;
        insert_disjoint_managed_path(&mut runtime_locations, &runtime.managed_relative_path)?;
        validate_relative_windows_path(&runtime.executable_relative_path)?;
        if !runtime
            .executable_relative_path
            .to_ascii_lowercase()
            .ends_with(".exe")
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime executable extension rejected",
            ));
        }
        if runtime.required_files.is_empty() || runtime.required_files.len() > MAX_REQUIRED_FILES {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime file list rejected",
            ));
        }
        let mut file_paths = BTreeSet::new();
        let mut previous = None::<String>;
        let mut executable_found = false;
        for required in &runtime.required_files {
            validate_relative_windows_path(&required.relative_path)?;
            validate_sha256(&required.sha256)?;
            if required.bytes == 0 {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "runtime file size rejected",
                ));
            }
            let folded = required.relative_path.to_ascii_lowercase();
            if previous
                .as_ref()
                .is_some_and(|value| value >= &folded || folded.starts_with(&format!("{value}/")))
                || !file_paths.insert(folded.clone())
            {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "runtime files not sorted or unique",
                ));
            }
            previous = Some(folded);
            if required
                .relative_path
                .eq_ignore_ascii_case(&runtime.executable_relative_path)
            {
                executable_found = true;
            } else if !required
                .relative_path
                .to_ascii_lowercase()
                .ends_with(".dll")
            {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "runtime installable file type rejected",
                ));
            }
        }
        if !executable_found {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime executable identity missing",
            ));
        }
        if runtime.license_asset.source_relative_path != LLAMA_CPP_LICENSE_SOURCE_PATH
            || runtime.license_asset.destination_relative_path != "LICENSE-MIT.txt"
            || runtime.license_asset.bytes == 0
            || validate_relative_windows_path(&runtime.license_asset.destination_relative_path)
                .is_err()
            || validate_sha256(&runtime.license_asset.sha256).is_err()
            || source_controlled_runtime_license_bytes(&runtime.license_asset).is_err()
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime license asset rejected",
            ));
        }
        let license_destination = runtime
            .license_asset
            .destination_relative_path
            .to_ascii_lowercase();
        if file_paths.contains(&license_destination) {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime license destination overlaps installable file",
            ));
        }
        if runtime.archive_members.is_empty()
            || runtime.archive_members.len() > MAX_RUNTIME_ARCHIVE_MEMBERS
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime archive member list rejected",
            ));
        }
        let mut archive_paths = BTreeSet::new();
        let mut archive_install_paths = BTreeSet::new();
        let mut archive_previous = None::<String>;
        for member in &runtime.archive_members {
            validate_relative_windows_path(&member.relative_path)?;
            let folded = member.relative_path.to_ascii_lowercase();
            if archive_previous
                .as_ref()
                .is_some_and(|value| value >= &folded || folded.starts_with(&format!("{value}/")))
                || !archive_paths.insert(folded.clone())
            {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "runtime archive members not sorted or unique",
                ));
            }
            archive_previous = Some(folded.clone());
            match member.disposition {
                RuntimeArchiveMemberDisposition::Install => {
                    if !file_paths.contains(&folded) || !archive_install_paths.insert(folded) {
                        return Err(ArtifactTrustError::new(
                            "invalid_catalog",
                            "runtime install disposition rejected",
                        ));
                    }
                }
                RuntimeArchiveMemberDisposition::RecognizedNotInstalled => {
                    if file_paths.contains(&folded)
                        || folded == runtime.executable_relative_path.to_ascii_lowercase()
                        || !folded.ends_with(".exe")
                    {
                        return Err(ArtifactTrustError::new(
                            "invalid_catalog",
                            "runtime recognized member disposition rejected",
                        ));
                    }
                }
            }
        }
        if archive_install_paths != file_paths {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "runtime archive install set mismatch",
            ));
        }
        insert_filename(
            &mut filenames,
            &runtime.asset_filename,
            &runtime.managed_relative_path,
        )?;
    }

    for model in &catalog.models {
        validate_artifact_id(&model.model_id)?;
        if !artifact_ids.insert(model.model_id.as_str()) {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "duplicate artifact id",
            ));
        }
        validate_required_texts(&[
            &model.provider,
            &model.family,
            &model.display_name,
            &model.upstream_repository,
            &model.upstream_revision,
            &model.license_id,
        ])?;
        if model.format != "GGUF"
            || model.quantization != "Q4_K_M"
            || model.asset_bytes == 0
            || model.asset_bytes > MAX_MODEL_BYTES
            || model.public_distribution
            || model.installer_bundled
            || model.bootstrap_purpose != INTERNAL_BOOTSTRAP_PURPOSE
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "model policy rejected",
            ));
        }
        validate_sha256(&model.asset_sha256)?;
        validate_filename(&model.asset_filename)?;
        validate_relative_windows_path(&model.managed_relative_path)?;
        validate_acquisition(
            &model.acquisition,
            ExpectedAcquisition {
                artifact_id: &model.model_id,
                artifact_kind: AcquisitionArtifactKind::Model,
                filename: &model.asset_filename,
                bytes: model.asset_bytes,
                sha256: &model.asset_sha256,
                destination: &model.managed_relative_path,
            },
            &mut acquisition_sources,
        )?;
        insert_disjoint_managed_path(&mut model_locations, &model.managed_relative_path)?;
        let managed_filename = model
            .managed_relative_path
            .rsplit('/')
            .next()
            .unwrap_or_default();
        if !model.asset_filename.to_ascii_lowercase().ends_with(".gguf")
            || !managed_filename.eq_ignore_ascii_case(&model.asset_filename)
            || model.compatible_runtime_ids.is_empty()
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "model path or compatibility rejected",
            ));
        }
        ensure_sorted_unique(
            model
                .compatible_runtime_ids
                .iter()
                .map(|runtime_id| runtime_id.as_str()),
        )?;
        for runtime_id in &model.compatible_runtime_ids {
            validate_artifact_id(runtime_id)?;
            if !runtime_ids.contains(runtime_id.as_str()) {
                return Err(ArtifactTrustError::new(
                    "invalid_catalog",
                    "unknown compatible runtime",
                ));
            }
        }
        insert_filename(
            &mut filenames,
            &model.asset_filename,
            &model.managed_relative_path,
        )?;
    }
    Ok(())
}

struct ExpectedAcquisition<'a> {
    artifact_id: &'a str,
    artifact_kind: AcquisitionArtifactKind,
    filename: &'a str,
    bytes: u64,
    sha256: &'a str,
    destination: &'a str,
}

fn validate_acquisition(
    acquisition: &ApprovedArtifactAcquisition,
    expected: ExpectedAcquisition<'_>,
    identities: &mut BTreeSet<String>,
) -> Result<(), ArtifactTrustError> {
    validate_artifact_id(&acquisition.artifact_id)?;
    if acquisition.artifact_id != expected.artifact_id
        || acquisition.artifact_kind != expected.artifact_kind
        || acquisition.source_type != AcquisitionSourceType::ApprovedHttps
        || acquisition.expected_filename != expected.filename
        || acquisition.expected_bytes != expected.bytes
        || acquisition.expected_sha256 != expected.sha256
        || acquisition.managed_relative_destination != expected.destination
        || acquisition.public_distribution
        || acquisition.installer_bundled
        || acquisition.automatic_download
        || !acquisition.user_confirmation_required
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "acquisition identity rejected",
        ));
    }
    validate_filename(&acquisition.expected_filename)?;
    validate_sha256(&acquisition.expected_sha256)?;
    validate_relative_windows_path(&acquisition.managed_relative_destination)?;
    if acquisition.expected_bytes == 0
        || acquisition.allowed_redirect_hosts.is_empty()
        || acquisition.allowed_redirect_hosts.len() > 16
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "acquisition metadata rejected",
        ));
    }
    let mut prior_host = None::<&str>;
    for host in &acquisition.allowed_redirect_hosts {
        validate_allowed_redirect_host(host)?;
        if prior_host.is_some_and(|prior| prior >= host.as_str()) {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "redirect hosts not sorted or unique",
            ));
        }
        prior_host = Some(host);
    }
    let primary_host = validate_https_url(&acquisition.primary_url)?;
    if !acquisition
        .allowed_redirect_hosts
        .iter()
        .any(|host| host == primary_host)
        || !identities.insert(acquisition.primary_url.clone())
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "acquisition source rejected",
        ));
    }
    if let Some(content_type) = &acquisition.content_type {
        if content_type.is_empty()
            || content_type.len() > 128
            || content_type.chars().any(|character| {
                character.is_control()
                    || !(character.is_ascii_alphanumeric()
                        || matches!(character, '/' | '-' | '+' | '.' | ';' | '=' | ' '))
            })
        {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "acquisition content type rejected",
            ));
        }
    }
    Ok(())
}

fn validate_allowed_redirect_host(value: &str) -> Result<(), ArtifactTrustError> {
    if value.is_empty()
        || value.len() > 253
        || value.starts_with('.')
        || value.ends_with('.')
        || !value.contains('.')
        || value.bytes().any(|byte| {
            !(byte.is_ascii_lowercase() || byte.is_ascii_digit() || matches!(byte, b'.' | b'-'))
        })
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "redirect host rejected",
        ));
    }
    Ok(())
}

fn validate_https_url(value: &str) -> Result<&str, ArtifactTrustError> {
    if value.len() > 2_048
        || value.chars().any(char::is_control)
        || !value.starts_with("https://")
        || value.contains(['?', '#', '@', '\\'])
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "HTTPS URL rejected",
        ));
    }
    let after_scheme = &value["https://".len()..];
    let Some((host, path)) = after_scheme.split_once('/') else {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "HTTPS URL path rejected",
        ));
    };
    validate_allowed_redirect_host(host)?;
    if path.is_empty() {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "HTTPS URL path rejected",
        ));
    }
    Ok(host)
}

fn validate_required_texts(values: &[&str]) -> Result<(), ArtifactTrustError> {
    if values.iter().any(|value| {
        value.trim().is_empty() || value.len() > 256 || value.chars().any(char::is_control)
    }) {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "required catalog field rejected",
        ));
    }
    Ok(())
}

fn validate_artifact_id(value: &str) -> Result<(), ArtifactTrustError> {
    if value.len() < 3
        || value.len() > 96
        || !value
            .bytes()
            .next()
            .is_some_and(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit())
        || value.bytes().any(|byte| {
            !(byte.is_ascii_lowercase()
                || byte.is_ascii_digit()
                || matches!(byte, b'.' | b'_' | b'-'))
        })
    {
        return Err(ArtifactTrustError::new(
            "invalid_artifact_id",
            "artifact id rejected",
        ));
    }
    Ok(())
}

fn validate_sha256(value: &str) -> Result<(), ArtifactTrustError> {
    if value.len() != 64
        || value
            .bytes()
            .any(|byte| !(byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte)))
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "SHA-256 rejected",
        ));
    }
    Ok(())
}

fn validate_filename(value: &str) -> Result<(), ArtifactTrustError> {
    validate_relative_windows_path(value)?;
    if value.contains('/')
        || !value
            .bytes()
            .next()
            .is_some_and(|byte| byte.is_ascii_alphanumeric())
    {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "artifact filename rejected",
        ));
    }
    Ok(())
}

fn validate_relative_windows_path(value: &str) -> Result<(), ArtifactTrustError> {
    if value.is_empty()
        || value.len() > 240
        || value.starts_with('/')
        || value.starts_with('\\')
        || value.contains('\\')
        || value.contains(':')
        || value.contains('\0')
        || value.ends_with('/')
        || value.bytes().any(|byte| {
            !(byte.is_ascii_alphanumeric() || matches!(byte, b'/' | b'.' | b'_' | b'+' | b'-'))
        })
    {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "managed relative path rejected",
        ));
    }
    let reserved = [
        "con", "prn", "aux", "nul", "clock$", "com1", "com2", "com3", "com4", "com5", "com6",
        "com7", "com8", "com9", "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8",
        "lpt9",
    ];
    for segment in value.split('/') {
        let lowered = segment.to_ascii_lowercase();
        let stem = lowered.split('.').next().unwrap_or("");
        if segment.is_empty()
            || segment == "."
            || segment == ".."
            || segment.ends_with([' ', '.'])
            || reserved.contains(&stem)
        {
            return Err(ArtifactTrustError::new(
                "invalid_path",
                "managed path segment rejected",
            ));
        }
    }
    Ok(())
}

fn ensure_sorted_unique<'a>(
    values: impl Iterator<Item = &'a str>,
) -> Result<(), ArtifactTrustError> {
    let mut previous = None::<&str>;
    for value in values {
        if previous.is_some_and(|prior| prior >= value) {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "catalog IDs not sorted or unique",
            ));
        }
        previous = Some(value);
    }
    Ok(())
}

fn insert_filename(
    filenames: &mut BTreeMap<String, String>,
    filename: &str,
    relative_path: &str,
) -> Result<(), ArtifactTrustError> {
    let key = filename.to_ascii_lowercase();
    if let Some(existing) = filenames.insert(key, relative_path.to_ascii_lowercase()) {
        if existing != relative_path.to_ascii_lowercase() {
            return Err(ArtifactTrustError::new(
                "invalid_catalog",
                "conflicting artifact filename",
            ));
        }
    }
    Ok(())
}

fn insert_disjoint_managed_path(
    locations: &mut BTreeSet<String>,
    relative_path: &str,
) -> Result<(), ArtifactTrustError> {
    let folded = relative_path.to_ascii_lowercase();
    let nested_prefix = format!("{folded}/");
    if locations.iter().any(|existing| {
        existing == &folded
            || existing.starts_with(&nested_prefix)
            || folded.starts_with(&format!("{existing}/"))
    }) {
        return Err(ArtifactTrustError::new(
            "invalid_catalog",
            "managed artifact paths overlap",
        ));
    }
    locations.insert(folded);
    Ok(())
}

pub(crate) fn resolve_contained(
    root: &Path,
    relative: &str,
) -> Result<PathBuf, ArtifactTrustError> {
    validate_relative_windows_path(relative)?;
    let mut path = root.to_path_buf();
    for segment in relative.split('/') {
        path.push(segment);
    }
    if !path.starts_with(root) {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "managed path containment failed",
        ));
    }
    Ok(path)
}

fn ensure_existing_safe_path(
    trust_root: &Path,
    root: &Path,
    path: &Path,
    directory: bool,
) -> Result<(), ArtifactTrustError> {
    if !path.starts_with(root) {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "managed path escaped root",
        ));
    }
    let metadata = path
        .metadata()
        .map_err(|_| ArtifactTrustError::new("invalid_path", "managed path unavailable"))?;
    if (directory && !metadata.is_dir()) || (!directory && !metadata.is_file()) {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "managed path type rejected",
        ));
    }
    reject_reparse_chain(trust_root, path)?;
    let canonical_root = root
        .canonicalize()
        .map_err(|_| ArtifactTrustError::new("invalid_path", "managed root unavailable"))?;
    let canonical_path = path
        .canonicalize()
        .map_err(|_| ArtifactTrustError::new("invalid_path", "managed path unavailable"))?;
    if !canonical_path.starts_with(&canonical_root) {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "managed path canonical escape",
        ));
    }
    Ok(())
}

fn reject_unlisted_runtime_files(
    package_dir: &Path,
    listed: &BTreeSet<String>,
) -> Result<(), ArtifactTrustError> {
    let mut stack = vec![package_dir.to_path_buf()];
    let mut visited = 0_usize;
    while let Some(directory) = stack.pop() {
        for entry in fs::read_dir(&directory)
            .map_err(|_| ArtifactTrustError::new("io_error", "runtime package unreadable"))?
        {
            let entry =
                entry.map_err(|_| ArtifactTrustError::new("io_error", "runtime scan failed"))?;
            visited += 1;
            if visited > 256 {
                return Err(ArtifactTrustError::new(
                    "invalid_runtime",
                    "runtime package entry limit exceeded",
                ));
            }
            let path = entry.path();
            reject_reparse_point(&path)?;
            let file_type = entry
                .file_type()
                .map_err(|_| ArtifactTrustError::new("io_error", "runtime entry unreadable"))?;
            if file_type.is_dir() {
                let relative = path
                    .strip_prefix(package_dir)
                    .map_err(|_| ArtifactTrustError::new("invalid_path", "runtime path escaped"))?
                    .to_string_lossy()
                    .replace('\\', "/")
                    .to_ascii_lowercase();
                let prefix = format!("{relative}/");
                if !listed.iter().any(|item| item.starts_with(&prefix)) {
                    return Err(ArtifactTrustError::new(
                        "unexpected_file",
                        "unapproved runtime directory",
                    ));
                }
                stack.push(path);
                continue;
            }
            let relative = path
                .strip_prefix(package_dir)
                .map_err(|_| ArtifactTrustError::new("invalid_path", "runtime path escaped"))?
                .to_string_lossy()
                .replace('\\', "/")
                .to_ascii_lowercase();
            if !file_type.is_file() || !listed.contains(&relative) {
                return Err(ArtifactTrustError::new(
                    "unexpected_file",
                    "unapproved runtime file",
                ));
            }
        }
    }
    Ok(())
}

fn reject_reparse_chain(root: &Path, path: &Path) -> Result<(), ArtifactTrustError> {
    let relative = path
        .strip_prefix(root)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "managed path escaped root"))?;
    reject_reparse_point(root)?;
    let mut current = root.to_path_buf();
    for component in relative.components() {
        current.push(component.as_os_str());
        reject_reparse_point(&current)?;
    }
    Ok(())
}

fn open_directory_guard_chain(
    root: &Path,
    target: &Path,
    create_missing: bool,
) -> Result<Vec<File>, ArtifactTrustError> {
    let relative = target
        .strip_prefix(root)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "managed directory escaped root"))?;
    let root_metadata = fs::symlink_metadata(root)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "app data root unavailable"))?;
    if !root_metadata.is_dir() {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "app data root type rejected",
        ));
    }
    reject_reparse_point(root)?;
    let mut handles = vec![open_directory_guard(root)?];
    let mut current = root.to_path_buf();
    for component in relative.components() {
        current.push(component.as_os_str());
        match fs::symlink_metadata(&current) {
            Ok(metadata) => {
                if !metadata.is_dir() {
                    return Err(ArtifactTrustError::new(
                        "invalid_path",
                        "managed directory type rejected",
                    ));
                }
            }
            Err(error) if error.kind() == std::io::ErrorKind::NotFound && create_missing => {
                if let Err(create_error) = fs::create_dir(&current) {
                    if create_error.kind() != std::io::ErrorKind::AlreadyExists {
                        return Err(ArtifactTrustError::new(
                            "io_error",
                            "managed directory creation failed",
                        ));
                    }
                }
                let metadata = fs::symlink_metadata(&current).map_err(|_| {
                    ArtifactTrustError::new("invalid_path", "managed directory unavailable")
                })?;
                if !metadata.is_dir() {
                    return Err(ArtifactTrustError::new(
                        "invalid_path",
                        "managed directory type rejected",
                    ));
                }
            }
            Err(_) => {
                return Err(ArtifactTrustError::new(
                    "invalid_path",
                    "managed directory unavailable",
                ))
            }
        }
        reject_reparse_point(&current)?;
        handles.push(open_directory_guard(&current)?);
    }
    Ok(handles)
}

#[cfg(windows)]
fn reject_reparse_point(path: &Path) -> Result<(), ArtifactTrustError> {
    const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
    let metadata = fs::symlink_metadata(path)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "path metadata unavailable"))?;
    if metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "reparse point rejected",
        ));
    }
    Ok(())
}

#[cfg(not(windows))]
fn reject_reparse_point(path: &Path) -> Result<(), ArtifactTrustError> {
    let metadata = fs::symlink_metadata(path)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "path metadata unavailable"))?;
    if metadata.file_type().is_symlink() {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "symbolic link rejected",
        ));
    }
    Ok(())
}

#[cfg(windows)]
fn open_model_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    const GENERIC_READ: u32 = 0x8000_0000;
    const FILE_SHARE_READ: u32 = 0x0000_0001;
    OpenOptions::new()
        .read(true)
        .access_mode(GENERIC_READ)
        .share_mode(FILE_SHARE_READ)
        .open(path)
        .map_err(|_| ArtifactTrustError::new("model_locked", "model identity guard failed"))
}

#[cfg(windows)]
fn open_runtime_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    const GENERIC_READ: u32 = 0x8000_0000;
    const FILE_SHARE_READ: u32 = 0x0000_0001;
    OpenOptions::new()
        .read(true)
        .access_mode(GENERIC_READ)
        .share_mode(FILE_SHARE_READ)
        .open(path)
        .map_err(|_| ArtifactTrustError::new("runtime_locked", "runtime identity guard failed"))
}

#[cfg(windows)]
fn open_directory_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    let wide: Vec<u16> = path
        .as_os_str()
        .encode_wide()
        .chain(std::iter::once(0))
        .collect();
    let handle = unsafe {
        CreateFileW(
            wide.as_ptr(),
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            std::ptr::null(),
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
            std::ptr::null_mut(),
        )
    };
    if handle.is_null() || handle == INVALID_HANDLE_VALUE {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "directory identity guard failed",
        ));
    }
    let file = unsafe { File::from_raw_handle(handle.cast()) };
    const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
    let metadata = file
        .metadata()
        .map_err(|_| ArtifactTrustError::new("invalid_path", "directory metadata unavailable"))?;
    if !metadata.is_dir() || metadata.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "directory identity rejected",
        ));
    }
    Ok(file)
}

#[cfg(not(windows))]
fn open_model_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    File::open(path)
        .map_err(|_| ArtifactTrustError::new("model_locked", "model identity guard failed"))
}

#[cfg(not(windows))]
fn open_runtime_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    File::open(path)
        .map_err(|_| ArtifactTrustError::new("runtime_locked", "runtime identity guard failed"))
}

#[cfg(not(windows))]
fn open_directory_guard(path: &Path) -> Result<File, ArtifactTrustError> {
    reject_reparse_point(path)?;
    let file = File::open(path)
        .map_err(|_| ArtifactTrustError::new("invalid_path", "directory identity guard failed"))?;
    if !file
        .metadata()
        .map_err(|_| ArtifactTrustError::new("invalid_path", "directory metadata unavailable"))?
        .is_dir()
    {
        return Err(ArtifactTrustError::new(
            "invalid_path",
            "directory identity rejected",
        ));
    }
    Ok(file)
}

fn sha256_file(path: &Path) -> Result<String, ArtifactTrustError> {
    let start = std::time::Instant::now();
    let file = File::open(path)
        .map_err(|_| ArtifactTrustError::new("io_error", "hash input unavailable"))?;
    let mut reader = BufReader::with_capacity(1024 * 1024, file);
    let mut hasher = Sha256::new();
    let mut buffer = vec![0_u8; 1024 * 1024];
    loop {
        let count = reader
            .read(&mut buffer)
            .map_err(|_| ArtifactTrustError::new("io_error", "hash read failed"))?;
        if count == 0 {
            break;
        }
        hasher.update(&buffer[..count]);
    }
    let result = format!("{:x}", hasher.finalize());
    let dur_ms = start.elapsed().as_millis();
    if perf_logging_enabled() {
        eprintln!("[PERF] sha256_file path={} dur_ms={dur_ms}", path.display());
    }
    Ok(result)
}

fn sha256_bytes(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

pub(crate) fn perf_logging_enabled() -> bool {
    perf_logging_enabled_from(std::env::var("LOCALCOMET_PERF").ok().as_deref())
}

fn perf_logging_enabled_from(value: Option<&str>) -> bool {
    value == Some("1")
}

fn now_unix_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis() as u64)
        .unwrap_or(0)
}

struct UniqueValue(Value);

impl<'de> Deserialize<'de> for UniqueValue {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        deserializer.deserialize_any(UniqueValueVisitor)
    }
}

struct UniqueValueVisitor;

impl<'de> Visitor<'de> for UniqueValueVisitor {
    type Value = UniqueValue;

    fn expecting(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("a duplicate-free JSON value")
    }

    fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::Bool(value)))
    }

    fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::Number(value.into())))
    }

    fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::Number(value.into())))
    }

    fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
    where
        E: serde::de::Error,
    {
        serde_json::Number::from_f64(value)
            .map(Value::Number)
            .map(UniqueValue)
            .ok_or_else(|| E::custom("invalid number"))
    }

    fn visit_str<E>(self, value: &str) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::String(value.to_string())))
    }

    fn visit_string<E>(self, value: String) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::String(value)))
    }

    fn visit_none<E>(self) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::Null))
    }

    fn visit_unit<E>(self) -> Result<Self::Value, E> {
        Ok(UniqueValue(Value::Null))
    }

    fn visit_some<D>(self, deserializer: D) -> Result<Self::Value, D::Error>
    where
        D: Deserializer<'de>,
    {
        UniqueValue::deserialize(deserializer)
    }

    fn visit_seq<A>(self, mut sequence: A) -> Result<Self::Value, A::Error>
    where
        A: SeqAccess<'de>,
    {
        let mut values = Vec::new();
        while let Some(value) = sequence.next_element::<UniqueValue>()? {
            values.push(value.0);
        }
        Ok(UniqueValue(Value::Array(values)))
    }

    fn visit_map<A>(self, mut map: A) -> Result<Self::Value, A::Error>
    where
        A: MapAccess<'de>,
    {
        let mut values = serde_json::Map::new();
        while let Some((key, value)) = map.next_entry::<String, UniqueValue>()? {
            if values.insert(key, value.0).is_some() {
                return Err(serde::de::Error::custom("duplicate JSON key"));
            }
        }
        Ok(UniqueValue(Value::Object(values)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU64, Ordering};

    const TEST_RUNTIME_BYTES: &[u8] = b"test-runtime";
    const TEST_MODEL_BYTES: &[u8] = b"GGUFtest-model";

    static TEST_SEQUENCE: AtomicU64 = AtomicU64::new(0);

    #[test]
    fn perf_logging_gates_on_localcomet_perf_flag() {
        assert!(perf_logging_enabled_from(Some("1")));
        assert!(!perf_logging_enabled_from(Some("0")));
        assert!(!perf_logging_enabled_from(None));
        assert!(!perf_logging_enabled_from(Some("true")));
        assert!(!perf_logging_enabled_from(Some("")));
        assert!(!perf_logging_enabled_from(Some("11")));
    }

    struct TestWorkspace {
        root: PathBuf,
    }

    impl TestWorkspace {
        fn new() -> Self {
            let sequence = TEST_SEQUENCE.fetch_add(1, Ordering::Relaxed);
            let root = std::env::temp_dir().join(format!(
                "localcomet-artifact-trust-{}-{}-{sequence}",
                std::process::id(),
                now_unix_ms()
            ));
            fs::create_dir_all(&root).expect("create test workspace");
            Self { root }
        }

        fn roots(&self) -> ManagedArtifactRoots {
            ManagedArtifactRoots {
                app_data_root: self.root.clone(),
                runtime_root: self.root.join("runtimes"),
                model_root: self.root.join("models"),
                state_root: self.root.join("state"),
            }
        }
    }

    impl Drop for TestWorkspace {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.root);
        }
    }

    fn test_runtime(runtime_id: &str, managed_path: &str) -> ApprovedRuntimeArtifact {
        ApprovedRuntimeArtifact {
            runtime_id: runtime_id.into(),
            provider: "test-provider".into(),
            release_tag: "b1".into(),
            platform: "windows".into(),
            architecture: "x86-64".into(),
            variant: "cpu".into(),
            upstream_repository: "test/runtime".into(),
            upstream_revision: "1111111111111111111111111111111111111111".into(),
            asset_filename: format!("{runtime_id}.zip"),
            asset_bytes: 7,
            asset_sha256: sha256_bytes(b"archive"),
            acquisition: ApprovedArtifactAcquisition {
                artifact_id: runtime_id.into(),
                artifact_kind: AcquisitionArtifactKind::Runtime,
                source_type: AcquisitionSourceType::ApprovedHttps,
                primary_url: format!("https://example.test/{runtime_id}.zip"),
                allowed_redirect_hosts: vec!["example.test".into()],
                expected_filename: format!("{runtime_id}.zip"),
                expected_bytes: 7,
                expected_sha256: sha256_bytes(b"archive"),
                content_type: Some("application/octet-stream".into()),
                managed_relative_destination: managed_path.into(),
                public_distribution: false,
                installer_bundled: false,
                automatic_download: false,
                user_confirmation_required: true,
            },
            archive_format: "zip".into(),
            managed_relative_path: managed_path.into(),
            executable_relative_path: "llama-server.exe".into(),
            archive_members: vec![ApprovedRuntimeArchiveMember {
                relative_path: "llama-server.exe".into(),
                disposition: RuntimeArchiveMemberDisposition::Install,
            }],
            required_files: vec![ApprovedRuntimeFile {
                relative_path: "llama-server.exe".into(),
                bytes: TEST_RUNTIME_BYTES.len() as u64,
                sha256: sha256_bytes(TEST_RUNTIME_BYTES),
            }],
            license_asset: ApprovedRuntimeLicenseAsset {
                source_relative_path: LLAMA_CPP_LICENSE_SOURCE_PATH.into(),
                destination_relative_path: "LICENSE-MIT.txt".into(),
                bytes: LLAMA_CPP_LICENSE_BYTES.len() as u64,
                sha256: sha256_bytes(LLAMA_CPP_LICENSE_BYTES),
            },
            permitted_bind_scope: "loopback-only".into(),
            supported_api_protocol: "openai-compatible-v1".into(),
            license_id: "MIT".into(),
            public_distribution: false,
            status: CatalogStatus::ApprovedInternalBootstrap,
        }
    }

    fn test_model(compatible_runtime_ids: Vec<String>) -> ApprovedModelArtifact {
        ApprovedModelArtifact {
            model_id: "test-model".into(),
            provider: "test-provider".into(),
            family: "test-family".into(),
            display_name: "Test model".into(),
            format: "GGUF".into(),
            quantization: "Q4_K_M".into(),
            upstream_repository: "test/model".into(),
            upstream_revision: "2222222222222222222222222222222222222222".into(),
            asset_filename: "test-model.gguf".into(),
            asset_bytes: TEST_MODEL_BYTES.len() as u64,
            asset_sha256: sha256_bytes(TEST_MODEL_BYTES),
            acquisition: ApprovedArtifactAcquisition {
                artifact_id: "test-model".into(),
                artifact_kind: AcquisitionArtifactKind::Model,
                source_type: AcquisitionSourceType::ApprovedHttps,
                primary_url: "https://example.test/test-model.gguf".into(),
                allowed_redirect_hosts: vec!["example.test".into()],
                expected_filename: "test-model.gguf".into(),
                expected_bytes: TEST_MODEL_BYTES.len() as u64,
                expected_sha256: sha256_bytes(TEST_MODEL_BYTES),
                content_type: Some("application/octet-stream".into()),
                managed_relative_destination: "test-model/test-model.gguf".into(),
                public_distribution: false,
                installer_bundled: false,
                automatic_download: false,
                user_confirmation_required: true,
            },
            license_id: "Apache-2.0".into(),
            compatible_runtime_ids,
            managed_relative_path: "test-model/test-model.gguf".into(),
            public_distribution: false,
            installer_bundled: false,
            bootstrap_purpose: INTERNAL_BOOTSTRAP_PURPOSE.into(),
            status: CatalogStatus::ApprovedInternalBootstrap,
        }
    }

    fn test_catalog() -> ApprovedArtifactCatalog {
        ApprovedArtifactCatalog {
            schema_version: SCHEMA_VERSION,
            catalog_id: CATALOG_ID.into(),
            catalog_version: "1.0.0-test".into(),
            runtimes: vec![test_runtime("test-runtime", "test-runtime")],
            models: vec![test_model(vec!["test-runtime".into()])],
        }
    }

    fn canonical_bytes(catalog: &ApprovedArtifactCatalog) -> Vec<u8> {
        let mut text = serde_json::to_string_pretty(catalog).expect("serialize test catalog");
        text.push('\n');
        text.into_bytes()
    }

    fn embedded_catalog_lf_bytes() -> Vec<u8> {
        let catalog = parse_catalog(CATALOG_BYTES).expect("parse embedded catalog fixture");
        canonical_bytes(&catalog)
    }

    fn with_crlf_line_endings(lf: &[u8]) -> Vec<u8> {
        let mut crlf =
            Vec::with_capacity(lf.len() + lf.iter().filter(|byte| **byte == b'\n').count());
        for byte in lf {
            if *byte == b'\n' {
                crlf.push(b'\r');
            }
            crlf.push(*byte);
        }
        crlf
    }

    fn service_for(
        catalog: &ApprovedArtifactCatalog,
        workspace: &TestWorkspace,
    ) -> ArtifactTrustService {
        ArtifactTrustService::from_catalog_bytes(&canonical_bytes(catalog), workspace.roots())
            .expect("valid test catalog")
    }

    fn install_runtime(
        workspace: &TestWorkspace,
        runtime: &ApprovedRuntimeArtifact,
        bytes: &[u8],
    ) -> PathBuf {
        let package = workspace
            .roots()
            .runtime_root
            .join(&runtime.managed_relative_path);
        fs::create_dir_all(&package).expect("create runtime package");
        let executable = package.join(&runtime.executable_relative_path);
        fs::write(&executable, bytes).expect("write runtime fixture");
        let license_bytes = source_controlled_runtime_license_bytes(&runtime.license_asset)
            .expect("test runtime license asset");
        fs::write(
            package.join(&runtime.license_asset.destination_relative_path),
            license_bytes,
        )
        .expect("write runtime license fixture");
        executable
    }

    fn install_model(
        workspace: &TestWorkspace,
        model: &ApprovedModelArtifact,
        bytes: &[u8],
    ) -> PathBuf {
        let path = workspace
            .roots()
            .model_root
            .join(model.managed_relative_path.split('/').collect::<PathBuf>());
        fs::create_dir_all(path.parent().expect("model parent")).expect("create model directory");
        fs::write(&path, bytes).expect("write model fixture");
        path
    }

    #[test]
    fn application_data_root_anchors_runtime_model_state_and_acquisition_paths() {
        let workspace = TestWorkspace::new();
        let application_root = workspace.root.join("isolated-profile").join("LocalComet");
        fs::create_dir_all(&application_root).expect("create isolated application root");
        let catalog = test_catalog();
        let service = ArtifactTrustService::from_catalog_bytes(
            &canonical_bytes(&catalog),
            ManagedArtifactRoots::from_application_data_root(&application_root),
        )
        .expect("create isolated trust service");
        let runtime = service
            .approved_download_artifact("test-runtime")
            .expect("approved runtime");
        let model = service
            .approved_download_artifact("test-model")
            .expect("approved model");

        assert_eq!(service.roots().app_data_root, application_root);
        assert_eq!(
            service.roots().runtime_root,
            service
                .roots()
                .app_data_root
                .join("runtimes")
                .join("llama.cpp")
        );
        assert_eq!(
            service.roots().model_root,
            service.roots().app_data_root.join("models")
        );
        assert_eq!(
            service.roots().state_root,
            service.roots().app_data_root.join("runtime-state")
        );
        assert_eq!(
            service.acquisition_root().expect("acquisition root"),
            service.roots().app_data_root.join("acquisition")
        );
        assert_eq!(
            service
                .acquisition_event_log_path()
                .expect("acquisition diagnostic log path"),
            service
                .roots()
                .app_data_root
                .join("logs")
                .join("acquisition-events.jsonl")
        );
        assert!(service
            .download_destination(&runtime)
            .expect("runtime destination")
            .starts_with(&service.roots().app_data_root));
        assert!(service
            .download_destination(&model)
            .expect("model destination")
            .starts_with(&service.roots().app_data_root));
    }

    #[test]
    fn isolated_model_root_neither_discovers_nor_targets_a_default_profile_model() {
        let workspace = TestWorkspace::new();
        let default_root = workspace.root.join("default-profile").join("LocalComet");
        let isolated_root = workspace.root.join("isolated-profile").join("LocalComet");
        let catalog = test_catalog();
        let default_model = default_root
            .join("models")
            .join("test-model")
            .join("test-model.gguf");
        fs::create_dir_all(default_model.parent().expect("default model parent"))
            .expect("create default model parent");
        fs::write(&default_model, TEST_MODEL_BYTES).expect("write default model fixture");
        fs::create_dir_all(&isolated_root).expect("create isolated root");
        let service = ArtifactTrustService::from_catalog_bytes(
            &canonical_bytes(&catalog),
            ManagedArtifactRoots::from_application_data_root(&isolated_root),
        )
        .expect("create isolated trust service");
        let model = service
            .approved_download_artifact("test-model")
            .expect("approved model");
        let removal_destination = service
            .download_destination(&model)
            .expect("removal destination");

        assert_eq!(
            service
                .artifact_validation_status("test-model")
                .expect("model validation")
                .installation_status,
            InstallationStatus::NotInstalled
        );
        assert!(default_model.is_file());
        assert_eq!(
            removal_destination,
            isolated_root
                .join("models")
                .join("test-model")
                .join("test-model.gguf")
        );
        assert!(!removal_destination.starts_with(&default_root));
    }

    fn assert_catalog_invalid(catalog: &ApprovedArtifactCatalog) {
        assert!(validate_catalog(catalog).is_err());
    }

    #[test]
    fn embedded_catalog_is_canonical_and_exactly_pinned() {
        let workspace = TestWorkspace::new();
        let catalog_bytes =
            canonical_embedded_catalog_bytes().expect("embedded catalog identity must be valid");
        let service =
            ArtifactTrustService::from_catalog_bytes(catalog_bytes.as_ref(), workspace.roots())
                .expect("embedded catalog must be valid");
        assert_eq!(
            sha256_bytes(catalog_bytes.as_ref()),
            EMBEDDED_CATALOG_SHA256
        );
        assert_eq!(service.catalog.runtimes.len(), 1);
        assert_eq!(service.catalog.models.len(), 1);

        let runtime = &service.catalog.runtimes[0];
        assert_eq!(runtime.runtime_id, "llama-cpp-windows-x86-64-cpu-bootstrap");
        assert_eq!(runtime.release_tag, "b10068");
        assert_eq!(
            runtime.upstream_revision,
            "571d0d540df04f25298d0e159e520d9fc62ed121"
        );
        assert_eq!(runtime.asset_bytes, 18_007_324);
        assert_eq!(
            runtime.asset_sha256,
            "01d5f30876acfb4a0be59396710f450213495c7181d8fbcce2fad045835ceb89"
        );
        assert_eq!(runtime.archive_members.len(), 51);
        assert_eq!(
            runtime
                .archive_members
                .iter()
                .filter(|member| member.disposition == RuntimeArchiveMemberDisposition::Install)
                .count(),
            30
        );
        assert_eq!(runtime.required_files.len(), 30);
        assert_eq!(
            runtime.license_asset.source_relative_path,
            "third_party/llama.cpp/LICENSE-MIT.txt"
        );
        assert_eq!(
            runtime.license_asset.destination_relative_path,
            "LICENSE-MIT.txt"
        );
        assert_eq!(runtime.license_asset.bytes, 1_078);
        assert_eq!(
            runtime.license_asset.sha256,
            "94f29bbed6a22c35b992c5c6ebf0e7c92f13b836b90f36f461c9cf2f0f1d010d"
        );

        let model = &service.catalog.models[0];
        assert_eq!(model.model_id, "qwen2.5-1.5b-instruct-q4-k-m");
        assert_eq!(
            model.upstream_revision,
            "91cad51170dc346986eccefdc2dd33a9da36ead9"
        );
        assert_eq!(model.asset_filename, "qwen2.5-1.5b-instruct-q4_k_m.gguf");
        assert_eq!(model.asset_bytes, 1_117_320_736);
        assert_eq!(
            model.asset_sha256,
            "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
        );
        assert_eq!(
            model.acquisition.primary_url,
            "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf"
        );
        assert_eq!(
            model.acquisition.expected_filename,
            "qwen2.5-1.5b-instruct-q4_k_m.gguf"
        );
        assert_eq!(model.acquisition.expected_bytes, 1_117_320_736);
        assert_eq!(
            model.acquisition.expected_sha256,
            "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e"
        );
        let model_hosts: Vec<&str> = model
            .acquisition
            .allowed_redirect_hosts
            .iter()
            .map(String::as_str)
            .collect();
        assert_eq!(
            model_hosts,
            vec![
                "cas-bridge.xethub.hf.co",
                "cdn-lfs-us-1.hf.co",
                "cdn-lfs.hf.co",
                "huggingface.co",
                "transfer.xethub.hf.co",
                "us.aws.cdn.hf.co",
            ]
        );
        assert!(!runtime
            .acquisition
            .allowed_redirect_hosts
            .iter()
            .any(|host| host == "us.aws.cdn.hf.co"));
    }

    #[test]
    fn synthetic_lf_and_crlf_catalogs_normalize_to_the_same_pinned_bytes() {
        let workspace = TestWorkspace::new();
        let lf = embedded_catalog_lf_bytes();
        let normalized_lf =
            normalize_catalog_line_endings(&lf).expect("canonical LF must be accepted unchanged");
        assert!(matches!(normalized_lf, Cow::Borrowed(_)));
        assert_eq!(normalized_lf.as_ref(), lf.as_slice());
        let pinned_lf = canonical_catalog_bytes(&lf).expect("canonical LF must match the pin");
        ArtifactTrustService::from_catalog_bytes(pinned_lf.as_ref(), workspace.roots())
            .expect("LF catalog must retain schema and canonical validation");

        let crlf = with_crlf_line_endings(&lf);
        assert!(crlf.windows(2).any(|pair| pair == b"\r\n"));
        let normalized_crlf = normalize_catalog_line_endings(&crlf)
            .expect("synthetic CRLF must execute the normalization branch");
        assert!(matches!(normalized_crlf, Cow::Owned(_)));
        assert_eq!(normalized_crlf.as_ref(), lf.as_slice());
        let pinned_crlf =
            canonical_catalog_bytes(&crlf).expect("equivalent CRLF must match the LF pin");
        assert_eq!(sha256_bytes(pinned_crlf.as_ref()), EMBEDDED_CATALOG_SHA256);
        ArtifactTrustService::from_catalog_bytes(pinned_crlf.as_ref(), workspace.roots())
            .expect("normalized CRLF catalog must retain schema and canonical validation");
    }

    #[test]
    fn catalog_line_endings_reject_bare_cr_and_mixed_invalid_input() {
        let lf = embedded_catalog_lf_bytes();
        let first_lf = lf
            .iter()
            .position(|byte| *byte == b'\n')
            .expect("catalog contains line endings");
        let mut bare_cr = lf.clone();
        bare_cr[first_lf] = b'\r';
        assert!(normalize_catalog_line_endings(&bare_cr).is_err());
        assert!(canonical_catalog_bytes(&bare_cr).is_err());

        let mut mixed = with_crlf_line_endings(&lf);
        let last_cr = mixed
            .iter()
            .rposition(|byte| *byte == b'\r')
            .expect("CRLF fixture contains CR");
        mixed.remove(last_cr + 1);
        assert!(mixed.windows(2).any(|pair| pair == b"\r\n"));
        assert!(mixed.contains(&b'\r'));
        assert!(normalize_catalog_line_endings(&mixed).is_err());
        assert!(canonical_catalog_bytes(&mixed).is_err());
    }

    #[test]
    fn catalog_normalization_cannot_bypass_the_pinned_sha256() {
        let lf = embedded_catalog_lf_bytes();

        let mut one_byte_mutation = lf.clone();
        one_byte_mutation[0] ^= 1;
        assert!(canonical_catalog_bytes(&one_byte_mutation).is_err());

        let mut appended = lf.clone();
        appended.push(b' ');
        assert!(canonical_catalog_bytes(&appended).is_err());

        let mut removed = lf.clone();
        removed.pop();
        assert!(canonical_catalog_bytes(&removed).is_err());

        let mut whitespace_mutation = lf.clone();
        let first_lf = whitespace_mutation
            .iter()
            .position(|byte| *byte == b'\n')
            .expect("catalog contains line endings");
        whitespace_mutation.insert(first_lf, b' ');
        assert!(canonical_catalog_bytes(&whitespace_mutation).is_err());

        let unrelated_crlf = b"{\r\n  \"unrelated\": true\r\n}\r\n";
        let normalized = normalize_catalog_line_endings(unrelated_crlf)
            .expect("well-formed CRLF separators may be normalized");
        assert_eq!(normalized.as_ref(), b"{\n  \"unrelated\": true\n}\n");
        assert!(canonical_catalog_bytes(unrelated_crlf).is_err());
    }

    #[test]
    fn parser_rejects_duplicate_keys_unknown_fields_and_noncanonical_bytes() {
        let duplicate = br#"{"schema_version":1,"schema_version":1}"#;
        assert!(parse_catalog(duplicate).is_err());

        let mut value = serde_json::to_value(test_catalog()).expect("catalog value");
        value
            .as_object_mut()
            .expect("catalog object")
            .insert("approval_override".into(), Value::Bool(true));
        assert!(serde_json::from_value::<ApprovedArtifactCatalog>(value).is_err());

        let catalog = test_catalog();
        let compact = serde_json::to_vec(&catalog).expect("compact catalog");
        assert!(validate_canonical_catalog_bytes(&compact, &catalog).is_err());
        let mut crlf = String::from_utf8(canonical_bytes(&catalog)).expect("catalog UTF-8");
        crlf = crlf.replace('\n', "\r\n");
        assert!(validate_canonical_catalog_bytes(crlf.as_bytes(), &catalog).is_err());
        let mut extra_newline = canonical_bytes(&catalog);
        extra_newline.push(b'\n');
        assert!(validate_canonical_catalog_bytes(&extra_newline, &catalog).is_err());
    }

    #[test]
    fn catalog_schema_rejects_all_authority_boundary_violations() {
        let baseline = test_catalog();

        let mut catalog = baseline.clone();
        catalog.schema_version = 2;
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes.push(catalog.runtimes[0].clone());
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models.push(catalog.models[0].clone());
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].runtime_id = "../runtime".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].asset_sha256 = "ABC".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].asset_bytes = 0;
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].managed_relative_path = "C:/runtime".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].executable_relative_path = "../llama-server.exe".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].managed_relative_path = "/model/test-model.gguf".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].provider.clear();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].provider = "   ".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].display_name = "bad\nname".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].asset_filename = "bad?.gguf".into();
        catalog.models[0].managed_relative_path = "test-model/bad?.gguf".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].compatible_runtime_ids = vec!["unknown-runtime".into()];
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        let mut conflicting = catalog.models[0].clone();
        conflicting.model_id = "zzz-model".into();
        conflicting.managed_relative_path = "zzz-model/test-model.gguf".into();
        catalog.models.push(conflicting);
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].architecture = "arm64".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].archive_members.pop();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0]
            .archive_members
            .iter_mut()
            .find(|member| member.relative_path == "llama-server.exe")
            .expect("test launcher envelope member")
            .disposition = RuntimeArchiveMemberDisposition::RecognizedNotInstalled;
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].license_asset.sha256 = "0".repeat(64);
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].public_distribution = true;
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].acquisition.primary_url = "http://example.test/model.gguf".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].acquisition.allowed_redirect_hosts =
            vec!["z.example.test".into(), "a.example.test".into()];
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].acquisition.expected_sha256 = "a".repeat(64);
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.runtimes[0].acquisition.managed_relative_destination = "../runtime".into();
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline.clone();
        catalog.models[0].acquisition.automatic_download = true;
        assert_catalog_invalid(&catalog);

        let mut catalog = baseline;
        catalog.runtimes.clear();
        assert_catalog_invalid(&catalog);
    }

    #[test]
    fn relative_windows_paths_reject_absolute_drive_traversal_and_reserved_forms() {
        for rejected in [
            "C:/model.gguf",
            "C:model.gguf",
            "/model.gguf",
            "\\\\server\\share",
            "../model.gguf",
            "models/../model.gguf",
            "models\\model.gguf",
            "models//model.gguf",
            "models/CON.txt",
            "models/model.gguf.",
        ] {
            assert!(
                validate_relative_windows_path(rejected).is_err(),
                "path should be rejected: {rejected}"
            );
        }
        assert!(validate_relative_windows_path("models/model.gguf").is_ok());
    }

    #[test]
    fn live_inventory_revalidates_exact_bytes_and_ignores_appdata_authority() {
        let workspace = TestWorkspace::new();
        let catalog = test_catalog();
        let runtime_path = install_runtime(&workspace, &catalog.runtimes[0], TEST_RUNTIME_BYTES);
        let model_path = install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
        let service = service_for(&catalog, &workspace);

        let inventory = service.installed_artifacts();
        assert_eq!(inventory.artifacts.len(), 2);
        assert!(inventory
            .artifacts
            .iter()
            .all(|artifact| artifact.installation_status == InstallationStatus::Valid));
        let readiness = service.model_readiness("test-model").expect("readiness");
        assert_eq!(readiness.compatibility, CompatibilityStatus::Compatible);
        assert_eq!(readiness.readiness, ModelReadiness::Ready);
        assert!(readiness.launchable);

        fs::create_dir_all(&workspace.roots().state_root).expect("create state root");
        let hostile_inventory = workspace
            .roots()
            .state_root
            .join("installed-artifacts.v1.json");
        for contents in [
            br#"{not-json"#.as_slice(),
            br#"{"schema_version":1,"catalog_digest":"stale","artifact_id":"unknown-runtime","relative_path":"../../outside","approved":true}"#.as_slice(),
            br#"{"schema_version":1,"catalog_digest":"stale","artifact_id":"unknown-runtime","relative_path":"C:/outside/runtime.exe","hash_bypass":true}"#.as_slice(),
        ] {
            fs::write(&hostile_inventory, contents).expect("write hostile inventory");
            assert!(service
                .artifact_validation_status("unknown-runtime")
                .is_err());
            assert_eq!(service.installed_artifacts().artifacts.len(), 2);
            assert!(service
                .model_readiness("test-model")
                .expect("readiness remains live-derived")
                .launchable);
        }
        fs::write(
            workspace.roots().model_root.join("unapproved.gguf"),
            b"GGUFunapproved",
        )
        .expect("write unapproved model");
        assert!(service
            .artifact_validation_status("unknown-runtime")
            .is_err());
        assert_eq!(service.installed_artifacts().artifacts.len(), 2);

        fs::write(&model_path, b"GGUFtest-mOdel").expect("tamper model");
        let model_status = service
            .artifact_validation_status("test-model")
            .expect("known model status");
        assert_eq!(
            model_status.installation_status,
            InstallationStatus::HashMismatch
        );
        assert!(
            !service
                .model_readiness("test-model")
                .expect("readiness")
                .launchable
        );

        fs::write(&model_path, b"short").expect("truncate model");
        assert_eq!(
            service
                .artifact_validation_status("test-model")
                .expect("known model status")
                .installation_status,
            InstallationStatus::BytesMismatch
        );

        fs::write(&runtime_path, b"test-runtimE").expect("tamper runtime");
        assert_eq!(
            service
                .artifact_validation_status("test-runtime")
                .expect("known runtime status")
                .installation_status,
            InstallationStatus::HashMismatch
        );
    }

    #[test]
    fn runtime_package_rejects_unlisted_files_and_model_rejects_bad_magic() {
        let workspace = TestWorkspace::new();
        let catalog = test_catalog();
        install_runtime(&workspace, &catalog.runtimes[0], TEST_RUNTIME_BYTES);
        let model_path = install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
        let service = service_for(&catalog, &workspace);

        let package = workspace
            .roots()
            .runtime_root
            .join(&catalog.runtimes[0].managed_relative_path);
        fs::write(package.join("unlisted.txt"), b"not approved").expect("write extra file");
        assert_eq!(
            service
                .artifact_validation_status("test-runtime")
                .expect("runtime status")
                .installation_status,
            InstallationStatus::UnexpectedFile
        );

        fs::write(&model_path, b"NOPEtest-model").expect("replace magic");
        assert_eq!(
            service
                .artifact_validation_status("test-model")
                .expect("model status")
                .installation_status,
            InstallationStatus::InvalidFormat
        );
    }

    #[test]
    fn readiness_distinguishes_missing_invalid_and_incompatible_runtime() {
        let workspace = TestWorkspace::new();
        let mut catalog = test_catalog();
        catalog.runtimes = vec![
            test_runtime("aaa-compatible-runtime", "aaa-compatible-runtime"),
            test_runtime("zzz-incompatible-runtime", "zzz-incompatible-runtime"),
        ];
        catalog.models[0].compatible_runtime_ids = vec!["aaa-compatible-runtime".into()];
        install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
        install_runtime(&workspace, &catalog.runtimes[1], TEST_RUNTIME_BYTES);
        let service = service_for(&catalog, &workspace);

        let readiness = service.model_readiness("test-model").expect("readiness");
        assert_eq!(
            readiness.compatibility,
            CompatibilityStatus::IncompatibleRuntimeInstalled
        );
        assert_eq!(readiness.readiness, ModelReadiness::Incompatible);
        assert!(!readiness.launchable);

        install_runtime(&workspace, &catalog.runtimes[0], b"test-runtimE");
        let readiness = service.model_readiness("test-model").expect("readiness");
        assert_eq!(readiness.readiness, ModelReadiness::RuntimeInvalid);
        assert!(!readiness.launchable);
    }

    #[cfg(windows)]
    #[test]
    fn resolved_launch_holds_model_and_runtime_identity_guards() {
        let workspace = TestWorkspace::new();
        let catalog = test_catalog();
        let runtime_path = install_runtime(&workspace, &catalog.runtimes[0], TEST_RUNTIME_BYTES);
        let model_path = install_model(&workspace, &catalog.models[0], TEST_MODEL_BYTES);
        let service = service_for(&catalog, &workspace);
        let launch = service
            .resolve_launch("test-model")
            .expect("resolve launch");
        let package = runtime_path.parent().expect("runtime package");
        let model_parent = model_path.parent().expect("model parent");
        let moved_package = package.with_file_name("moved-runtime");
        let moved_model_parent = model_parent.with_file_name("moved-model");

        assert!(OpenOptions::new().write(true).open(&model_path).is_err());
        assert!(OpenOptions::new().write(true).open(&runtime_path).is_err());
        assert!(fs::rename(package, &moved_package).is_err());
        assert!(fs::rename(model_parent, &moved_model_parent).is_err());
        drop(launch);
        assert!(OpenOptions::new().write(true).open(&model_path).is_ok());
        assert!(OpenOptions::new().write(true).open(&runtime_path).is_ok());
        fs::rename(package, &moved_package).expect("rename unlocked runtime directory");
        fs::rename(&moved_package, package).expect("restore runtime directory");
        fs::rename(model_parent, &moved_model_parent).expect("rename unlocked model directory");
        fs::rename(&moved_model_parent, model_parent).expect("restore model directory");

        let state_handles = service
            .guard_runtime_state_root()
            .expect("guard runtime state root");
        let state_root = workspace.roots().state_root;
        let moved_state = state_root.with_file_name("moved-state");
        assert!(fs::rename(&state_root, &moved_state).is_err());
        drop(state_handles);
        fs::rename(&state_root, &moved_state).expect("rename unlocked state directory");
        fs::rename(&moved_state, &state_root).expect("restore state directory");
    }

    #[cfg(windows)]
    #[test]
    fn app_data_ancestor_reparse_point_is_rejected_when_supported() {
        use std::os::windows::fs::symlink_dir;

        let workspace = TestWorkspace::new();
        let redirected = workspace.root.join("redirected-localcomet");
        fs::create_dir_all(redirected.join("runtimes")).expect("create redirected runtime root");
        fs::create_dir_all(redirected.join("models")).expect("create redirected model root");
        let localcomet_link = workspace.root.join("LocalComet");
        if symlink_dir(&redirected, &localcomet_link).is_err() {
            eprintln!("symbolic-link creation unavailable; lexical containment remains covered");
            return;
        }

        let catalog = test_catalog();
        let roots = ManagedArtifactRoots {
            app_data_root: workspace.root.clone(),
            runtime_root: localcomet_link.join("runtimes"),
            model_root: localcomet_link.join("models"),
            state_root: localcomet_link.join("state"),
        };
        let service = ArtifactTrustService::from_catalog_bytes(&canonical_bytes(&catalog), roots)
            .expect("valid catalog");
        let package = redirected
            .join("runtimes")
            .join(&catalog.runtimes[0].managed_relative_path);
        fs::create_dir_all(&package).expect("create redirected package");
        fs::write(package.join("llama-server.exe"), TEST_RUNTIME_BYTES)
            .expect("write redirected runtime");

        assert_eq!(
            service
                .artifact_validation_status("test-runtime")
                .expect("known runtime")
                .installation_status,
            InstallationStatus::InvalidPath
        );
        fs::remove_dir(&localcomet_link).expect("remove test link");
    }

    #[test]
    #[ignore = "requires the owner-provisioned UP05-WP00 bootstrap artifacts"]
    fn provisioned_bootstrap_is_discovered_only_through_the_catalog() {
        let local_data = std::env::var_os("LOCALAPPDATA").expect("LOCALAPPDATA is required");
        let application_data_root = Path::new(&local_data).join("LocalComet");
        let service = ArtifactTrustService::production(&application_data_root)
            .expect("embedded production catalog");
        assert_eq!(
            service.catalog.runtimes[0].runtime_id,
            "llama-cpp-windows-x86-64-cpu-bootstrap"
        );
        assert_eq!(
            service.catalog.models[0].model_id,
            "qwen2.5-1.5b-instruct-q4-k-m"
        );

        let installed = service.installed_artifacts();
        assert_eq!(installed.artifacts.len(), 2);
        assert!(installed
            .artifacts
            .iter()
            .all(|artifact| artifact.installation_status == InstallationStatus::Valid));
        let readiness = service
            .model_readiness("qwen2.5-1.5b-instruct-q4-k-m")
            .expect("approved model readiness");
        assert_eq!(readiness.compatibility, CompatibilityStatus::Compatible);
        assert_eq!(readiness.readiness, ModelReadiness::Ready);
        assert!(readiness.launchable);
        let launch = service
            .resolve_launch("qwen2.5-1.5b-instruct-q4-k-m")
            .expect("catalog-resolved launch identity");
        assert_eq!(launch.runtime_id, "llama-cpp-windows-x86-64-cpu-bootstrap");
        assert_eq!(launch.model_id, "qwen2.5-1.5b-instruct-q4-k-m");
        drop(launch);
        assert!(service
            .artifact_validation_status("unapproved-runtime")
            .is_err());
    }

    #[test]
    #[ignore = "requires the owner-provisioned UP05-WP00 bootstrap artifacts to be temporarily moved"]
    fn production_bootstrap_absence_is_live_derived() {
        let local_data = std::env::var_os("LOCALAPPDATA").expect("LOCALAPPDATA is required");
        let application_data_root = Path::new(&local_data).join("LocalComet");
        let service = ArtifactTrustService::production(&application_data_root)
            .expect("embedded production catalog");
        let installed = service.installed_artifacts();
        assert_eq!(installed.artifacts.len(), 2);
        assert!(installed.artifacts.iter().all(|artifact| {
            artifact.installation_status == InstallationStatus::NotInstalled
                && artifact.observed_bytes.is_none()
                && artifact.observed_sha256.is_none()
        }));
        let readiness = service
            .model_readiness("qwen2.5-1.5b-instruct-q4-k-m")
            .expect("approved model readiness");
        assert_eq!(readiness.readiness, ModelReadiness::ModelNotInstalled);
        assert!(!readiness.launchable);
        assert!(service
            .resolve_launch("qwen2.5-1.5b-instruct-q4-k-m")
            .is_err());
        assert!(service
            .artifact_validation_status("unapproved-runtime")
            .is_err());
    }
}
````

