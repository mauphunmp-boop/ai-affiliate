import { screen, render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ErrorBoundary from '../../components/ErrorBoundary.jsx';
import React from 'react';

// Component an toàn (không ném lỗi thật)
function SafeChild(){ return <div data-testid="safe-child">OK</div>; }

// Helper query tolerant với i18n chưa tải (hiển thị key) hoặc đã dịch.
const headingMatcher = /Sự cố không mong muốn|error_boundary_unexpected/i;
const reloadAreaMatcher = /Thử tải lại khu vực|common_reload_area/i;

describe('ErrorBoundary', () => {
  test('mô phỏng lỗi, hiển thị fallback và khôi phục sau reset mà không cần remount', async () => {
    const user = userEvent.setup();

    // 1. Ban đầu: bình thường
    const { rerender } = render(<ErrorBoundary><SafeChild /></ErrorBoundary>);
    expect(screen.getByTestId('safe-child')).toBeInTheDocument();

    // 2. Mô phỏng lỗi bằng prop testError (không throw thật -> tránh noise stderr)
    rerender(<ErrorBoundary testError="Kaboom"><SafeChild /></ErrorBoundary>);
    // Chấp nhận cả key hoặc bản dịch
    expect(screen.getByText(headingMatcher)).toBeInTheDocument();
  const kabooms = screen.getAllByText(/Kaboom/);
  expect(kabooms.length).toBeGreaterThanOrEqual(1);

    // 3. Reset: click nút (gọi this.reset), vì prop testError không đổi nên state sẽ về null và không tái set (logic chỉ set khi testError thay đổi)
    await user.click(screen.getByRole('button', { name: reloadAreaMatcher }));
    expect(screen.getByTestId('safe-child')).toBeInTheDocument();
    // Đảm bảo fallback & message biến mất
    expect(screen.queryByText(headingMatcher)).not.toBeInTheDocument();
    expect(screen.queryByText(/Kaboom/)).not.toBeInTheDocument();
  });
});
