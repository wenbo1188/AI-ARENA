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

GAME='octopath'
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
    from arena.games.octopath.battle import Battle,Unit
    from arena.games.octopath.data import SKILLS,LATENT_SKILLS,TRAVELERS
    from arena.games.octopath import loadout as LO
    import random

    class ArenaHPTests(unittest.TestCase):
        def test_all_travelers_start_with_bonus_and_full_hp(self):
            for key,base in TRAVELERS.items():
                u=Unit(0,0,key,0)
                self.assertEqual(u.max_hp,base['hp']+1000)
                self.assertEqual(u.hp,u.max_hp)
                self.assertEqual(u.max_sp,base['sp'])
        def test_bonus_after_subjob_and_support(self):
            for key,t in TRAVELERS.items():
                for job in LO.JOB_ZH:
                    if job==t['job_en']:continue
                    u=Unit(0,0,key,0,{'sub_job':job,'supports':['hale_and_hearty']})
                    expected=int(t['hp']*(1+LO.JOB_BONUS[job].get('hp',0)/100))+500+1000
                    self.assertEqual(u.max_hp,expected)
                    self.assertEqual(u.hp,expected)
        def test_observation_and_replay_report_final_hp(self):
            g=CLS(seed=12);picks=list(TRAVELERS)[:4]
            g.step([{'pick':picks},{'pick':picks}]);g.step([{'loadout':[]},{'loadout':[]}])
            for team in (0,1):
                for i,u in enumerate(g.observe(team)['me']):
                    self.assertEqual(u['max_hp'],TRAVELERS[picks[i]]['hp']+1000)
                    self.assertEqual(g.replay_meta()['unit_max'][team][i][0],u['max_hp'])
            self.assertEqual(g.init_message(0)['arena_rules'],g.replay_meta()['arena_rules'])
            self.assertEqual(g.init_message(0)['arena_rules']['hp_bonus'],1000)
        def test_first_round_divine_and_full_power_retained(self):
            job='Thief'
            skills=[s for s in LO.job_grid(job) if s not in LO.free_skills(job)]
            lo,notes=LO.validate(['partitio'],[{'sub_job':job,'learn':skills,'supports':['full_power']}])
            self.assertFalse(notes)
            b=Battle([['partitio'],['hikari']],random.Random(12),loadouts=[lo,[{}]])
            u=b.teams[0][0]
            self.assertEqual(b.round,1);self.assertEqual(u.latent,100)
            self.assertTrue(b.usable(u,LO.job_divine(job),latent=True))
        def test_percentage_poison_uses_new_max_hp(self):
            b=Battle([['hikari'],['osvald']],random.Random(12))
            u=b.current;u.st['poison']=2;before=u.hp
            b.act({'skill':'defend'})
            self.assertEqual(before-u.hp,int(u.max_hp/6))

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
        def test_original_formula(self): self.assertEqual(self.hit(),int((300*1.3-200/2)*2*1.36328125))
        def test_weakness(self): self.assertEqual(self.hit(weak=True),int((300*1.3-100)*2*1.36328125*1.3))
        def test_break_does_not_stack(self): self.assertEqual(self.hit(weak=True,broken=True),self.hit(broken=True))
        def test_buff_outside_base_stats(self): self.assertEqual(self.hit(buffed=True),int((300*1.3-100)*2*1.36328125*1.5))
        def test_critical_multiplier(self):
            b,a,t=self.setup_battle();t.weak=[]
            d=b._hit(a,t,'phys','sword',1,set(),{'invocation':1.3,'ratio':2,'crit_chance':1})
            self.assertEqual(d,int((390-100)*2*1.36328125*1.25))
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
        def test_poison_weakness_on_damage_only(self):
            b,a,t=self.setup_battle();t.st['poison_weak']=3
            b._poison(a,t,2);self.assertEqual(t.shields,t.max_shields)
            b.current=t;t.hp=t.max_hp=600;b.act({'skill':'defend'})
            self.assertEqual(t.hp,500);self.assertEqual(t.shields,t.max_shields-1)
        def test_poison_break_and_death(self):
            b,a,t=self.setup_battle();t.st.update(poison=2,poison_weak=3);t.shields=1
            b.current=t;t.hp=t.max_hp=600;b.act({'skill':'defend'})
            self.assertTrue(t.broken);self.assertEqual(t.hp,500)
            b,a,t=self.setup_battle();t.hp=50;t.max_hp=600;t.st['poison']=2
            b.current=t;b.act({'skill':'defend'});self.assertFalse(t.alive)
        def test_regen_twenty_percent(self):
            b,a,t=self.setup_battle();t.max_hp=1000;t.hp=100;t.st['regen']=3
            b.current=t;b.act({'skill':'defend'});self.assertEqual(t.hp,300)
        def test_expanded_damage_cap(self):
            b,a,t=self.setup_battle();a.sup.add('deal_more_damage');t.weak=[]
            self.assertEqual(b._hit(a,t,'elem',None,1,set(),{'invocation':10000}),99999)
        def test_hien_queued_end_of_round(self):
            b,a,t=self.setup_battle();b._dodged=set();b._phys_taken={};b._src=a
            b._skill(a,'hien',LATENT_SKILLS['hien'],0,0,set())
            self.assertEqual(b.hien_pending,[a]);self.assertIsNone(b.pending_double)

if __name__=='__main__': unittest.main()
