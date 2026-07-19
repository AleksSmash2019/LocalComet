# LocalComet v6.84.5 Local Model Gateway

v6.84.5 adds the first bounded text-only local inference path:

```text
Svelte UI -> fixed Tauri commands -> Rust bridge -> framed IPC -> Python sidecar
  -> ProviderAdapter -> HarnessAdapter -> user-operated 127.0.0.1 model server
```

The only provider registry entry is `openai-compatible-local`. The endpoint is constructed internally as `http://127.0.0.1:<PORT>/v1`; the user can provide only a decimal port in the range `1024..65535`. There is no URL field, API key field, custom header field, proxy support, redirect following, DNS, LAN, cloud, HTTPS fallback, cookie support, or credential support.

The harness registry is fixed to `minimal` and `native-localcomet`. `minimal` emits one user message. `native-localcomet` emits one fixed LocalComet system message plus the user message, with no tools, files, project context, attachments, or hidden environment data.

Model discovery is explicit. A binding can be confirmed only for the exact provider, harness, numeric port, and model ID returned by the current discovery result. Bindings are memory-only and are invalidated when the port or discovered model set no longer matches.

Inference is one active text turn globally. Streaming uses bounded SSE parsing, accepts only choice index `0`, accepts only string content deltas, requires `[DONE]` or a bounded accepted finish reason, and fails closed on tool/function markers. Cancellation is idempotent, closes the active HTTP connection, joins the worker within a bounded timeout, and releases the single-active lock.

The frontend contacts only fixed Tauri commands. It never contacts the provider directly.
