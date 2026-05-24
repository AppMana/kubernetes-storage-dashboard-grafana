import React from 'react';
import { css } from '@emotion/css';
import { GrafanaTheme2 } from '@grafana/data';
import { useStyles2 } from '@grafana/ui';
import { RowModel, formatBytes } from '../transform';

interface Props {
  row: RowModel;
}

// Sorted descending by bytes, so the most prominent segments come
// first in the legend. Free is always last for visual consistency.
export const Legend: React.FC<Props> = ({ row }) => {
  const styles = useStyles2(getStyles);
  const items = [...row.segments].sort((a, b) => {
    if (a.category === 'free' && b.category !== 'free') return 1;
    if (b.category === 'free' && a.category !== 'free') return -1;
    return b.bytes - a.bytes;
  });
  return (
    <div className={styles.legend}>
      {items.map((s, i) => (
        <span key={`${s.category}-${i}`} className={styles.chip}>
          <span className={styles.swatch} style={{ background: s.color }} />
          {s.label}
          <em className={styles.value}>{formatBytes(s.bytes)}</em>
        </span>
      ))}
    </div>
  );
};

const getStyles = (theme: GrafanaTheme2) => ({
  legend: css`
    display: flex;
    flex-wrap: wrap;
    gap: ${theme.spacing(0.5)} 0;
    margin-top: ${theme.spacing(0.5)};
    font-size: ${theme.typography.bodySmall.fontSize};
    color: ${theme.colors.text.primary};
  `,
  chip: css`
    display: inline-flex;
    align-items: center;
    gap: ${theme.spacing(0.625)};
    white-space: nowrap;
    margin-right: ${theme.spacing(1.75)};
  `,
  swatch: css`
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  `,
  value: css`
    color: ${theme.colors.text.secondary};
    font-style: normal;
    margin-left: ${theme.spacing(0.25)};
  `,
});
