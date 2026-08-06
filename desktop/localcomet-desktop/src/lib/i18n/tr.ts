import type { TranslationMap } from './index';

/**
 * Turkish interface chrome. Keys absent here fall back to English.
 */
export const tr: TranslationMap = {
  // Navigation
  'nav.chat': 'Sohbet',
  'nav.tasks': 'Görevler',
  'nav.diagnostics': 'Tanılama',
  'nav.settings': 'Ayarlar',
  'nav.hf_browser': 'HF Modelleri',

  // Sidebar
  'sidebar.label': 'Oturum kenar çubuğu',
  'sidebar.collapse': 'Kenar çubuğunu daralt veya genişlet',
  'sidebar.toggle': 'Sohbet kenar çubuğunu göster veya gizle',
  'sidebar.new_conversation': 'Yeni sohbet',
  'conversation.empty': 'Sohbet yok',
  'group.local_chats': 'Yerel sohbetler',

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
  'chat.retry': 'Yeniden dene',
  'chat.connect_model': 'Modeli bağla',

  // Model picker and prompt cards
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
