import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import IngestWizard from '../pages/Ingest/IngestWizard.jsx';
import { I18nProvider } from '../i18n/I18nProvider.jsx';

function wrap(ui){ return <I18nProvider initial="vi">{ui}</I18nProvider>; }

describe('IngestWizard scaffold', () => {
  it('advances steps', () => {
    render(wrap(<IngestWizard />));
    fireEvent.click(screen.getByText(/Tiếp|next/i));
    expect(screen.getByText(/Mapping trường/i)).toBeTruthy();
  });
});
