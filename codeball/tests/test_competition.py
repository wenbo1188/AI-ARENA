import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import kit
from arena.bot import BotSpec
from arena.games import get_game
from arena.runner import run_match

GAME='football'
CLS=get_game(GAME)

class RuntimeTests(unittest.TestCase):
    def run_case(self,mode,**kwargs):
        with tempfile.TemporaryDirectory(prefix='arena test ') as tmp:
            path=Path(tmp)/'strategy.py'
            code='''import json,sys,time
for line in sys.stdin:
 m=json.loads(line)
 if m['type']=='end': break
 if MODE=='bad_json': print('not json',flush=True); continue
 if MODE=='nan': print('{"ready":true,"bad":NaN}',flush=True); continue
 if MODE=='memory': a=bytearray(400*1024*1024)
 if MODE=='sleep': time.sleep(.2)
 if MODE=='cpu':
  start=time.process_time()
  while time.process_time()-start<.4: pass
 if MODE=='exit': sys.exit(2)
 if m['type']=='init': print('{"ready":true}',flush=True); continue
 if MODE=='late': time.sleep(.03)
 r={'tick':m['tick']}
 if 'game' in m: r['actions']={}
 elif m['your_turn']:
  if m['phase']=='pick': r['pick']=m['available'][:m['pick_count']]
  elif m['phase']=='loadout': r['loadout']=[]
  else: r['action']={'skill':'attack'}
 if MODE=='tick': r['tick']=m['tick']+1
 print(json.dumps(r),flush=True)
'''.replace('MODE',repr(mode))
            path.write_text(code,encoding='utf-8')
            bots=[BotSpec('candidate',[sys.executable,'-u',str(path)],tmp),kit.spec(ROOT/('bots/quickstart_bot.py' if GAME=='football' else 'bots/octopath/quickstart_bot.py'),'baseline')]
            opts={'ticks':60,'stage':'round1'} if GAME=='football' else {'max_rounds':3}
            return run_match(GAME,bots,**opts,**kwargs)
    def test_game_budget(self):
        g=CLS()
        self.assertEqual(g.match_rules()['memory_mb'],256)
        self.assertEqual(g.official_time_budget_ms(),420000 if GAME=='football' else 60000)
    def test_bad_json_stops(self):
        r=self.run_case('bad_json');self.assertTrue(r.stats[0]['crashed']);self.assertGreater(r.stats[0]['invalid_lines'],0)
    def test_nonfinite_json_stops(self):
        r=self.run_case('nan');self.assertTrue(r.stats[0]['crashed'])
    def test_memory_limit(self):
        r=self.run_case('memory');self.assertTrue(r.stats[0]['crashed'])
    def test_wrong_tick_defaults_without_stopping(self):
        r=self.run_case('tick');self.assertFalse(r.stats[0]['crashed']);self.assertGreater(r.stats[0]['invalid_lines'],0)
    def test_timeout_stops(self):
        r=self.run_case('sleep',time_limit_ms=100);self.assertTrue(r.stats[0]['crashed']);self.assertEqual(r.stats[0]['timeouts'],1)
    def test_exit_continues(self):
        r=self.run_case('exit');self.assertTrue(r.stats[0]['crashed']);self.assertGreater(r.ticks,2)
        self.assertFalse(r.stats[1]['crashed'])
    def test_budget_enforced(self):
        if GAME=='football':
            r=self.run_case('late',total_time_ms=1000,time_limit_ms=1000)
            self.assertTrue(r.stats[0]['crashed']);self.assertIn('总时间',r.stats[0]['crash_reason'])
            self.assertGreater(r.stats[0]['used_ms'],r.stats[0]['cpu_ms'])
        else:
            r=self.run_case('cpu',total_time_ms=80,time_limit_ms=1000)
            self.assertTrue(r.stats[0]['crashed']);self.assertIn('CPU',r.stats[0]['crash_reason'])

if GAME=='octopath':
    from arena.games.octopath.battle import Battle
    from arena.games.octopath.data import SKILLS,LATENT_SKILLS
    import random

    class MathTests(unittest.TestCase):
        def setup_battle(self):
            b=Battle([['hikari'],['osvald']],random.Random(0))
            a,t=b.teams[0][0],b.teams[1][0]
            a.base.update(pa=300,ea=300,acc=999,crit=0)
            t.base.update(pd=200,ed=200,eva=0)
            t.hp=t.max_hp=100000
            b.rng.uniform=lambda x,y: 1.0
            b.rng.random=lambda: .99
            return b,a,t
        def hit(self,weak=False,broken=False,buffed=False):
            b,a,t=self.setup_battle();t.weak=['sword'] if weak else [];t.broken=broken
            if buffed: a.up['pa']=3
            return b._hit(a,t,'phys','sword',1,set(),{'invocation':1.3,'ratio':2})
        def test_original_formula(self): self.assertEqual(self.hit(),int((300*1.3-200/2)*2*1.40625))
        def test_weakness(self): self.assertEqual(self.hit(weak=True),int((300*1.3-100)*2*1.40625*1.3))
        def test_break_does_not_stack(self): self.assertEqual(self.hit(weak=True,broken=True),self.hit(broken=True))
        def test_buff_outside_base_stats(self): self.assertEqual(self.hit(buffed=True),int((300*1.3-100)*2*1.40625*1.5))
        def test_critical_multiplier(self):
            b,a,t=self.setup_battle();t.weak=[]
            d=b._hit(a,t,'phys','sword',1,set(),{'invocation':1.3,'ratio':2,'crit_chance':1})
            self.assertEqual(d,int((390-100)*2*1.40625*1.25))
        def test_heal_scales_defense(self):
            b,a,t=self.setup_battle();a.base['ed']=200;a.base['ea']=999
            n=b._healing_amount(a,'heal_wounds',0)
            a.base['ea']=1;self.assertEqual(n,b._healing_amount(a,'heal_wounds',0))
            a.base['ed']=400;self.assertEqual(2*n,b._healing_amount(a,'heal_wounds',0))
        def test_break_recovers_fixed_sp(self):
            b,a,t=self.setup_battle();a.sup={'inspiriting_break'};a.max_sp=300;a.sp=0
            b._reduce_shields(a,t,100);self.assertEqual(a.sp,20)
        def test_spell_boost_consumption(self):
            b,a,t=self.setup_battle();a.tier=[2,3]
            self.assertEqual(b._spell_tier(a,SKILLS['holy_light']),1);self.assertEqual(a.tier,[2,3])
            self.assertEqual(b._spell_tier(a,SKILLS['fireball']),2);self.assertEqual(a.tier,[2,2])
        def test_beast_howl_no_damage(self):
            self.assertNotIn('kind',LATENT_SKILLS['beast_roar'])
            b,a,t=self.setup_battle();b._src=a;b._boost=0;b._inspired=set()
            hp,shield=t.hp,t.shields
            b._skill(a,'beast_roar',LATENT_SKILLS['beast_roar'],0,0,set())
            self.assertEqual(t.hp,hp);self.assertEqual(t.shields,shield-1);self.assertEqual(t.down,{'pd':3,'ed':3})
        def test_hien_queued_end_of_round(self):
            b,a,t=self.setup_battle();b._dodged=set();b._phys_taken={};b._src=a
            b._skill(a,'hien',LATENT_SKILLS['hien'],0,0,set())
            self.assertEqual(b.hien_pending,[a]);self.assertIsNone(b.pending_double)

if __name__=='__main__': unittest.main()
