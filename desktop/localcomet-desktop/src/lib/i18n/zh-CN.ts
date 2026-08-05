import type { TranslationMap } from './index';

/**
 * Simplified Chinese interface chrome. Keys absent here fall back to English.
 */
export const zhCN: TranslationMap = {
  // Navigation
  'nav.chat': '对话',
  'nav.tasks': '任务',
  'nav.diagnostics': '诊断',
  'nav.audit': '审计',
  'nav.settings': '设置',
  'nav.setup': '设置向导',
  'nav.main': '主导航',
  'nav.later': '稍后',
  'nav.hf_browser': 'HF 模型',
  'app.title_bar': 'LocalComet 应用栏',

  // Sidebar
  'sidebar.label': '会话侧栏',
  'sidebar.new_thread': '新建会话线程',
  'sidebar.collapse': '折叠或展开侧栏',
  'sidebar.toggle': '显示或隐藏对话侧栏',
  'sidebar.new_conversation': '新建对话',
  'sidebar.pinned': '已固定',
  'sidebar.project_labels': '项目标签',
  'conversation.empty': '暂无对话',
  'group.local_chats': '本地对话',
  'group.reserved': '已保留',
  'group.disabled': '已停用',
  'item.new_chat': '新建对话',
  'item.audit': '审计',
  'item.documents': '文档',
  'item.model_not_connected': '模型未连接',
  'item.model_required': '需要模型',
  'item.later': '稍后',

  // Command palette
  'commandPalette.label': '命令面板',
  'commandPalette.search': '查找命令',
  'commandPalette.placeholder': '输入命令…',
  'commandPalette.commands': '可用命令',
  'commandPalette.empty': '没有匹配的命令',
  'commandPalette.command.chat': '打开对话',
  'commandPalette.command.settings': '打开设置',
  'commandPalette.command.setup': '打开本地设置',
  'commandPalette.command.models': '打开模型管理器',
  'commandPalette.command.observability': '打开日志与可观测性',
  'commandPalette.command.showDiagnostics': '显示诊断',
  'commandPalette.command.hideDiagnostics': '隐藏诊断',

  // Theme and language
  'theme.manage': '主题设置',
  'theme.system': '使用系统主题',
  'theme.light': '使用浅色主题',
  'theme.dark': '使用深色主题',
  'lang.select': '选择语言',

  // Settings
  'settings.title': '设置',
  'settings.sections': '设置分区',
  'settings.tab_interface': '界面',
  'settings.tab_models': '模型',
  'settings.tab_observability': '日志',
  'settings.tab_about': '关于',
  'settings.close': '关闭设置',
  'settings.appearance': '外观',
  'settings.theme': '主题',
  'settings.theme_system': '跟随系统',
  'settings.theme_light': '浅色',
  'settings.theme_dark': '深色',
  'settings.language': '语言',
  'settings.diagnostics': '诊断',
  'settings.connection_state': '控制平面连接',
  'settings.show_diagnostics': '显示诊断',
  'settings.hide_diagnostics': '隐藏诊断',
  'settings.about': '关于',
  'settings.application': '应用程序',
  'settings.version': '版本',
  'settings.build': '构建',
  'settings.build_status': '构建状态',
  'settings.capabilities': '当前能力',
  'settings.available': '可用',
  'settings.unavailable': '不可用',

  // Common
  'common.skip_link': '跳转到对话',
  'common.ready': '就绪',
  'common.verified': '已验证',
  'common.not_determined': '未确定',

  // Chat essentials
  'chat.type_message': '输入消息…',
  'chat.connect_model_first': '请先连接模型',
  'chat.send': '发送',
  'chat.stop': '停止',
  'chat.model_not_connected': '模型未连接',
  'chat.retry': '重试',
  'chat.connect_model': '连接模型',
  'chat.open_models': '打开模型',

  // Model picker and prompt cards
  'chat.search': '搜索',
  'chat.how_can_i_help': '需要什么帮助？',
  'prompt.create_component': '创建组件',
  'prompt.create_component_sub': 'React 与 Tailwind',
  'prompt.explain_error': '解释错误',
  'prompt.explain_error_sub': '服务器控制台中的',
  'prompt.write_tests': '编写测试',
  'prompt.write_tests_sub': '用于 API 端点',
  'prompt.optimize': '优化',
  'prompt.optimize_sub': 'SQL 查询',
};
