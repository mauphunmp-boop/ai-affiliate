import api from '../api.js';

// Settings policies
export const setIngestPolicy = (only_with_commission=false) => api.post('/ingest/policy', null, { params: { only_with_commission }});
export const setCheckUrlsPolicy = (enable=false) => api.post('/ingest/policy/check-urls', null, { params: { enable }});

// Core ingest endpoints
export const ingestCampaignsSync = (payload={}) => api.post('/ingest/campaigns/sync', payload);
export const ingestPromotions = (payload={}) => api.post('/ingest/promotions', payload);
export const ingestTopProducts = (payload={}) => api.post('/ingest/top-products', payload);
export const ingestDatafeedsAll = (payload={}) => api.post('/ingest/datafeeds/all', payload);
export const ingestProducts = (payload={}) => api.post('/ingest/products', payload);
export const ingestCommissions = (payload={}) => api.post('/ingest/commissions', payload);

// Note: Legacy preset TikTok ingest removed per requirements.

// Scheduler: ingest refresh orchestration (mutexed)
export const getIngestLockStatus = () => api.get('/scheduler/ingest/lock/status');
export const releaseIngestLock = (owner=null, force=false, adminKey) => {
	const headers = {};
	if (adminKey) headers['X-Admin-Key'] = adminKey;
	return api.post('/scheduler/ingest/lock/release', null, { params: { owner, force }, headers });
};
export const runIngestRefresh = (payload={}) => api.post('/scheduler/ingest/refresh', payload);
