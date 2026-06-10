'use strict';

(function () {
  function getInputs(root, selector) {
    const scope = root && root.querySelectorAll ? root : document;
    const inputs = Array.from(scope.querySelectorAll(selector));

    if (scope.matches && scope.matches(selector)) {
      inputs.unshift(scope);
    }

    return inputs.filter(function (input) {
      return !input.dataset.datepickerInitialized;
    });
  }

  function applyPicker(input, options) {
    if (!window.flatpickr || input.disabled) {
      return;
    }

    input.dataset.datepickerInitialized = 'true';
    input.setAttribute('autocomplete', 'off');

    window.flatpickr(
      input,
      Object.assign(
        {
          allowInput: false,
          disableMobile: true
        },
        options
      )
    );
  }

  function initializeDatePickers(root) {
    getInputs(root, 'input[type="date"], input[data-date-picker="date"]').forEach(function (input) {
      applyPicker(input, {
        dateFormat: 'Y-m-d'
      });
    });

    getInputs(root, 'input[type="datetime-local"], input[data-date-picker="datetime"]').forEach(function (input) {
      applyPicker(input, {
        dateFormat: 'Y-m-d\\TH:i',
        enableTime: true,
        minuteIncrement: 1,
        time_24hr: true
      });
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initializeDatePickers(document);
  });

  document.body.addEventListener('htmx:afterSwap', function (event) {
    initializeDatePickers(event.target);
  });
})();
