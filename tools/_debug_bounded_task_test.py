import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from modules.computer_use_real_actions_ru import build_real_action_plan, run_bounded_interaction_task, _extract_hotkey, _norm
from modules.local_model_gateway_ru import _deterministic_computer_use_call
import json
print('norm=', repr(_norm('Нажми Ctrl+F и прокрути вниз.')))
print('hotkey=', _extract_hotkey('Нажми Ctrl+F и прокрути вниз.'))
print(json.dumps(build_real_action_plan('Нажми Ctrl+F и прокрути вниз.', max_steps=6), ensure_ascii=False, indent=2))
print(json.dumps(run_bounded_interaction_task('Нажми Ctrl+F и прокрути вниз.', simulate=True, max_steps=6), ensure_ascii=False, indent=2))
print(json.dumps(_deterministic_computer_use_call('Нажми Ctrl+F и прокрути вниз.'), ensure_ascii=False, indent=2))
