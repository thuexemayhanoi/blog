// DIGITAL FLAGSHIP EXPERIENCE - Rental Calculator

(function() {
  'use strict';

  var VALID_RATE_TYPES = ['day', 'week', 'month'];

  var Calculator = {
    init: function() {
      this._bindForm();
      this._bindVehicleSelect();
    },
    _bindForm: function() {
      var form = document.querySelector('#rental-calculator');
      if (!form) return;
      form.addEventListener('input', this._handleInput.bind(this));
      form.addEventListener('change', this._handleInput.bind(this));
    },
    _bindVehicleSelect: function() {
      var vehicleSelect = document.querySelector('#vehicle-select');
      if (!vehicleSelect) return;
      vehicleSelect.addEventListener('change', this._handleVehicleChange.bind(this));
    },
    _handleInput: function() { this._calculate(); },
    _handleVehicleChange: function() {
      this._calculate();
      this._updateWhatsAppMessage();
    },
    _calculate: function() {
      var vehicleSelect = document.querySelector('#vehicle-select');
      var daysInput = document.querySelector('#days-input');
      if (!vehicleSelect || !daysInput) return;
      var vehicleId = vehicleSelect.value;
      var days = parseInt(daysInput.value) || 0;
      if (days <= 0) { this._displayNoPrice(); return; }
      var vehicle = this._getVehicleData(vehicleId);
      if (!vehicle) { this._displayNoPrice(); return; }
      var hasValidPrices = this._hasValidPrices(vehicle);
      if (!hasValidPrices) { this._displayNoPrice(); return; }
      var minEstimate = this._calculateEstimate(vehicle, days, 'min');
      var maxEstimate = this._calculateEstimate(vehicle, days, 'max');
      this._displayResult(vehicle, days, minEstimate, maxEstimate);
      this._updateWhatsAppMessage(vehicle, days, minEstimate);
    },
    _getVehicleData: function(vehicleId) {
      return window.NGUYEN_TU_PRICING && window.NGUYEN_TU_PRICING.vehicles
        ? window.NGUYEN_TU_PRICING.vehicles[vehicleId] : null;
    },
    _hasValidPrices: function(vehicle) {
      if (!vehicle || !vehicle.rates) return false;
      for (var i = 0; i < VALID_RATE_TYPES.length; i++) {
        var rateType = VALID_RATE_TYPES[i];
        if (vehicle.rates[rateType] && vehicle.rates[rateType].min !== null) {
          return true;
        }
      }
      return false;
    },
    _calculateEstimate: function(vehicle, days, rateSide) {
      var rates = {};
      for (var i = 0; i < VALID_RATE_TYPES.length; i++) {
        var rateType = VALID_RATE_TYPES[i];
        if (vehicle.rates && vehicle.rates[rateType] && vehicle.rates[rateType][rateSide] !== null) {
          rates[rateType] = vehicle.rates[rateType][rateSide];
        }
      }
      if (Object.keys(rates).length === 0) return null;
      var bestPrice = Infinity;
      var maxMonths = Math.ceil(days / 30) + 2;
      var maxWeeks = Math.ceil(days / 7) + 2;
      var maxDays = days + 1;
      for (var m = 0; m <= maxMonths; m++) {
        for (var w = 0; w <= maxWeeks; w++) {
          for (var d = 0; d <= maxDays; d++) {
            var totalDays = m * 30 + w * 7 + d * 1;
            if (totalDays >= days) {
              var totalPrice = 0;
              var valid = true;
              if (m > 0 && !rates.month) valid = false;
              if (w > 0 && !rates.week) valid = false;
              if (d > 0 && !rates.day) valid = false;
              if (valid) {
                if (m > 0) totalPrice += m * rates.month;
                if (w > 0) totalPrice += w * rates.week;
                if (d > 0) totalPrice += d * rates.day;
                if (totalPrice < bestPrice) {
                  bestPrice = totalPrice;
                }
              }
            }
          }
        }
      }
      return bestPrice !== Infinity ? bestPrice : null;
    },
    _displayResult: function(vehicle, days, minEstimate, maxEstimate) {
      var resultEl = document.querySelector('#estimated-price');
      var breakdownEl = document.querySelector('#price-breakdown');
      if (!resultEl) return;
      var lang = document.documentElement.lang || document.querySelector('html').lang || 'vi';
      resultEl.textContent = this._formatPrice(minEstimate, lang);
      if (breakdownEl && minEstimate !== null && maxEstimate !== null) {
        breakdownEl.innerHTML = '';
        var minItem = document.createElement('div');
        minItem.className = 'calculator__breakdown-item';
        minItem.innerHTML = '<span>' + (lang === 'en' ? 'Minimum' : 'Tối thiểu') + '</span><span>' + this._formatPrice(minEstimate, lang) + '</span>';
        breakdownEl.appendChild(minItem);
        var maxItem = document.createElement('div');
        maxItem.className = 'calculator__breakdown-item';
        maxItem.innerHTML = '<span>' + (lang === 'en' ? 'Maximum' : 'Tối đa') + '</span><span>' + this._formatPrice(maxEstimate, lang) + '</span>';
        breakdownEl.appendChild(maxItem);
        breakdownEl.style.display = 'block';
      }
    },
    _displayNoPrice: function() {
      var resultEl = document.querySelector('#estimated-price');
      var breakdownEl = document.querySelector('#price-breakdown');
      if (!resultEl) return;
      var lang = document.documentElement.lang || document.querySelector('html').lang || 'vi';
      resultEl.textContent = lang === 'en' ? 'Contact Nguyễn Tú for current pricing' : 'Liên hệ Nguyễn Tú để kiểm tra giá hiện tại';
      if (breakdownEl) breakdownEl.style.display = 'none';
    },
    _formatPrice: function(price, lang) {
      if (price === null || price === undefined) return lang === 'en' ? 'N/A' : 'Không có';
      if (lang === 'vi') return price.toLocaleString('vi-VN') + 'đ';
      else return price.toLocaleString('en-US') + ' VND';
    },
    _updateWhatsAppMessage: function(vehicle, days, price) {
      var vehicleName = vehicle ? (vehicle.name || (vehicle.id || 'vehicle')) : 'vehicle';
      var lang = document.documentElement.lang || document.querySelector('html').lang || 'vi';
      var whatsappBtn = document.querySelector('[data-whatsapp-calculator]');
      if (!whatsappBtn) return;
      var formattedPrice = price !== null ? this._formatPrice(price, lang) : (lang === 'en' ? 'N/A' : 'chưa có');
      var message = lang === 'en'
        ? 'Hello Nguyễn Tú, I would like to rent ' + vehicleName + ' for ' + days + ' days. The website estimate is ' + formattedPrice + '. Please confirm vehicle availability and the current price.'
        : 'Xin chào Nguyễn Tú, tôi muốn thuê ' + vehicleName + ' trong ' + days + ' ngày. Giá website ước tính ' + formattedPrice + '. Vui lòng kiểm tra tình trạng xe và giá hiện tại.';
      var phoneNumber = window.NGUYEN_TU_BUSINESS && window.NGUYEN_TU_BUSINESS.contact && window.NGUYEN_TU_BUSINESS.contact.whatsapp
        ? window.NGUYEN_TU_BUSINESS.contact.whatsapp : '84942467674';
      whatsappBtn.href = 'https://wa.me/' + phoneNumber + '?text=' + encodeURIComponent(message);
    }
  };
  function initCalculator() { Calculator.init(); }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCalculator);
  } else { initCalculator(); }
  window.Calculator = Calculator;
})();