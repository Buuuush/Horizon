// Horizon Dashboard JavaScript

const API_BASE = '';
let currentProfile = null;

// ===== DOM Helpers =====

function $(selector) {
    return document.querySelector(selector);
}

function $$(selector) {
    return document.querySelectorAll(selector);
}

// ===== Initialization =====

document.addEventListener('DOMContentLoaded', async () => {
    console.log('🌅 Horizon Dashboard initialized');
    
    setupTabNavigation();
    setupEventListeners();
    
    await updateStatus();
    await loadProfiles();
    // Bind create profile button after profiles are loaded
    const createBtn = $('#btn-create-profile');
    if (createBtn) {
        createBtn.addEventListener('click', async () => {
            const name = prompt('Enter new profile name:');
            if (!name) return;
            try {
                await fetchAPI('/api/profiles', {
                    method: 'POST',
                    body: JSON.stringify({ name }),
                });
                showNotification(`Profile "${name}" created`, 'success');
                await loadProfiles(); // refresh list
            } catch (e) {
                showNotification('Failed to create profile', 'error');
            }
        });
    }
    await loadSummaries();
    
    // Refresh status every 5 seconds
    setInterval(updateStatus, 5000);
});

// ===== Tab Navigation =====

function setupTabNavigation() {
    $$('.nav-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tabName = e.target.dataset.tab;
            switchTab(tabName);
        });
    });
}

function switchTab(tabName) {
    // Hide all tabs
    $$('.tab-content').forEach(tab => tab.classList.remove('active'));
    $$('.nav-btn').forEach(btn => btn.classList.remove('active'));
    
    // Show selected tab
    const tab = $(`#tab-${tabName}`);
    if (tab) {
        tab.classList.add('active');
        $(`[data-tab="${tabName}"]`).classList.add('active');
        
        // Load tab content if needed
        if (tabName === 'feedback') {
            loadFeedbackStats();
        }
    }
}

// ===== Event Listeners =====

function setupEventListeners() {
    $('#refresh-btn').addEventListener('click', async () => {
        connectWebSocket();
    });
    
    $('#archive-date-filter').addEventListener('change', async (e) => {
        const date = e.target.value;
        if (date) {
            await loadSummaryForDate(date);
        }
    });
    
    // Close modal when clicking outside
    const modal = $('#article-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeArticleModal();
            }
        });
    }
}

// ===== API Calls =====

async function fetchAPI(endpoint, options = {}) {
    // Generic helper for all API calls
    // Returns parsed JSON or throws on error
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });
        if (!response.ok) {
            const errText = await response.text();
            throw new Error(`API error ${response.status}: ${errText}`);
        }
        return await response.json();
    } catch (e) {
        console.error('fetchAPI error:', e);
        throw e;
    }
}

