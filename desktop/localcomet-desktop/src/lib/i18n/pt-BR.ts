import type { TranslationMap } from './index';

/**
 * Brazilian Portuguese interface chrome. Keys absent here fall back to English.
 */
export const ptBR: TranslationMap = {
  // Navigation
  'nav.chat': 'Chat',
  'nav.tasks': 'Tarefas',
  'nav.diagnostics': 'Diagnóstico',
  'nav.audit': 'Auditoria',
  'nav.settings': 'Configurações',
  'nav.setup': 'Configuração',
  'nav.main': 'Navegação principal',
  'nav.later': 'mais tarde',
  'nav.hf_browser': 'Modelos HF',
  'app.title_bar': 'Barra do aplicativo LocalComet',

  // Sidebar
  'sidebar.label': 'Barra lateral da sessão',
  'sidebar.new_thread': 'Novo tópico',
  'sidebar.collapse': 'Recolher ou expandir a barra lateral',
  'sidebar.toggle': 'Mostrar ou ocultar a barra lateral do chat',
  'sidebar.new_conversation': 'Novo chat',
  'sidebar.pinned': 'Fixado',
  'sidebar.project_labels': 'Rótulos do projeto',
  'conversation.empty': 'Nenhuma conversa',
  'group.local_chats': 'Chats locais',
  'group.reserved': 'Reservado',
  'group.disabled': 'Desativado',
  'item.new_chat': 'Novo chat',
  'item.audit': 'Auditoria',
  'item.documents': 'Documentos',
  'item.model_not_connected': 'Modelo não conectado',
  'item.model_required': 'Modelo necessário',
  'item.later': 'Mais tarde',

  // Command palette
  'commandPalette.label': 'Paleta de comandos',
  'commandPalette.search': 'Buscar um comando',
  'commandPalette.placeholder': 'Digite um comando…',
  'commandPalette.commands': 'Comandos disponíveis',
  'commandPalette.empty': 'Nenhum comando correspondente',
  'commandPalette.command.chat': 'Abrir o chat',
  'commandPalette.command.settings': 'Abrir as configurações',
  'commandPalette.command.setup': 'Abrir a configuração local',
  'commandPalette.command.models': 'Abrir o gerenciador de modelos',
  'commandPalette.command.observability': 'Abrir registros e observabilidade',
  'commandPalette.command.showDiagnostics': 'Mostrar o diagnóstico',
  'commandPalette.command.hideDiagnostics': 'Ocultar o diagnóstico',

  // Theme and language
  'theme.manage': 'Configurações de tema',
  'theme.system': 'Usar o tema do sistema',
  'theme.light': 'Usar o tema claro',
  'theme.dark': 'Usar o tema escuro',
  'lang.select': 'Selecionar idioma',

  // Settings
  'settings.title': 'Configurações',
  'settings.sections': 'Seções de configurações',
  'settings.tab_interface': 'Interface',
  'settings.tab_models': 'Modelos',
  'settings.tab_observability': 'Registros',
  'settings.tab_about': 'Sobre',
  'settings.close': 'Fechar as configurações',
  'settings.appearance': 'Aparência',
  'settings.theme': 'Tema',
  'settings.theme_system': 'Sistema',
  'settings.theme_light': 'Claro',
  'settings.theme_dark': 'Escuro',
  'settings.language': 'Idioma',
  'settings.diagnostics': 'Diagnóstico',
  'settings.connection_state': 'Conexão do plano de controle',
  'settings.show_diagnostics': 'Mostrar o diagnóstico',
  'settings.hide_diagnostics': 'Ocultar o diagnóstico',
  'settings.about': 'Sobre',
  'settings.application': 'Aplicativo',
  'settings.version': 'Versão',
  'settings.build': 'Build',
  'settings.build_status': 'Status do build',
  'settings.capabilities': 'Recursos atuais',
  'settings.available': 'Disponível',
  'settings.unavailable': 'Indisponível',

  // Common
  'common.skip_link': 'Ir para o chat',
  'common.ready': 'Pronto',
  'common.verified': 'Verificado',
  'common.not_determined': 'Não determinado',

  // Chat essentials
  'chat.type_message': 'Digite uma mensagem…',
  'chat.connect_model_first': 'Conecte um modelo primeiro',
  'chat.send': 'Enviar',
  'chat.stop': 'Parar',
  'chat.model_not_connected': 'Modelo não conectado',
  'chat.retry': 'Tentar novamente',
  'chat.connect_model': 'Conectar o modelo',
  'chat.open_models': 'Abrir os modelos',

  // Model picker and prompt cards
  'chat.search': 'Pesquisar',
  'chat.how_can_i_help': 'Como posso ajudar?',
  'prompt.create_component': 'Criar um componente',
  'prompt.create_component_sub': 'React com Tailwind',
  'prompt.explain_error': 'Explicar um erro',
  'prompt.explain_error_sub': 'no console do servidor',
  'prompt.write_tests': 'Escrever testes',
  'prompt.write_tests_sub': 'para um endpoint de API',
  'prompt.optimize': 'Otimizar',
  'prompt.optimize_sub': 'uma consulta SQL',
};
