# Исследование полностью автономных Computer Use agents — 2026-08-25

Статус: промежуточные проверенные findings для обновления LocalComet roadmap; не являются product acceptance.

## Источники

1. OpenAI, **Computer use | OpenAI API**: https://developers.openai.com/api/docs/guides/tools-computer-use
2. Anthropic, **Computer use tool — Claude Platform Docs**: https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool

## Подтверждённые архитектурные принципы

### 1. Автономность — это bounded agent loop, а не один большой вызов

Оба официальных руководства описывают один и тот же цикл: отправить задачу с Computer Use capability; получить структурированный набор UI actions; выполнить каждый action по порядку; вернуть результат/новый screenshot; повторять, пока модель не перестанет возвращать tool call. Для LocalComet это означает явный state machine `goal → observe → plan/action batch → execute → observe → verify → continue/replan/stop`, а не blind fire-and-forget.

### 2. Harness обязан быть владельцем исполнения

Модель предлагает действия, но приложение/harness выполняет их в контролируемой среде и возвращает результаты. Каждое действие из batch должно быть обработано в порядке; ошибки должны быть возвращены как error result, а не скрываться или превращаться в PASS. LocalComet должен сохранять host broker как authority для launch/navigation и sidecar как bounded dispatcher.

### 3. Нужен screenshot/observation после действий

Официальный OpenAI loop возвращает updated screenshot после выполнения action batch; первый ответ часто является screenshot-first turn. Следовательно, LocalComet должен уметь наблюдать не только перед действием, но и после него, с отдельной postcondition verification. Наличие tool-card или process PID недостаточно.

### 4. Изоляция и минимальные полномочия обязательны даже при автономном режиме

OpenAI рекомендует изолированный browser/VM, предварительно определить разрешённые sites/accounts/actions и считать screenshots, page text, tool outputs, PDFs, emails и chats untrusted input. Anthropic также рекомендует dedicated VM/container с минимальными privileges, не давать доступ к sensitive data и ограничивать internet allowlist-ом.

### 5. Prompt injection — отдельная threat class, а не обычная ошибка модели

Оба источника предупреждают, что инструкции на webpages/images/third-party content могут конфликтовать с user intent и привести модель к ошибочному действию. Anthropic описывает дополнительный classifier defense, но прямо указывает, что precautions remain important. Для LocalComet нужен content provenance/untrusted marker, deny-by-default для instructions found in page content, ограничение доменов и stop/escalate policy.

### 6. Human confirmation нужна для meaningful consequences

Anthropic explicitly приводит accepting cookies, financial transactions, terms of service и другие affirmative-consent действия как случаи, где требуется human confirmation. Полностью автономный режим LocalComet поэтому должен быть автономным только внутри заранее заданного scope; подтверждение/пауза остаются обязательными для опасных или внешне необратимых действий.

## Адаптация к LocalComet

- `ReadOnly`: observe/screenshot/wait и безопасные локальные чтения; могут идти без modal approval, но с обязательным scope и postcondition.
- `Guarded`: launch/type/paste/key/hotkey/folder/file mutation/click/task; допускается session capability только при явном opt-in, correlated request/action IDs и canonical input digest.
- `Dangerous`: delete, external submission, credentials, financial/terms actions; всегда pause + explicit human confirmation, даже в autonomous mode.
- Каждый шаг обязан иметь `step_id`, input digest, authorization context, pre/post observation, terminal state и evidence class.
- Автономность должна быть bounded: max steps, wall-clock budget, retries, cancellation, liveness watchdog, checkpoint/resume и stop on uncertainty.

## Что ещё проверить

Нужно дополнительно прочитать официальные материалы по Operator/Computer-Using Agent, OSWorld benchmark и safety evaluation; затем обновить `todo.md` с уровнями 9,5 и 10/10 и начать реализацию только после согласования threat model с текущими LocalComet invariants.

## Дополнительные проверенные findings

### OpenAI Computer-Using Agent / Operator

Источник: OpenAI, **Computer-Using Agent** — https://openai.com/index/computer-using-agent/

OpenAI описывает layered safety across model, Operator system и post-deployment processes. Для model mistakes применяются user confirmations перед external side effects, ограничения на высокорисковые задачи и watch mode для особенно чувствительных сайтов. Для prompt injection используются cautious navigation, отдельный monitor, который может приостановить выполнение, и detection pipeline. Для LocalComet это усиливает требование: autonomous mode не должен быть одной настройкой «разрешить всё»; нужны отдельные policy layers, domain/action restrictions и pause/escalate на irreversible external effects.

### OSWorld benchmark

