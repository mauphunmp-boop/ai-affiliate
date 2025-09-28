import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { NotificationProvider, useNotify } from '../../components/NotificationProvider.jsx';

function Demo() {
  const notify = useNotify();
  return <button onClick={() => { notify('error', 'Network fail'); }}>fire</button>;
}

describe('NotificationProvider collapse', () => {
  test('duplicate error suppressed within collapse window', async () => {
    render(<NotificationProvider collapseNetworkErrorsMs={1200}><Demo /></NotificationProvider>);
    const btn = screen.getByText('fire');
    await act(async () => { btn.click(); });
    expect(await screen.findByText('Network fail')).toBeInTheDocument();
    await act(async () => { btn.click(); }); // second duplicate soon
    // Should still be only one snackbar text visible
    const alerts = screen.getAllByText('Network fail');
    expect(alerts.length).toBe(1);
  });
});
