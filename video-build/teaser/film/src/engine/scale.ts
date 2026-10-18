// Output resolution multiplier, read once from the page URL (`?scale=2` renders 3840x2160).
// Scenes keep laying out in logical 1920x1080 px; the engine renders at SCALE x that.
// Kept in its own module so glsl/common.ts can use it without an import cycle through gl.ts.
function readScale() {
  if (typeof location === 'undefined') return 1;
  const raw = Number(new URLSearchParams(location.search).get('scale') ?? '1');
  if (!Number.isFinite(raw) || raw <= 0) return 1;
  // below 1: a quick low-res draft (e.g. 1/3 → 640x360); at 1 and above, integer multiples only
  if (raw < 1) return Math.max(raw, 0.25);
  return Math.min(Math.round(raw), 4);
}

/** Physical pixels per logical pixel of the output (integer 1..4, default 1; a fraction for low-res drafts). */
export const SCALE = readScale();