Источник: Xie et al., NeurIPS 2024, **OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments** — https://proceedings.neurips.cc/paper_files/paper/2024/hash/5d413e48f84dc61244b6be550f1cd8f5-Abstract-Datasets_and_Benchmarks_Track.html

OSWorld содержит 369 real-world задач с web/desktop apps, OS file I/O и workflow между несколькими приложениями; каждое задание имеет initial state setup и custom execution-based evaluation script. В опубликованной оценке люди достигали более 72,36%, а лучший проверенный агент — 12,24%, главным образом из-за GUI grounding и operational knowledge. Для LocalComet это означает, что «модель смогла нажать кнопку» не является достаточным quality target: нужны reproducible initial state, execution-based postconditions, cross-app workflows и отдельные метрики grounding/recovery.

## Вывод для автономного режима

Полностью автоматический пользовательский опыт должен выглядеть так: пользователь задаёт цель один раз; агент строит bounded plan; перед каждым шагом получает observation; классифицирует внешнее содержимое как untrusted; выполняет только разрешённый action batch; после каждого batch получает новую observation; проверяет postcondition; при неуспехе делает ограниченный replan/retry; при неопределённости, выходе за scope, prompt injection, irreversible side effect, credential/financial/terms action или превышении budget останавливается и запрашивает подтверждение.

Это не означает бесконтрольное управление физическим рабочим столом. В LocalComet автономный режим должен включать execution profile: `hidden_isolated` для разработки/acceptance и `user_desktop` только с явным opt-in, видимым status bar, emergency Stop и более строгими confirmation policies. Автономный режим должен быть bounded по шагам, времени, retries, domains, workspace paths, processes и memory.

## Модель качества для LocalComet

1. **Task success:** independent postcondition, а не `PASS` pill или наличие PID.
2. **Reliability:** idempotent actions, retry budget, checkpoints, cancellation, liveness и recovery.
3. **Grounding:** real UIA/DOM semantic target с scope validation; coordinate-only fallback не даёт verified PASS.
4. **Safety:** layered policy, authorization context, prompt-injection detection/stop, allowlists, secrets isolation и human confirmation for consequential actions.
5. **Evaluation:** representative cross-app workflows with reproducible setup and execution-based assertions; no artificial 1000-case campaign.
6. **Auditability:** step IDs, request/action IDs, canonical input digest, observation hashes, policy decision, terminal verdict и trace без секретов.

## Agent design findings

### Anthropic — Building Effective Agents

Источник: Anthropic Engineering, **Building Effective Agents** — https://www.anthropic.com/engineering/building-effective-agents

Anthropic различает workflows, где LLM и tools соединены заранее заданными code paths, и agents, где LLM динамически направляет процесс и tool usage. Рекомендация — начинать с простейшей архитектуры и добавлять agentic complexity только когда она действительно улучшает outcome. Для agent runtime критичны ground truth от environment на каждом шаге, checkpoints для human feedback/blockers, stopping conditions и maximum iterations. Агент обычно представляет собой LLM с tools в loop, поэтому качество Agent-Computer Interface (ACI), документации tools и evaluation важнее количества abstraction layers.

Полезные паттерны для LocalComet: routing между read-only и guarded/dangerous tools; prompt chaining для фиксированных частей; evaluator/optimizer для проверки результата; orchestrator-workers не нужен для одного desktop worker до доказанной необходимости. В production нужно явно показывать план/текущее действие, сохранять простые composable primitives и не скрывать prompts/responses за framework, который затрудняет debugging.

### OpenAI — ChatGPT agent

Источник: OpenAI, **Introducing ChatGPT agent: bridging research and action** — https://openai.com/index/introducing-chatgpt-agent/

Product-level autonomy сохраняет контроль пользователя: агент показывает, что делает, запрашивает разрешение перед значимыми действиями, позволяет прервать задачу, передать управление браузеру или полностью остановить выполнение. Даже после authentication для действий на внешних сайтах управление возвращается браузеру и требуется user authorization. Для LocalComet это означает, что autonomous profile должен иметь видимый task status, emergency Stop, pause/handoff, approval checkpoint и явное разделение «агент исследует/готовит» и «агент совершает необратимое действие».

## Обновлённая архитектурная рекомендация

LocalComet не следует превращать в unrestricted desktop macro. Лучший target — **bounded autonomous operator**: цель вводится один раз, но execution остаётся контролируемым state machine с policy gates. Структура:

