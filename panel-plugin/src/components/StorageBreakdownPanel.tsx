import React, { useMemo } from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2, PanelProps } from '@grafana/data';
import { useStyles2 } from '@grafana/ui';
import { PanelOptions } from '../types';
import { transform, formatBytes } from '../transform';
import { DiskRow } from './DiskRow';
import { Legend } from './Legend';

type Props = PanelProps<PanelOptions>;

// Panel entry component. Receives Grafana's query results as
// `data.series` and the user's panel options as `options`. Groups
// frames by refId, runs `transform`, renders one DiskRow + Legend
// per (node, mountpoint).
export const StorageBreakdownPanel: React.FC<Props> = ({ data, options }) => {
  const styles = useStyles2(getStyles);

  const rows = useMemo(() => {
    const framesByRef = {
      size: data.series.filter((f) => f.refId === 'size'),
      used: data.series.filter((f) => f.refId === 'used'),
      categories: data.series.filter((f) => f.refId === 'categories'),
      longhorn: data.series.filter((f) => f.refId === 'longhorn'),
    };
    return transform({
      ...framesByRef,
      categoryDefs: options.categories,
      showFree: options.showFree,
      showOther: options.showOther,
      sortMode: options.sortMode,
    });
  }, [data.series, options.categories, options.showFree, options.showOther, options.sortMode]);

  const totals = useMemo(() => {
    let size = 0;
    let used = 0;
    for (const r of rows) {
      size += r.size;
      used += r.used;
    }
    return { size, used };
  }, [rows]);

  if (rows.length === 0) {
    return <div className={styles.empty}>No storage data. Check that your exporter is scraping and the queries match the metric prefix.</div>;
  }

  const summaryPct = totals.size > 0 ? Math.round((100 * totals.used) / totals.size) : 0;
  let lastNode: string | null = null;

  return (
    <div className={styles.root}>
      <div className={styles.summary}>
        {formatBytes(totals.used)} of {formatBytes(totals.size)} used across{' '}
        {rows.length} disks ({summaryPct}%)
      </div>
      {rows.map((row) => {
        const showNodeLabel = row.node !== lastNode;
        lastNode = row.node;
        return (
          <div key={`${row.node}|${row.mountpoint}`}>
            <DiskRow row={row} rowHeight={options.rowHeight} showNodeLabel={showNodeLabel} />
            <Legend row={row} />
          </div>
        );
      })}
    </div>
  );
};

const getStyles = (theme: GrafanaTheme2) => ({
  root: css`
    padding: ${theme.spacing(0.5, 1)};
    font-family: ${theme.typography.fontFamily};
    color: ${theme.colors.text.primary};
    overflow-y: auto;
    height: 100%;
  `,
  summary: css`
    color: ${theme.colors.text.secondary};
    margin-bottom: ${theme.spacing(0.75)};
    font-size: ${theme.typography.body.fontSize};
  `,
  empty: css`
    padding: ${theme.spacing(2)};
    color: ${theme.colors.text.secondary};
    font-style: italic;
  `,
});
