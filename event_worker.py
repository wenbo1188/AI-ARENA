"""One game in the project's own import namespace; not a security sandbox."""
from pathlib import Path
import json
import sys
from competition.tournament import write_json


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    project = Path(job['project']).resolve()
    sys.path.insert(0, str(project))
    from arena.bot import BotSpec
    from arena.runner import run_match, save_replay
    event = job['event']
    specs = []
    for seat, participant in enumerate(job['bots']):
        path = str(Path(participant['bot']).resolve())
        template = job.get('bot_command')
        command = ([token.format(bot=path, seat=seat, python=sys.executable) for token in template]
                   if template else [sys.executable, '-u', path])
        specs.append(BotSpec(participant['name'], command, str(Path(path).parent)))
    options = ({'team_size': 4, 'pick_mode': 'blind', 'max_rounds': event['max_rounds']}
               if event['game'] == 'octopath' else {'stage': event['stage'], 'ticks': event['ticks']})
    result = run_match(event['game'], specs, seed=job['seed'], **options)
    dest = job['replay']
    save_replay(result, dest + '.json', dest + '.html')
    write_json(job['result'], dict(scores=result.scores, ticks=result.ticks, stats=result.stats,
                                  fixture={'seed':job['seed'], 'bots':[b['name'] for b in job['bots']],
                                           'event':event}))


if __name__ == '__main__':
    main()
