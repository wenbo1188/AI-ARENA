// The edit, cut to the v8 music: the Octopath II battle theme at 128 BPM (beat 0.46875 s, bar 1.875 s), 32 bars.
// Every scene starts on a bar line; the title lands on the drop after the silent break (24.375).
import type { TimelineEntry } from './engine/engine';
import type { SceneClass } from './engine/scene';

const modules = import.meta.glob<{ default: SceneClass }>('./scenes/*.ts');
const scene = (name: string) => () => {
  const m = modules[`./scenes/${name}.ts`];
  return m ? m() : Promise.reject(new Error(`scene module not found: scenes/${name}.ts`));
};

export function makeTimeline(): TimelineEntry[] {
  const E = (id: string, file: string, start: number, end: number, extra: Partial<TimelineEntry> = {}): TimelineEntry =>
    ({ id, load: scene(file), start, end, ...extra });
  const BAR = 1.875, b = (n: number) => n * BAR;
  return [
    E('open', 'reel', b(0), b(2), { params: { reel: 'open' } }),
    E('city', 'city', b(2), b(5)),
    E('masters', 'masters', b(5), b(8)),
    E('seals', 'seals', b(8), b(10)),
    E('rift', 'rift', b(10), b(14)),
    E('era1', 'era', b(14), b(18), { params: { era: 0 } }),
    E('era2', 'era', b(18), b(21), { params: { era: 1 } }),
    E('era3', 'era', b(21), b(25), { params: { era: 2 } }),
    E('montage', 'reel', b(25), b(31), { params: { reel: 'montage' } }),
    E('finale', 'finale', b(31), b(39)),
  ];
}
