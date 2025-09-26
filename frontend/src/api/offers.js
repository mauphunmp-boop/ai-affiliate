import api from '../api.js';

export const listOffers = ({ merchant, skip=0, limit=20, category='offers' } = {}) => {
  const params = { skip, limit, category };
  if (merchant && merchant.trim()) params.merchant = merchant.trim();
  return api.get('/offers', { params });
};

export const getOfferExtras = (offerId) => {
  return api.get(`/offers/${offerId}/extras`);
};
