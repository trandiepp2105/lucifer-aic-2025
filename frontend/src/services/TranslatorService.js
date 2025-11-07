// Google Cloud Translate API Service
class TranslatorService {
  constructor() {
    // API key từ environment variables
    this.apiKey = process.env.REACT_APP_GOOGLE_CLOUD_TRANSLATE_API_KEY;
    this.endpoint = 'https://translation.googleapis.com/language/translate/v2';
    
    // Kiểm tra xem có API key hợp lệ không
    this.hasValidApiKey = this.apiKey && this.apiKey !== 'YOUR_API_KEY_HERE' && this.apiKey.length > 10;
    
    // Rate limiting và caching
    this.requestQueue = [];
    this.isProcessing = false;
    this.cache = new Map();
    this.lastRequestTime = 0;
    this.minRequestInterval = 10; // Giảm xuống 10ms giữa các requests
  }

  // Debounce function để tránh spam requests
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  }

  // Wait function để delay giữa các requests
  async wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  // Tạo cache key cho request
  getCacheKey(text, targetLanguage, sourceLanguage) {
    return `${text}|${targetLanguage}|${sourceLanguage || 'auto'}`;
  }

  async translateText(text, targetLanguage, sourceLanguage = 'auto') {
    if (!text || text.trim() === '') {
      return text;
    }

    // Kiểm tra API key trước khi thực hiện
    if (!this.hasValidApiKey) {
      throw new Error('Google Cloud Translate API key is required but not configured');
    }

    // Kiểm tra cache trước
    const cacheKey = this.getCacheKey(text, targetLanguage, sourceLanguage);
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey);
    }

    try {
      // Rate limiting: đảm bảo có khoảng cách tối thiểu giữa các requests
      const now = Date.now();
      const timeSinceLastRequest = now - this.lastRequestTime;
      if (timeSinceLastRequest < this.minRequestInterval) {
        await this.wait(this.minRequestInterval - timeSinceLastRequest);
      }

      const params = new URLSearchParams({
        key: this.apiKey,
        q: text,
        target: targetLanguage,
        format: 'text'
      });

      // Nếu source language được chỉ định và không phải 'auto'
      if (sourceLanguage && sourceLanguage !== 'auto') {
        params.append('source', sourceLanguage);
      }

      this.lastRequestTime = Date.now();

      const response = await fetch(`${this.endpoint}?${params}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        }
      });
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        
        // Xử lý các loại lỗi cụ thể
        if (response.status === 400) {
          throw new Error(`Rate limit exceeded or invalid request. Please slow down your requests.`);
        } else if (response.status === 403) {
          throw new Error(`API key quota exceeded or invalid permissions.`);
        } else if (response.status === 429) {
          throw new Error(`Too many requests. Please wait before trying again.`);
        }
        
        throw new Error(`Google Cloud Translate API failed: ${response.status} ${response.statusText}. ${errorData.error?.message || ''}`);
      }

      const result = await response.json();
      
      if (result && result.data && result.data.translations && result.data.translations[0]) {
        const translatedText = result.data.translations[0].translatedText;
        
        // Lưu vào cache
        this.cache.set(cacheKey, translatedText);
        
        // Giới hạn cache size
        if (this.cache.size > 1000) {
          const firstKey = this.cache.keys().next().value;
          this.cache.delete(firstKey);
        }
        
        return translatedText;
      }
      
      throw new Error('Invalid response format from Google Cloud Translate API');
    } catch (error) {
      // Nếu lỗi rate limit, thử lại sau một khoảng thời gian
      if (error.message.includes('Rate limit') || error.message.includes('Too many requests')) {
        console.warn('Translation rate limit hit, please slow down requests');
      }
      throw error;
    }
  }

  async translateToEnglish(text) {
    return this.translateText(text, 'en');
  }

  async translateToVietnamese(text) {
    return this.translateText(text, 'vi');
  }

  // Detect language using Google Cloud Translate API
  async detectLanguage(text) {
    // Kiểm tra API key trước khi thực hiện
    if (!this.hasValidApiKey) {
      throw new Error('Google Cloud Translate API key is required for language detection');
    }
    
    // Kiểm tra cache trước
    const cacheKey = `detect:${text}`;
    if (this.cache.has(cacheKey)) {
      return this.cache.get(cacheKey);
    }
    
    try {
      // Rate limiting
      const now = Date.now();
      const timeSinceLastRequest = now - this.lastRequestTime;
      if (timeSinceLastRequest < this.minRequestInterval) {
        await this.wait(this.minRequestInterval - timeSinceLastRequest);
      }

      const params = new URLSearchParams({
        key: this.apiKey,
        q: text
      });

      this.lastRequestTime = Date.now();

      const response = await fetch(`https://translation.googleapis.com/language/translate/v2/detect?${params}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        
        // Xử lý các loại lỗi cụ thể
        if (response.status === 400) {
          throw new Error(`Rate limit exceeded or invalid request. Please slow down your requests.`);
        } else if (response.status === 403) {
          throw new Error(`API key quota exceeded or invalid permissions.`);
        } else if (response.status === 429) {
          throw new Error(`Too many requests. Please wait before trying again.`);
        }
        
        throw new Error(`Language detection failed: ${response.status} ${response.statusText}. ${errorData.error?.message || ''}`);
      }

      const result = await response.json();
      
      if (result && result.data && result.data.detections && result.data.detections[0] && result.data.detections[0][0]) {
        const detectedLanguage = result.data.detections[0][0].language;
        
        // Lưu vào cache
        this.cache.set(cacheKey, detectedLanguage);
        
        return detectedLanguage;
      }
      
      throw new Error('Invalid response format from language detection API');
    } catch (error) {
      // Nếu lỗi rate limit, thử lại sau một khoảng thời gian
      if (error.message.includes('Rate limit') || error.message.includes('Too many requests')) {
        console.warn('Language detection rate limit hit, please slow down requests');
      }
      throw error;
    }
  }
}

// Export singleton instance
export const translatorService = new TranslatorService();
export default TranslatorService;
