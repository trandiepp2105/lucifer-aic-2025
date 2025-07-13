// Microsoft Translator API Service
class TranslatorService {
  constructor() {
    // API key từ environment variables
    this.apiKey = process.env.REACT_APP_TRANSLATOR_API_KEY;
    this.endpoint = 'https://api.cognitive.microsofttranslator.com';
    this.region = process.env.REACT_APP_TRANSLATOR_REGION || 'global';
    
    // Kiểm tra xem có API key hợp lệ không
    this.hasValidApiKey = this.apiKey && this.apiKey !== 'YOUR_API_KEY_HERE' && this.apiKey.length > 10;
  }

  async translateText(text, targetLanguage, sourceLanguage = 'auto') {
    if (!text || text.trim() === '') {
      return text;
    }

    // Nếu không có API key hợp lệ, sử dụng fallback ngay
    if (!this.hasValidApiKey) {
      return this.fallbackTranslate(text, targetLanguage);
    }

    try {
      const url = `${this.endpoint}/translate?api-version=3.0&to=${targetLanguage}`;
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Ocp-Apim-Subscription-Key': this.apiKey,
          'Ocp-Apim-Subscription-Region': this.region,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify([
          {
            text: text
          }
        ])
      });

      if (!response.ok) {
        throw new Error(`Translation failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result && result[0] && result[0].translations && result[0].translations[0]) {
        return result[0].translations[0].text;
      }
      
      throw new Error('Invalid response format');
    } catch (error) {
      // Fallback: Sử dụng LibreTranslate miễn phí nếu Microsoft API fail
      return this.fallbackTranslate(text, targetLanguage);
    }
  }

  async fallbackTranslate(text, targetLanguage) {
    try {
      // Thử LibreTranslate đầu tiên
      const response = await fetch('https://libretranslate.de/translate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          q: text,
          source: 'auto',
          target: targetLanguage === 'vi' ? 'vi' : 'en',
          format: 'text'
        })
      });

      if (response.ok) {
        const result = await response.json();
        if (result.translatedText) {
          return result.translatedText;
        }
      }
      
      throw new Error('LibreTranslate failed');
    } catch (error) {
      // Fallback thứ 2: Thử API khác hoặc trả về text gốc
      try {
        // Có thể thêm API dịch miễn phí khác ở đây
        
        // Ví dụ: Google Translate API miễn phí (không chính thức)
        // Hoặc các API dịch miễn phí khác
        
        // Tạm thời trả về text gốc
        return text;
      } catch (fallbackError) {
        return text; // Trả về text gốc nếu tất cả đều fail
      }
    }
  }

  async translateToEnglish(text) {
    return this.translateText(text, 'en');
  }

  async translateToVietnamese(text) {
    return this.translateText(text, 'vi');
  }

  // Detect language
  async detectLanguage(text) {
    // Nếu không có API key hợp lệ, skip detection
    if (!this.hasValidApiKey) {
      return 'auto';
    }
    
    try {
      const url = `${this.endpoint}/detect?api-version=3.0`;
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Ocp-Apim-Subscription-Key': this.apiKey,
          'Ocp-Apim-Subscription-Region': this.region,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify([
          {
            text: text
          }
        ])
      });

      if (!response.ok) {
        return 'auto';
      }

      const result = await response.json();
      
      if (result && result[0] && result[0].language) {
        return result[0].language;
      }
      
      return 'auto';
    } catch (error) {
      return 'auto';
    }
  }
}

// Export singleton instance
export const translatorService = new TranslatorService();
export default TranslatorService;
