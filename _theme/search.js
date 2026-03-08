(function() {
  'use strict';

  var searchIndex = null;
  var searchResultsEl = null;
  var SEARCH_INDEX_URL = '/search-index.json';

  function init() {
    createResultsContainer();
    interceptForms();
    checkUrlForSearch();
  }

  // ── Create results container ────────────────────────
  function createResultsContainer() {
    searchResultsEl = document.createElement('div');
    searchResultsEl.id = 'searchResults';
    searchResultsEl.className = 'search-results-container';
    searchResultsEl.setAttribute('role', 'region');
    searchResultsEl.setAttribute('aria-label', 'Search results');
    searchResultsEl.style.display = 'none';

    var header = document.getElementById('siteHeader');
    if (header && header.nextSibling) {
      header.parentNode.insertBefore(searchResultsEl, header.nextSibling);
    } else {
      document.body.appendChild(searchResultsEl);
    }
  }

  // ── Intercept all search forms ──────────────────────
  function interceptForms() {
    var forms = document.querySelectorAll(
      '.header-search-form, .mobile-search-form, .mobile-nav-search form, .mobile-nav-panel form'
    );
    forms.forEach(function(form) {
      form.addEventListener('submit', function(e) {
        e.preventDefault();
        var input = form.querySelector('input[name="s"]');
        if (input && input.value.trim()) {
          performSearch(input.value.trim());
        }
      });
    });
  }

  // ── Check URL for ?s= parameter on page load ───────
  function checkUrlForSearch() {
    var params = new URLSearchParams(window.location.search);
    var query = params.get('s');
    if (query) {
      document.querySelectorAll('input[name="s"]').forEach(function(input) {
        input.value = query;
      });
      performSearch(query);
    }
  }

  // ── Fetch index (with caching) ──────────────────────
  function fetchIndex(callback) {
    if (searchIndex) {
      callback(searchIndex);
      return;
    }
    var xhr = new XMLHttpRequest();
    xhr.open('GET', SEARCH_INDEX_URL);
    xhr.onload = function() {
      if (xhr.status === 200) {
        searchIndex = JSON.parse(xhr.responseText);
        callback(searchIndex);
      }
    };
    xhr.send();
  }

  // ── Main search function ────────────────────────────
  function performSearch(query) {
    var url = new URL(window.location);
    url.searchParams.set('s', query);
    history.pushState({}, '', url);

    closeMobilePanels();
    showLoading(query);

    fetchIndex(function(index) {
      var results = scoreResults(query, index);
      renderResults(query, results);
    });
  }

  // ── Scoring algorithm ───────────────────────────────
  function scoreResults(query, index) {
    var queryLower = query.toLowerCase();
    var words = queryLower.split(/\s+/).filter(function(w) {
      return w.length > 1;
    });

    if (words.length === 0) return [];

    var scored = [];

    for (var i = 0; i < index.length; i++) {
      var entry = index[i];
      var titleLower = (entry.title || '').toLowerCase();
      var descLower = (entry.description || '').toLowerCase();
      var contentLower = (entry.content || '').toLowerCase();
      var score = 0;

      // Exact phrase match in title
      if (titleLower.indexOf(queryLower) !== -1) {
        score += 20;
      }

      // Exact phrase match in description
      if (descLower.indexOf(queryLower) !== -1) {
        score += 8;
      }

      // Individual word matches
      for (var j = 0; j < words.length; j++) {
        var word = words[j];
        if (titleLower.indexOf(word) !== -1) score += 10;
        if (descLower.indexOf(word) !== -1) score += 5;
        if (contentLower.indexOf(word) !== -1) score += 1;
      }

      // Boost dosage and article pages
      if (entry.type === 'dosage' || entry.type === 'article') {
        score = Math.ceil(score * 1.1);
      }

      // Demote legal/category pages
      if (entry.type === 'legal') {
        score = Math.floor(score * 0.5);
      }
      if (entry.type === 'category') {
        score = Math.floor(score * 0.7);
      }

      if (score > 0) {
        scored.push({ entry: entry, score: score });
      }
    }

    scored.sort(function(a, b) { return b.score - a.score; });
    return scored.slice(0, 20);
  }

  // ── Render search results ───────────────────────────
  function renderResults(query, results) {
    var html = '<div class="search-results-inner">';
    html += '<div class="search-results-header">';
    html += '<h2>Search Results for \u201c<span class="search-query-text">' +
            escapeHtml(query) + '</span>\u201d</h2>';
    html += '<button class="search-close-btn" aria-label="Close search results">';
    html += '<i class="fas fa-times"></i></button>';
    html += '</div>';

    if (results.length === 0) {
      html += '<div class="search-no-results">';
      html += '<i class="fas fa-search"></i>';
      html += '<p>No results found for \u201c<strong>' + escapeHtml(query) + '</strong>\u201d</p>';
      html += '<p class="search-suggestions">Try different keywords or browse our ';
      html += '<a href="/dosages-and-protocols/">dosage protocols</a> and ';
      html += '<a href="/articles/">articles</a>.</p>';
      html += '</div>';
    } else {
      html += '<p class="search-result-count">' + results.length + ' result' +
              (results.length !== 1 ? 's' : '') + ' found</p>';
      html += '<div class="search-results-list">';

      for (var i = 0; i < results.length; i++) {
        var r = results[i].entry;
        var typeLabel = getTypeLabel(r.type);

        html += '<a href="' + r.url + '" class="search-result-card">';
        html += '<div class="search-result-type">' + typeLabel + '</div>';
        html += '<h3 class="search-result-title">' + highlightTerms(r.title, query) + '</h3>';
        if (r.description) {
          html += '<p class="search-result-desc">' +
                  highlightTerms(truncate(r.description, 160), query) + '</p>';
        }
        html += '</a>';
      }

      html += '</div>';
    }

    html += '</div>';

    searchResultsEl.innerHTML = html;
    searchResultsEl.style.display = 'block';

    searchResultsEl.scrollIntoView({ behavior: 'smooth', block: 'start' });

    var closeBtn = searchResultsEl.querySelector('.search-close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeSearch);
    }
  }

  // ── Close search ────────────────────────────────────
  function closeSearch() {
    searchResultsEl.style.display = 'none';
    searchResultsEl.innerHTML = '';
    var url = new URL(window.location);
    url.searchParams.delete('s');
    history.pushState({}, '', url.pathname);
  }

  // ── Loading state ───────────────────────────────────
  function showLoading(query) {
    searchResultsEl.innerHTML = '<div class="search-results-inner">' +
      '<div class="search-loading"><i class="fas fa-spinner fa-spin"></i>' +
      ' Searching for \u201c' + escapeHtml(query) + '\u201d\u2026</div></div>';
    searchResultsEl.style.display = 'block';
  }

  // ── Type labels ─────────────────────────────────────
  function getTypeLabel(type) {
    var labels = {
      dosage: 'Dosage Protocol',
      article: 'Article',
      guide: 'Guide',
      blog: 'Blog',
      category: 'Category',
      tool: 'Tool',
      info: 'Info',
      index: 'Index',
      legal: 'Legal',
      page: 'Page'
    };
    return labels[type] || 'Page';
  }

  // ── Close mobile panels ─────────────────────────────
  function closeMobilePanels() {
    var overlay = document.getElementById('mobileSearchOverlay');
    var navPanel = document.getElementById('mobileNavPanel');
    var mobileOverlay = document.getElementById('mobileOverlay');
    var hamburger = document.getElementById('mobileHamburgerBtn');

    if (overlay) overlay.classList.remove('visible');
    if (navPanel) navPanel.classList.remove('open');
    if (mobileOverlay) {
      mobileOverlay.classList.remove('visible');
      mobileOverlay.setAttribute('aria-hidden', 'true');
    }
    if (hamburger) hamburger.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  // ── Escape HTML ─────────────────────────────────────
  function escapeHtml(text) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
  }

  // ── Highlight search terms ──────────────────────────
  function highlightTerms(text, query) {
    var words = query.toLowerCase().split(/\s+/).filter(function(w) {
      return w.length > 1;
    });
    var escaped = escapeHtml(text);
    words.forEach(function(word) {
      var regex = new RegExp('(' + word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi');
      escaped = escaped.replace(regex, '<mark>$1</mark>');
    });
    return escaped;
  }

  // ── Truncate text ───────────────────────────────────
  function truncate(text, maxLen) {
    if (text.length <= maxLen) return text;
    return text.substring(0, maxLen).replace(/\s+\S*$/, '') + '\u2026';
  }

  // ── Run on DOM ready ────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
