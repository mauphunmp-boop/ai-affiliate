import React from 'react';
import { ColorModeProvider } from '../../context/ColorModeContext.jsx';
import NotificationProvider from '../../components/NotificationProvider.jsx';

export function renderWithProviders(ui) {
  return (<ColorModeProvider><NotificationProvider>{ui}</NotificationProvider></ColorModeProvider>);
}