async function fetchAPI(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers,
            },
        });
        
        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API call failed: ${endpoint}`, error);
        throw error;
    }
}

// ===== Status Updates =====

async function updateStatus() {
    try {
        const status = await fetchAPI('/api/status');
        
        const indicator = $('#status-indicator');
        const text = $('#status-text');
        
        if (status.status === 'ok') {
            indicator.classList.add('connected');
            indicator.classList.remove('error');
            text.textContent = `Online • Profile: ${status.active_profile || 'None'}`;
        } else if (status.status === 'degraded') {
            indicator.classList.remove('connected');
            indicator.classList.add('error');
            text.textContent = `⚠ Degraded: ${status.message}`;
            
            // Show warning message
            const profileArea = $('#profile-selector');
            if (profileArea && profileArea.innerHTML.includes('Loading')) {
                profileArea.innerHTML = `
                    <div style="background-color: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 1rem; color: #856404;">
                        <strong>⚠️ Configuration Required</strong>
                        <p style="margin-top: 0.5rem; font-size: 0.9rem;">
                            ${status.detail}
                        </p>
                        <p style="margin-top: 0.5rem; font-size: 0.85rem;">
                            Please create <code style="background: #f0f0f0; padding: 0.2rem 0.4rem; border-radius: 3px;">data/config.json</code> 
                            based on <code style="background: #f0f0f0; padding: 0.2rem 0.4rem; border-radius: 3px;">data/config.example.json</code>
                        </p>
                    </div>
                `;
            }
        } else {
            indicator.classList.add('error');
            indicator.classList.remove('connected');
            text.textContent = 'Offline';
        }
    } catch (error) {
        $('#status-indicator').classList.add('error');
        $('#status-indicator').classList.remove('connected');
        $('#status-text').textContent = 'Offline';
    }
}

// ===== Profiles =====

async function loadProfiles() {
    try {
        const response = await fetchAPI('/api/profiles');
        const selector = $('#profile-selector');
        
        if (!response || response.length === 0) {
            selector.innerHTML = '<p class="placeholder">No profiles found</p>';
            return;
        }
        
        selector.innerHTML = '';
        response.forEach(profile => {
            const card = document.createElement('div');
            card.className = `profile-card ${profile.is_active ? 'active' : ''}`;
            card.innerHTML = `
                <h4>${profile.name}</h4>
                <p>${profile.description || '(no description)'}</p>
                <p>Threshold: ${profile.ai_score_threshold}</p>
            `;
            
            card.addEventListener('click', async () => {
                await selectProfile(profile.name);
            });
            
            selector.appendChild(card);
        });
        
        currentProfile = response.find(p => p.is_active);
        if (currentProfile) {
            displayProfileDetails(currentProfile);
        }
    } catch (error) {
        console.error('Failed to load profiles', error);
        const selector = $('#profile-selector');
        if (selector) {
            selector.innerHTML = `
                <div style="background-color: #f8d7da; border: 1px solid #f5c6cb; border-radius: 8px; padding: 1rem; color: #721c24;">
                    <strong>Error loading profiles</strong>
                    <p style="margin-top: 0.5rem; font-size: 0.9rem;">${error.message}</p>
                </div>
            `;
        }
    }
}

async function selectProfile(profileName) {
    try {
        await fetchAPI(`/api/profiles/${profileName}/activate`, { method: 'POST' });
        await loadProfiles();
        await updateStatus();
    } catch (error) {
        console.error('Failed to activate profile', error);
    }
}

function displayProfileDetails(profile) {
    const details = $('#profile-details');
    
    const sourcesHtml = profile.active_sources.length > 0 
        ? profile.active_sources.join(', ')
        : '(all enabled)';
    
    details.innerHTML = `
        <dl>
            <dt>Name</dt>
            <dd>${profile.name}</dd>
            
            <dt>Description</dt>
            <dd>${profile.description || '(none)'}</dd>
            
            <dt>Score Threshold</dt>
            <dd>${profile.ai_score_threshold}</dd>
            
            <dt>Active Sources</dt>
            <dd>${sourcesHtml}</dd>
            
            <dt>Custom Prompts</dt>
            <dd>${Object.keys(profile.per_source_prompts).length} source(s) customized</dd>
            
            <dt>Created</dt>
            <dd>${new Date(profile.created_at).toLocaleDateString()}</dd>
            
            <dt>Updated</dt>
            <dd>${new Date(profile.updated_at).toLocaleDateString()}</dd>
        </dl>
    `;
}

// ===== Summaries =====

async function loadSummaries() {
    try {
        const response = await fetchAPI('/api/summaries?limit=30');
        const listArea = $('#archive-list');
        
        if (!response.summaries || response.summaries.length === 0) {
            listArea.innerHTML = '<p class="placeholder">No summaries found</p>';
            return;
        }
        
        listArea.innerHTML = '';
        response.summaries.forEach(summary => {
            const item = document.createElement('div');
            item.className = 'summary-item';
            item.style.cssText = `
                padding: 1rem;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                margin-bottom: 1rem;
                cursor: pointer;
                transition: all 0.3s ease;
            `;
            
            item.innerHTML = `
                <strong>${summary.date}</strong> 
                <small style="color: #999;">(${summary.language.toUpperCase()} • ${Math.round(summary.size_bytes / 1024)}KB)</small>
            `;
            
            item.addEventListener('click', async () => {
                await loadSummaryForDate(summary.date, summary.language);
            });
            
            item.addEventListener('mouseenter', () => {
                item.style.backgroundColor = '#f9f9f9';
                item.style.borderColor = '#3498db';
            });
            
            item.addEventListener('mouseleave', () => {
                item.style.backgroundColor = 'transparent';
                item.style.borderColor = '#e0e0e0';
            });
            
            listArea.appendChild(item);
        });
    } catch (error) {
        console.error('Failed to load summaries', error);
        $('#archive-list').innerHTML = '<p class="placeholder">Error loading summaries</p>';
    }
}

async function loadSummaryForDate(date, language = 'en') {
    try {
        const response = await fetch(`/api/summaries/${date}?language=${language}`);
        if (!response.ok) throw new Error('Summary not found');
        
        const html = await response.text();
        const todayContent = $('#today-content');
        todayContent.innerHTML = html;
        
        switchTab('today');
    } catch (error) {
        console.error('Failed to load summary', error);
        $('#today-content').innerHTML = '<p class="placeholder">Error loading summary</p>';
    }
}

// ===== Feedback =====

async function loadFeedbackStats() {
    if (!currentProfile) {
        $('#feedback-content').innerHTML = '<p class="placeholder">No profile selected</p>';
        return;
    }
    
    try {
        const stats = await fetchAPI(`/api/feedback/${currentProfile.name}/stats`);
        const recommendations = await fetchAPI(`/api/feedback/${currentProfile.name}/recommendations`);
        
        // Update stats
        $('#stat-total').textContent = stats.total_feedback;
        $('#stat-accuracy').textContent = stats.accuracy_rate;
        $('#stat-misscored').textContent = stats.misscored_items;
        $('#stat-favorites').textContent = stats.favorites;
        
        // Update recommendations
        const recArea = $('#recommendations');
        if (recommendations.recommendations && recommendations.recommendations.length > 0) {
            recArea.innerHTML = recommendations.recommendations.map(rec => `
                <div class="recommendation-item ${rec.priority}">
                    <div class="recommendation-priority">${rec.priority}</div>
                    <div class="recommendation-title">${rec.title || ''}</div>
                    <div class="recommendation-action">${rec.action}</div>
                </div>
            `).join('');
        } else {
            recArea.innerHTML = '<p class="placeholder">No recommendations yet</p>';
        }
    } catch (error) {
        console.error('Failed to load feedback stats', error);
    }
}

async function submitFeedback(itemId, rating, isFavorite = false, notes = '') {
    if (!currentProfile) {
        console.error('No profile selected');
        return;
    }
    
    try {
        await fetchAPI(`/api/feedback/${currentProfile.name}`, {
            method: 'POST',
            body: JSON.stringify({
                item_id: itemId,
                user_rating: rating,
                is_favorite: isFavorite,
                notes: notes,
            }),
        });
        
        console.log('✓ Feedback submitted');
        await loadFeedbackStats();
    } catch (error) {
        console.error('Failed to submit feedback', error);
    }
}

// ===== Article Viewing =====

let currentArticle = null;
let currentProfileForArticle = null;

function openArticleModal(article) {
    currentArticle = article;
    currentProfileForArticle = currentProfile;
    
    const modal = $('#article-modal');
    const title = $('#article-title');
    const source = $('#article-source');
    const score = $('#article-score');
    const date = $('#article-date');
    const content = $('#article-content');
    const link = $('#article-link');
    
    title.textContent = article.title || 'Article';
    source.textContent = article.source || '—';
    score.textContent = `Score: ${article.score ? article.score.toFixed(1) : '—'}`;
    date.textContent = article.date || new Date().toLocaleDateString();
    content.innerHTML = `<p>${article.summary || article.description || 'No content available'}</p>`;
    link.href = article.url || '#';
    
    // Reset feedback buttons
    $$('.btn-feedback').forEach(btn => btn.classList.remove('active'));
    $('#article-notes').value = '';
    
    modal.style.display = 'flex';
}

function closeArticleModal() {
    const modal = $('#article-modal');
    modal.style.display = 'none';
    currentArticle = null;
}

async function submitArticleFeedback(rating) {
    if (!currentArticle || !currentProfileForArticle) {
        console.error('No article or profile selected');
        return;
    }
    
    const notes = $('#article-notes').value;
    const btn = rating > 0 ? $('#btn-thumbs-up') : $('#btn-thumbs-down');
    
    try {
        await submitFeedback(currentArticle.item_id, rating, false, notes);
        btn.classList.add('active');
        showNotification('✓ Feedback submitted', 'success');
    } catch (error) {
        showNotification('✗ Failed to submit feedback', 'error');
    }
}

async function toggleFavorite() {
    if (!currentArticle || !currentProfileForArticle) {
        console.error('No article or profile selected');
        return;
    }
    
    try {
        const btn = $('#btn-favorite');
        const isFavorite = !btn.classList.contains('active');
        
        await fetchAPI(`/api/favorites/${currentProfileForArticle.name}`, {
            method: 'POST',
            body: JSON.stringify({
                item_id: currentArticle.item_id,
                is_favorite: isFavorite,
            }),
        });
        
        btn.classList.toggle('active');
        showNotification(isFavorite ? '⭐ Added to favorites' : '⭐ Removed from favorites', 'success');
    } catch (error) {
        showNotification('✗ Failed to update favorite', 'error');
    }
}

// ===== WebSocket Real-time Updates =====

let ws = null;

function connectWebSocket() {
    if (!currentProfile) {
        showNotification('Please select a profile first', 'warning');
        return;
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/progress/${currentProfile.name}`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        console.log('✓ WebSocket connected');
        $('#live-indicator').style.display = 'inline-flex';
        showNotification('🟢 Starting live scraping...', 'info');
    };
    
    ws.onmessage = (event) => {
        try {
            const message = JSON.parse(event.data);
            handleWebSocketMessage(message);
        } catch (error) {
            console.error('Failed to parse WebSocket message', error);
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error', error);
        showNotification('⚠ WebSocket connection error', 'warning');
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        $('#live-indicator').style.display = 'none';
        showNotification('⚫ Live scraping ended', 'info');
    };
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'progress':
            console.log(`Progress: ${message.stage} (${message.current}/${message.total || '?'})`);
            updateProgressIndicator(message);
            break;
        
        case 'item_scored':
            console.log(`Scored: ${message.title} (${message.score.toFixed(1)})`);
            addArticleToList(message);
            break;
        
        case 'summary_complete':
            console.log(`Summary complete: ${message.path}`);
            loadSummaryForDate(message.timestamp.split('T')[0], message.language);
            break;
        
        default:
            console.log('Unknown message type', message);
    }
}

