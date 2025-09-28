// Metadata mô tả các tác vụ ingest và tham số để sinh form động.
// Mỗi field: { key, type, default, required?, example?, group?, textarea?, json?, enum?, min?, max? }

export const INGEST_TASKS = [
  {
    id: 'campaigns_sync',
    api: 'ingestCampaignsSync',
    titleKey: 'ingest_task_campaigns_sync_title',
    descKey: 'ingest_task_campaigns_sync_desc',
    defaultPayload: {
      provider: 'accesstrade',
      statuses: ['running','paused'],
      only_my: true,
      enrich_user_status: true,
      limit_per_page: 50,
      page_concurrency: 6,
      window_pages: 10,
      throttle_ms: 50,
      merchant: ''
    },
    fields: [
  { key: 'provider', type: 'string', required: true },
  { key: 'statuses', type: 'list', placeholder: 'running, paused', required: true },
      { key: 'only_my', type: 'boolean' },
      { key: 'enrich_user_status', type: 'boolean' },
      { key: 'limit_per_page', type: 'number', min:1 },
      { key: 'page_concurrency', type: 'number', min:1 },
      { key: 'window_pages', type: 'number', min:1 },
      { key: 'throttle_ms', type: 'number', min:0 },
      { key: 'merchant', type: 'string', placeholder: 'vd: dienthoaivui' }
    ]
  },
  {
    id: 'promotions',
    api: 'ingestPromotions',
    titleKey: 'ingest_task_promotions_title',
    descKey: 'ingest_task_promotions_desc',
    defaultPayload: {
      provider: 'accesstrade',
      merchant: '',
      verbose: false,
      throttle_ms: 50
    },
    fields: [
      { key: 'provider', type: 'string', required: true },
      { key: 'merchant', type: 'string', placeholder: 'tikivn' },
      { key: 'verbose', type: 'boolean' },
      { key: 'throttle_ms', type: 'number', min:0 }
    ]
  },
  {
    id: 'top_products',
    api: 'ingestTopProducts',
    titleKey: 'ingest_task_top_products_title',
    descKey: 'ingest_task_top_products_desc',
    defaultPayload: {
      provider: 'accesstrade',
      merchant: '',
      date_from: '',
      date_to: '',
      limit_per_page: 50,
      max_pages: 1,
      check_urls: false,
      verbose: false,
      throttle_ms: 50
    },
    fields: [
  { key: 'provider', type: 'string', required: true },
      { key: 'merchant', type: 'string' },
      { key: 'date_from', type: 'string', placeholder: 'YYYY-MM-DD' },
      { key: 'date_to', type: 'string', placeholder: 'YYYY-MM-DD' },
      { key: 'limit_per_page', type: 'number', min:1 },
      { key: 'max_pages', type: 'number', min:1 },
      { key: 'check_urls', type: 'boolean' },
      { key: 'verbose', type: 'boolean' },
      { key: 'throttle_ms', type: 'number', min:0 }
    ]
  },
  {
    id: 'datafeeds_all',
    api: 'ingestDatafeedsAll',
    titleKey: 'ingest_task_datafeeds_all_title',
    descKey: 'ingest_task_datafeeds_all_desc',
    defaultPayload: {
      provider: 'accesstrade',
      merchant: '',
      limit_per_page: 100,
      max_pages: 1,
      throttle_ms: 50,
      check_urls: false,
      verbose: false
    },
    fields: [
  { key: 'provider', type: 'string', required: true },
  // params previously JSON; now explicit merchant only
  { key: 'merchant', type: 'string', placeholder: 'tikivn' },
      { key: 'limit_per_page', type: 'number', min:1 },
      { key: 'max_pages', type: 'number', min:1 },
      { key: 'check_urls', type: 'boolean' },
      { key: 'verbose', type: 'boolean' },
      { key: 'throttle_ms', type: 'number', min:0 }
    ]
  },
  {
    id: 'products',
    api: 'ingestProducts',
    titleKey: 'ingest_task_products_title',
    descKey: 'ingest_task_products_desc',
    defaultPayload: {
      provider: 'accesstrade',
      path: '/v1/datafeeds',
      merchant: '',
      page: 1,
      limit: 50,
      check_urls: false,
      verbose: false,
      throttle_ms: 50
    },
    fields: [
      { key: 'provider', type: 'string', required: true },
      { key: 'path', type: 'string' },
  // params split into separate fields
  { key: 'merchant', type: 'string', placeholder: 'tikivn' },
  { key: 'page', type: 'number', min:1, placeholder: '1' },
  { key: 'limit', type: 'number', min:1, placeholder: '50' },
      { key: 'check_urls', type: 'boolean' },
      { key: 'verbose', type: 'boolean' },
      { key: 'throttle_ms', type: 'number', min:0 }
    ]
  },
  {
    id: 'commissions',
    api: 'ingestCommissions',
    titleKey: 'ingest_task_commissions_title',
    descKey: 'ingest_task_commissions_desc',
    defaultPayload: {
      provider: 'accesstrade',
      campaign_ids: [],
      merchant: '',
      max_campaigns: 100,
      verbose: false
    },
    fields: [
      { key: 'provider', type: 'string', required: true },
  { key: 'campaign_ids', type: 'list', placeholder: 'CAMP1, CAMP2' },
      { key: 'merchant', type: 'string' },
      { key: 'max_campaigns', type: 'number', min:1 },
      { key: 'verbose', type: 'boolean' }
    ]
  }
];
