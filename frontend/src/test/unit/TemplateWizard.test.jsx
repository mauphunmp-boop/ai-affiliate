import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import TemplateWizard from '../../components/TemplateWizard.jsx';
import { vi } from 'vitest';
import { ColorModeProvider } from '../../context/ColorModeContext.jsx';
import NotificationProvider from '../../components/NotificationProvider.jsx';

vi.mock('../../api/affiliate', () => ({
  upsertAffiliateTemplate: vi.fn().mockResolvedValue({ data: { id: 1 } })
}));

function wrap(ui){
  return <ColorModeProvider><NotificationProvider>{ui}</NotificationProvider></ColorModeProvider>;
}

describe('TemplateWizard', () => {
  test('creates template with params', async () => {
    const user = userEvent.setup();
    const onCreated = vi.fn();
    render(wrap(<TemplateWizard open onClose={()=>{}} onCreated={onCreated} />));
    // Step 1 -> set platform and next
    await user.type(screen.getByLabelText(/Platform/i), 'shopee');
    await user.click(screen.getByRole('button', { name:/Tiếp tục/i }));
    // Step 2 -> template already has {target}
  screen.getByTestId('wizard-template');
  // Field đã có giá trị mặc định, không cần gõ gì
    // Add param
    await user.click(screen.getByRole('button', { name:/Thêm param/i }));
    const keyInputs = screen.getAllByLabelText(/Key/i);
    await user.type(keyInputs[keyInputs.length-1], 'utm_source');
    const valueInputs = screen.getAllByLabelText(/Value/i);
    await user.type(valueInputs[valueInputs.length-1], 'wizard');
    await user.click(screen.getByRole('button', { name:/Tạo template/i }));
    // Expect onCreated eventually
    // (We cannot easily assert notification text without exposing queue, rely on callback)
    await new Promise(r=>setTimeout(r,10));
    expect(onCreated).toHaveBeenCalled();
  });
});
