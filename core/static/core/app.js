document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.querySelector('[data-menu]');
  if (toggle) toggle.addEventListener('click', () => {
    const open = document.body.classList.toggle('nav-open');
    toggle.setAttribute('aria-expanded', String(open));
  });
  document.querySelectorAll('.decision-form').forEach(form => {
    const action = form.querySelector('[name="action"]');
    const update = () => {
      form.querySelectorAll('[data-action-fields]').forEach(group => {
        const visible = group.dataset.actionFields.split(' ').includes(action.value);
        group.hidden = !visible;
        group.querySelectorAll('input, textarea, select').forEach(field => field.disabled = !visible);
      });
    };
    action.addEventListener('change', update);
    update();
  });
});
document.addEventListener('htmx:beforeSwap', event => {
  if (event.detail.xhr.status === 422) {
    event.detail.shouldSwap = true;
    event.detail.isError = false;
  }
});
