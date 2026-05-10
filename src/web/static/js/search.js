// Search page JavaScript

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('search-form');
    const resultsDiv = document.getElementById('results');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        resultsDiv.innerHTML = '<p>Recherche en cours…</p>';
        const params = new URLSearchParams({
            q: document.getElementById('q').value,
            tag: document.getElementById('tag').value,
            source: document.getElementById('source').value,
            date_start: document.getElementById('date_start').value,
            date_end: document.getElementById('date_end').value,
            limit: '20',
        });
        try {
            const resp = await fetch(`/api/search?${params}`);
            if (!resp.ok) throw new Error(`Erreur ${resp.status}`);
            const data = await resp.json();
            renderResults(data.results);
        } catch (err) {
            console.error('search error', err);
            resultsDiv.innerHTML = `<p style="color:red;">Erreur de recherche : ${err.message}</p>`;
        }
    });
});

function renderResults(items) {
    const container = document.getElementById('results');
    if (!items || items.length === 0) {
        container.innerHTML = '<p>Aucun résultat trouvé.</p>';
        return;
    }
    const html = items.map(item => `
        <div class="result-card" style="margin-bottom:1rem;">
            <h3><a href="${item.url}" target="_blank">${item.title}</a></h3>
            <p>Score : ${item.score.toFixed(2)} | Source : ${item.source} | Publiée : ${item.published?.split('T')[0] || 'N/A'}</p>
            <p>Balises : ${Array.isArray(item.tags) ? item.tags.map(t => `#${t}`).join(' ') : ''}</p>
        </div>`).join('');
    container.innerHTML = html;
}
