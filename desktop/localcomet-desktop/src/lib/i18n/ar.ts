import type { TranslationMap } from './index';

/**
 * Arabic interface chrome. Keys absent here fall back to English.
 * This locale is right-to-left; index.ts sets document.dir accordingly.
 */
export const ar: TranslationMap = {
  // Navigation
  'nav.chat': 'المحادثة',
  'nav.tasks': 'المهام',
  'nav.diagnostics': 'التشخيص',
  'nav.audit': 'التدقيق',
  'nav.settings': 'الإعدادات',
  'nav.setup': 'الإعداد',
  'nav.main': 'التنقل الرئيسي',
  'nav.later': 'لاحقًا',
  'nav.hf_browser': 'نماذج HF',
  'app.title_bar': 'شريط تطبيق LocalComet',

  // Sidebar
  'sidebar.label': 'الشريط الجانبي للجلسة',
  'sidebar.new_thread': 'موضوع جديد',
  'sidebar.collapse': 'طي الشريط الجانبي أو توسيعه',
  'sidebar.toggle': 'إظهار الشريط الجانبي للمحادثة أو إخفاؤه',
  'sidebar.new_conversation': 'محادثة جديدة',
  'sidebar.pinned': 'مثبّت',
  'sidebar.project_labels': 'تسميات المشروع',
  'conversation.empty': 'لا توجد محادثات',
  'group.local_chats': 'المحادثات المحلية',
  'group.reserved': 'محجوز',
  'group.disabled': 'معطّل',
  'item.new_chat': 'محادثة جديدة',
  'item.audit': 'التدقيق',
  'item.documents': 'المستندات',
  'item.model_not_connected': 'النموذج غير متصل',
  'item.model_required': 'النموذج مطلوب',
  'item.later': 'لاحقًا',

  // Command palette
  'commandPalette.label': 'لوحة الأوامر',
  'commandPalette.search': 'ابحث عن أمر',
  'commandPalette.placeholder': 'اكتب أمرًا…',
  'commandPalette.commands': 'الأوامر المتاحة',
  'commandPalette.empty': 'لا توجد أوامر مطابقة',
  'commandPalette.command.chat': 'فتح المحادثة',
  'commandPalette.command.settings': 'فتح الإعدادات',
  'commandPalette.command.setup': 'فتح الإعداد المحلي',
  'commandPalette.command.models': 'فتح مدير النماذج',
  'commandPalette.command.observability': 'فتح السجلات والمراقبة',
  'commandPalette.command.showDiagnostics': 'إظهار التشخيص',
  'commandPalette.command.hideDiagnostics': 'إخفاء التشخيص',

  // Theme and language
  'theme.manage': 'إعدادات المظهر',
  'theme.system': 'استخدام مظهر النظام',
  'theme.light': 'استخدام المظهر الفاتح',
  'theme.dark': 'استخدام المظهر الداكن',
  'lang.select': 'اختيار اللغة',

  // Settings
  'settings.title': 'الإعدادات',
  'settings.sections': 'أقسام الإعدادات',
  'settings.tab_interface': 'الواجهة',
  'settings.tab_models': 'النماذج',
  'settings.tab_observability': 'السجلات',
  'settings.tab_about': 'حول',
  'settings.close': 'إغلاق الإعدادات',
  'settings.appearance': 'المظهر',
  'settings.theme': 'السمة',
  'settings.theme_system': 'النظام',
  'settings.theme_light': 'فاتح',
  'settings.theme_dark': 'داكن',
  'settings.language': 'اللغة',
  'settings.diagnostics': 'التشخيص',
  'settings.connection_state': 'اتصال مستوى التحكم',
  'settings.show_diagnostics': 'إظهار التشخيص',
  'settings.hide_diagnostics': 'إخفاء التشخيص',
  'settings.about': 'حول',
  'settings.application': 'التطبيق',
  'settings.version': 'الإصدار',
  'settings.build': 'البنية',
  'settings.build_status': 'حالة البنية',
  'settings.capabilities': 'القدرات الحالية',
  'settings.available': 'متاح',
  'settings.unavailable': 'غير متاح',

  // Common
  'common.skip_link': 'الانتقال إلى المحادثة',
  'common.ready': 'جاهز',
  'common.verified': 'تم التحقق',
  'common.not_determined': 'غير محدد',

  // Chat essentials
  'chat.type_message': 'اكتب رسالة…',
  'chat.connect_model_first': 'قم بتوصيل نموذج أولاً',
  'chat.send': 'إرسال',
  'chat.stop': 'إيقاف',
  'chat.model_not_connected': 'النموذج غير متصل',
  'chat.retry': 'إعادة المحاولة',
  'chat.connect_model': 'توصيل النموذج',
  'chat.open_models': 'فتح النماذج',

  // Model picker and prompt cards
  'chat.search': 'بحث',
  'chat.how_can_i_help': 'كيف يمكنني المساعدة؟',
  'prompt.create_component': 'إنشاء مكوّن',
  'prompt.create_component_sub': 'React مع Tailwind',
  'prompt.explain_error': 'شرح خطأ',
  'prompt.explain_error_sub': 'في وحدة تحكم الخادم',
  'prompt.write_tests': 'كتابة اختبارات',
  'prompt.write_tests_sub': 'لنقطة نهاية API',
  'prompt.optimize': 'تحسين',
  'prompt.optimize_sub': 'استعلام SQL',
};
