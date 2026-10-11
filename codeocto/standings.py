"""Rank only complete, verified schedules using exact rational averages."""
import argparse
from collections import Counter
from fractions import Fraction
import html
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/'COMPETITION.json').read_text(encoding='utf-8'))

def aggregate(manifest,matches):
    from kit import fixtures,sha
    if manifest.get('game')!=CFG['game'] or manifest.get('competition_sha256')!=sha(ROOT/'COMPETITION.json'):
        raise ValueError('赛事规则版本不匹配')
    names=sorted(manifest['participants'])
    expected=fixtures(names,manifest['seed'])
    if manifest.get('fixtures')!=expected: raise ValueError('赛程被修改或不完整')
    if len(matches)!=len(expected): raise ValueError('比赛尚未全部完成，不能发布正式排名')
    by_id={m['match']:m for m in matches}
    if len(by_id)!=len(matches): raise ValueError('重复比赛编号')
    rows={n:{s:{'played':0,'win':0,'draw':0,'loss':0,'points':0} for s in CFG['stages']} for n in names}
    for f in expected:
        m=by_id.get(f['match'])
        if m is None or any(m.get(k)!=v for k,v in f.items()): raise ValueError('对阵、种子或赛段不匹配')
        sc=m.get('scores')
        if not isinstance(sc,list) or len(sc)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) or x<0 for x in sc):
            raise ValueError('比分须为非负有限数值')
        for i,n in enumerate(f['bots']):
            r=rows[n][f['stage']]
            result='win' if sc[i]>sc[1-i] else 'draw' if sc[i]==sc[1-i] else 'loss'
            r['played']+=1;r[result]+=1;r['points']+={'win':3,'draw':1,'loss':0}[result]
    ranked=[]
    for n,stages in rows.items():
        total=Fraction(0)
        for row in stages.values():
            v=Fraction(row['points'],row['played']);total+=v/len(stages)
            row.update(average=float(v),average_exact=str(v))
        ranked.append({'bot':n,'stages':stages,'total':float(total),'total_exact':str(total)})
    ranked.sort(key=lambda r:(-Fraction(r['total_exact']),r['bot']))
    last=None;rank=0
    for i,row in enumerate(ranked,1):
        if Fraction(row['total_exact'])!=last: rank=i
        row['rank']=rank;last=Fraction(row['total_exact'])
    return {'game':CFG['game'],'points':{'win':3,'draw':1,'loss':0},'tie_policy':'shared_rank','leaderboard':ranked}

def write_results(result,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'overall.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    cols=''.join('<th>'+html.escape(s)+'</th>' for s in CFG['stages'])
    rows=[]
    for r in result['leaderboard']:
        cells=[str(r['rank']),html.escape(r['bot'])]+[f"{r['stages'][s]['average']:.4f}" for s in CFG['stages']]+[f"{r['total']:.4f}"]
        rows.append('<tr>'+''.join('<td>'+v+'</td>' for v in cells)+'</tr>')
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>比赛总榜</title><style>body{font:16px/1.8 system-ui;max-width:1000px;margin:40px auto;background:#faf8f2;color:#282722}td,th{padding:12px 24px;border-bottom:1px solid #ddd}table{border-collapse:collapse}</style>'
    page+='<h1>'+html.escape(CFG['title'])+'</h1><p>胜3平1负0；赛段场均积分等权平均，同分并列。显示四位小数，按精确分数排名。</p><table><tr><th>名次</th><th>AI</th>'+cols+'<th>总分</th></tr>'+''.join(rows)+'</table></html>'
    (out/'overall.html').write_text(page,encoding='utf-8')

def main():
    p=argparse.ArgumentParser();p.add_argument('results',type=Path);a=p.parse_args()
    try:
        m=json.loads((a.results/'schedule.json').read_text(encoding='utf-8'))
        games=json.loads((a.results/'matches.json').read_text(encoding='utf-8'))
        write_results(aggregate(m,games),a.results);print(a.results/'overall.html');return 0
    except (OSError,ValueError,KeyError) as e: print('不能发布总榜：',e);return 1

if __name__=='__main__': raise SystemExit(main())
