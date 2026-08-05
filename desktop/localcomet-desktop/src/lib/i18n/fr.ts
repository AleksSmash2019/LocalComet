import type { TranslationMap } from './index';

/**
 * French interface chrome. Keys absent here fall back to English.
 */
export const fr: TranslationMap = {
  // Navigation
  'nav.chat': 'Discussion',
  'nav.tasks': 'Tâches',
  'nav.diagnostics': 'Diagnostic',
  'nav.audit': 'Audit',
  'nav.settings': 'Paramètres',
  'nav.setup': 'Configuration',
  'nav.main': 'Navigation principale',
  'nav.later': 'plus tard',
  'nav.hf_browser': 'Modèles HF',
  'app.title_bar': "Barre de l'application LocalComet",

  // Sidebar
  'sidebar.label': 'Barre latérale de session',
  'sidebar.new_thread': 'Nouveau fil',
  'sidebar.collapse': 'Réduire ou développer la barre latérale',
  'sidebar.toggle': 'Afficher ou masquer la barre latérale',
  'sidebar.new_conversation': 'Nouvelle discussion',
  'sidebar.pinned': 'Épinglé',
  'sidebar.project_labels': 'Étiquettes du projet',
  'conversation.empty': 'Aucune conversation',
  'group.local_chats': 'Discussions locales',
  'group.reserved': 'Réservé',
  'group.disabled': 'Désactivé',
  'item.new_chat': 'Nouvelle discussion',
  'item.audit': 'Audit',
  'item.documents': 'Documents',
  'item.model_not_connected': 'Modèle non connecté',
  'item.model_required': 'Modèle requis',
  'item.later': 'Plus tard',

  // Command palette
  'commandPalette.label': 'Palette de commandes',
  'commandPalette.search': 'Rechercher une commande',
  'commandPalette.placeholder': 'Saisissez une commande…',
  'commandPalette.commands': 'Commandes disponibles',
  'commandPalette.empty': 'Aucune commande correspondante',
  'commandPalette.command.chat': 'Ouvrir la discussion',
  'commandPalette.command.settings': 'Ouvrir les paramètres',
  'commandPalette.command.setup': 'Ouvrir la configuration locale',
  'commandPalette.command.models': 'Ouvrir le gestionnaire de modèles',
  'commandPalette.command.observability': "Ouvrir les journaux et l'observabilité",
  'commandPalette.command.showDiagnostics': 'Afficher le diagnostic',
  'commandPalette.command.hideDiagnostics': 'Masquer le diagnostic',

  // Theme and language
  'theme.manage': 'Paramètres du thème',
  'theme.system': 'Utiliser le thème du système',
  'theme.light': 'Utiliser le thème clair',
  'theme.dark': 'Utiliser le thème sombre',
  'lang.select': 'Choisir la langue',

  // Settings
  'settings.title': 'Paramètres',
  'settings.sections': 'Sections des paramètres',
  'settings.tab_interface': 'Interface',
  'settings.tab_models': 'Modèles',
  'settings.tab_observability': 'Journaux',
  'settings.tab_about': 'À propos',
  'settings.close': 'Fermer les paramètres',
  'settings.appearance': 'Apparence',
  'settings.theme': 'Thème',
  'settings.theme_system': 'Système',
  'settings.theme_light': 'Clair',
  'settings.theme_dark': 'Sombre',
  'settings.language': 'Langue',
  'settings.diagnostics': 'Diagnostic',
  'settings.connection_state': 'Connexion du plan de contrôle',
  'settings.show_diagnostics': 'Afficher le diagnostic',
  'settings.hide_diagnostics': 'Masquer le diagnostic',
  'settings.about': 'À propos',
  'settings.application': 'Application',
  'settings.version': 'Version',
  'settings.build': 'Build',
  'settings.build_status': 'État du build',
  'settings.capabilities': 'Capacités actuelles',
  'settings.available': 'Disponible',
  'settings.unavailable': 'Indisponible',

  // Common
  'common.skip_link': 'Aller à la discussion',
  'common.ready': 'Prêt',
  'common.verified': 'Vérifié',
  'common.not_determined': 'Non déterminé',

  // Chat essentials
  'chat.type_message': 'Saisissez un message…',
  'chat.connect_model_first': "Connectez d'abord un modèle",
  'chat.send': 'Envoyer',
  'chat.stop': 'Arrêter',
  'chat.model_not_connected': 'Modèle non connecté',
  'chat.retry': 'Réessayer',
  'chat.connect_model': 'Connecter le modèle',
  'chat.open_models': 'Ouvrir les modèles',

  // Model picker and prompt cards
  'chat.search': 'Rechercher',
  'chat.how_can_i_help': 'Comment puis-je aider ?',
  'prompt.create_component': 'Créer un composant',
  'prompt.create_component_sub': 'React avec Tailwind',
  'prompt.explain_error': 'Expliquer une erreur',
  'prompt.explain_error_sub': 'dans la console du serveur',
  'prompt.write_tests': 'Écrire des tests',
  'prompt.write_tests_sub': 'pour un point de terminaison d\'API',
  'prompt.optimize': 'Optimiser',
  'prompt.optimize_sub': 'une requête SQL',
};
