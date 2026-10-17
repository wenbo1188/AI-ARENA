import json
from pathlib import Path
import sys
import unittest
from arena.bot import BotSpec
from arena.runner import run_match

GAME = 'codeside'

def strategy(mode):
    return """import sys,json,time
for line in sys.stdin:
 m=json.loads(line)
 if m['type']=='end': break
 if m['type']=='init': print('{"ready":true}',flush=True); continue
 t=m['tick'];r={'tick':t}
 if 'your_turn' in m:
  if m['your_turn']:
   if m['phase']=='pick':r['pick']=m['available'][:m['pick_count']]
   elif m['phase']=='loadout':r['loadout']=[]
   else:r['action']={'skill':'attack'}
 else:r['actions']={}
 if MODE=='exit' and t==1:sys.exit(2)
 if MODE=='slow' and t==1:time.sleep(1.2)
 if MODE=='json' and t==1:print('broken',flush=True);continue
 if MODE=='action' and t==1:r['actions']=[];r['loadout']=False
 print(json.dumps(r),flush=True)
""".replace('MODE',repr(mode))

class RecoveryTests(unittest.TestCase):
 def run_mode(self,mode):
  specs=[BotSpec('candidate',[sys.executable,'-u','-c',strategy(mode)]),
         BotSpec('other',[sys.executable,'-u','-c',strategy('ok')])]
  opts={'max_rounds':2} if GAME=='octopath' else {'stage':'round1','ticks':8}
  return run_match(GAME,specs,time_limit_ms=1000,**opts)
 def test_late_reply_does_not_stop_or_poison_next_tick(self):
  r=self.run_mode('slow');s=r.stats[0]
  self.assertFalse(s['crashed'],s);self.assertEqual(s['timeouts'],1)
  self.assertGreater(s['accepted_turns'],2)
 def test_malformed_json_recovers(self):
  s=self.run_mode('json').stats[0]
  self.assertFalse(s['crashed'],s);self.assertEqual(s['invalid_lines'],1)
  self.assertEqual(s['timeouts'],0);self.assertGreater(s['accepted_turns'],2)
 def test_invalid_action_types_recover(self):
  s=self.run_mode('action').stats[0]
  self.assertFalse(s['crashed'],s);self.assertEqual(s['invalid_lines'],1)
  self.assertGreater(s['accepted_turns'],2)
 def test_crash_does_not_restart(self):
  s=self.run_mode('exit').stats[0]
  self.assertTrue(s['crashed']);self.assertEqual(s['accepted_turns'],1)

if __name__=='__main__':unittest.main()
