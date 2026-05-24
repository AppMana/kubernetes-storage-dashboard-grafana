import React from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import { useStyles2 } from '@grafana/ui';
import { RowModel, formatBytes } from '../transform';

interface Props {
  row: RowModel;
  rowHeight: number;
  showNodeLabel: boolean;
}

export const DiskRow: React.FC<Props> = ({ row, rowHeight, showNodeLabel }) => {
  const styles = useStyles2((theme) => getStyles(theme, rowHeight));
  const usedPct = row.size > 0 ? Math.round((100 * row.used) / row.size) : 0;
  return (
    <div className={styles.row}>
      <div className={styles.header}>
        <span>
          {showNodeLabel ? (
            <strong>{row.node}</strong>
          ) : (
            <span className={styles.nodeSpacer}>&nbsp;</span>
          )}
          <span className={styles.mountpoint}>{row.mountpoint}</span>
        </span>
        <span className={styles.usedSummary}>
          {formatBytes(row.used)} of {formatBytes(row.size)} used{' '}
          <em className={styles.usedPct}>({usedPct}%)</em>
        </span>
      </div>
      <div className={styles.bar}>
        {row.segments.map((s, i) => {
          const pct = (100 * s.bytes) / Math.max(row.size, 1);
          const segPct = pct.toFixed(3);
          const tooltip = `${s.label}: ${formatBytes(s.bytes)} (${pct.toFixed(1)}%)`;
          return (
            <div
              key={`${s.category}-${i}`}
              title={tooltip}
              className={styles.segment}
              style={{ width: `${segPct}%`, background: s.color }}
            />
          );
        })}
      </div>
    </div>
  );
};

const getStyles = (theme: GrafanaTheme2, rowHeight: number) => ({
  row: css`
    margin-top: ${theme.spacing(1.5)};
  `,
  header: css`
    display: flex;
    justify-content: space-between;
    margin-bottom: ${theme.spacing(0.75)};
    font-size: ${theme.typography.bodySmall.fontSize};
    color: ${theme.colors.text.secondary};
  `,
  nodeSpacer: css`
    color: transparent;
  `,
  mountpoint: css`
    margin-left: ${theme.spacing(1)};
    font-family: ${theme.typography.fontFamilyMonospace};
    font-size: ${theme.typography.bodySmall.fontSize};
    color: ${theme.colors.text.secondary};
  `,
  usedSummary: css`
    color: ${theme.colors.text.primary};
  `,
  usedPct: css`
    color: ${theme.colors.text.secondary};
    font-style: normal;
  `,
  bar: css`
    display: flex;
    height: ${rowHeight}px;
    border-radius: ${theme.shape.radius.default};
    overflow: hidden;
    background: ${theme.colors.background.secondary};
    box-shadow: inset 0 0 0 1px ${theme.colors.border.weak};
  `,
  segment: css`
    height: 100%;
    border-right: 1px solid rgba(0, 0, 0, 0.25);
    &:last-child { border-right: 0; }
  `,
});
