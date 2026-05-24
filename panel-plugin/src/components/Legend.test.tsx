import React from 'react';
import { render, screen } from '@testing-library/react';
import { Legend } from './Legend';
import { RowModel } from '../transform';

const row: RowModel = {
  node: 'n1',
  mountpoint: '/',
  size: 1000,
  used: 700,
  segments: [
    { category: 'free', bytes: 300, color: '#000', label: 'Free' },
    { category: 'home', bytes: 100, color: '#000', label: 'Home' },
    { category: 'journald', bytes: 600, color: '#000', label: 'Journald logs' },
  ],
  free: 300,
  other: 0,
};

describe('<Legend>', () => {
  it('lists every segment label', () => {
    render(<Legend row={row} />);
    expect(screen.getByText('Home')).toBeInTheDocument();
    expect(screen.getByText('Journald logs')).toBeInTheDocument();
    expect(screen.getByText('Free')).toBeInTheDocument();
  });

  it('sorts descending by bytes with Free pinned last', () => {
    const { container } = render(<Legend row={row} />);
    const html = container.innerHTML;
    const journaldAt = html.indexOf('Journald logs');
    const homeAt = html.indexOf('Home');
    const freeAt = html.indexOf('Free');
    expect(journaldAt).toBeGreaterThan(-1);
    expect(homeAt).toBeGreaterThan(-1);
    expect(freeAt).toBeGreaterThan(-1);
    expect(journaldAt).toBeLessThan(homeAt);
    expect(homeAt).toBeLessThan(freeAt);
  });
});
