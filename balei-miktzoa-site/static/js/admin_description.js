(function(global){
  if (global.AdminDescription) {
    return;
  }
  var STATUS_POLL_INTERVAL = 4000;
  var SCROLL_STORAGE_KEY = 'admin_pending_scroll';
  var scrollInitialized = false;
  function getCsrfToken(){
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
  }
  function showMessage(panel, text, tone){
    var feedback = panel.querySelector('[data-role="panel-feedback"]');
    if (!feedback) return;
    feedback.textContent = text || '';
    feedback.setAttribute('data-tone', tone || 'info');
  }
  function setBusy(panel, busy){
    ['[data-action="generate"]', '[data-action="refresh-status"]', '[data-action="next-prompt"]'].forEach(function(selector){
      var btn = panel.querySelector(selector);
      if (btn) {
        if (busy) {
          btn.setAttribute('disabled', 'disabled');
          btn.classList.add('is-busy');
        } else {
          btn.removeAttribute('disabled');
          btn.classList.remove('is-busy');
        }
      }
    });
  }
  function activateTab(panel, style){
    var tabs = panel.querySelectorAll('[data-variant-tab]');
    var variantPanels = panel.querySelectorAll('.variant-panel');
    tabs.forEach(function(tab){
      var isActive = tab.getAttribute('data-variant-tab') === style;
      tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
      tab.classList.toggle('is-active', isActive);
    });
    variantPanels.forEach(function(el){
      if (el.getAttribute('data-variant-style') === style) {
        el.classList.add('is-active');
      } else {
        el.classList.remove('is-active');
      }
    });
  }
  function initTabs(panel){
    var initialStyle = panel.getAttribute('data-initial-style');
    if (!initialStyle) {
      var firstTab = panel.querySelector('[data-variant-tab]');
      initialStyle = firstTab ? firstTab.getAttribute('data-variant-tab') : null;
    }
    if (initialStyle) {
      activateTab(panel, initialStyle);
    }
    panel.querySelectorAll('[data-variant-tab]').forEach(function(tab){
      tab.addEventListener('click', function(){
        var style = tab.getAttribute('data-variant-tab');
        activateTab(panel, style);
      });
    });
  }
  function parseVariantPayload(article){
    if (!article) return null;
    var payloadStr = article.getAttribute('data-variant');
    if (!payloadStr) return null;
    try {
      return JSON.parse(payloadStr);
    } catch (err) {
      console.error('Failed to parse variant payload', err);
      return null;
    }
  }
  function handleSelect(panel, article){
    var payload = parseVariantPayload(article);
    if (!payload || (!payload.teaser && !payload.body)) {
      showMessage(panel, 'אין תוכן לשמירה בסגנון זה.', 'warning');
      return;
    }
    var url = panel.getAttribute('data-select-url');
    if (!url) return;
    showMessage(panel, 'שומר תיאור שנבחר…', 'info');
    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'fetch',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({
        style: payload.style || '',
        source: payload.source || 'ai',
        teaser: payload.teaser || '',
        body: payload.body || ''
      })
    }).then(function(resp){
      if (!resp.ok) {
        throw new Error('select_failed');
      }
      return resp.json();
    }).then(function(){
      showMessage(panel, 'נשמר בהצלחה. מרענן…', 'success');
      setTimeout(function(){ window.location.reload(); }, 600);
    }).catch(function(){
      showMessage(panel, 'שמירת התיאור נכשלה.', 'error');
    });
  }
  function pollStatus(panel, attempt){
    var url = panel.getAttribute('data-status-url');
    if (!url) return;
    fetch(url, { cache: 'no-store' })
      .then(function(resp){ return resp.json(); })
      .then(function(data){
        var status = (data && data.status) || 'idle';
        if (status === 'done') {
          showMessage(panel, 'ה-AI סיים לעבוד. מרענן…', 'success');
          setTimeout(function(){ window.location.reload(); }, 600);
          return;
        }
        if (status === 'error') {
          showMessage(panel, 'אירעה שגיאה בעיבוד ה-AI.', 'error');
          setBusy(panel, false);
          return;
        }
        var tone = (status === 'running' || status === 'pending') ? 'info' : 'muted';
        var text = (status === 'running' || status === 'pending') ? 'ה-AI עדיין פועל…' : 'אין עבודה פעילה כרגע.';
        showMessage(panel, text, tone);
        setTimeout(function(){ pollStatus(panel, (attempt || 0) + 1); }, STATUS_POLL_INTERVAL);
      }).catch(function(){
        showMessage(panel, 'לא ניתן למשוך סטטוס.', 'error');
        setBusy(panel, false);
      });
  }
  function replacePanel(panel, html, message, tone){
    if (!html) {
      if (message) {
        showMessage(panel, message, tone || 'info');
      }
      setBusy(panel, false);
      return;
    }
    var temp = document.createElement('div');
    temp.innerHTML = html;
    var nextPanel = temp.querySelector('.description-panel');
    if (!nextPanel) {
      if (message) {
        showMessage(panel, message, tone || 'info');
      }
      setBusy(panel, false);
      return;
    }
    panel.replaceWith(nextPanel);
    if (global.AdminDescription) {
      global.AdminDescription.setupPanel(nextPanel);
    }
    initPreserveScroll();
    if (message) {
      showMessage(nextPanel, message, tone || 'info');
    }
  }
  function handleGenerate(panel){
    var url = panel.getAttribute('data-generate-url');
    if (!url) return;
    setBusy(panel, true);
    showMessage(panel, 'שולח בקשה ל-AI…', 'info');
    var formData = new FormData();
    formData.append('csrf_token', getCsrfToken());
    fetch(url, {
      method: 'POST',
      body: formData,
      headers: {
        'X-Requested-With': 'fetch'
      }
    }).then(function(resp){
      if (!resp.ok) {
        throw new Error('generate_failed');
      }
      showMessage(panel, 'הבקשה נשלחה. נעקוב אחרי ההתקדמות…', 'info');
      pollStatus(panel, 0);
    }).catch(function(){
      showMessage(panel, 'הבקשה ל-AI נכשלה.', 'error');
      setBusy(panel, false);
    });
  }
  function handleRefresh(panel){
    showMessage(panel, 'בודק סטטוס…', 'info');
    pollStatus(panel, 0);
  }
  function handleNextPrompt(panel){
    var url = panel.getAttribute('data-next-prompt-url');
    if (!url) {
      return;
    }
    setBusy(panel, true);
    showMessage(panel, 'יוצר וריאנט נוסף…', 'info');
    var formData = new FormData();
    formData.append('csrf_token', getCsrfToken());
    var modalAttr = panel.getAttribute('data-is-modal');
    if (modalAttr !== null) {
      formData.append('is_modal', modalAttr);
    }
    fetch(url, {
      method: 'POST',
      body: formData,
      headers: {
        'X-Requested-With': 'fetch',
        'Accept': 'application/json'
      }
    }).then(function(resp){
      if (!resp.ok) {
        throw new Error('next_prompt_failed');
      }
      return resp.json();
    }).then(function(data){
      var tone = (data && data.tone) || (data && data.ok ? 'success' : 'error');
      var message = (data && data.message) || '';
      if (data && data.panel_html) {
        replacePanel(panel, data.panel_html, message, tone);
        return;
      }
      showMessage(panel, message || 'הפעולה הושלמה.', tone || 'info');
      setBusy(panel, false);
    }).catch(function(){
      showMessage(panel, 'לא הצלחנו להביא פרומפט חדש.', 'error');
      setBusy(panel, false);
    });
  }
  function setupPanel(panel){
    if (!panel || panel.__adminDescriptionReady) {
      return;
    }
    panel.__adminDescriptionReady = true;
    initTabs(panel);
    var generateBtn = panel.querySelector('[data-action="generate"]');
    if (generateBtn) {
      generateBtn.addEventListener('click', function(){ handleGenerate(panel); });
    }
    var refreshBtn = panel.querySelector('[data-action="refresh-status"]');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', function(){ handleRefresh(panel); });
    }
    var nextPromptBtn = panel.querySelector('[data-action="next-prompt"]');
    if (nextPromptBtn) {
      nextPromptBtn.addEventListener('click', function(){ handleNextPrompt(panel); });
    }
    panel.querySelectorAll('[data-action="select-variant"]').forEach(function(btn){
      btn.addEventListener('click', function(){ handleSelect(panel, btn.closest('.variant-panel')); });
    });
  }
  function bindPreserveScrollForms(){
    document.querySelectorAll('form[data-preserve-scroll]').forEach(function(form){
      if (form.__adminPreserveScrollBound) {
        return;
      }
      form.__adminPreserveScrollBound = true;
      form.addEventListener('submit', function(){
        try {
          sessionStorage.setItem(SCROLL_STORAGE_KEY, String(window.scrollY || 0));
        } catch (err) {
          // ignore storage errors (private mode, etc.)
        }
      });
    });
  }
  function initPreserveScroll(){
    bindPreserveScrollForms();
    if (scrollInitialized) {
      return;
    }
    scrollInitialized = true;
    try {
      var stored = sessionStorage.getItem(SCROLL_STORAGE_KEY);
      if (stored !== null) {
        var value = parseInt(stored, 10);
        if (!isNaN(value)) {
          window.scrollTo({ top: value, behavior: 'auto' });
        }
        sessionStorage.removeItem(SCROLL_STORAGE_KEY);
      }
    } catch (err) {
      // ignore retrieval errors
    }
  }
  var AdminDescription = {
    setupPanel: setupPanel,
    mountPanels: function(root){
      (root || document).querySelectorAll('.description-panel').forEach(setupPanel);
    }
  };
  global.AdminDescription = AdminDescription;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPreserveScroll);
  } else {
    initPreserveScroll();
  }
})(window);