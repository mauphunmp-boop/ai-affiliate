import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LinksManager from '../pages/Links/LinksManager.jsx';
import * as api from '../api.js';
import { renderWithProviders, screen, waitFor, fireEvent } from '../test/test-utils.jsx';

// Mock i18n + NotificationProvider minimal
vi.mock('../i18n/I18nProvider.jsx', () => ({ useT: () => ({ t: (k) => {
  const map = {
    'links_title':'Links',
    'links_add':'Add',
    'links_field_name':'Name',
    'dlg_cancel':'Cancel',
    'dlg_create':'Create',
    'dlg_save':'Save',
    'links_create_title':'Create Link',
    'links_edit_title':'Edit Link',
    'api_configs_form_required':'Required'
  }; return map[k] || k; } }) }));
vi.mock('../components/NotificationProvider.jsx', () => ({ useNotify: () => vi.fn() }));
// Đường dẫn thực tế LinksManager.jsx sử dụng '../../components/...'
vi.mock('../../components/DataTable.jsx', () => ({ __esModule:true, default: ({ rows }) => <div data-testid="datatable">DT({rows.length})</div>}));
vi.mock('../../components/ConfirmDialog.jsx', () => ({ __esModule:true, default: () => null }));
vi.mock('../../components/SkeletonSection.jsx', () => ({ __esModule:true, default: () => <div data-testid="skeleton" /> }));

function openDialog() {
  const addBtn = screen.getByRole('button', { name:'Add' });
  fireEvent.click(addBtn);
}

describe('LinksManager', () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it('loads initial links', async () => {
    vi.spyOn(api, 'getLinks').mockResolvedValueOnce({ data: [] });
    renderWithProviders(<LinksManager />);
    await screen.findByTestId('datatable');
    expect(api.getLinks).toHaveBeenCalled();
  });

  it('validation: requires name and at least one URL', async () => {
    vi.spyOn(api, 'getLinks').mockResolvedValueOnce({ data: [] });
    renderWithProviders(<LinksManager />);
    await screen.findByTestId('datatable');
    openDialog();
    const createBtn = screen.getByRole('button', { name:'Create' });
    fireEvent.click(createBtn); // no name & urls
    // We cannot easily assert toast (mock fn created), but ensure createLink not called
    const createSpy = vi.spyOn(api, 'createLink').mockResolvedValue({ data:{ id:1 } });
    // Fill only name now
  // MUI thêm ký tự * cho label required => dùng regex để khớp 'Name' bất kể có dấu *
  fireEvent.change(screen.getByLabelText(/Name/i), { target:{ value:'My Link' } });
    fireEvent.click(createBtn); // still missing URLs
    expect(createSpy).not.toHaveBeenCalled();
  });

  it('creates with single URL populating both fields', async () => {
    vi.spyOn(api, 'getLinks').mockResolvedValueOnce({ data: [] });
    const createSpy = vi.spyOn(api, 'createLink').mockResolvedValueOnce({ data:{ id:42 } });
    renderWithProviders(<LinksManager />);
    await screen.findByTestId('datatable');
    openDialog();
  fireEvent.change(screen.getByLabelText(/Name/i), { target:{ value:'Solo Link' } });
    fireEvent.change(screen.getByLabelText('URL'), { target:{ value:'https://example.com' } });
    const createBtn = screen.getByRole('button', { name:'Create' });
    fireEvent.click(createBtn);

    await waitFor(()=> expect(createSpy).toHaveBeenCalled());
    const payload = createSpy.mock.calls[0][0];
    expect(payload.url).toBe('https://example.com');
    expect(payload.affiliate_url).toBe('https://example.com');
  });

  it('rejects invalid URL format', async () => {
    vi.spyOn(api, 'getLinks').mockResolvedValueOnce({ data: [] });
    const createSpy = vi.spyOn(api, 'createLink').mockResolvedValue({});
    renderWithProviders(<LinksManager />);
    await screen.findByTestId('datatable');
    openDialog();
  fireEvent.change(screen.getByLabelText(/Name/i), { target:{ value:'Bad URL' } });
    fireEvent.change(screen.getByLabelText('URL'), { target:{ value:'notaurl' } });
    const createBtn = screen.getByRole('button', { name:'Create' });
    fireEvent.click(createBtn);
    expect(createSpy).not.toHaveBeenCalled();
  });
});
