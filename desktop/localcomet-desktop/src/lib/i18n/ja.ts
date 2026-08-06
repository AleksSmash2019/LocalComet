import type { TranslationMap } from './index';

/**
 * Japanese interface chrome. Keys absent here fall back to English.
 */
export const ja: TranslationMap = {
  // Navigation
  'nav.chat': 'チャット',
  'nav.tasks': 'タスク',
  'nav.diagnostics': '診断',
  'nav.settings': '設定',
  'nav.hf_browser': 'HF モデル',

  // Sidebar
  'sidebar.label': 'セッションサイドバー',
  'sidebar.collapse': 'サイドバーを折りたたむ / 展開する',
  'sidebar.toggle': 'チャットサイドバーの表示を切り替える',
  'sidebar.new_conversation': '新しいチャット',
  'conversation.empty': '会話がありません',
  'group.local_chats': 'ローカルチャット',

  // Command palette
  'commandPalette.label': 'コマンドパレット',
  'commandPalette.search': 'コマンドを検索',
  'commandPalette.placeholder': 'コマンドを入力…',
  'commandPalette.commands': '利用できるコマンド',
  'commandPalette.empty': '一致するコマンドがありません',
  'commandPalette.command.chat': 'チャットを開く',
  'commandPalette.command.settings': '設定を開く',
  'commandPalette.command.setup': 'ローカルセットアップを開く',
  'commandPalette.command.models': 'モデルマネージャーを開く',
  'commandPalette.command.observability': 'ログと可観測性を開く',
  'commandPalette.command.showDiagnostics': '診断を表示',
  'commandPalette.command.hideDiagnostics': '診断を非表示',

  // Theme and language
  'theme.manage': 'テーマ設定',
  'lang.select': '言語を選択',

  // Settings
  'settings.title': '設定',
  'settings.sections': '設定セクション',
  'settings.tab_interface': 'インターフェース',
  'settings.tab_models': 'モデル',
  'settings.tab_observability': 'ログ',
  'settings.tab_about': '情報',
  'settings.close': '設定を閉じる',
  'settings.appearance': '外観',
  'settings.theme': 'テーマ',
  'settings.theme_system': 'システム',
  'settings.theme_light': 'ライト',
  'settings.theme_dark': 'ダーク',
  'settings.language': '言語',
  'settings.diagnostics': '診断',
  'settings.connection_state': 'コントロールプレーン接続',
  'settings.show_diagnostics': '診断を表示',
  'settings.hide_diagnostics': '診断を非表示',
  'settings.about': '情報',
  'settings.application': 'アプリケーション',
  'settings.version': 'バージョン',
  'settings.build': 'ビルド',
  'settings.build_status': 'ビルド状態',
  'settings.capabilities': '現在の機能',
  'settings.available': '利用可能',
  'settings.unavailable': '利用不可',

  // Common
  'common.skip_link': 'チャットへ移動',
  'common.ready': '準備完了',
  'common.verified': '検証済み',
  'common.not_determined': '未確定',

  // Chat essentials
  'chat.type_message': 'メッセージを入力…',
  'chat.connect_model_first': '先にモデルを接続してください',
  'chat.send': '送信',
  'chat.stop': '停止',
  'chat.retry': '再試行',
  'chat.connect_model': 'モデルを接続',

  // Model picker and prompt cards
  'chat.how_can_i_help': '何をお手伝いしましょうか？',
  'prompt.create_component': 'コンポーネントを作成',
  'prompt.create_component_sub': 'React と Tailwind',
  'prompt.explain_error': 'エラーを説明',
  'prompt.explain_error_sub': 'サーバーコンソールの',
  'prompt.write_tests': 'テストを書く',
  'prompt.write_tests_sub': 'API エンドポイント向け',
  'prompt.optimize': '最適化',
  'prompt.optimize_sub': 'SQL クエリ',
};
