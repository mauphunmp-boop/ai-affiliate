import { screen, waitForElementToBeRemoved } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import OfflineBanner from '../../components/OfflineBanner.jsx';
import { renderWithProviders } from '../utils/renderWithProviders.jsx';

describe('OfflineBanner', () => {
  test('shows when offline event fired and can dismiss', async () => {
    const user = userEvent.setup();
    // Start online
    Object.defineProperty(window.navigator, 'onLine', { value: true, configurable: true });
  renderWithProviders(<OfflineBanner />);
  expect(screen.queryByText(/Mất kết nối mạng/)).toBeNull();
    // Go offline
    Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true });
    window.dispatchEvent(new Event('offline'));
    expect(await screen.findByText(/Mất kết nối mạng/)).toBeInTheDocument();
    // Dismiss
  await user.click(screen.getByRole('button', { name:/dismiss offline/i }));
  await waitForElementToBeRemoved(() => screen.queryByText(/Mất kết nối mạng/));
  });
});
