import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (refreshToken) {
          const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
            refresh_token: refreshToken
          });
          
          const { access_token } = response.data;
          localStorage.setItem('token', access_token);
          
          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        localStorage.removeItem('token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }
    
    return Promise.reject(error);
  }
);

export const authService = {
  async login(email, password) {
    const response = await api.post('/api/auth/login', {
      email,
      password
    });
    
    const { access_token, refresh_token } = response.data;
    
    if (refresh_token) {
      localStorage.setItem('refresh_token', refresh_token);
    }
    
    return response.data;
  },

  async logout(token) {
    try {
      await api.post('/api/auth/logout', {}, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });
    } finally {
      localStorage.removeItem('token');
      localStorage.removeItem('refresh_token');
    }
  },

  async verifyToken(token) {
    const response = await api.post('/api/auth/verify', {}, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    return response.data.user;
  },

  async refreshToken(refreshToken) {
    const response = await api.post('/api/auth/refresh', {
      refresh_token: refreshToken
    });
    return response.data;
  },

  async getCurrentUser() {
    const response = await api.get('/api/auth/me');
    return response.data;
  },

  async changePassword(currentPassword, newPassword) {
    const response = await api.post('/api/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword
    });
    return response.data;
  }
};

export default api;

