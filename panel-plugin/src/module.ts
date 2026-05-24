import { PanelPlugin } from '@grafana/data';
import { StorageBreakdownPanel } from './components/StorageBreakdownPanel';
import { DEFAULT_OPTIONS, PanelOptions } from './types';

export const plugin = new PanelPlugin<PanelOptions>(StorageBreakdownPanel).setPanelOptions((builder) => {
  return builder
    .addTextInput({
      path: 'metricPrefix',
      name: 'Metric prefix',
      description: 'Used for default queries when the panel is freshly added. Matches your exporter\'s metric_prefix.',
      defaultValue: DEFAULT_OPTIONS.metricPrefix,
    })
    .addBooleanSwitch({
      path: 'showFree',
      name: 'Show free space',
      description: 'Render the implied free-space segment (size minus used) at the end of each bar.',
      defaultValue: DEFAULT_OPTIONS.showFree,
    })
    .addBooleanSwitch({
      path: 'showOther',
      name: 'Show Other residual',
      description: 'Render a residual segment for bytes that are used but not in any configured category.',
      defaultValue: DEFAULT_OPTIONS.showOther,
    })
    .addNumberInput({
      path: 'rowHeight',
      name: 'Row height (px)',
      defaultValue: DEFAULT_OPTIONS.rowHeight,
      settings: { min: 8, max: 80, integer: true },
    })
    .addSelect({
      path: 'sortMode',
      name: 'Row sort',
      defaultValue: DEFAULT_OPTIONS.sortMode,
      settings: {
        options: [
          { value: 'node-asc',  label: 'Node A→Z' },
          { value: 'node-desc', label: 'Node Z→A' },
          { value: 'used-desc', label: 'Most used first' },
          { value: 'used-asc',  label: 'Least used first' },
        ],
      },
    })
    .addCustomEditor({
      id: 'categories',
      path: 'categories',
      name: 'Category palette',
      description: 'Per-category color and label. id must match the `category` label your exporter emits.',
      defaultValue: DEFAULT_OPTIONS.categories,
      editor: function CategoriesEditor() {
        // The categories array is large; keep the default editor as a
        // raw JSON paste field rather than building a per-row UI.
        // Users who want a per-row UI can edit the dashboard JSON.
        return null;
      },
    });
});
