// UAE Market Intelligence — Frontend (rebuilt)
// All fetch calls use credentials: 'include' for session cookie auth.
// Auth check runs in parallel with data loading — does NOT block rendering.

(function () {
    'use strict';

    const API_BASE = '/api';

    let allSignals = [];
    let allOpportunities = [];
    let activeFilters = { sector: 'all', type: 'all' };
    let activeOppFilter = 'all';
    let currentSearch = '';
    let autoRefreshTimer = null;

    // ======================== BOOT ========================
    document.addEventListener('DOMContentLoaded', function () {
        bindEvents();
        checkAuth();   // non-blocking — redirects only if 401
        loadAll();     // loads data immediately
        startAutoRefresh();
    });

    // ======================== AUTH (non-blocking) ========================
    function checkAuth() {
        fetch(API_BASE + '/auth/verify', { credentials: 'include' })
            .then(function (res) {
                if (!res.ok) {
                    window.location.href = 'https://aldhaheri.co';
                }
            })
            .catch(function () {
                // Network error — don't redirect, let the data calls fail visibly
            });
    }

    // ======================== DATA ========================
    function loadAll() {
        Promise.all([loadSignals(), loadOpportunities()])
            .then(function () {
                renderSectorFilters();
                applyFilters();
                renderSectorsTab();
                renderPlatformsTab();
                updateStats();
                renderOpportunities();
            });
    }

    function loadSignals() {
        return fetch(API_BASE + '?action=all', { credentials: 'include' })
            .then(function (res) {
                if (!res.ok) throw new Error('Signals API returned ' + res.status);
                return res.json();
            })
            .then(function (data) {
                allSignals = data.signals || [];
                document.getElementById('lastUpdated').textContent = 'Updated ' + formatRelative(new Date());
            })
            .catch(function (err) {
                console.error('loadSignals error:', err);
                allSignals = [];
                document.getElementById('lastUpdated').textContent = 'Unable to load signals';
                showError('feedGrid', 'Unable to load signals. Check your connection or try refreshing.');
            });
    }

    function loadOpportunities() {
        return fetch(API_BASE + '/opportunities', { credentials: 'include' })
            .then(function (res) {
                if (!res.ok) throw new Error('Opportunities API returned ' + res.status);
                return res.json();
            })
            .then(function (data) {
                allOpportunities = data.opportunities || [];
            })
            .catch(function (err) {
                console.error('loadOpportunities error:', err);
                allOpportunities = [];
                showError('opportunitiesGrid', 'Unable to load opportunities.');
            });
    }

    function refreshData() {
        var btn = document.getElementById('refreshBtn');
        btn.classList.add('spinning');
        btn.disabled = true;
        Promise.all([loadSignals(), loadOpportunities()])
            .then(function () {
                renderSectorFilters();
                applyFilters();
                renderSectorsTab();
                renderPlatformsTab();
                updateStats();
                renderOpportunities();
            })
            .finally(function () {
                setTimeout(function () {
                    btn.classList.remove('spinning');
                    btn.disabled = false;
                }, 600);
            });
    }

    function startAutoRefresh() {
        if (autoRefreshTimer) clearInterval(autoRefreshTimer);
        autoRefreshTimer = setInterval(refreshData, 5 * 60 * 1000);
    }

    // ======================== EVENT BINDING ========================
    function bindEvents() {
        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', refreshData);

        // Search input
        document.getElementById('searchInput').addEventListener('input', applyFilters);

        // Type filter chips (static)
        document.getElementById('typeFilters').addEventListener('click', function (e) {
            var chip = e.target.closest('.filter-chip');
            if (!chip) return;
            var value = chip.dataset.type;
            activeFilters.type = value;
            this.querySelectorAll('.filter-chip').forEach(function (c) { c.classList.remove('active'); });
            chip.classList.add('active');
            applyFilters();
        });

        // Sector filter chips (delegated — chips are dynamic)
        document.getElementById('sectorFilters').addEventListener('click', function (e) {
            var chip = e.target.closest('.filter-chip');
            if (!chip) return;
            var value = chip.dataset.sector;
            activeFilters.sector = value;
            this.querySelectorAll('.filter-chip').forEach(function (c) { c.classList.remove('active'); });
            chip.classList.add('active');
            applyFilters();
        });

        // Tabs
        document.querySelector('.tabs').addEventListener('click', function (e) {
            var tab = e.target.closest('.tab');
            if (!tab) return;
            var tabName = tab.dataset.tab;
            document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
            document.querySelectorAll('.tab-content').forEach(function (tc) { tc.classList.remove('active'); });
            tab.classList.add('active');
            var target = document.getElementById('tab-' + tabName);
            if (target) target.classList.add('active');
        });

        // Opportunity toggles
        document.querySelector('.opp-toggles').addEventListener('click', function (e) {
            var btn = e.target.closest('.opp-toggle');
            if (!btn) return;
            activeOppFilter = btn.dataset.oppFilter;
            this.querySelectorAll('.opp-toggle').forEach(function (b) { b.classList.remove('active'); });
            btn.classList.add('active');
            renderOpportunities();
        });

        // Methodology toggle
        document.getElementById('methodologyToggle').addEventListener('click', function () {
            var panel = document.getElementById('methodologyPanel');
            var isOpen = panel.classList.toggle('open');
            this.textContent = isOpen ? 'Hide Scoring Methodology' : 'Scoring Methodology';
        });

        // Modal close
        document.getElementById('modalOverlay').addEventListener('click', function (e) {
            if (e.target === this) closeModal();
        });
        document.getElementById('modalCloseBtn').addEventListener('click', closeModal);
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') closeModal();
        });

        // Delegated clicks for signal cards and opportunity cards
        document.getElementById('feedGrid').addEventListener('click', function (e) {
            var card = e.target.closest('.signal-card');
            if (card) openSignalModal(parseInt(card.dataset.signalId, 10));
        });

        document.getElementById('sectorsGrid').addEventListener('click', function (e) {
            var item = e.target.closest('.sector-signal-item');
            if (item) openSignalModal(parseInt(item.dataset.signalId, 10));
        });

        document.getElementById('opportunitiesGrid').addEventListener('click', function (e) {
            // Check if clicked a supporting signal tag
            var sigTag = e.target.closest('.opp-signal-tag');
            if (sigTag) {
                e.stopPropagation();
                openSignalModal(parseInt(sigTag.dataset.signalId, 10));
                return;
            }
            var card = e.target.closest('.opp-card');
            if (card) openOppModal(parseInt(card.dataset.oppId, 10));
        });

        // Nav links
        document.querySelectorAll('.project-nav a:not(.active)').forEach(function (a) {
            a.addEventListener('click', function (e) {
                e.preventDefault();
                window.location.href = this.href;
            });
        });
    }

    // ======================== FILTERS ========================
    function applyFilters() {
        currentSearch = document.getElementById('searchInput').value.toLowerCase().trim();
        var filtered = allSignals;

        if (activeFilters.sector !== 'all') {
            filtered = filtered.filter(function (s) { return s.sector === activeFilters.sector; });
        }
        if (activeFilters.type !== 'all') {
            filtered = filtered.filter(function (s) { return s.type === activeFilters.type; });
        }
        if (currentSearch) {
            filtered = filtered.filter(function (s) {
                var haystack = (s.title || '').toLowerCase() + ' ' +
                    (s.summary || '').toLowerCase() + ' ' +
                    (s.keywords || []).join(' ').toLowerCase();
                return haystack.indexOf(currentSearch) !== -1;
            });
        }
        renderFeed(filtered);
    }

    // ======================== RENDER: SECTOR FILTERS ========================
    function renderSectorFilters() {
        var sectors = [];
        var seen = {};
        allSignals.forEach(function (s) {
            if (s.sector && !seen[s.sector]) {
                seen[s.sector] = true;
                sectors.push(s.sector);
            }
        });
        sectors.sort();

        var container = document.getElementById('sectorFilters');
        var html = '<button class="filter-chip' + (activeFilters.sector === 'all' ? ' active' : '') + '" data-sector="all">All Sectors</button>';
        sectors.forEach(function (sec) {
            html += '<button class="filter-chip' + (activeFilters.sector === sec ? ' active' : '') + '" data-sector="' + esc(sec) + '">' + esc(sec) + '</button>';
        });
        container.innerHTML = html;
    }

    // ======================== RENDER: FEED ========================
    function renderFeed(signals) {
        var grid = document.getElementById('feedGrid');
        if (!signals || !signals.length) {
            grid.innerHTML = '<div class="empty-msg">No signals match the current filters.</div>';
            return;
        }
        grid.innerHTML = signals.map(function (s) { return signalCardHTML(s); }).join('');
    }

    function signalCardHTML(s) {
        var priorityClass = (s.priority || '').toLowerCase();
        return '<div class="signal-card priority-' + priorityClass + '" data-signal-id="' + s.id + '">' +
            '<div class="card-header">' +
                '<div class="card-meta">' +
                    '<span class="card-type ' + (s.type || '') + '">' + formatType(s.type) + '</span>' +
                    '<span class="card-sector">' + esc(s.sector) + '</span>' +
                '</div>' +
                '<span class="priority-badge ' + priorityClass + '">' + esc(s.priority) + '</span>' +
            '</div>' +
            '<div class="card-title">' + esc(s.title) + '</div>' +
            '<div class="card-summary">' + esc(s.summary) + '</div>' +
            '<div class="card-footer">' +
                '<div class="card-platform"><div class="platform-dot"></div>' + esc(s.platform) + '</div>' +
                '<div class="card-stats">' +
                    (s.mentions ? '<span class="card-stat">' + s.mentions + ' mentions</span>' : '') +
                '</div>' +
                '<span class="card-score">Score: ' + (s.score != null ? s.score : '--') + '</span>' +
            '</div>' +
            (s.arabic_title ? '<div class="card-arabic">' + esc(s.arabic_title) + '</div>' : '') +
        '</div>';
    }

    // ======================== RENDER: SECTORS TAB ========================
    function renderSectorsTab() {
        var sectors = {};
        allSignals.forEach(function (s) {
            if (!sectors[s.sector]) sectors[s.sector] = [];
            sectors[s.sector].push(s);
        });

        var entries = Object.keys(sectors).map(function (name) {
            return { name: name, signals: sectors[name] };
        }).sort(function (a, b) { return b.signals.length - a.signals.length; });

        var grid = document.getElementById('sectorsGrid');
        if (!entries.length) {
            grid.innerHTML = '<div class="empty-msg">No sector data available.</div>';
            return;
        }

        grid.innerHTML = entries.map(function (entry) {
            var top5 = entry.signals.slice(0, 5);
            return '<div class="sector-block">' +
                '<div class="sector-block-header">' +
                    '<div class="sector-block-name">' + esc(entry.name) + '</div>' +
                    '<div class="sector-block-count">' + entry.signals.length + ' signals</div>' +
                '</div>' +
                '<div class="sector-signal-list">' +
                    top5.map(function (s) {
                        var pClass = (s.priority || '').toLowerCase();
                        return '<div class="sector-signal-item" data-signal-id="' + s.id + '">' +
                            '<div class="sector-signal-title">' + esc(s.title) + '</div>' +
                            '<div class="sector-signal-meta">' +
                                '<span class="card-type ' + (s.type || '') + '" style="font-size:10px;">' + formatType(s.type) + '</span>' +
                                '<span class="priority-badge ' + pClass + '" style="font-size:10px;">' + esc(s.priority) + '</span>' +
                            '</div>' +
                        '</div>';
                    }).join('') +
                '</div>' +
            '</div>';
        }).join('');
    }

    // ======================== RENDER: PLATFORMS TAB ========================
    function renderPlatformsTab() {
        var platforms = {};
        allSignals.forEach(function (s) {
            if (!platforms[s.platform]) platforms[s.platform] = [];
            platforms[s.platform].push(s);
        });

        var entries = Object.keys(platforms).map(function (name) {
            return { name: name, signals: platforms[name] };
        }).sort(function (a, b) { return b.signals.length - a.signals.length; });

        var grid = document.getElementById('platformsGrid');
        if (!entries.length) {
            grid.innerHTML = '<div class="empty-msg">No platform data available.</div>';
            return;
        }

        var maxCount = Math.max.apply(null, entries.map(function (e) { return e.signals.length; }));

        grid.innerHTML = entries.map(function (entry) {
            var typesSet = {};
            entry.signals.forEach(function (s) { typesSet[s.type] = true; });
            var types = Object.keys(typesSet);
            var pct = Math.round((entry.signals.length / maxCount) * 100);

            return '<div class="platform-block">' +
                '<div class="platform-block-header">' +
                    '<div class="platform-block-name">' + esc(entry.name) + '</div>' +
                '</div>' +
                '<div class="platform-block-count">' + entry.signals.length + '</div>' +
                '<div class="platform-block-label">signals tracked</div>' +
                '<div class="platform-bar"><div class="platform-bar-fill" style="width:' + pct + '%"></div></div>' +
                '<div class="platform-types">' +
                    types.map(function (t) { return '<span class="platform-type-tag">' + formatType(t) + '</span>'; }).join('') +
                '</div>' +
            '</div>';
        }).join('');
    }

    // ======================== STATS ========================
    function updateStats() {
        animateCount('statTotal', allSignals.length);
        animateCount('statHigh', allSignals.filter(function (s) { return s.priority === 'High'; }).length);

        var sectorSet = {};
        var platformSet = {};
        allSignals.forEach(function (s) {
            if (s.sector) sectorSet[s.sector] = true;
            if (s.platform) platformSet[s.platform] = true;
        });
        animateCount('statSectors', Object.keys(sectorSet).length);
        animateCount('statPlatforms', Object.keys(platformSet).length);
    }

    function animateCount(id, target) {
        var el = document.getElementById(id);
        if (!el) return;
        if (target === 0) { el.textContent = '0'; return; }
        var current = 0;
        var step = Math.max(1, Math.ceil(target / 30));
        var interval = setInterval(function () {
            current = Math.min(current + step, target);
            el.textContent = current;
            if (current >= target) clearInterval(interval);
        }, 35);
    }

    // ======================== RENDER: OPPORTUNITIES ========================
    function renderOpportunities() {
        var grid = document.getElementById('opportunitiesGrid');
        if (!grid) return;

        var opps = allOpportunities;
        if (activeOppFilter !== 'all') {
            opps = opps.filter(function (o) { return o.opp_type === activeOppFilter; });
        }

        if (!opps.length) {
            var msg = allOpportunities.length === 0
                ? 'No opportunities generated yet. Run the scraper to generate signals, then opportunities will be synthesized automatically.'
                : 'No opportunities match this filter.';
            grid.innerHTML = '<div class="empty-msg">' + msg + '</div>';
            return;
        }

        grid.innerHTML = opps.map(function (opp, idx) {
            var score = opp.composite_score || 50;
            var colorClass = scoreColorClass(score);
            var borderColor = colorClass === 'score-green' ? 'var(--green)' : colorClass === 'score-gold' ? 'var(--gold)' : 'var(--blue)';
            var typeLabel = opp.opp_type === 'product' ? 'Product' : 'Service';
            var typeBg = opp.opp_type === 'product' ? 'var(--purple-dim)' : 'var(--blue-dim)';
            var typeColor = opp.opp_type === 'product' ? 'var(--purple)' : 'var(--blue)';

            var signalIds = opp.signal_ids || [];
            var signals = signalIds.map(function (sid) {
                return allSignals.find(function (s) { return s.id === sid; });
            }).filter(Boolean);

            return '<div class="opp-card ' + colorClass + '" data-opp-id="' + opp.id + '" style="border-top:3px solid ' + borderColor + ';">' +
                '<div class="opp-rank">#' + (idx + 1) + '</div>' +
                '<div class="opp-score-ring ' + colorClass + '">' +
                    '<span class="opp-score-value">' + score + '</span>' +
                '</div>' +
                '<div class="opp-card-body">' +
                    '<div class="opp-name">' + esc(opp.name) + '</div>' +
                    '<div style="display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap;">' +
                        '<span class="opp-sector-tag">' + esc(opp.sector) + '</span>' +
                        '<span class="opp-sector-tag" style="background:' + typeBg + ';color:' + typeColor + ';border:1px solid ' + typeColor + '20;">' + typeLabel + '</span>' +
                    '</div>' +
                    '<div class="opp-concept">' + esc(opp.concept) + '</div>' +
                    (signals.length ? '<div class="opp-signals-row">' +
                        signals.slice(0, 4).map(function (s) {
                            var label = s.title.length > 30 ? s.title.substring(0, 30) + '...' : s.title;
                            return '<span class="opp-signal-tag" data-signal-id="' + s.id + '" title="' + esc(s.title) + '">' + esc(label) + '</span>';
                        }).join('') +
                    '</div>' : '') +
                    '<div class="opp-metrics">' +
                        '<span class="opp-metric"><strong>' + signals.length + '</strong> signals</span>' +
                        '<span class="opp-metric"><strong>' + (opp.gap_severity || 3) + '/5</strong> gap severity</span>' +
                    '</div>' +
                '</div>' +
            '</div>';
        }).join('');
    }

    // ======================== MODALS ========================
    function openSignalModal(id) {
        var s = allSignals.find(function (x) { return x.id === id; });
        if (!s) return;

        var typeColors = { trending: 'var(--gold)', pain_point: 'var(--red)', opportunity: 'var(--green)', mention: 'var(--blue)' };
        var typeBgs = { trending: 'var(--gold-dim)', pain_point: 'var(--red-dim)', opportunity: 'var(--green-dim)', mention: 'var(--blue-dim)' };

        var html = '<div class="modal-type-badge" style="background:' + (typeBgs[s.type] || 'var(--bg-card)') + ';color:' + (typeColors[s.type] || 'var(--text-primary)') + ';">' + formatType(s.type) + '</div>' +
            '<div class="modal-title">' + esc(s.title) + '</div>' +
            '<div class="modal-summary">' + esc(s.summary) + '</div>' +
            '<div class="modal-detail-grid">' +
                detailItem('Sector', esc(s.sector)) +
                detailItem('Platform', esc(s.platform)) +
                detailItem('Priority', esc(s.priority)) +
                detailItem('Score', s.score != null ? String(s.score) : '--') +
                (s.mentions ? detailItem('Mentions', String(s.mentions)) : '') +
                detailItem('Date Collected', s.date_collected || '--') +
            '</div>';

        if (s.keywords && s.keywords.length) {
            html += '<div class="modal-section-title">Keywords</div>' +
                '<div class="modal-keywords">' +
                s.keywords.map(function (k) { return '<span class="modal-keyword">' + esc(k) + '</span>'; }).join('') +
                '</div>';
        }

        if (s.raw_text || s.source_url) {
            html += '<div class="modal-section-title">Original Source</div>' +
                '<div class="modal-source-embed">' +
                    '<div class="source-embed-header">' +
                        '<div class="source-embed-platform">' +
                            '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>' +
                            esc(s.platform || 'Source') +
                        '</div>' +
                        (s.date_collected ? '<div class="source-embed-date">' + esc(s.date_collected) + '</div>' : '') +
                    '</div>' +
                    (s.raw_text
                        ? '<div class="source-embed-content">' + esc(s.raw_text) + '</div>'
                        : '<div class="source-embed-content" style="color:var(--text-muted);font-style:italic;">No content available</div>') +
                    (s.source_url ? '<div class="source-embed-footer"><a href="' + esc(s.source_url) + '" target="_blank" rel="noopener" class="source-embed-url">' + esc(s.source_url) + '</a></div>' : '') +
                '</div>';
        }

        if (s.arabic_title) {
            html += '<div class="modal-section-title">Arabic</div>' +
                '<div class="modal-arabic-text">' + esc(s.arabic_title) + '</div>';
        }

        document.getElementById('modalBody').innerHTML = html;
        document.getElementById('modalOverlay').classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function openOppModal(id) {
        var opp = allOpportunities.find(function (o) { return o.id === id; });
        if (!opp) return;

        var score = opp.composite_score || 50;
        var colorClass = scoreColorClass(score);
        var colorVar = colorClass === 'score-green' ? 'var(--green)' : colorClass === 'score-gold' ? 'var(--gold)' : 'var(--blue)';
        var colorDim = colorClass === 'score-green' ? 'var(--green-dim)' : colorClass === 'score-gold' ? 'var(--gold-dim)' : 'var(--blue-dim)';
        var typeLabel = opp.opp_type === 'product' ? 'Product' : 'Service';

        var signalIds = opp.signal_ids || [];
        var signals = signalIds.map(function (sid) {
            return allSignals.find(function (s) { return s.id === sid; });
        }).filter(Boolean);

        var visibleOpps = allOpportunities.filter(function (o) {
            return activeOppFilter === 'all' || o.opp_type === activeOppFilter;
        });
        var rank = visibleOpps.indexOf(opp) + 1;

        var html = '<div class="modal-type-badge" style="background:' + colorDim + ';color:' + colorVar + ';">Opportunity #' + rank + ' -- ' + typeLabel + '</div>' +
            '<div class="modal-title">' + esc(opp.name) + '</div>' +
            '<div class="modal-summary">' + esc(opp.concept) + '</div>' +
            '<div class="modal-detail-grid">' +
                detailItem('Sector', esc(opp.sector)) +
                detailItem('Composite Score', '<span style="color:' + colorVar + ';">' + score + '/100</span>') +
                detailItem('Type', typeLabel + '-Based') +
                detailItem('Target Market', esc(opp.target_market)) +
                detailItem('Revenue Model', esc(opp.revenue_model)) +
                detailItem('Competition', esc(opp.competition)) +
                detailItem('Gap Severity', (opp.gap_severity || 3) + '/5') +
            '</div>';

        if (signals.length) {
            html += '<div class="modal-section-title">Supporting Signals</div>';
            signals.forEach(function (s) {
                html += '<div class="opp-signal-embed" data-signal-id="' + s.id + '" style="cursor:pointer;">' +
                    '<div class="source-embed-header">' +
                        '<div class="source-embed-platform">' +
                            '<svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>' +
                            esc(s.platform || 'Source') +
                        '</div>' +
                        (s.date_collected ? '<div class="source-embed-date">' + esc(s.date_collected) + '</div>' : '') +
                    '</div>' +
                    '<div class="opp-signal-embed-title">' + esc(s.title) + '</div>' +
                    (s.raw_text ? '<div class="source-embed-content">' + esc(s.raw_text) + '</div>' : '') +
                    (s.source_url ? '<div class="source-embed-footer"><span class="source-embed-url">' + esc(s.source_url) + '</span></div>' : '') +
                '</div>';
            });
        }

        document.getElementById('modalBody').innerHTML = html;
        document.getElementById('modalOverlay').classList.add('open');
        document.body.style.overflow = 'hidden';

        // Allow clicking supporting signals inside opp modal
        document.getElementById('modalBody').querySelectorAll('.opp-signal-embed').forEach(function (embed) {
            embed.addEventListener('click', function () {
                var sid = parseInt(this.dataset.signalId, 10);
                closeModal();
                setTimeout(function () { openSignalModal(sid); }, 250);
            });
        });
    }

    function closeModal() {
        document.getElementById('modalOverlay').classList.remove('open');
        document.body.style.overflow = '';
    }

    // ======================== UTILITIES ========================
    function esc(str) {
        if (str == null) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function formatType(t) {
        var map = { trending: 'Trending', pain_point: 'Pain Point', opportunity: 'Opportunity', mention: 'Mention' };
        return map[t] || t || '';
    }

    function formatRelative() {
        return 'just now';
    }

    function scoreColorClass(score) {
        if (score >= 85) return 'score-green';
        if (score >= 70) return 'score-gold';
        return 'score-blue';
    }

    function detailItem(label, value) {
        return '<div class="modal-detail-item">' +
            '<div class="modal-detail-label">' + label + '</div>' +
            '<div class="modal-detail-value">' + value + '</div>' +
        '</div>';
    }

    function showError(containerId, message) {
        var el = document.getElementById(containerId);
        if (el) el.innerHTML = '<div class="error-msg">' + esc(message) + '</div>';
    }

})();
