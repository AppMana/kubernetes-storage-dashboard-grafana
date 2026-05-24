// Joins the four query results (size, used, categories, longhorn) by
// (node, mountpoint) and produces one RowModel per disk. This is the
// piece every test gets to exercise: the React component is a thin
// shell on top of the RowModel shape.

import { DataFrame, getDisplayProcessor, GrafanaTheme2 } from '@grafana/data';
import { CategoryDef, FREE_COLOR, OTHER_COLOR } from './types';

export interface Segment {
  category: string;
  bytes: number;
  color: string;
  label: string;
}

export interface RowModel {
  node: string;
  mountpoint: string;
  size: number;
  used: number;
  segments: Segment[];
  free: number;
  other: number;
}

// Pull the latest numeric value out of a Grafana DataFrame field. Each
// query result is a frame; we want the most recent point.
function lastValue(frame: DataFrame): number | undefined {
  const valueField = frame.fields.find((f) => f.type === 'number');
  if (!valueField || valueField.values.length === 0) {
    return undefined;
  }
  return valueField.values[valueField.values.length - 1];
}

// Pull a label value out of a DataFrame. Prometheus query results
// land as a labels object on every value field.
function getLabel(frame: DataFrame, key: string): string | undefined {
  const valueField = frame.fields.find((f) => f.type === 'number');
  return valueField?.labels?.[key];
}

interface FrameKey {
  node: string;
  mountpoint: string;
}

function indexByNodeMountpoint(frames: DataFrame[]): Map<string, { frame: DataFrame; value: number } & FrameKey> {
  const out = new Map<string, { frame: DataFrame; value: number; node: string; mountpoint: string }>();
  for (const frame of frames) {
    const v = lastValue(frame);
    if (v === undefined) continue;
    const node = getLabel(frame, 'node') ?? '';
    const mountpoint = getLabel(frame, 'mountpoint') ?? '';
    if (!node) continue;
    out.set(`${node}|${mountpoint}`, { frame, value: v, node, mountpoint });
  }
  return out;
}

// Kubelet stats give us mountpoint="imageFs" / mountpoint="ephemeral",
// which aren't real mounts. Pick the canonical mountpoint to attribute
// them to: prefer "/", otherwise the first known mountpoint on the
// node.
function resolveSyntheticMountpoint(
  mp: string,
  node: string,
  known: Set<string>,
): string {
  if (mp !== 'imageFs' && mp !== 'ephemeral') return mp;
  if (known.has(`${node}|/`)) return '/';
  // first mountpoint we have for this node
  for (const key of known) {
    const [n, m] = key.split('|');
    if (n === node) return m;
  }
  return '/';
}

// Same disk-path → mountpoint mapping the JS dashboard did: pick the
// longest mountpoint prefix the disk_path is rooted in.
function resolveLonghornMountpoint(
  diskPath: string,
  node: string,
  nodeMountpoints: string[],
): string {
  const normalized = diskPath.replace(/\/+$/, '') || '/';
  let best = '/';
  let bestLen = -1;
  for (const mp of nodeMountpoints) {
    const prefix = mp === '/' ? '/' : mp + '/';
    if (normalized === mp || normalized.startsWith(prefix)) {
      if (mp.length > bestLen) {
        best = mp;
        bestLen = mp.length;
      }
    }
  }
  if (bestLen < 0) {
    return nodeMountpoints.includes('/') ? '/' : (nodeMountpoints[0] ?? '/');
  }
  return best;
}

export interface TransformInput {
  size: DataFrame[];
  used: DataFrame[];
  categories: DataFrame[];
  longhorn: DataFrame[];
  categoryDefs: CategoryDef[];
  showFree: boolean;
  showOther: boolean;
  sortMode: 'node-asc' | 'node-desc' | 'used-desc' | 'used-asc';
}

