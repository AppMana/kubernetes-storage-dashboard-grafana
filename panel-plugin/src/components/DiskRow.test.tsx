import React from 'react';
import { render, screen } from '@testing-library/react';
import { DiskRow } from './DiskRow';
import { RowModel } from '../transform';

const row: RowModel = {
  node: 'appmana-002',
  mountpoint: '/',
  size: 1000,
  used: 600,
  segments: [
    { category: 'home', bytes: 200, color: '#EF4444', label: 'Home' },
    { category: 'other', bytes: 400, color: '#9CA3AF', label: 'Other' },
    { category: 'free', bytes: 400, color: '#3a3f46', label: 'Free' },
  ],
  free: 400,
  other: 400,
};

describe('<DiskRow>', () => {
  it('renders the node name when showNodeLabel is true', () => {
    render(<DiskRow row={row} rowHeight={22} showNodeLabel />);
    expect(screen.getByText('appmana-002')).toBeInTheDocument();
  });

  it('hides the node name when showNodeLabel is false', () => {
    render(<DiskRow row={row} rowHeight={22} showNodeLabel={false} />);
    expect(screen.queryByText('appmana-002')).not.toBeInTheDocument();
  });

  it('shows used/total/percent in the header', () => {
    render(<DiskRow row={row} rowHeight={22} showNodeLabel />);
    expect(screen.getByText(/600 B of 1000 B used/)).toBeInTheDocument();
    expect(screen.getByText('(60%)')).toBeInTheDocument();
  });

  it('renders one segment per row.segments entry', () => {
    const { container } = render(<DiskRow row={row} rowHeight={22} showNodeLabel />);
    // Bar is the inner div with `display: flex`. Its children are the segments.
    const segments = container.querySelectorAll('[title^="Home"], [title^="Other"], [title^="Free"]');
    expect(segments.length).toBe(3);
  });
});