function updateProgressIndicator(message) {
    const indicator = $('#live-indicator');
    if (indicator && message.current && message.total) {
        const percent = Math.round((message.current / message.total) * 100);
        indicator.textContent = `🔴 LIVE: ${message.stage} ${percent}%`;
    }
}

function addArticleToList(article) {
    const container = $('#articles-container');
    if (!container) return;
    
    const card = document.createElement('div');
    card.className = 'article-card';
    card.innerHTML = `
        <div class="article-card-title">${article.title}</div>
        <div class="article-card-meta">
            <span class="article-card-score">${article.score.toFixed(1)}</span>
            <span class="article-card-source">${article.source}</span>
        </div>
        <div class="article-card-summary" style="font-size: 0.85rem; color: #666; line-height: 1.4; margin-bottom: 0.5rem;">
            ${article.summary || '(no summary)'}
        </div>
        <div class="article-card-footer">
            <button class="article-card-btn" onclick="openArticleModal({
                title: '${article.title.replace(/'/g, "\\'")}',
                source: '${article.source}',
                score: ${article.score},
                url: '${article.url}',
                summary: '${(article.summary || '').replace(/'/g, "\\'")}',
                item_id: '${article.item_id}',
                date: new Date().toLocaleDateString()
            })">View</button>
            <button class="article-card-btn" style="background-color: #f0f0f0;">👍</button>
            <button class="article-card-btn" style="background-color: #f0f0f0;">👎</button>
        </div>
    `;
    
    container.insertBefore(card, container.firstChild);
    
    // Show articles list if hidden
    const articlesList = $('#articles-list');
    if (articlesList) articlesList.style.display = 'block';
}

function showNotification(message, type = 'info') {
    console.log(`[${type}] ${message}`);
    
    // Create toast notification
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background-color: ${type === 'success' ? '#2ecc71' : type === 'error' ? '#e74c3c' : type === 'warning' ? '#f39c12' : '#3498db'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        font-weight: 500;
        z-index: 2000;
        animation: slideIn 0.3s ease-out;
    `;
    
    toast.textContent = message;
    document.body.appendChild(toast);
    
    // Auto-remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
