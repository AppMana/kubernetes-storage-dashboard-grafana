// Pixel sizes here match the reference JavaScript implementation
// 1:1. Theme-derived spacing made the rows visually loose; explicit
// values match the iPhone-Settings layout the panel is modeled on.

import React from 'react';
import { css } from '@emotion/css';
import { RowModel, formatBytes } from '../transform';

interface Props {
  row: RowModel;
  rowHeight: number;
  showNodeLabel: boolean;
}

const styles = {
  row: (sameNodeAsPrev: boolean) => css`
    margin-top: ${sameNodeAsPrev ? 4 : 18}px;
  `,
  header: css`
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
    font-size: 13px;
  `,
  mountpoint: css`
    color: #888;
    margin-left: 8px;
    font-family: monospace;
    font-size: 12px;
  `,
  usedSummary: css`
    color: #aaa;
  `,
  usedPct: css`
    color: #888;
    font-style: normal;
  `,
  bar: (height: number) => css`
    display: flex;
    height: ${height}px;
    border-radius: 5px;
    overflow: hidden;
    background: #3a3f46;
    box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.05);
  `,
  segment: css`
    height: 100%;
    border-right: 1px solid rgba(0, 0, 0, 0.25);
    &:last-child {
      border-right: 0;
    }
  `,
};

export const DiskRow: React.FC<Props> = ({ row, rowHeight, showNodeLabel }) => {
  const usedPct = row.size > 0 ? Math.round((100 * row.used) / row.size) : 0;
  return (
    <div className={styles.row(!showNodeLabel)}>
      <div className={styles.header}>
        <span>
          {showNodeLabel ? <strong>{row.node}</strong> : <span>&nbsp;</span>}
          <span className={styles.mountpoint}>{row.mountpoint}</span>
        </span>
        <span className={styles.usedSummary}>
          {formatBytes(row.used)} of {formatBytes(row.size)} used{' '}
          <em className={styles.usedPct}>({usedPct}%)</em>
        </span>
      </div>
      <div className={styles.bar(rowHeight)}>
        {row.segments.map((s, i) => {
          const pct = (100 * s.bytes) / Math.max(row.size, 1);
          const tooltip = `${s.label}: ${formatBytes(s.bytes)} (${pct.toFixed(1)}%)`;
          return (
            <div
              key={`${s.category}-${i}`}
              title={tooltip}
              className={styles.segment}
              style={{ width: `${pct.toFixed(3)}%`, background: s.color }}
            />
          );
        })}
      </div>
    </div>
  );
};
