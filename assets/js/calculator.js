// DIGITAL FLAGSHIP EXPERIENCE - Rental Calculator

(function() {
  'use strict';

  var PACKAGES = {
    day: { days: 1, label: { vi: 'ngay', en: 'day' } },
    week: { days: 7, label: { vi: 'tuan', en: 'week' } },
    month: { days: 30, label: { vi: 'thang', en: 'month' } }
  };

  var VALID_RATE_TYPES = ['day', 'week', 'month'];

  var Calculator = {
    init: function() {
      this._bindForm();
      this._bindVehicleSelect();
    },
    _bindForm: function() {
      var form = document.querySelector('.calculator__form');
      if (!form) return;
      form.addEventListener('input', this._handleInput.bind(this));
      form.addEventListener('change', this._handleInput.bind(this));
    },
    _bindVehicleSelect: function() {
      var vehicleSelect = document.querySelector('[name="vehicle"]');
      if (!vehicleSelect) return;
      vehicleSelect.addEventListener('change', this._handleVehicleChange.bind(this));
    },
    _handleInput: function() { this._calculate(); },
    _handleVehicleChange: function() {
      this._calculate();
      this._updateWhatsAppMessage();
    },
    _calculate: function() {
      var vehicleSelect = document.querySelector('[name="vehicle"]');
      var daysInput = document.querySelector('[name="days"]');
      if (!vehicleSelect || !daysInput) return;
      var vehicleId = vehicleSelect.value;
      var days = parseInt(daysInput.value) || 0;
      if (days <= 0) { this._displayNoPrice(); return; }
      var vehicle = this._getVehicleData(vehicleId);
      if (!vehicle) { this._displayNoPrice(); return; }
      var hasValidPrices = this._hasValidPrices(vehicle);
      if (!hasValidPrices) { this._displayNoPriceState(); return; }
      var minEstimate = this._calculateMinimumEstimate(vehicle, days);
      var maxEstimate = this._calculateMaximumEstimate(vehicle, days);
      this._displayResult(vehicle, days, minEstimate, maxEstimate);
      this._updateWhatsAppMessage(vehicle, days, minEstimate);
    },
    _getVehicleData: function(vehicleId) {
      return window.calculatorData && window.calculatorData.vehicles
        ? window.calculatorData.vehicles[vehicleId] : null;
    },
    _hasValidPrices: function(vehicle) {
      if (!vehicle || !vehicle.prices) return false;
      for (var type in vehicle.prices) {
        if (VALID_RATE_TYPES.indexOf(type) !== -1 && vehicle.prices[type] !== null) {
          return true;
        }
      }
      return false;
    },
    _calculateMinimumEstimate: function(vehicle, days) {
      return this._findCheapestCombination(vehicle, days, 'min');
    },
    _calculateMaximumEstimate: function(vehicle, days) {
      return this._findCheapestCombination(vehicle, days, 'max');
    },
    _findCheapestCombination: function(vehicle, days, type) {
      var rates = {};
      for (var i = 0; i < VALID_RATE_TYPES.length; i++) {
        var rateType = VALID_RATE_TYPES[i];
        if (vehicle.prices && vehicle.prices[rateType] !== null && vehicle.prices[rateType] !== undefined) {
          rates[rateType] = vehicle.prices[rateType];
        }
      }
      if (Object.keys(rates).length === 0) return null;
      var minTotal = Infinity;
      var bestCombination = null;
      var maxMonths = Math.ceil(days / 30) + 2;
      var maxWeeks = Math.ceil(days / 7) + 2;
      var maxDays = days + 1;
      for (var m = 0; m <= maxMonths; m++) {
        for (var w = 0; w <= maxWeeks; w++) {
          for (var d = 0; d <= maxDays; d++) {
            var totalDays = m * 30 + w * 7 + d * 1;
            if (totalDays >= days) {
              var totalPrice = 0;
              if (rates.month && m > 0) totalPrice += m * rates.month;
              if (rates.week && w > 0) totalPrice += w * rates.week;
              if (rates.day && d > 0) totalPrice += d * rates.day;
              if (type === 'min') {
                if (totalPrice < minTotal) {
                  minTotal = totalPrice;
                  bestCombination = { months: m, weeks: w, days: d, totalDays: totalDays, totalPrice: totalPrice };
                }
              } else {
                if (totalPrice > minTotal) {
                  minTotal = totalPrice;
                  bestCombination = { months: m, weeks: w, days: d, totalDays: totalDays, totalPrice: totalPrice };
                }
              }
            }
          }
        }
      }
      return bestCombination ? bestCombination.totalPrice : null;
    },
    _displayResult: function(vehicle, days, minEstimate, maxEstimate) {
      var resultEl = document.querySelector('.calculator__result');
      var breakdownEl = document.querySelector('.calculator__breakdown');
      if (!resultEl) return;
      var lang = document.documentElement.lang || document.querySelector('html').lang || 'vi';
      var formattedPrice = this._formatPrice(minEstimate, lang);
      var resultTitle = document.querySelector('.calculator__result-title');
      var resultValue = document.querySelector('.calculator__result-value');
      if (resultTitle) resultTitle.textContent = lang === 'en' ? 'Estimated Price:' : 'Gia uoc tinh:';
      if (resultValue) resultValue.textContent = formattedPrice;
      if (breakdownEl && minEstimate && maxEstimate) {
        var breakdownTitle = breakdownEl.querySelector('.calculator__breakdown-title');
        var breakdownContent = breakdownEl.querySelector('.calculator__breakdown-content');
        if (breakdownTitle) breakdownTitle.textContent = lang === 'en' ? 'Price Breakdown' : 'Chi tiet gia';
        if (breakdownContent) {
          breakdownContent.innerHTML = '';
          var minItem = document.createElement('div');
          minItem.className = 'calculator__breakdown-item';
          minItem.innerHTML = '<span>' + (lang === 'en' ? 'Minimum' : 'Toi thieu') + '</span><span>' + this._formatPrice(minEstimate, lang) + '</span>';
          breakdownContent.appendChild(minItem);
          var maxItem = document.createElement('div');
          maxItem.className = 'calculator__breakdown-item';
          maxItem.innerHTML = '<span>' + (lang === 'en' ? 'Maximum' : 'Toi da') + '</span><span>' + this._formatPrice(maxEstimate, lang) + '</span>';
          breakdownContent.appendChild(maxItem);
        }
      }
      resultEl.style.display = 'block';
      if (breakdownEl) breakdownEl.style.display = 'block';
    },
    _displayNoPriceState: function() {
      var resultEl = document.querySelector('.calculator__result');
      var breakdownEl = document.querySelector('.calculator__breakdown');
      if (!resultEl) return;
      var lang = document.documentElement.lang || document.querySelector('html').lang || 'vi';
      var message = lang === 'en' ? 'Contact Nguyen Tu for current pricing' : 'Lien he Nguyen Tu de kiem tra gia hien tai';
      var resultTitle = document.querySelector('.calculator__result-title');
      var resultValue = document.querySelector('.calculator__result-value');
      if (resultTitle) resultTitle.textContent = lang === 'en' ? 'Price Not Available' : 'Gia chua co';
      if (resultValue) resultValue.textContent = message;
      if (breakdownEl) breakdownEl.style.display = 'none';
      resultEl.style.display = 'block';
    },
    _displayNoPrice: function() { this._displayNoPriceState(); },
    _formatPrice: function(price, lang) {
      if (price === null || price === undefined) return lang === 'en' ? 'N/A' : 'Khong co';
      var currency = lang === 'en' ? 'USD' : 'VND';
      if (currency === 'VND') return price.toLocaleString('vi-VN') + 'd';
      else return '$' + price.toLocaleString('en-US');
    },
    _updateWhatsAppMessage: function(vehicle, days, price) {
      var vehicleName = vehicle ? (vehicle.name || (vehicle.id || 'vehicle')) : 'vehicle';
      var lang = document.documentElement.lang || document.querySelector('html').lang || 'vi';
      var whatsappBtn = document.querySelector('[data-whatsapp-calculator]');
      if (!whatsappBtn) return;
      var message = '';
      if (lang === 'en') {
        message = 'Hello Nguyen Tu, I want to rent ' + vehicleName + ' for ' + days + ' days. Website estimated price: ' + (price ? this._formatPrice(price, 'en') : 'N/A') + '. Please check availability and current pricing.';
      } else {
        message = 'Xin chao Nguyen Tu, toi muon thue ' + vehicleName + ' trong ' + days + ' ngay. Gia website uoc tinh ' + (price ? this._formatPrice(price, 'vi') : 'chua co') + '. Vui long kiem tra tinh trang xe va gia hien tai.';
      }
      var phoneNumber = '84942467674';
      var whatsappUrl = 'https://wa.me/' + phoneNumber + '?text=' + encodeURIComponent(message);
      whatsappBtn.href = whatsappUrl;
    }
  };
  function initCalculator() { Calculator.init(); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCalculator);
  } else { initCalculator(); }
  window.Calculator = Calculator;
})();