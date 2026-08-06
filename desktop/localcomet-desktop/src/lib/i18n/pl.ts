import type { TranslationMap } from './index';

/**
 * Polish interface chrome. Keys absent here fall back to English.
 */
export const pl: TranslationMap = {
  // Navigation
  'nav.chat': 'Czat',
  'nav.tasks': 'Zadania',
  'nav.diagnostics': 'Diagnostyka',
  'nav.settings': 'Ustawienia',
  'nav.hf_browser': 'Modele HF',

  // Sidebar
  'sidebar.label': 'Panel boczny sesji',
  'sidebar.collapse': 'Zwiń lub rozwiń panel boczny',
  'sidebar.toggle': 'Pokaż lub ukryj panel boczny czatu',
  'sidebar.new_conversation': 'Nowy czat',
  'conversation.empty': 'Brak rozmów',
  'group.local_chats': 'Czaty lokalne',

  // Command palette
  'commandPalette.label': 'Paleta poleceń',
  'commandPalette.search': 'Znajdź polecenie',
  'commandPalette.placeholder': 'Wpisz polecenie…',
  'commandPalette.commands': 'Dostępne polecenia',
  'commandPalette.empty': 'Brak pasujących poleceń',
  'commandPalette.command.chat': 'Otwórz czat',
  'commandPalette.command.settings': 'Otwórz ustawienia',
  'commandPalette.command.setup': 'Otwórz konfigurację lokalną',
  'commandPalette.command.models': 'Otwórz menedżera modeli',
  'commandPalette.command.observability': 'Otwórz dzienniki i obserwowalność',
  'commandPalette.command.showDiagnostics': 'Pokaż diagnostykę',
  'commandPalette.command.hideDiagnostics': 'Ukryj diagnostykę',

  // Theme and language
  'theme.manage': 'Ustawienia motywu',
  'lang.select': 'Wybierz język',

  // Settings
  'settings.title': 'Ustawienia',
  'settings.sections': 'Sekcje ustawień',
  'settings.tab_interface': 'Interfejs',
  'settings.tab_models': 'Modele',
  'settings.tab_observability': 'Dzienniki',
  'settings.tab_about': 'O aplikacji',
  'settings.close': 'Zamknij ustawienia',
  'settings.appearance': 'Wygląd',
  'settings.theme': 'Motyw',
  'settings.theme_system': 'Systemowy',
  'settings.theme_light': 'Jasny',
  'settings.theme_dark': 'Ciemny',
  'settings.language': 'Język',
  'settings.diagnostics': 'Diagnostyka',
  'settings.connection_state': 'Połączenie warstwy sterowania',
  'settings.show_diagnostics': 'Pokaż diagnostykę',
  'settings.hide_diagnostics': 'Ukryj diagnostykę',
  'settings.about': 'O aplikacji',
  'settings.application': 'Aplikacja',
  'settings.version': 'Wersja',
  'settings.build': 'Kompilacja',
  'settings.build_status': 'Stan kompilacji',
  'settings.capabilities': 'Bieżące możliwości',
  'settings.available': 'Dostępne',
  'settings.unavailable': 'Niedostępne',

  // Common
  'common.skip_link': 'Przejdź do czatu',
  'common.ready': 'Gotowe',
  'common.verified': 'Zweryfikowano',
  'common.not_determined': 'Nieokreślone',

  // Chat essentials
  'chat.type_message': 'Wpisz wiadomość…',
  'chat.connect_model_first': 'Najpierw połącz model',
  'chat.send': 'Wyślij',
  'chat.stop': 'Zatrzymaj',
  'chat.retry': 'Ponów',
  'chat.connect_model': 'Połącz model',

  // Model picker and prompt cards
  'chat.how_can_i_help': 'W czym mogę pomóc?',
  'prompt.create_component': 'Utwórz komponent',
  'prompt.create_component_sub': 'React z Tailwind',
  'prompt.explain_error': 'Wyjaśnij błąd',
  'prompt.explain_error_sub': 'w konsoli serwera',
  'prompt.write_tests': 'Napisz testy',
  'prompt.write_tests_sub': 'dla punktu końcowego API',
  'prompt.optimize': 'Zoptymalizuj',
  'prompt.optimize_sub': 'zapytanie SQL',
};
