# Evidence Ledger — Best-of-Two Audit Archive

**Дата:** 2026-07-25
**Ветка:** `integration/best-of-two-local-agent` @ `767a7e9`

## Присутствует (включено в архив)

| Материал | Путь | Статус |
|---|---|---|
| Master Prompt (Best-of-Two) | `audit/donor-briefs/LocalComet Best-of-Two Integration Master Prompt.pdf` | PRESENT (binary, не читается моделью — только как артефакт) |
| WP-1.45.4 Independent Verification | `audit/donor-briefs/WP-1.45.4_Independent_Verification_2026-07-25.txt` | PRESENT |
| WP-1.45.4 Engineering Brief | `audit/donor-briefs/WP-1.45.4-engineering-brief.md` | PRESENT |
| WP-1.45.3 Engineering Brief | `audit/donor-briefs/WP-1.45.3-engineering-brief.md` | PRESENT |
| WP-1.45.2 Remediation Prompt | `audit/donor-briefs/WP-1.45.2-remediation-prompt.md` | PRESENT |
| Donor archive (lad-wp1454) | `audit/donor-briefs/lad-wp1454.tar.gz` | PRESENT (353 250 байт) |
| Migration matrix | `docs/engineering/best-of-two-migration-matrix.md` | PRESENT |
| Final report | `docs/engineering/best-of-two-final-report.md` | PRESENT |
| Invariants registry | `security/invariants/invariants.toml` | PRESENT |
| Non-authorities registry | `security/invariants/non_authorities.toml` | PRESENT |
| Evidence JSON | `artifacts/evidence/best-of-two-evidence.json` | PRESENT |
| Trust-chain gate | `tests/test_trust_chain_invariants.py` | PRESENT |
| Command parity gate | `scripts/check_command_parity.py` | PRESENT |

## Отсутствует (НЕ включено — не найдено в среде)

| Материал | Ожидаемый путь | Влияние |
|---|---|---|
| LocalComet Detailed Static Audit | `LocalComet_Detailed_Static_Audit_2026-07-25.txt` | Нет внешнего статического аудита LocalComet — аудитору придётся делать с нуля |
| Source vs Audit Diff | `LocalAgent_Source_vs_Audit_Diff_2026-07-25.txt` | Нет diff между исходниками и аудитом донора |
| local-agent-desktop-source (1/2).tar.gz | Downloads | Нет полных исходников донора (только WP-архив lad-wp1454) |
| local-agent-desktop-audit.zip | Downloads | Нет отдельного аудит-архива донора |
| LocalComet-ProjectArchive-20260725.zip | Downloads | Нет проектного архива |
| localcomet-dossier.zip | Downloads | Нет досье |

## Donor SHA-256 (из верификации WP-1.45.4)

```
lad-wp1454.tar.gz  85109c26669462e40f2ff65c83dc94cfce3094d4a27a739575555ee6ec5e827d
```

(заявлено в `WP-1.45.4_Independent_Verification_2026-07-25.txt`; сверить при распаковке)

## Проведённые проверки (локально, на момент сборки)

| Команда | Результат |
|---|---|
| `cargo test` | 143 passed, 0 failed, 6 ignored |
| `python tests/test_trust_chain_invariants.py` | OK: 14 files pass byte invariants |
| `python scripts/check_command_parity.py` | OK: 39 commands (parity holds) |

## Пометки способа получения

- Все числа тестов — `[прогон]` (реальное исполнение в этой среде).
- Классификация продукта — `[вычислено]` на основе чтения кода и прогонов.
- Утверждения о donor-дефектах — из `WP-1.45.4_Independent_Verification`, `[ЗАЯВЛЕНО]`
  относительно donor-кода (исходники донора в этой среде не запускались).
