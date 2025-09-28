import React from 'react';
import { render, screen } from '@testing-library/react';
import { autoHighlight } from '../components/GlossaryTerm.jsx';

function Wrapper({ text }) { return <p>{autoHighlight(text)}</p>; }

describe('Glossary autoHighlight', () => {
  it('wraps known terms with tooltip span', () => {
    render(<Wrapper text="Tạo shortlink cho merchant mới" />);
    const el = screen.getByText(/shortlink/i);
    expect(el).toHaveAttribute('data-glossary-term','shortlink');
  });
});
