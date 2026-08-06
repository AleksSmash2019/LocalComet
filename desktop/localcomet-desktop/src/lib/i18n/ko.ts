import type { TranslationMap } from './index';

/**
 * Korean interface chrome. Keys absent here fall back to English.
 */
export const ko: TranslationMap = {
  // Navigation
  'nav.chat': '채팅',
  'nav.tasks': '작업',
  'nav.diagnostics': '진단',
  'nav.settings': '설정',
  'nav.hf_browser': 'HF 모델',

  // Sidebar
  'sidebar.label': '세션 사이드바',
  'sidebar.collapse': '사이드바 접기 또는 펼치기',
  'sidebar.toggle': '채팅 사이드바 표시 전환',
  'sidebar.new_conversation': '새 채팅',
  'conversation.empty': '대화 없음',
  'group.local_chats': '로컬 채팅',

  // Command palette
  'commandPalette.label': '명령 팔레트',
  'commandPalette.search': '명령 찾기',
  'commandPalette.placeholder': '명령 입력…',
  'commandPalette.commands': '사용 가능한 명령',
  'commandPalette.empty': '일치하는 명령이 없습니다',
  'commandPalette.command.chat': '채팅 열기',
  'commandPalette.command.settings': '설정 열기',
  'commandPalette.command.setup': '로컬 설치 열기',
  'commandPalette.command.models': '모델 관리자 열기',
  'commandPalette.command.observability': '로그 및 관측 열기',
  'commandPalette.command.showDiagnostics': '진단 표시',
  'commandPalette.command.hideDiagnostics': '진단 숨기기',

  // Theme and language
  'theme.manage': '테마 설정',
  'lang.select': '언어 선택',

  // Settings
  'settings.title': '설정',
  'settings.sections': '설정 섹션',
  'settings.tab_interface': '인터페이스',
  'settings.tab_models': '모델',
  'settings.tab_observability': '로그',
  'settings.tab_about': '정보',
  'settings.close': '설정 닫기',
  'settings.appearance': '모양',
  'settings.theme': '테마',
  'settings.theme_system': '시스템',
  'settings.theme_light': '라이트',
  'settings.theme_dark': '다크',
  'settings.language': '언어',
  'settings.diagnostics': '진단',
  'settings.connection_state': '컨트롤 플레인 연결',
  'settings.show_diagnostics': '진단 표시',
  'settings.hide_diagnostics': '진단 숨기기',
  'settings.about': '정보',
  'settings.application': '애플리케이션',
  'settings.version': '버전',
  'settings.build': '빌드',
  'settings.build_status': '빌드 상태',
  'settings.capabilities': '현재 기능',
  'settings.available': '사용 가능',
  'settings.unavailable': '사용 불가',

  // Common
  'common.skip_link': '채팅으로 이동',
  'common.ready': '준비됨',
  'common.verified': '검증됨',
  'common.not_determined': '확인되지 않음',

  // Chat essentials
  'chat.type_message': '메시지를 입력하세요…',
  'chat.connect_model_first': '먼저 모델을 연결하세요',
  'chat.send': '보내기',
  'chat.stop': '중지',
  'chat.retry': '다시 시도',
  'chat.connect_model': '모델 연결',

  // Model picker and prompt cards
  'chat.how_can_i_help': '무엇을 도와드릴까요?',
  'prompt.create_component': '컴포넌트 만들기',
  'prompt.create_component_sub': 'React 및 Tailwind',
  'prompt.explain_error': '오류 설명',
  'prompt.explain_error_sub': '서버 콘솔에서',
  'prompt.write_tests': '테스트 작성',
  'prompt.write_tests_sub': 'API 엔드포인트용',
  'prompt.optimize': '최적화',
  'prompt.optimize_sub': 'SQL 쿼리',
};
