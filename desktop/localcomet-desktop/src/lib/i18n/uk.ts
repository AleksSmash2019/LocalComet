import type { TranslationMap } from './index';

/**
 * Ukrainian interface chrome. Keys absent here fall back to English.
 */
export const uk: TranslationMap = {
  // Navigation
  'nav.chat': 'Чат',
  'nav.tasks': 'Завдання',
  'nav.diagnostics': 'Діагностика',
  'nav.audit': 'Аудит',
  'nav.settings': 'Налаштування',
  'nav.setup': 'Налаштування',
  'nav.main': 'Основна навігація',
  'nav.later': 'пізніше',
  'nav.hf_browser': 'Моделі HF',
  'app.title_bar': 'Панель застосунку LocalComet',

  // Sidebar
  'sidebar.label': 'Бічна панель сеансу',
  'sidebar.new_thread': 'Нова гілка',
  'sidebar.collapse': 'Згорнути або розгорнути бічну панель',
  'sidebar.toggle': 'Показати або приховати бічну панель чату',
  'sidebar.new_conversation': 'Новий чат',
  'sidebar.pinned': 'Закріплено',
  'sidebar.project_labels': 'Мітки проєкту',
  'conversation.empty': 'Немає розмов',
  'group.local_chats': 'Локальні чати',
  'group.reserved': 'Зарезервовано',
  'group.disabled': 'Вимкнено',
  'item.new_chat': 'Новий чат',
  'item.audit': 'Аудит',
  'item.documents': 'Документи',
  'item.model_not_connected': 'Модель не підключено',
  'item.model_required': 'Потрібна модель',
  'item.later': 'Пізніше',

  // Command palette
  'commandPalette.label': 'Палітра команд',
  'commandPalette.search': 'Знайти команду',
  'commandPalette.placeholder': 'Введіть команду…',
  'commandPalette.commands': 'Доступні команди',
  'commandPalette.empty': 'Немає відповідних команд',
  'commandPalette.command.chat': 'Відкрити чат',
  'commandPalette.command.settings': 'Відкрити налаштування',
  'commandPalette.command.setup': 'Відкрити локальне налаштування',
  'commandPalette.command.models': 'Відкрити менеджер моделей',
  'commandPalette.command.observability': 'Відкрити журнали та спостережуваність',
  'commandPalette.command.showDiagnostics': 'Показати діагностику',
  'commandPalette.command.hideDiagnostics': 'Приховати діагностику',

  // Theme and language
  'theme.manage': 'Налаштування теми',
  'theme.system': 'Використовувати системну тему',
  'theme.light': 'Використовувати світлу тему',
  'theme.dark': 'Використовувати темну тему',
  'lang.select': 'Вибрати мову',

  // Settings
  'settings.title': 'Налаштування',
  'settings.sections': 'Розділи налаштувань',
  'settings.tab_interface': 'Інтерфейс',
  'settings.tab_models': 'Моделі',
  'settings.tab_observability': 'Журнали',
  'settings.tab_about': 'Про застосунок',
  'settings.close': 'Закрити налаштування',
  'settings.appearance': 'Оформлення',
  'settings.theme': 'Тема',
  'settings.theme_system': 'Системна',
  'settings.theme_light': 'Світла',
  'settings.theme_dark': 'Темна',
  'settings.language': 'Мова',
  'settings.diagnostics': 'Діагностика',
  'settings.connection_state': "Підключення контуру керування",
  'settings.show_diagnostics': 'Показати діагностику',
  'settings.hide_diagnostics': 'Приховати діагностику',
  'settings.about': 'Про застосунок',
  'settings.application': 'Застосунок',
  'settings.version': 'Версія',
  'settings.build': 'Збірка',
  'settings.build_status': 'Стан збірки',
  'settings.capabilities': 'Поточні можливості',
  'settings.available': 'Доступно',
  'settings.unavailable': 'Недоступно',

  // Common
  'common.skip_link': 'Перейти до чату',
  'common.ready': 'Готово',
  'common.verified': 'Перевірено',
  'common.not_determined': 'Не визначено',

  // Chat essentials
  'chat.type_message': 'Введіть повідомлення…',
  'chat.connect_model_first': 'Спершу підключіть модель',
  'chat.send': 'Надіслати',
  'chat.stop': 'Зупинити',
  'chat.model_not_connected': 'Модель не підключено',
  'chat.retry': 'Повторити',
  'chat.connect_model': 'Підключити модель',
  'chat.open_models': 'Відкрити моделі',

  // Model picker and prompt cards
  'chat.search': 'Шукати',
  'chat.how_can_i_help': 'Чим допомогти?',
  'prompt.create_component': 'Створити компонент',
  'prompt.create_component_sub': 'React із Tailwind',
  'prompt.explain_error': 'Пояснити помилку',
  'prompt.explain_error_sub': 'у консолі сервера',
  'prompt.write_tests': 'Написати тести',
  'prompt.write_tests_sub': 'для API-ендпоінта',
  'prompt.optimize': 'Оптимізувати',
  'prompt.optimize_sub': 'SQL-запит',
};
