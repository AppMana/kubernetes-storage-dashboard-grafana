// Integration-style test for the top-level panel. Feeds a complete
// set of fake Grafana DataFrames (one per refId) into the React
// component, asserts that the rendered DOM contains the expected
// summary, rows, segments, and legend entries. Covers the wire
// between transform.ts and the rendering layer.

import React from 'react';
import { render, screen } from '@testing-library/react';
import { toDataFrame, FieldType, DataFrame, EventBusSrv, LoadingState } from '@grafana/data';
import { StorageBreakdownPanel } from './StorageBreakdownPanel';
import { DEFAULT_CATEGORIES, PanelOptions } from '../types';

function series(value: number, labels: Record<string, string>, refId: string): DataFrame {
  return toDataFrame({
    refId,
    fields: [
      { name: 'Time', type: FieldType.time, values: [0] },
      { name: 'Value', type: FieldType.number, values: [value], labels },
    ],
  });
}

const options: PanelOptions = {
  metricPrefix: 'nsd',
  categories: DEFAULT_CATEGORIES,
  showFree: true,
  showOther: true,
  rowHeight: 22,
  sortMode: 'node-asc',
};

function makeProps(seriesArr: DataFrame[]) {
  return {
    id: 1,
    data: {
      series: seriesArr,
      state: LoadingState.Done,
      timeRange: {} as any,
    },
    timeRange: {} as any,
    timeZone: 'browser',
    options,
    transparent: false,
    width: 1200,
    height: 600,
    fieldConfig: { defaults: {}, overrides: [] } as any,
    renderCounter: 0,
    title: '',
    onOptionsChange: () => undefined,
    onFieldConfigChange: () => undefined,
    onChangeTimeRange: () => undefined,
    replaceVariables: (v: string) => v,
    eventBus: new EventBusSrv(),
  } as any;
}

describe('<StorageBreakdownPanel> integration', () => {
  it('shows an empty-state message when there is no data', () => {
    render(<StorageBreakdownPanel {...makeProps([])} />);
    expect(screen.getByText(/No storage data/)).toBeInTheDocument();
  });

  it('renders one row per (node, mountpoint) plus a summary line', () => {
    const frames: DataFrame[] = [
      series(1000, { node: 'alpha', mountpoint: '/' }, 'size'),
      series(2000, { node: 'alpha', mountpoint: '/mnt/data' }, 'size'),
      series(1000, { node: 'beta',  mountpoint: '/' }, 'size'),
      series(400,  { node: 'alpha', mountpoint: '/' }, 'used'),
      series(800,  { node: 'alpha', mountpoint: '/mnt/data' }, 'used'),
      series(600,  { node: 'beta',  mountpoint: '/' }, 'used'),
      series(150,  { node: 'alpha', mountpoint: '/', category: 'home' }, 'categories'),
      series(200,  { node: 'alpha', mountpoint: 'imageFs', category: 'containerd-images' }, 'categories'),
      series(500,  { node: 'beta',  mountpoint: '/', category: 'longhorn' }, 'categories'),
      series(300,  { node: 'alpha', disk_path: '/mnt/data/longhorn' }, 'longhorn'),
    ];
    render(<StorageBreakdownPanel {...makeProps(frames)} />);

    // Summary line: 1800 used of 4000 across 3 disks (45%).
    expect(screen.getByText(/1\.8 KB of 3\.9 KB used across 3 disks/)).toBeInTheDocument();

    // Node labels for the first row of each node.
    expect(screen.getByText('alpha')).toBeInTheDocument();
    expect(screen.getByText('beta')).toBeInTheDocument();

    // Mountpoints shown (sorted: alpha /, alpha /mnt/data, beta /).
    expect(screen.getAllByText('/')).toHaveLength(2);
    expect(screen.getByText('/mnt/data')).toBeInTheDocument();

    // Category labels appear in at least one legend.
    expect(screen.getAllByText('Containerd images').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Longhorn data').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Home').length).toBeGreaterThan(0);
  });

  it('maps the synthetic imageFs mountpoint back to /', () => {
    const frames: DataFrame[] = [
      series(1000, { node: 'n', mountpoint: '/' }, 'size'),
      series(500,  { node: 'n', mountpoint: '/' }, 'used'),
      series(200,  { node: 'n', mountpoint: 'imageFs', category: 'containerd-images' }, 'categories'),
    ];
    const { container } = render(<StorageBreakdownPanel {...makeProps(frames)} />);
    // Only one row visible (the / row), and it has a containerd-images segment.
    const containerdSegment = container.querySelector('[title^="Containerd images: 200 B"]');
    expect(containerdSegment).not.toBeNull();
  });

  it('renders no free segment when showFree=false', () => {
    const frames: DataFrame[] = [
      series(1000, { node: 'n', mountpoint: '/' }, 'size'),
      series(400,  { node: 'n', mountpoint: '/' }, 'used'),
    ];
    const propsNoFree = { ...makeProps(frames), options: { ...options, showFree: false } };
    const { container } = render(<StorageBreakdownPanel {...propsNoFree} />);
    expect(container.querySelector('[title^="Free:"]')).toBeNull();
  });

  it('respects sortMode=used-desc', () => {
    const frames: DataFrame[] = [
      series(1000, { node: 'alpha', mountpoint: '/' }, 'size'),
      series(1000, { node: 'beta',  mountpoint: '/' }, 'size'),
      series(100,  { node: 'alpha', mountpoint: '/' }, 'used'),
      series(900,  { node: 'beta',  mountpoint: '/' }, 'used'),
    ];
    const propsSort = { ...makeProps(frames), options: { ...options, sortMode: 'used-desc' as const } };
    const { container } = render(<StorageBreakdownPanel {...propsSort} />);
    // beta should come before alpha in render order.
    const html = container.innerHTML;
    expect(html.indexOf('beta')).toBeLessThan(html.indexOf('alpha'));
  });
});
