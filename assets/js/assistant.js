/**
 * NGUYEN TU BLOG - Rule-based Assistant
 * No external APIs, pure JavaScript
 * Vietnamese-only version
 */

class NguyenTuAssistant {
  constructor() {
    this.toggleBtn = document.getElementById('assistant-toggle');
    this.panel = document.getElementById('assistant-panel');
    this.input = document.getElementById('assistant-input');
    this.messages = document.getElementById('assistant-messages');
    this.sendBtn = document.querySelector('.assistant-send');
    this.closeBtn = document.querySelector('.assistant-close');
    
    this.currentLang = 'vi';
    this.quickQuestions = window.NGUYEN_TU_ASSISTANT?.quick_questions || [];
    this.business = window.NGUYEN_TU_BUSINESS || {};
    this.pricing = window.NGUYEN_TU_PRICING || {};
    
    this.init();
  }

  init() {
    if (!this.toggleBtn || !this.panel) return;

    this.toggleBtn.addEventListener('click', () => this.togglePanel());
    
    if (this.closeBtn) {
      this.closeBtn.addEventListener('click', () => this.closePanel());
    }

    this.panel.addEventListener('click', (e) => {
      if (e.target === this.panel) {
        this.closePanel();
      }
    });

    if (this.input && this.sendBtn) {
      this.input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') this.sendMessage();
      });
      this.sendBtn.addEventListener('click', () => this.sendMessage());
    }

    document.querySelectorAll('.assistant-question-btn[data-question-id]').forEach(btn => {
      btn.addEventListener('click', () => {
        const questionId = btn.dataset.questionId;
        this.handleQuickQuestion(questionId);
      });
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.panel.classList.contains('active')) {
        this.closePanel();
      }
    });
  }

  togglePanel() {
    this.panel.classList.toggle('active');
    const isOpen = this.panel.classList.contains('active');
    
    if (isOpen) {
      this.toggleBtn.setAttribute('aria-expanded', 'true');
      document.body.classList.add('assistant-open');
      
      if (this.input) {
        setTimeout(() => this.input.focus(), 100);
      }
      
      this.updateBadge(0);
    } else {
      this.toggleBtn.setAttribute('aria-expanded', 'false');
      document.body.classList.remove('assistant-open');
    }
  }

  closePanel() {
    this.panel.classList.remove('active');
    this.toggleBtn.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('assistant-open');
  }

  sendMessage() {
    if (!this.input || !this.input.value.trim()) return;

    const question = this.input.value.trim();
    this.input.value = '';

    this.addMessage(question, 'user');

    const answer = this.processQuestion(question);
    
    setTimeout(() => {
      this.addMessage(answer, 'assistant');
    }, 300);
  }

  handleQuickQuestion(questionId) {
    const question = this.getQuestionText(questionId);
    const answer = this.getAnswerText(questionId);

    this.addMessage(question, 'user');

    setTimeout(() => {
      this.addMessage(answer, 'assistant');
    }, 300);

    // FIX F: Removed mobile auto-close behavior
    // Panel stays open after clicking quick question
  }

  getQuestionText(questionId) {
    const qq = this.quickQuestions.find(q => q.id === questionId);
    if (qq && qq.question) {
      return qq.question;
    }
    return questionId;
  }

  getAnswerText(questionId) {
    const qq = this.quickQuestions.find(q => q.id === questionId);
    if (qq && qq.answer) {
      return this.processTemplate(qq.answer);
    }
    return this.getNotFoundMessage();
  }

  processQuestion(question) {
    const normalized = this.normalizeVietnamese(question.toLowerCase().trim());

    for (const qq of this.quickQuestions) {
      const qText = this.normalizeVietnamese(qq.question?.toLowerCase() || '');
      if (normalized.includes(qText) || qText.includes(normalized)) {
        return this.processTemplate(qq.answer || this.getNotFoundMessage()
);
      }
    }

    const keywords = {
      'bang gia': 'pricing',
      'tinh gia': 'calculator',
      'dia chi': 'address',
      'gio mo cua': 'hours',
      'xe so': 'honda-wave',
      'xe ga': 'honda-vision',
      'xe dien': 'electric-bike',
      'xe 50cc': 'electric-scooter',
      'thue tuan': 'weekly-rental',
      'thue thang': 'monthly-rental',
      'zalo': 'zalo',
      'whatsapp': 'whatsapp',
      'google maps': 'maps'
    };

    for (const [keyword, qid] of Object.entries(keywords)) {
      if (normalized.includes(this.normalizeVietnamese(keyword))) {
        return this.getAnswerText(qid);
      }
    }

    return this.getNotFoundMessage();
  }

  normalizeVietnamese(text) {
    // Simple normalization: lowercase and remove accents
    // This is a simplified approach - for production, use a proper library
    const accentMap = {
      'á': 'a', 'à': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
      'ă': 'a', 'ắ': 'a', 'ằ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
      'â': 'a', 'ấ': 'a', 'ầ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
      'đ': 'd',
      'é': 'e', 'è': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
      'ê': 'e', 'ế': 'e', 'ề': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
      'í': 'i', 'ì': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
      'ó': 'o', 'ò': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
      'ô': 'o', 'ố': 'o', 'ồ': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
      'ơ': 'o', 'ớ': 'o', 'ờ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
      'ú': 'u', 'ù': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
      'ư': 'u', 'ứ': 'u', 'ừ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
      'ý': 'y', 'ỳ': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y',
      'Á': 'A', 'À': 'A', 'Ả': 'A', 'Ã': 'A', 'Ạ': 'A',
      'Ă': 'A', 'Ắ': 'A', 'Ằ': 'A', 'Ẳ': 'A', 'Ẵ': 'A', 'Ặ': 'A',
      'Â': 'A', 'Ấ': 'A', 'Ầ': 'A', 'Ẩ': 'A', 'Ẫ': 'A', 'Ậ': 'A',
      'Đ': 'D',
      'É': 'E', 'È': 'E', 'Ẻ': 'E', 'Ẽ': 'E', 'Ẹ': 'E',
      'Ê': 'E', 'Ế': 'E', 'Ề': 'E', 'Ể': 'E', 'Ễ': 'E', 'Ệ': 'E',
      'Í': 'I', 'Ì': 'I', 'Ỉ': 'I', 'Ĩ': 'I', 'Ị': 'I',
   
   'Ó': 'O', 'Ò': 'O', 'Ỏ': 'O', 'Õ': 'O', 'Ọ': 'O',
      'Ô': 'O', 'Ố': 'O', 'Ồ': 'O', 'Ổ': 'O', 'Ỗ': 'O', 'Ộ': 'O',
      'Ơ': 'O', 'Ớ': 'O', 'Ờ': 'O', 'Ở': 'O', 'Ỡ': 'O', 'Ợ': 'O',
      'Ú': 'U', 'Ù': 'U', 'Ủ': 'U', 'Ũ': 'U', 'Ụ': 'U',
      'Ư': 'U', 'Ứ': 'U', 'Ừ': 'U', 'Ử': 'U', 'Ữ': 'U', 'Ự': 'U',
      'Ý': 'Y', 'Ỳ': 'Y', 'Ỷ': 'Y', 'Ỹ': 'Y', 'Ỵ': 'Y'
    };
    
    return text.split('').map(c => accentMap[c] || c).join('');
  }

  processTemplate(template) {
    // FIX E: Use correct template replacement with proper regex
    let processed = template;
    
    // Replacement map for business data
    const replacements = {
      '{{ business.contact.phone }}': this.business.contact?.phone || '',
      '{{ business.contact.phone_uri }}': this.business.contact?.phone_uri || '',
      '{{ business.contact.zalo }}': this.business.contact?.zalo || '',
      '{{ business.contact.whatsapp }}': this.business.contact?.whatsapp || '',
      '{{ business.contact.maps }}': this.business.contact?.maps || '',
      '{{ business.contact.email }}': this.business.contact?.email || '',
      '{{ business.address.full }}': this.business.address?.full || '',
      '{{ business.hours }}': this.business.hours || '',
      '{{ business.display_name }}': this.business.display_name || '',
      '{{ business.url }}': this.business.url || ''
    };
    
    // Apply replacements
    for (const [placeholder, value] of Object.entries(replacements)) {
      processed = processed.split(placeholder).join(value);
    }
    
    return processed;
  }

  getNotFoundMessage() {
    // FIX G: Use accented Vietnamese fallback
    return 'Mình chưa có thông tin chắc chắn về nội dung này. Bạn có thể liên hệ Nguyễn Tú qua Zalo, WhatsApp hoặc điện thoại để xác nhận.';
  }

  addMessage(text, type) {
    if (!this.messages) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = 'assistant-message ' + type;
    messageDiv.textContent = text;
    
    this.messages.
appendChild(messageDiv);
    this.messages.scrollTop = this.messages.scrollHeight;

    if (type === 'user') {
      const count = parseInt(this.toggleBtn.querySelector('.assistant-badge')?.textContent || '0');
      this.updateBadge(count + 1);
    }
  }

  updateBadge(count) {
    const badge = this.toggleBtn.querySelector('.assistant-badge');
    if (badge) {
      badge.textContent = count > 0 ? count : '';
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  new NguyenTuAssistant();
});
