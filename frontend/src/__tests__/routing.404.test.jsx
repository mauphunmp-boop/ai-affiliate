import { describe, it, expect } from 'vitest';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { render, screen } from '@testing-library/react';
import NotFound from '../pages/NotFound.jsx';

function Dummy() { return <div>Home</div>; }

describe('NotFound routing', () => {
  it('renders 404 page for unknown path', () => {
    render(
      <MemoryRouter initialEntries={['/unknown/path']}> 
        <Routes>
          <Route path='/' element={<Dummy />} />
          <Route path='*' element={<NotFound />} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText('404')).toBeInTheDocument();
    expect(screen.getByText('Không tìm thấy trang')).toBeInTheDocument();
  });
});