1. **Intent compiler:** переводит пользовательскую цель в typed task plan с action classes, allowed workspace/domain/process scope и expected postconditions.
2. **Planner:** выбирает skills/tools и формирует короткий plan; не получает право сам расширять allowlist.
3. **Observer:** снимает screenshot/UIA/DOM/filesystem observations и маркирует external content как untrusted.
4. **Executor:** выполняет только validated action batch через host broker/sidecar/skill adapter; порядок действий сохраняется.
5. **Verifier:** проверяет независимый postcondition (UIA value, file bytes/hash, URL/readiness, process ownership, screenshot metadata), а не UI pill.
6. **Recovery controller:** допускает ограниченный idempotent retry/replan; после budget exhaustion, scope mismatch или uncertainty останавливается.
7. **Policy gate:** разрешает read-only; при guarded action проверяет session capability/grant; для dangerous/irreversible/external side effect создаёт visible confirmation checkpoint.
8. **Task ledger:** хранит step IDs, inputs/digests, authorisation context, observations, outputs, retry count, reason codes и terminal verdict.
9. **Stop/handoff:** мгновенно отменяет pending work, блокирует stale completions и позволяет человеку взять управление.

## Уровни автономности для LocalComet

| Профиль | Поведение | Применение |
|---|---|---|
| Assist | Агент предлагает plan/action, пользователь подтверждает шаги | Разработка, неизвестные сайты, sensitive data |
| Bounded autonomous | Агент сам выполняет разрешённые read-only/guarded шаги в заранее заданном scope; останавливается на checkpoint | Основной целевой Windows-first режим |
| Supervised autonomous | Как bounded, но с активным наблюдением/возможностью takeover на browser и внешних действиях | Browser forms, login, external side effects |
| Unrestricted | Произвольные действия на физическом desktop без policy/stop/evidence | Не принимать в LocalComet; это небезопасно и не является quality target |

## Definition of Done для 10/10

10/10 нельзя присвоить за demo или количество сценариев. Нужны: representative cross-app tasks с reproducible setup; independent postconditions; stable recovery/cancellation; no false PASS; authorization and prompt-injection controls; bounded resource/process scope; clear UI plan/status/stop; browser/files/UIA/screenshot coverage; reproducible gates; fresh evidence and independent review. Если хотя бы один P0 остаётся unverified, итоговый score должен быть ниже 10/10.

## Security framework findings

### OWASP Top 10 for Agentic Applications 2026

Источник: OWASP GenAI Security Project, **OWASP Top 10 for Agentic Applications for 2026** — https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/

OWASP описывает framework как peer-reviewed operational starting point для автономных систем, которые планируют, действуют и принимают решения в complex workflows. Для LocalComet это подтверждает необходимость threat model не только модели: защищать нужно agent loop, skills/tools, authorization, state, data flows, memory и внешние actions. В roadmap добавляются dedicated threat-model review для excessive agency, tool misuse, privilege/scope escalation, untrusted content, data exfiltration и недостаточной наблюдаемости.

### NIST — Agent hijacking evaluations

Источник: NIST CAISI, **Technical Blog: Strengthening AI Agent Hijacking Evaluations** — https://www.nist.gov/news-events/news/2025/01/technical-blog-strengthening-ai-agent-hijacking-evaluations

NIST определяет agent hijacking как indirect prompt injection, при которой атакующий помещает malicious instructions в данные, которые агент должен обработать, и тем самым заставляет его выполнить нежелательные действия. В рассмотренных сценариях были remote code execution через untrusted URL, массовая exfiltration cloud files и automated phishing. NIST подчёркивает, что evaluation должна быть adaptive: red team attacks нужно разрабатывать под конкретную модель/среду и проверять на held-out tasks, потому что прошлые тесты не гарантируют защиты от новых атак.

Для LocalComet это означает: skills и autonomous loop должны маркировать page/file/email content как data, а не instructions; download/run или send/exfiltration actions должны быть отдельными policy decisions; security regression должен содержать novel injection cases, held-out cases и task-specific metrics, а не только фиксированный список старых strings.

## Обязательные controls, добавленные в roadmap

- typed plan с явными `allowed_processes`, `allowed_domains`, `allowed_paths`, `max_steps`, `time_budget`, `retry_budget` и expected postconditions;
- отдельный untrusted-content channel/marker для browser pages, files, OCR, screenshots, email и tool outputs;
- policy gate перед каждым state-changing action; модель не может сама расширить allowlist или capability;
- interrupt/stop/handoff, который немедленно блокирует stale completions и pending work;
- approval checkpoint для send/submit/delete/install/login/credential/financial/terms actions;
- audit ledger с correlation IDs, action digest, observation hash, policy decision, result и terminal verdict;
- adaptive red-team suite с indirect prompt injection, data exfiltration, RCE/download-run и phishing-like task variants;
- отдельные метрики task success, unsafe-action rate, false-PASS rate, recovery rate, cancellation latency и resource budget compliance.

