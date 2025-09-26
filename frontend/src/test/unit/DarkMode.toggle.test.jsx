import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ColorModeProvider, useColorMode } from '../../context/ColorModeContext.jsx';
import React from 'react';

function ToggleProbe(){
  const { dark, toggle } = useColorMode();
  return <button onClick={toggle}>{dark ? 'dark' : 'light'}</button>;
}

describe('Dark mode context', () => {
  test('toggles dark flag', async () => {
    const user = userEvent.setup();
    render(<ColorModeProvider><ToggleProbe /></ColorModeProvider>);
    const btn = screen.getByRole('button');
    const initial = btn.textContent;
    await user.click(btn);
    expect(btn.textContent).not.toBe(initial);
  });
});
