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

    // Toggle panel
    this.toggleBtn.addEventListener('click', () => this.togglePanel());
    
    // Close panel
    if (this.closeBtn) {
      this.closeBtn.addEventListener('click', () => this.closePanel());
    }

    // Close on backdrop click
    this.panel.addEventListener('click', (e) => {
      if (e.target === this.panel) {
        this.closePanel();
      }
    });

    // Send message
    if (this.input && this.sendBtn) {
      this.input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') this.sendMessage();
      });
      this.sendBtn.addEventListener('click', () => this.sendMessage());
    }

    // Quick question buttons
    document.querySelectorAll('.assistant-question-btn[data-question-id]').forEach(btn => {
      btn.addEventListener('click', () => {
        const questionId = btn.dataset.questionId;
        this.handleQuickQuestion(questionId);
      });
    });

    // Close on Escape
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
      
      // Focus input
      if (this.input) {
        setTimeout(() => this.input.focus(), 100);
      }
      
      // Update badge
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

    // Add user message
    this.addMessage(question, 'user');

    // Process and get answer
    const answer = this.processQuestion(question);
    
    // Add assistant message
    setTimeout(() => {
      this.addMessage(answer, 'assistant');
    }, 300);
  }

  handleQuickQuestion(questionId) {
    const question = this.getQuestionText(questionId);
    const answer = this.getAnswerText(questionId);

    // Add user message
    this.addMessage(question, 'user');

    // Add assistant message
    setTimeout(() => {
      this.addMessage(answer, 'assistant');
    }, 300);

    // Close panel on mobile
    if (window.innerWidth <= 768) {
      this.closePanel();
    }
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
    const normalized = question.toLowerCase().trim();

    // Try to match with quick questions
    for (const qq of this.quickQuestions) {
      const qText = qq.question?.toLowerCase() || '';
      if (normalized.includes(qText) || qText.includes(normalized)) {
        return this.processTemplate(qq.answer || this.getNotFoundMessage());
      }
    }

    // Try to match keywords - Vietnamese only
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
      if (normalized.includes(keyword)) {
        return this.getAnswerText(qid);
      }
    }

    // Default response
    return this.getNotFoundMessage();
  }

  processTemplate(template) {
    // Replace business data placeholders
    let processed = template;
    
    // Replace business.contact references
    if (this.business.contact) {
      processed = processed.replace(/{{s*business.contact.phones*}}/g, this.business.contact.phone || '');
      processed = processed.replace(/{{s*business.contact.phone_uris*}}/g, this.business.contact.phone_uri || '');
      processed = processed.replace(/{{s*business.contact.zalos*}}/g, this.business.contact.zalo || '');
      processed = processed.replace(/{{s*business.contact.whatsapps*}}/g, this.business.contact.whatsapp || '');
      processed = processed.replace(/{{s*business.contact.mapss*}}/g, this.business.contact.maps || '');
      processed = processed.replace(/{{s*business.contact.emails*}}/g, this.business.contact.email || '');
    }

    // Replace business.address references
    if (this.business.address) {
      processed = processed.replace(/{{s*business.address.fulls*}}/g, this.business.address.full || '');
    }

    // Replace business.hours
    if (this.business.hours) {
      processed = processed.replace(/{{s*business.hourss*}}/g, this.business.hours);
    }

    // Replace business.display_name
    if (this.business.display_name) {
      processed = processed.replace(/{{s*business.display_names*}}/g, this.business.display_name);
    }

    // Replace business.url
    if (this.business.url) {
      processed = processed.replace(/{{s*business.urls*}}/g, this.business.url);
    }

    // Replace site.url
    if (window.NGUYEN_TU_BUSINESS && window.NGUYEN_TU_BUSINESS.url) {
      processed = processed.replace(/{{s*site.urls*}}/g, window.NGUYEN_TU_BUSINESS.url);
    }

    return processed;
  }

  getNotFoundMessage() {
    return 'Mình chưa có thông tin chắc chắn về nội dung này. Bạn có thể liên hệ Nguyễn Tú qua Zalo, WhatsApp hoặc điện thoại để xác nhận.';
  }

  addMessage(text, type) {
    if (!this.messages) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = 'assistant-message ' + type;
    messageDiv.textContent = text;
    
    this.messages.appendChild(messageDiv);
    this.messages.scrollTop = this.messages.scrollHeight;

    // Update badge
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

// Initialize assistant when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  new NguyenTuAssistant();
});