import type { TranslationMap } from './index';

/**
 * Spanish interface chrome. Keys absent here fall back to English.
 */
export const es: TranslationMap = {
  // Navigation
  'nav.chat': 'Chat',
  'nav.tasks': 'Tareas',
  'nav.diagnostics': 'Diagnóstico',
  'nav.settings': 'Ajustes',
  'nav.hf_browser': 'Modelos HF',

  // Sidebar
  'sidebar.label': 'Barra lateral de sesión',
  'sidebar.collapse': 'Contraer o expandir la barra lateral',
  'sidebar.toggle': 'Mostrar u ocultar la barra lateral del chat',
  'sidebar.new_conversation': 'Chat nuevo',
  'conversation.empty': 'Sin conversaciones',
  'group.local_chats': 'Chats locales',

  // Command palette
  'commandPalette.label': 'Paleta de comandos',
  'commandPalette.search': 'Buscar un comando',
  'commandPalette.placeholder': 'Escribe un comando…',
  'commandPalette.commands': 'Comandos disponibles',
  'commandPalette.empty': 'No hay comandos coincidentes',
  'commandPalette.command.chat': 'Abrir el chat',
  'commandPalette.command.settings': 'Abrir los ajustes',
  'commandPalette.command.setup': 'Abrir la configuración local',
  'commandPalette.command.models': 'Abrir el gestor de modelos',
  'commandPalette.command.observability': 'Abrir registros y observabilidad',
  'commandPalette.command.showDiagnostics': 'Mostrar el diagnóstico',
  'commandPalette.command.hideDiagnostics': 'Ocultar el diagnóstico',

  // Theme and language
  'theme.manage': 'Ajustes de tema',
  'lang.select': 'Seleccionar idioma',

  // Settings
  'settings.title': 'Ajustes',
  'settings.sections': 'Secciones de ajustes',
  'settings.tab_interface': 'Interfaz',
  'settings.tab_models': 'Modelos',
  'settings.tab_observability': 'Registros',
  'settings.tab_about': 'Acerca de',
  'settings.close': 'Cerrar los ajustes',
  'settings.appearance': 'Apariencia',
  'settings.theme': 'Tema',
  'settings.theme_system': 'Sistema',
  'settings.theme_light': 'Claro',
  'settings.theme_dark': 'Oscuro',
  'settings.language': 'Idioma',
  'settings.diagnostics': 'Diagnóstico',
  'settings.connection_state': 'Conexión del plano de control',
  'settings.show_diagnostics': 'Mostrar el diagnóstico',
  'settings.hide_diagnostics': 'Ocultar el diagnóstico',
  'settings.about': 'Acerca de',
  'settings.application': 'Aplicación',
  'settings.version': 'Versión',
  'settings.build': 'Compilación',
  'settings.build_status': 'Estado de la compilación',
  'settings.capabilities': 'Capacidades actuales',
  'settings.available': 'Disponible',
  'settings.unavailable': 'No disponible',

  // Common
  'common.skip_link': 'Ir al chat',
  'common.ready': 'Listo',
  'common.verified': 'Verificado',
  'common.not_determined': 'Sin determinar',

  // Chat essentials
  'chat.type_message': 'Escribe un mensaje…',
  'chat.connect_model_first': 'Conecta primero un modelo',
  'chat.send': 'Enviar',
  'chat.stop': 'Detener',
  'chat.retry': 'Reintentar',
  'chat.connect_model': 'Conectar el modelo',

  // Model picker and prompt cards
  'chat.how_can_i_help': '¿En qué puedo ayudarte?',
  'prompt.create_component': 'Crear un componente',
  'prompt.create_component_sub': 'React con Tailwind',
  'prompt.explain_error': 'Explicar un error',
  'prompt.explain_error_sub': 'en la consola del servidor',
  'prompt.write_tests': 'Escribir pruebas',
  'prompt.write_tests_sub': 'para un endpoint de API',
  'prompt.optimize': 'Optimizar',
  'prompt.optimize_sub': 'una consulta SQL',
};
