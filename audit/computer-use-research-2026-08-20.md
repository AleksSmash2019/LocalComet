# Computer Use — критерии аудита Windows UI Automation

Microsoft описывает UI Automation как клиентский API для работы с контролами других приложений. Для действий над интерфейсом клиент должен опираться на фактически поддерживаемые control patterns и их состояние, а не на предположение по таймеру или координатам.[1][2]

| Принцип | Применение к LocalComet |
|---|---|
| Проверять доступную capability перед действием | Grounded click/type должны возвращать понятный отказ при отсутствии подтверждённого элемента, а не симулировать успех. |
| Использовать семантику control patterns | Для `Invoke`, `Selection`, `Value`, `Text` и `Scroll` приоритетны роли и состояние UI map; координаты — ограниченный fallback. |
| Отделять изменение интерфейса от успеха операции | После действия нужно сообщать факт выполнения, наблюдаемое изменение и следующий безопасный шаг. Изменение окна само по себе не является ошибкой. |
| Уважать privilege boundary | UAC/protected desktop не должны обходиться или имитироваться. Для защищённого UI обычный Computer Use должен вернуть понятный блокирующий статус.[3] |
| Сохранять пользовательский контекст | Вставка Unicode-текста не должна оставлять буфер обмена пользователя в изменённом состоянии после штатного завершения. |

## References

[1]: https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiautocore-overview
[2]: https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-controlpatternsoverview
[3]: https://learn.microsoft.com/en-us/dotnet/framework/ui-automation/ui-automation-security-overview
