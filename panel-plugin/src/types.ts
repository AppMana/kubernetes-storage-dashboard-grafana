// Panel options surfaced in Grafana's right-sidebar editor.
//
// The defaults below are used both as the initial values for new
// panels and as the fallback inside the React component when an
// individual field is undefined.

export interface CategoryDef {
  // Matches the `category` label produced by the exporter.
  id: string;
  // CSS color string for the bar segment.
  color: string;
  // Human-readable label shown in the legend.
  label: string;
}

export interface PanelOptions {
  metricPrefix: string;
  categories: CategoryDef[];
  showFree: boolean;
  showOther: boolean;
  rowHeight: number;
  sortMode: 'node-asc' | 'node-desc' | 'used-desc' | 'used-asc';
}

export const DEFAULT_CATEGORIES: CategoryDef[] = [
  { id: 'containerd-images', color: '#3B82F6', label: 'Containerd images' },
  { id: 'longhorn',          color: '#10B981', label: 'Longhorn data' },
  { id: 'pod-ephemeral',     color: '#A855F7', label: 'Pod ephemeral' },
  { id: 'local-path-pvc',    color: '#64748B', label: 'Local-path PVCs' },
  { id: 'local-path-cache',  color: '#22D3EE', label: 'Local-path caches' },
  { id: 'buildkit',          color: '#FBBF24', label: 'BuildKit' },
  { id: 'dockerd',           color: '#F97316', label: 'Dockerd' },
  { id: 'fscache',           color: '#B877D9', label: 'NFS/SMB cache' },
  { id: 'apt-cache',         color: '#73BF69', label: 'APT cache' },
  { id: 'journald',          color: '#F59E0B', label: 'Journald logs' },
  { id: 'snap',              color: '#FFB357', label: 'Snap' },
  { id: 'home',              color: '#EF4444', label: 'Home' },
  { id: 'crash-dumps',       color: '#FF7383', label: 'Kernel crash dumps' },
  { id: 'swap',              color: '#6B7280', label: 'Swap' },
];

export const DEFAULT_OPTIONS: PanelOptions = {
  metricPrefix: 'nsd',
  categories: DEFAULT_CATEGORIES,
  showFree: true,
  showOther: true,
  rowHeight: 22,
  sortMode: 'node-asc',
};

export const FREE_COLOR = '#3a3f46';
export const OTHER_COLOR = '#9CA3AF';
