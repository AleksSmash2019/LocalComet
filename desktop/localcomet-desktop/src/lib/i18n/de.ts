import type { TranslationMap } from './index';

/**
 * German interface chrome. Keys absent here fall back to English.
 */
export const de: TranslationMap = {
  // Navigation
  'nav.chat': 'Chat',
  'nav.tasks': 'Aufgaben',
  'nav.diagnostics': 'Diagnose',
  'nav.settings': 'Einstellungen',
  'nav.hf_browser': 'HF-Modelle',

  // Sidebar
  'sidebar.label': 'Sitzungsleiste',
  'sidebar.collapse': 'Seitenleiste ein- oder ausklappen',
  'sidebar.toggle': 'Chat-Seitenleiste ein- oder ausblenden',
  'sidebar.new_conversation': 'Neuer Chat',
  'conversation.empty': 'Keine Unterhaltungen',
  'group.local_chats': 'Lokale Chats',

  // Command palette
  'commandPalette.label': 'Befehlspalette',
  'commandPalette.search': 'Befehl suchen',
  'commandPalette.placeholder': 'Befehl eingeben…',
  'commandPalette.commands': 'Verfügbare Befehle',
  'commandPalette.empty': 'Keine passenden Befehle',
  'commandPalette.command.chat': 'Chat öffnen',
  'commandPalette.command.settings': 'Einstellungen öffnen',
  'commandPalette.command.setup': 'Lokale Einrichtung öffnen',
  'commandPalette.command.models': 'Modellverwaltung öffnen',
  'commandPalette.command.observability': 'Protokolle und Observability öffnen',
  'commandPalette.command.showDiagnostics': 'Diagnose anzeigen',
  'commandPalette.command.hideDiagnostics': 'Diagnose ausblenden',

  // Theme and language
  'theme.manage': 'Design-Einstellungen',
  'lang.select': 'Sprache auswählen',

  // Settings
  'settings.title': 'Einstellungen',
  'settings.sections': 'Einstellungsbereiche',
  'settings.tab_interface': 'Oberfläche',
  'settings.tab_models': 'Modelle',
  'settings.tab_observability': 'Protokolle',
  'settings.tab_about': 'Über',
  'settings.close': 'Einstellungen schließen',
  'settings.appearance': 'Darstellung',
  'settings.theme': 'Design',
  'settings.theme_system': 'System',
  'settings.theme_light': 'Hell',
  'settings.theme_dark': 'Dunkel',
  'settings.language': 'Sprache',
  'settings.diagnostics': 'Diagnose',
  'settings.connection_state': 'Control-Plane-Verbindung',
  'settings.show_diagnostics': 'Diagnose anzeigen',
  'settings.hide_diagnostics': 'Diagnose ausblenden',
  'settings.about': 'Über',
  'settings.application': 'Anwendung',
  'settings.version': 'Version',
  'settings.build': 'Build',
  'settings.build_status': 'Build-Status',
  'settings.capabilities': 'Aktuelle Fähigkeiten',
  'settings.available': 'Verfügbar',
  'settings.unavailable': 'Nicht verfügbar',

  // Common
  'common.skip_link': 'Zum Chat springen',
  'common.ready': 'Bereit',
  'common.verified': 'Verifiziert',
  'common.not_determined': 'Nicht ermittelt',

  // Chat essentials
  'chat.type_message': 'Nachricht eingeben…',
  'chat.connect_model_first': 'Zuerst ein Modell verbinden',
  'chat.send': 'Senden',
  'chat.stop': 'Stoppen',
  'chat.retry': 'Erneut versuchen',
  'chat.connect_model': 'Modell verbinden',

  // Model picker and prompt cards
  'chat.how_can_i_help': 'Wie kann ich helfen?',
  'prompt.create_component': 'Komponente erstellen',
  'prompt.create_component_sub': 'React mit Tailwind',
  'prompt.explain_error': 'Fehler erklären',
  'prompt.explain_error_sub': 'in der Serverkonsole',
  'prompt.write_tests': 'Tests schreiben',
  'prompt.write_tests_sub': 'für einen API-Endpunkt',
  'prompt.optimize': 'Optimieren',
  'prompt.optimize_sub': 'eine SQL-Abfrage',
};
