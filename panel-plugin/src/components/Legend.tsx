import React from 'react';
import { css } from '@emotion/css';
import { RowModel, formatBytes } from '../transform';

interface Props {
  row: RowModel;
}

const styles = {
  legend: css`
    display: flex;
    flex-wrap: wrap;
    gap: 4px 0;
    margin-top: 5px;
    font-size: 11px;
    color: #ccc;
  `,
  chip: css`
    display: inline-flex;
    align-items: center;
    gap: 5px;
    white-space: nowrap;
    margin-right: 14px;
  `,
  swatch: css`
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  `,
  value: css`
    color: #888;
    font-style: normal;
    margin-left: 2px;
  `,
};

// Sorted descending by bytes, with Free pinned last for visual
// consistency.
export const Legend: React.FC<Props> = ({ row }) => {
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
