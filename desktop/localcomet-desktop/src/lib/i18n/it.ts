import type { TranslationMap } from './index';

/**
 * Italian interface chrome. Keys absent here fall back to English.
 */
export const it: TranslationMap = {
  // Navigation
  'nav.chat': 'Chat',
  'nav.tasks': 'Attività',
  'nav.diagnostics': 'Diagnostica',
  'nav.settings': 'Impostazioni',
  'nav.hf_browser': 'Modelli HF',

  // Sidebar
  'sidebar.label': 'Barra laterale della sessione',
  'sidebar.collapse': 'Comprimi o espandi la barra laterale',
  'sidebar.toggle': 'Mostra o nascondi la barra laterale della chat',
  'sidebar.new_conversation': 'Nuova chat',
  'conversation.empty': 'Nessuna conversazione',
  'group.local_chats': 'Chat locali',

  // Command palette
  'commandPalette.label': 'Palette dei comandi',
  'commandPalette.search': 'Cerca un comando',
  'commandPalette.placeholder': 'Digita un comando…',
  'commandPalette.commands': 'Comandi disponibili',
  'commandPalette.empty': 'Nessun comando corrispondente',
  'commandPalette.command.chat': 'Apri la chat',
  'commandPalette.command.settings': 'Apri le impostazioni',
  'commandPalette.command.setup': 'Apri la configurazione locale',
  'commandPalette.command.models': 'Apri la gestione dei modelli',
  'commandPalette.command.observability': "Apri i registri e l'osservabilità",
  'commandPalette.command.showDiagnostics': 'Mostra la diagnostica',
  'commandPalette.command.hideDiagnostics': 'Nascondi la diagnostica',

  // Theme and language
  'theme.manage': 'Impostazioni del tema',
  'lang.select': 'Seleziona la lingua',

  // Settings
  'settings.title': 'Impostazioni',
  'settings.sections': 'Sezioni delle impostazioni',
  'settings.tab_interface': 'Interfaccia',
  'settings.tab_models': 'Modelli',
  'settings.tab_observability': 'Registri',
  'settings.tab_about': 'Informazioni',
  'settings.close': 'Chiudi le impostazioni',
  'settings.appearance': 'Aspetto',
  'settings.theme': 'Tema',
  'settings.theme_system': 'Sistema',
  'settings.theme_light': 'Chiaro',
  'settings.theme_dark': 'Scuro',
  'settings.language': 'Lingua',
  'settings.diagnostics': 'Diagnostica',
  'settings.connection_state': 'Connessione del control plane',
  'settings.show_diagnostics': 'Mostra la diagnostica',
  'settings.hide_diagnostics': 'Nascondi la diagnostica',
  'settings.about': 'Informazioni',
  'settings.application': 'Applicazione',
  'settings.version': 'Versione',
  'settings.build': 'Build',
  'settings.build_status': 'Stato della build',
  'settings.capabilities': 'Funzionalità attuali',
  'settings.available': 'Disponibile',
  'settings.unavailable': 'Non disponibile',

  // Common
  'common.skip_link': 'Vai alla chat',
  'common.ready': 'Pronto',
  'common.verified': 'Verificato',
  'common.not_determined': 'Non determinato',

  // Chat essentials
  'chat.type_message': 'Scrivi un messaggio…',
  'chat.connect_model_first': 'Collega prima un modello',
  'chat.send': 'Invia',
  'chat.stop': 'Interrompi',
  'chat.retry': 'Riprova',
  'chat.connect_model': 'Collega il modello',

  // Model picker and prompt cards
  'chat.how_can_i_help': 'Come posso aiutarti?',
  'prompt.create_component': 'Crea un componente',
  'prompt.create_component_sub': 'React con Tailwind',
  'prompt.explain_error': 'Spiega un errore',
  'prompt.explain_error_sub': 'nella console del server',
  'prompt.write_tests': 'Scrivi test',
  'prompt.write_tests_sub': 'per un endpoint API',
  'prompt.optimize': 'Ottimizza',
  'prompt.optimize_sub': 'una query SQL',
};
