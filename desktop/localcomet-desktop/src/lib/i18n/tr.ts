import type { TranslationMap } from './index';

/**
 * Turkish interface chrome. Keys absent here fall back to English.
 */
export const tr: TranslationMap = {
  // Navigation
  'nav.chat': 'Sohbet',
  'nav.tasks': 'Görevler',
  'nav.diagnostics': 'Tanılama',
  'nav.audit': 'Denetim',
  'nav.settings': 'Ayarlar',
  'nav.setup': 'Kurulum',
  'nav.main': 'Ana gezinme',
  'nav.later': 'daha sonra',
  'nav.hf_browser': 'HF Modelleri',
  'app.title_bar': 'LocalComet uygulama çubuğu',

  // Sidebar
  'sidebar.label': 'Oturum kenar çubuğu',
  'sidebar.new_thread': 'Yeni konu',
  'sidebar.collapse': 'Kenar çubuğunu daralt veya genişlet',
  'sidebar.toggle': 'Sohbet kenar çubuğunu göster veya gizle',
  'sidebar.new_conversation': 'Yeni sohbet',
  'sidebar.pinned': 'Sabitlendi',
  'sidebar.project_labels': 'Proje etiketleri',
  'conversation.empty': 'Sohbet yok',
  'group.local_chats': 'Yerel sohbetler',
  'group.reserved': 'Ayrılmış',
  'group.disabled': 'Devre dışı',
  'item.new_chat': 'Yeni sohbet',
  'item.audit': 'Denetim',
  'item.documents': 'Belgeler',
  'item.model_not_connected': 'Model bağlı değil',
  'item.model_required': 'Model gerekli',
  'item.later': 'Daha sonra',

  // Command palette
  'commandPalette.label': 'Komut paleti',
  'commandPalette.search': 'Komut ara',
  'commandPalette.placeholder': 'Bir komut yazın…',
  'commandPalette.commands': 'Kullanılabilir komutlar',
  'commandPalette.empty': 'Eşleşen komut yok',
  'commandPalette.command.chat': 'Sohbeti aç',
  'commandPalette.command.settings': 'Ayarları aç',
  'commandPalette.command.setup': 'Yerel kurulumu aç',
  'commandPalette.command.models': 'Model yöneticisini aç',
  'commandPalette.command.observability': 'Günlükleri ve gözlemlenebilirliği aç',
  'commandPalette.command.showDiagnostics': 'Tanılamayı göster',
  'commandPalette.command.hideDiagnostics': 'Tanılamayı gizle',

  // Theme and language
  'theme.manage': 'Tema ayarları',
  'theme.system': 'Sistem temasını kullan',
  'theme.light': 'Açık temayı kullan',
  'theme.dark': 'Koyu temayı kullan',
  'lang.select': 'Dil seçin',

  // Settings
  'settings.title': 'Ayarlar',
  'settings.sections': 'Ayar bölümleri',
  'settings.tab_interface': 'Arayüz',
  'settings.tab_models': 'Modeller',
  'settings.tab_observability': 'Günlükler',
  'settings.tab_about': 'Hakkında',
  'settings.close': 'Ayarları kapat',
  'settings.appearance': 'Görünüm',
  'settings.theme': 'Tema',
  'settings.theme_system': 'Sistem',
  'settings.theme_light': 'Açık',
  'settings.theme_dark': 'Koyu',
  'settings.language': 'Dil',
  'settings.diagnostics': 'Tanılama',
  'settings.connection_state': 'Kontrol düzlemi bağlantısı',
  'settings.show_diagnostics': 'Tanılamayı göster',
  'settings.hide_diagnostics': 'Tanılamayı gizle',
  'settings.about': 'Hakkında',
  'settings.application': 'Uygulama',
  'settings.version': 'Sürüm',
  'settings.build': 'Yapı',
  'settings.build_status': 'Yapı durumu',
  'settings.capabilities': 'Mevcut yetenekler',
  'settings.available': 'Kullanılabilir',
  'settings.unavailable': 'Kullanılamaz',

  // Common
  'common.skip_link': 'Sohbete geç',
  'common.ready': 'Hazır',
  'common.verified': 'Doğrulandı',
  'common.not_determined': 'Belirlenmedi',

  // Chat essentials
  'chat.type_message': 'Bir mesaj yazın…',
  'chat.connect_model_first': 'Önce bir model bağlayın',
  'chat.send': 'Gönder',
  'chat.stop': 'Durdur',
  'chat.model_not_connected': 'Model bağlı değil',
  'chat.retry': 'Yeniden dene',
  'chat.connect_model': 'Modeli bağla',
  'chat.open_models': 'Modelleri aç',

  // Model picker and prompt cards
  'chat.search': 'Ara',
  'chat.how_can_i_help': 'Nasıl yardımcı olabilirim?',
  'prompt.create_component': 'Bileşen oluştur',
  'prompt.create_component_sub': 'Tailwind ile React',
  'prompt.explain_error': 'Hatayı açıkla',
  'prompt.explain_error_sub': 'sunucu konsolunda',
  'prompt.write_tests': 'Test yaz',
  'prompt.write_tests_sub': 'bir API uç noktası için',
  'prompt.optimize': 'İyileştir',
  'prompt.optimize_sub': 'bir SQL sorgusu',
};
