import { toDataFrame, FieldType, DataFrame } from '@grafana/data';
import { transform } from './transform';
import { DEFAULT_CATEGORIES } from './types';

// Helper: build a Prometheus-style DataFrame with a single value point.
function frame(value: number, labels: Record<string, string>): DataFrame {
  return toDataFrame({
    fields: [
      { name: 'Time', type: FieldType.time, values: [0] },
      { name: 'Value', type: FieldType.number, values: [value], labels },
    ],
  });
}

const baseInput = {
  showFree: true,
  showOther: true,
  sortMode: 'node-asc' as const,
  categoryDefs: DEFAULT_CATEGORIES,
};

describe('transform', () => {
  it('joins size + used + categories into one row per (node, mountpoint)', () => {
    const rows = transform({
      ...baseInput,
      size: [frame(1000, { node: 'n1', mountpoint: '/' })],
      used: [frame(400, { node: 'n1', mountpoint: '/' })],
      categories: [
        frame(100, { node: 'n1', mountpoint: '/', category: 'home' }),
        frame(200, { node: 'n1', mountpoint: '/', category: 'journald' }),
      ],
      longhorn: [],
    });
    expect(rows).toHaveLength(1);
    const r = rows[0];
    expect(r.node).toBe('n1');
    expect(r.mountpoint).toBe('/');
    expect(r.size).toBe(1000);
    expect(r.used).toBe(400);
    const segCats = r.segments.map((s) => s.category);
    expect(segCats).toContain('home');
    expect(segCats).toContain('journald');
  });

  it('remaps mountpoint=imageFs to / when known on the node', () => {
    const rows = transform({
      ...baseInput,
      size: [frame(1000, { node: 'n1', mountpoint: '/' })],
      used: [frame(500, { node: 'n1', mountpoint: '/' })],
      categories: [
        frame(300, { node: 'n1', mountpoint: 'imageFs', category: 'containerd-images' }),
      ],
      longhorn: [],
    });
    const r = rows[0];
    const imageSeg = r.segments.find((s) => s.category === 'containerd-images');
    expect(imageSeg).toBeDefined();
    expect(imageSeg!.bytes).toBe(300);
  });

  it('computes free and other residual correctly', () => {
    const rows = transform({
      ...baseInput,
      size: [frame(1000, { node: 'n1', mountpoint: '/' })],
      used: [frame(600, { node: 'n1', mountpoint: '/' })],
      categories: [
        frame(200, { node: 'n1', mountpoint: '/', category: 'home' }),
      ],
      longhorn: [],
    });
    const r = rows[0];
    expect(r.free).toBe(400); // size - used
    expect(r.other).toBe(400); // used - sum of known categories
    const freeSeg = r.segments.find((s) => s.category === 'free');
    const otherSeg = r.segments.find((s) => s.category === 'other');
    expect(freeSeg?.bytes).toBe(400);
    expect(otherSeg?.bytes).toBe(400);
  });

  it('omits free and other when their toggles are off', () => {
    const rows = transform({
      ...baseInput,
      showFree: false,
      showOther: false,
      size: [frame(1000, { node: 'n1', mountpoint: '/' })],
      used: [frame(600, { node: 'n1', mountpoint: '/' })],
      categories: [frame(200, { node: 'n1', mountpoint: '/', category: 'home' })],
      longhorn: [],
    });
    const cats = rows[0].segments.map((s) => s.category);
    expect(cats).not.toContain('free');
    expect(cats).not.toContain('other');
  });

  it('attributes longhorn series to the longest matching mountpoint prefix', () => {
    const rows = transform({
      ...baseInput,
      size: [
        frame(1000, { node: 'n1', mountpoint: '/' }),
        frame(2000, { node: 'n1', mountpoint: '/mnt/data' }),
      ],
      used: [
        frame(100, { node: 'n1', mountpoint: '/' }),
        frame(500, { node: 'n1', mountpoint: '/mnt/data' }),
      ],
      categories: [],
      longhorn: [frame(400, { node: 'n1', disk_path: '/mnt/data/longhorn' })],
    });
    const mntData = rows.find((r) => r.mountpoint === '/mnt/data')!;
    expect(mntData.segments.find((s) => s.category === 'longhorn')?.bytes).toBe(400);
    const root = rows.find((r) => r.mountpoint === '/')!;
    expect(root.segments.find((s) => s.category === 'longhorn')).toBeUndefined();
  });

  it('sorts rows by node-asc by default', () => {
    const rows = transform({
      ...baseInput,
      size: [
        frame(1, { node: 'zeta', mountpoint: '/' }),
        frame(1, { node: 'alpha', mountpoint: '/' }),
        frame(1, { node: 'mu', mountpoint: '/' }),
      ],
      used: [],
      categories: [],
      longhorn: [],
    });
    expect(rows.map((r) => r.node)).toEqual(['alpha', 'mu', 'zeta']);
  });

  it('emits zero rows when there is no size frame', () => {
    const rows = transform({
      ...baseInput,
      size: [],
      used: [frame(100, { node: 'n1', mountpoint: '/' })],
      categories: [frame(50, { node: 'n1', mountpoint: '/', category: 'home' })],
      longhorn: [],
    });
    expect(rows).toHaveLength(0);
  });
});
