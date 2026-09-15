/**
 * NGUYEN TU BLOG - Rule-based Assistant
 * FIXED: Removed all .vi/.en accessors - now uses direct scalar access
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

    for (const qq of this.quickQuestions) {
      const qText = qq.question?.toLowerCase() || '';
      if (normalized.includes(qText) || qText.includes(normalized)) {
        return this.processTemplate(qq.answer || this.getNotFoundMessage());
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
      if (normalized.includes(keyword)) {
        return this.getAnswerText(qid);
      }
    }

    return this.getNotFoundMessage();
  }

  processTemplate(template) {
    let processed = template;
    
    if (this.business.contact) {
      processed = processed.replace(/{{s*business\.contact\.phones*}}/g, this.business.contact.phone || '');
      processed = processed.replace(/{{s*business\.contact\.phone_uris*}}/g, this.business.contact.phone_uri || '');
      processed = processed.replace(/{{s*business\.contact\.zalos*}}/g, this.business.contact.zalo || '');
      processed = processed.replace(/{{s*business\.contact\.whatsapps*}}/g, this.business.contact.whatsapp || '');
      processed = processed.replace(/{{s*business\.contact\.mapss*}}/g, this.business.contact.maps || '');
      processed = processed.replace(/{{s*business\.contact\.emails*}}/g, this.business.contact.email || '');
    }

    if (this.business.address) {
      processed = processed.replace(/{{s*business\.address\.fulls*}}/g, this.business.address.full || '');
    }

    if (this.business.hours) {
      processed = processed.replace(/{{s*business\.hourss*}}/g, this.business.hours);
    }

    if (this.business.display_name) {
      processed = processed.replace(/{{s*business\.display_names*}}/g, this.business.display_name);
    }

    if (this.business.url) {
      processed = processed.replace(/{{s*business\.urls*}}/g, this.business.url);
    }

    if (window.NGUYEN_TU_BUSINESS && window.NGUYEN_TU_BUSINESS.url) {
      processed = processed.replace(/{{s*site\.urls*}}/g, window.NGUYEN_TU_BUSINESS.url);
    }

    return processed;
  }

  getNotFoundMessage() {
    return 'Minh chua co thong tin chac chan ve noi dung nay. Ban co the lien he Nguyen Tu qua Zalo, WhatsApp hoac dien thoai de xac nhan.';
  }

  addMessage(text, type) {
    if (!this.messages) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = 'assistant-message ' + type;
    messageDiv.textContent = text;
    
    this.messages.appendChild(messageDiv);
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