## LocalComet skills inventory

Проверен `modules/skills/registry.json` и активные manifests. `browser-pilot` — enabled skill с capabilities `browser.open`, `browser.fetch`, `browser.summarize`, но его entrypoint лишь проксирует `modules.browser_direct.BrowserHarness` и поддерживает `open/fetch/screenshot`; это не самостоятельный autonomous Computer Use executor и не заменяет host broker. `workspace-guard` — enabled helper с policy/validate capabilities, но его path checks ограничены простыми fragments и не заменяют canonical path, reparse/symlink и workspace confinement logic. `skills_invoker.py` даёт полезную изоляцию: только enabled skill, manifest permission check, `shell=False`, bounded env, 30-second timeout и bounded stdout/stderr.

Решение: **не импортировать внешний skill вслепую и не использовать Browser Pilot как обход broker**. Переиспользовать его только как optional read/fetch helper после проверки network/untrusted-content boundary; browser launch, hidden desktop binding, URL navigation, UIA grounding и postcondition остаются в native host broker/browser harness. Для folder/file operations использовать native workspace-constrained handlers, а Workspace Guard расширять только после отдельного security review.

## Browser defect confirmed in source

Natural phrase `Открой браузер хром` was recognized by `computer_use_real_actions_ru._resolve_app`, but the deterministic model fallback had no Chrome/Edge/Firefox aliases. This allowed a local model to choose malformed `open_url` without a URL, which then hit the host-only rejection path. The fix adds browser aliases and explicit gateway semantics: browser launch uses `open_app`; `open_url` requires a user-provided full HTTP(S) URL.

The broker also previously named its validator `validate_youtube_url` and accepted only `youtube.com`. It now validates general HTTP(S) URLs while rejecting empty/oversized/whitespace/control-character URLs, credentials, explicit ports, IPv6 literals, non-HTTP(S) schemes and missing hosts. Browser target remains allowlisted (`chrome`, `msedge`, `firefox`), hidden mode still requires the configured isolated profile/CDP port, and navigation remains guarded.


## Fresh official agentic IDE research — 2026-08-27

### OpenAI Codex Windows sandbox

Source: https://openai.com/index/building-codex-windows-sandbox/

OpenAI describes a coding-agent sandbox as an OS-enforced execution boundary whose restrictions propagate through the process tree. The Windows design separates workspace writes from protected paths, uses restricted tokens/identities and explicit process spawning, and treats network suppression as a separate enforcement problem rather than relying on a UI promise. The direct LocalComet implication is that workspace confinement, process ownership, and network policy must be enforced at the host boundary; a model instruction or environment variable alone is not sufficient for a 9/10 claim.

### OpenAI harness engineering

Source: https://openai.com/index/harness-engineering/

The agent-first engineering pattern emphasizes repository-local maps, executable plans, mechanical invariants, observable logs/metrics, isolated app instances, browser/CDP skills, reviewable changes, and feedback loops that make work legible to agents. It explicitly separates product code from the harness/evaluation infrastructure and treats tests, CI, documentation, observability and recovery as part of the product. LocalComet’s roadmap therefore adds repository-local acceptance plans, structural checks, per-run evidence, and no-success-without-postcondition rules.

### Anthropic Claude Code overview

Source: https://docs.anthropic.com/en/docs/claude-code/overview

Claude Code presents a modern coding-agent baseline: repository exploration, multi-file edits, tests/lint, Git integration, skills, hooks, MCP, custom agents, background/scheduled sessions and handoff across surfaces. The relevant LocalComet quality target is not feature-count parity; it is a reviewable end-to-end loop where the agent can inspect a repository, make bounded changes, run verification, report failures and preserve context/recovery without hiding the state transition.

### GitHub Copilot cloud agent

Source: https://docs.github.com/copilot/concepts/agents/cloud-agent/about-cloud-agent

GitHub’s cloud agent baseline includes repository research, implementation planning, branch-scoped changes, tests/linters, iterative review and optional pull requests in an ephemeral development environment. The documentation also states limits: one repository/branch per task and bounded session execution. LocalComet should similarly make task scope, workspace binding, branch identity, execution budget, reviewable diff and terminal evidence explicit rather than implying unlimited autonomy.

### Consequence for current scorecard

The fresh sources reinforce five score-critical requirements: (1) OS/process-tree enforcement, (2) repository-local plan and mechanical invariants, (3) reviewable diff plus test/evidence loop, (4) bounded task scope and interruption/recovery, and (5) explicit distinction between agent/model output and independent environmental postconditions. They do not prove any LocalComet capability; they update the target criteria only.
