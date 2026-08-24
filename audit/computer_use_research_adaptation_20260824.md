# Computer Use research for LocalComet — 2026-08-24

## Sources

1. OpenAI, **Computer use | OpenAI API**: https://developers.openai.com/api/docs/guides/tools-computer-use
2. Anthropic, **Computer use tool — Claude Platform Docs**: https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool

## Confirmed implementation pattern

Both official implementations describe an iterative agent loop rather than a single blind macro:

1. Send the task with the computer-use tool enabled.
2. Receive structured computer actions.
3. Execute every returned action in order.
4. Capture the updated screen/state.
5. Return the result to the model.
6. Continue until the model emits no further computer-use call or a bounded iteration limit is reached.

Anthropic's documented sampling loop explicitly uses a maximum iteration count to prevent infinite loops and unexpected cost. OpenAI's guide states the same conceptual cycle: inspect the returned computer call, run actions in order, capture the updated screen, return it, and repeat.

## Safety principles relevant to LocalComet

The official documentation emphasizes using an isolated browser or VM, keeping a human in the loop for high-impact actions, defining in advance which accounts and actions are in scope, and treating screenshots, page text, tool outputs, PDFs, emails, chats, and other third-party content as untrusted input. User authorization must not be inferred from content displayed on the controlled screen.

## Adaptation decision

LocalComet should use the same loop at the orchestration level, but with its existing stronger local boundaries:

- host broker remains the only path for launching apps, opening folders, and browser navigation;
- sidecar multi-step tasks remain bounded by a hard step limit;
- each primitive action must pass the existing grant and policy checks;
- before/after observation is required where the backend can observe it;
- stale, missing, derived, or non-executable UIA targets must fail closed;
- a completed action is not automatically a verified task result;
- task-level success requires an independent postcondition probe, otherwise the result is `NOT_INDEPENDENTLY_VERIFIED` / `verification=not_applicable`;
- no new Calculator scenarios are permitted; hidden validation must use a named isolated desktop and a safe Notepad flow.

## Immediate test target

Safe user-style scenario: `Открой Блокнот, дождись окна, напиши Привет и проверь, что текст появился.`

Expected evidence must distinguish:

- broker launch/PID proof;
- window readiness and real UIA target proof;
- text input action result;
- independent postcondition proof that the Notepad document contains the exact marker;
- cleanup scoped to the harness owner.

A harness exit code of 0, a model response, a visible frontend state, or a self-reported sidecar success is not sufficient by itself.
