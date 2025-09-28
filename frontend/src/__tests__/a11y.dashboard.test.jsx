import React from 'react';
import { render } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import Dashboard from '../pages/Dashboard/Dashboard.jsx';
import { I18nProvider } from '../i18n/I18nProvider.jsx';

expect.extend(toHaveNoViolations);

function wrap(ui){ return <I18nProvider initial="vi">{ui}</I18nProvider>; }

describe('Dashboard accessibility', () => {
  it('has no critical a11y violations (baseline)', async () => {
    const { container } = render(wrap(<Dashboard />));
    const results = await axe(container, { rules: { region: { enabled:false } } });
    expect(results).toHaveNoViolations();
  });
});
