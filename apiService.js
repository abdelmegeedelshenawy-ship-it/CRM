import api from './authService';

export const clientsService = {
  async getClients(params = {}) {
    const response = await api.get('/api/clients/companies', { params });
    return response.data;
  },

  async getClient(id) {
    const response = await api.get(`/api/clients/companies/${id}`);
    return response.data;
  },

  async createClient(data) {
    const response = await api.post('/api/clients/companies', data);
    return response.data;
  },

  async updateClient(id, data) {
    const response = await api.put(`/api/clients/companies/${id}`, data);
    return response.data;
  },

  async deleteClient(id) {
    const response = await api.delete(`/api/clients/companies/${id}`);
    return response.data;
  },

  async getContacts(params = {}) {
    const response = await api.get('/api/clients/contacts', { params });
    return response.data;
  },

  async createContact(data) {
    const response = await api.post('/api/clients/contacts', data);
    return response.data;
  },

  async getClientStats() {
    const response = await api.get('/api/clients/companies/stats');
    return response.data;
  }
};

export const dealsService = {
  async getDeals(params = {}) {
    const response = await api.get('/api/deals', { params });
    return response.data;
  },

  async getDeal(id) {
    const response = await api.get(`/api/deals/${id}`);
    return response.data;
  },

  async createDeal(data) {
    const response = await api.post('/api/deals', data);
    return response.data;
  },

  async updateDeal(id, data) {
    const response = await api.put(`/api/deals/${id}`, data);
    return response.data;
  },

  async deleteDeal(id) {
    const response = await api.delete(`/api/deals/${id}`);
    return response.data;
  },

  async getPipeline() {
    const response = await api.get('/api/deals/pipeline');
    return response.data;
  },

  async getDealStats() {
    const response = await api.get('/api/deals/stats');
    return response.data;
  },

  async getActivities(params = {}) {
    const response = await api.get('/api/deals/activities', { params });
    return response.data;
  },

  async createActivity(data) {
    const response = await api.post('/api/deals/activities', data);
    return response.data;
  }
};

export const ordersService = {
  async getOrders(params = {}) {
    const response = await api.get('/api/orders', { params });
    return response.data;
  },

  async getOrder(id) {
    const response = await api.get(`/api/orders/${id}`);
    return response.data;
  },

  async createOrder(data) {
    const response = await api.post('/api/orders', data);
    return response.data;
  },

  async updateOrder(id, data) {
    const response = await api.put(`/api/orders/${id}`, data);
    return response.data;
  },

  async getOrderStats() {
    const response = await api.get('/api/orders/stats');
    return response.data;
  },

  async getShipments(params = {}) {
    const response = await api.get('/api/orders/shipments', { params });
    return response.data;
  },

  async createShipment(data) {
    const response = await api.post('/api/orders/shipments', data);
    return response.data;
  },

  async updateShipmentTracking(id, data) {
    const response = await api.put(`/api/orders/shipments/${id}/track`, data);
    return response.data;
  }
};

export const analyticsService = {
  async getDashboardStats() {
    const response = await api.get('/api/analytics/dashboard');
    return response.data;
  },

  async getSalesMetrics(params = {}) {
    const response = await api.get('/api/analytics/sales', { params });
    return response.data;
  },

  async getRevenueMetrics(params = {}) {
    const response = await api.get('/api/analytics/revenue', { params });
    return response.data;
  },

  async getPerformanceMetrics(params = {}) {
    const response = await api.get('/api/analytics/performance', { params });
    return response.data;
  }
};

export const usersService = {
  async getUsers(params = {}) {
    const response = await api.get('/api/users', { params });
    return response.data;
  },

  async createUser(data) {
    const response = await api.post('/api/users', data);
    return response.data;
  },

  async updateUser(id, data) {
    const response = await api.put(`/api/users/${id}`, data);
    return response.data;
  },

  async deleteUser(id) {
    const response = await api.delete(`/api/users/${id}`);
    return response.data;
  },

  async getRoles() {
    const response = await api.get('/api/users/roles');
    return response.data;
  }
};

