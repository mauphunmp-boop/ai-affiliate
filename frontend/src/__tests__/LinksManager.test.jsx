import { describe, it, expect, vi, beforeEach } from 'vitest';
// Place mocks first to avoid module execution before mocks in full suite
vi.mock('../api.js', () => ({
  getLinks: vi.fn().mockResolvedValue({ data: [] }),
  createLink: vi.fn().mockResolvedValue({ data: { id: 1 } }),
  updateLink: vi.fn().mockResolvedValue({ data: { ok: true } }),
  deleteLink: vi.fn().mockResolvedValue({ data: { ok: true } })
}));
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
vi.mock('../../components/ConfirmDialog.jsx', () => ({ __esModule:true, default: () => null }));
vi.mock('../../components/SkeletonSection.jsx', () => ({ __esModule:true, default: () => <div data-testid="skeleton" /> }));

import React from 'react';
import LinksManager from '../pages/Links/LinksManager.jsx';
import * as api from '../api.js';
import { renderWithProviders, screen, waitFor } from '../test/test-utils.jsx';
import userEvent from '@testing-library/user-event';


async function openDialog() {
  const addBtn = await screen.findByRole('button', { name:'Add' });
  await userEvent.click(addBtn);
  // Wait for dialog inputs to mount
  await screen.findByLabelText(/Name/i);
}

describe('LinksManager', () => {
  beforeEach(() => {
    // reset mock call history but keep same mocked functions
    api.getLinks.mockClear();
    api.createLink.mockClear();
    api.updateLink.mockClear();
    api.deleteLink.mockClear();
    // default resolve value each test
    api.getLinks.mockResolvedValue({ data: [] });
  });

  it('loads initial links', async () => {
    renderWithProviders(<LinksManager />);
    await screen.findByTestId('datatable');
    expect(api.getLinks).toHaveBeenCalled();
  });

  it('validation: requires name and at least one URL', async () => {
    const createSpy = api.createLink; // already mocked
    renderWithProviders(<LinksManager />);
    await screen.findByTestId('datatable');
    await openDialog();
    const createBtn = await screen.findByTestId('links-save');
    await userEvent.click(createBtn); // no name & urls -> should not call
    // Assert still not called quickly before next actions
    expect(createSpy).not.toHaveBeenCalled();
    const nameInput = screen.getByLabelText(/Name/i);
    await userEvent.type(nameInput, 'My Link');
    // Small microtask flush
    await waitFor(()=> expect(nameInput).toHaveValue('My Link'));
    await userEvent.click(createBtn); // still missing URLs -> still not call
    expect(createSpy).not.toHaveBeenCalled();
  }, 15000);

  it('creates with single URL populating both fields', async () => {
    const createSpy = api.createLink.mockResolvedValueOnce({ data:{ id:42 } });
    renderWithProviders(<LinksManager />);
    await screen.findByTestId('datatable');
    await openDialog();
  const nameInput = screen.getByLabelText(/Name/i);
  const urlInput = screen.getByLabelText('URL');
  await userEvent.type(nameInput, 'Solo Link');
  await userEvent.type(urlInput, 'https://example.com');
  await waitFor(()=> expect(urlInput).toHaveValue('https://example.com'));
  const createBtn = await screen.findByTestId('links-save');
    await userEvent.click(createBtn);

    await waitFor(()=> expect(createSpy).toHaveBeenCalled());
    const payload = createSpy.mock.calls[0][0];
    expect(payload.url).toBe('https://example.com');
    expect(payload.affiliate_url).toBe('https://example.com');
  }, 15000);

  it('rejects invalid URL format', async () => {
    const createSpy = api.createLink;
    renderWithProviders(<LinksManager />);
    await screen.findByTestId('datatable');
    await openDialog();
  const nameInput2 = screen.getByLabelText(/Name/i);
  const urlInput2 = screen.getByLabelText('URL');
  await userEvent.type(nameInput2, 'Bad URL');
  await userEvent.type(urlInput2, 'notaurl');
  await waitFor(()=> expect(urlInput2).toHaveValue('notaurl'));
  const createBtn = await screen.findByTestId('links-save');
    await userEvent.click(createBtn);
    expect(createSpy).not.toHaveBeenCalled();
  }, 15000);
});
