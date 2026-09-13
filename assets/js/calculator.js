/**
 * NGUYEN TU BLOG - Rental Price Calculator
 * Pure JavaScript, no dependencies
 */

class RentalCalculator {
  constructor() {
    this.pricing = window.NGUYEN_TU_PRICING || {};
    this.currentLang = document.documentElement.lang || 'vi';
    this.init();
  }

  init() {
    this.vehicleSelect = document.getElementById('vehicle-select');
    this.daysInput = document.getElementById('days-input');
    this.estimatedPrice = document.getElementById('estimated-price');
    this.priceBreakdown = document.getElementById('price-breakdown');
    
    if (!this.vehicleSelect || !this.daysInput || !this.estimatedPrice) return;

    // Load pricing data from data attribute or global
    this.loadPricingData();
    
    // Set up event listeners
    this.vehicleSelect.addEventListener('change', () => this.calculate());
    this.daysInput.addEventListener('input', () => this.calculate());
    
    // Quick day buttons
    document.querySelectorAll('.day-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const days = parseInt(btn.dataset.days);
        this.daysInput.value = days;
        this.calculate();
      });
    });

    // Initial calculation
    this.calculate();
  }

  loadPricingData() {
    // Try to get from global variable (set in layout)
    if (window.NGUYEN_TU_PRICING) {
      this.pricing = window.NGUYEN_TU_PRICING;
      return;
    }

    // Try to get from data attributes on select options
    const options = this.vehicleSelect?.querySelectorAll('option');
    if (options && options.length > 0) {
      this.pricing.vehicles = [];
      options.forEach(opt => {
        const vehicle = {
          id: opt.value,
          name: opt.dataset.name || opt.text,
          category: opt.dataset.category || '',
          rates: {
            day: {
              min: parseFloat(opt.dataset.dayMin) || 0,
              max: parseFloat(opt.dataset.dayMax) || 0
            },
            week: {
              min: parseFloat(opt.dataset.weekMin) || null,
              max: parseFloat(opt.dataset.weekMax) || null
            },
            month: {
              min: parseFloat(opt.dataset.monthMin) || null,
              max: parseFloat(opt.dataset.monthMax) || null
            }
          }
        };
        this.pricing.vehicles.push(vehicle);
      });
    }
  }

  getSelectedVehicle() {
    const selectedId = this.vehicleSelect.value;
    return this.pricing.vehicles?.find(v => v.id === selectedId);
  }

  getDays() {
    return parseInt(this.daysInput.value) || 1;
  }

  calculate() {
    const vehicle = this.getSelectedVehicle();
    const days = this.getDays();

    if (!vehicle) {
      this.updateResults('Chon xe va ngay', 'Select vehicle and days');
      return;
    }

    const result = this.calculateOptimalPrice(vehicle, days);
    this.updateResults(result.formatted, result.breakdown);
  }

  calculateOptimalPrice(vehicle, days) {
    const rates = vehicle.rates || {};
    
    // Get all rate types with their day equivalents
    const rateTypes = [
      { type: 'month', days: 30, rate: rates.month },
      { type: 'week', days: 7, rate: rates.week },
      { type: 'day', days: 1, rate: rates.day }
    ];

    let remainingDays = days;
    let totalMin = 0;
    let totalMax = 0;
    const breakdown = [];

    // Try to use largest units first (month, then week, then day)
    for (const rateType of rateTypes) {
      if (!rateType.rate || rateType.rate.min === null || rateType.rate.max === null) continue;

      const count = Math.floor(remainingDays / rateType.days);
      if (count > 0) {
        const usedDays = count * rateType.days;
        const min = count * rateType.rate.min;
        const max = count * rateType.rate.max;
        
        totalMin += min;
        totalMax += max;
        remainingDays -= usedDays;
        
        const typeNames = {
          vi: { month: 'thang', week: 'tuan', day: 'ngay' },
          en: { month: 'month', week: 'week', day: 'day' }
        };
        const lang = this.currentLang.startsWith('vi') ? 'vi' : 'en';
        
        breakdown.push({
          count: count,
          type: rateType.type,
          name: typeNames[lang][rateType.type] || rateType.type,
          min: min,
          max: max
        });
      }
    }

    // Handle remaining days with day rate
    if (remainingDays > 0 && rates.day && rates.day.min !== null) {
      const min = remainingDays * rates.day.min;
      const max = remainingDays * rates.day.max;
      totalMin += min;
      totalMax += max;
      
      const typeNames = {
        vi: { day: 'ngay' },
        en: { day: 'day' }
      };
      const lang = this.currentLang.startsWith('vi') ? 'vi' : 'en';
      
      breakdown.push({
        count: remainingDays,
        type: 'day',
        name: typeNames[lang].day || 'day',
        min: min,
        max: max
      });
    }

    // Format the result
    const currency = this.pricing.currency || 'VND';
    const symbol = this.pricing.currency_symbol || 'd';
    
    let formatted;
    if (totalMin === totalMax) {
      formatted = this.formatCurrency(totalMin, currency, symbol);
    } else {
      formatted = this.formatCurrency(totalMin, currency, symbol) + ' - ' + this.formatCurrency(totalMax, currency, symbol);
    }

    return { formatted, breakdown, totalMin, totalMax };
  }

  formatCurrency(amount, currency, symbol) {
    const lang = this.currentLang.startsWith('vi') ? 'vi-VN' : 'en-US';
    const formatted = new Intl.NumberFormat(lang, {
      style: 'currency',
      currency: currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(amount);
    
    // Replace currency symbol with custom one if needed
    if (symbol !== formatted.charAt(0) && symbol !== formatted.slice(-1)) {
      const clean = formatted.replace(/[\s\$\u20AB]/g, '');
      return clean + symbol;
    }
    return formatted;
  }

  updateResults(formatted, breakdown) {
    if (this.estimatedPrice) {
      this.estimatedPrice.textContent = formatted;
    }

    if (this.priceBreakdown && breakdown && breakdown.length > 0) {
      const lang = this.currentLang.startsWith('vi') ? 'vi' : 'en';
      const breakdownText = breakdown.map(b => {
        const countText = b.count > 1 ? b.count + ' ' + b.name : b.name;
        const priceText = b.min === b.max 
          ? this.formatCurrency(b.min, this.pricing.currency || 'VND', this.pricing.currency_symbol || 'd')
          : this.formatCurrency(b.min, this.pricing.currency || 'VND', this.pricing.currency_symbol || 'd') + ' - ' + this.formatCurrency(b.max, this.pricing.currency || 'VND', this.pricing.currency_symbol || 'd');
        return countText + ' x ' + priceText;
      }).join(' + ');
      
      this.priceBreakdown.innerHTML = '<p>' + breakdownText + '</p>';
    }
  }
}

// Initialize calculator when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  new RentalCalculator();
});