export function transform(input: TransformInput): RowModel[] {
  const sizes = indexByNodeMountpoint(input.size);
  const useds = indexByNodeMountpoint(input.used);

  // Build the set of known (node, mountpoint) keys, which are the rows
  // we know the denominator for.
  const knownKeys = new Set(sizes.keys());

  // Per-row category accumulators.
  const categoryBytes = new Map<string, Map<string, number>>();
  const recordCategory = (key: string, category: string, bytes: number) => {
    if (!categoryBytes.has(key)) categoryBytes.set(key, new Map());
    const inner = categoryBytes.get(key)!;
    inner.set(category, (inner.get(category) ?? 0) + bytes);
  };

  // categories[] frames: one series per (node, mountpoint, category).
  for (const frame of input.categories) {
    const v = lastValue(frame);
    if (v === undefined) continue;
    const node = getLabel(frame, 'node') ?? '';
    const mountpointRaw = getLabel(frame, 'mountpoint') ?? '';
    const category = getLabel(frame, 'category') ?? '';
    if (!node || !category) continue;
    const mountpoint = resolveSyntheticMountpoint(mountpointRaw, node, knownKeys);
    recordCategory(`${node}|${mountpoint}`, category, v);
  }

  // longhorn series carry (node, disk_path) and need to land on the
  // right mountpoint via longest-prefix match.
  const nodeMountpoints = new Map<string, string[]>();
  for (const key of knownKeys) {
    const [n, m] = key.split('|');
    if (!nodeMountpoints.has(n)) nodeMountpoints.set(n, []);
    nodeMountpoints.get(n)!.push(m);
  }
  for (const frame of input.longhorn) {
    const v = lastValue(frame);
    if (v === undefined) continue;
    const node = getLabel(frame, 'node') ?? '';
    const diskPath = getLabel(frame, 'disk_path') ?? '/';
    if (!node) continue;
    const mps = nodeMountpoints.get(node) ?? ['/'];
    const mountpoint = resolveLonghornMountpoint(diskPath, node, mps);
    recordCategory(`${node}|${mountpoint}`, 'longhorn', v);
  }

  const rows: RowModel[] = [];

  for (const [key, sizeEntry] of sizes) {
    const usedEntry = useds.get(key);
    const used = usedEntry?.value ?? 0;
    const cats = categoryBytes.get(key) ?? new Map();

    // Build segments in the same order as the configured palette so
    // colors are consistent across rows.
    const segments: Segment[] = [];
    let seenKnown = 0;
    for (const def of input.categoryDefs) {
      const bytes = cats.get(def.id) ?? 0;
      if (bytes <= 0) continue;
      segments.push({ category: def.id, bytes, color: def.color, label: def.label });
      seenKnown += bytes;
    }

    const other = Math.max(0, used - seenKnown);
    const free = Math.max(0, sizeEntry.value - used);
    if (input.showOther && other > 0) {
      segments.push({ category: 'other', bytes: other, color: OTHER_COLOR, label: 'Other' });
    }
    if (input.showFree && free > 0) {
      segments.push({ category: 'free', bytes: free, color: FREE_COLOR, label: 'Free' });
    }

    rows.push({
      node: sizeEntry.node,
      mountpoint: sizeEntry.mountpoint,
      size: sizeEntry.value,
      used,
      segments,
      free,
      other,
    });
  }

  switch (input.sortMode) {
    case 'node-asc':
      rows.sort((a, b) => a.node.localeCompare(b.node) || a.mountpoint.localeCompare(b.mountpoint));
      break;
    case 'node-desc':
      rows.sort((a, b) => b.node.localeCompare(a.node) || a.mountpoint.localeCompare(b.mountpoint));
      break;
    case 'used-desc':
      rows.sort((a, b) => b.used - a.used);
      break;
    case 'used-asc':
      rows.sort((a, b) => a.used - b.used);
      break;
  }

  return rows;
}

// Friendly byte formatter (binary). Matches the unit choices the JS
// dashboard used.
export function formatBytes(n: number | null | undefined): string {
  if (n === null || n === undefined || !isFinite(n)) return '';
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  let v = n;
  let i = 0;
  while (Math.abs(v) >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  const precision = v < 10 ? 1 : 0;
  return `${v.toFixed(precision)} ${units[i]}`;
}

// Optional theme-aware formatter for places that want Grafana's full
// formatting machinery.
export function makeFormatter(theme: GrafanaTheme2) {
  return getDisplayProcessor({ theme, field: { config: { unit: 'bytes' } } as any });
}
