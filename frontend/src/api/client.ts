/**
 * Axios client for Memory Graph API
 * 
 * Configured with:
 * - Base URL from VITE_CORE_API
 * - Default X-Org-Id header
 * - 12s timeout
 */

import axios from 'axios';

export const CORE_API = import.meta.env.VITE_CORE_API || 'http://localhost:8000';
export const ORG = import.meta.env.VITE_ORG_ID || 'default';

export const api = axios.create({
  baseURL: CORE_API,
  timeout: 12000,
  headers: {
    'Content-Type': 'application/json',
    'X-Org-Id': ORG,
  },
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);
