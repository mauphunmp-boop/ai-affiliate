import '@testing-library/jest-dom';
import { afterEach } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import React from 'react';
import { I18nProvider } from '../i18n/I18nProvider.jsx';
import { ColorModeProvider } from '../context/ColorModeContext.jsx';
import { NotificationProvider } from '../components/NotificationProvider.jsx';

// Polyfill matchMedia for MUI useMediaQuery & color-scheme detection
if (typeof window !== 'undefined' && !window.matchMedia) {
	window.matchMedia = function matchMedia(query) {
		return {
			matches: false,
			media: query,
			onchange: null,
			addListener: function() {}, // deprecated
			removeListener: function() {},
			addEventListener: function() {},
			removeEventListener: function() {},
			dispatchEvent: function() { return false; }
		};
	};
}

// Custom render that wraps with all global providers so tests don't need to duplicate
function AllProviders({ children }) {
	return (
		<I18nProvider initial="vi">
			<ColorModeProvider>
				<NotificationProvider>
					{children}
				</NotificationProvider>
			</ColorModeProvider>
		</I18nProvider>
	);
}

export function renderWithApp(ui, options) {
	return render(ui, { wrapper: AllProviders, ...options });
}

// Auto cleanup between tests
afterEach(() => {
	cleanup();
});

// Expose to global so existing tests can opt-in without changing imports immediately
// (We will gradually migrate tests to import explicitly if desired.)
globalThis.renderWithApp = renderWithApp;
