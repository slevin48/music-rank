// ── State ──────────────────────────────────────────────────────────────────
const state = {
  user: null,
  playlists: [],
  activePlaylist: null,   // { id, name }
  duel: null,             // { track_a, track_b, duel_count }
};

// ── DOM helpers ─────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const screens = {
  loading: $('loading-screen'),
  login: $('login-screen'),
  playlist: $('playlist-screen'),
  duel: $('duel-screen'),
  leaderboard: $('leaderboard-screen'),
};

function showScreen(name) {
  Object.values(screens).forEach(s => s.classList.remove('active'));
  screens[name].classList.add('active');
}

// ── API ──────────────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, credentials: 'include', headers: {} };
  if (body !== undefined) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (res.status === 401) { showScreen('login'); throw new Error('Unauthorized'); }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

// ── Boot ─────────────────────────────────────────────────────────────────────
async function boot() {
  // Check URL for error param
  const params = new URLSearchParams(location.search);
  if (params.has('error')) {
    history.replaceState({}, '', '/');
    showScreen('login');
    const el = $('login-error');
    el.textContent = 'Spotify login failed: ' + params.get('error');
    el.classList.remove('hidden');
    return;
  }

  try {
    const user = await api('GET', '/api/me');
    state.user = user;
    renderUser();
    const playlists = await api('GET', '/api/playlists');
    state.playlists = playlists;
    renderPlaylists();
    showScreen('playlist');
  } catch {
    showScreen('login');
  }
}

// ── User ──────────────────────────────────────────────────────────────────────
function renderUser() {
  const { display_name, image } = state.user;
  $('user-name').textContent = display_name;
  const avatar = $('user-avatar');
  if (image) { avatar.src = image; avatar.style.display = 'block'; }
  else { avatar.style.display = 'none'; }
}

$('logout-btn').addEventListener('click', async () => {
  await api('POST', '/logout');
  state.user = null;
  state.activePlaylist = null;
  showScreen('login');
});

// ── Playlists ─────────────────────────────────────────────────────────────────
function renderPlaylists() {
  const grid = $('playlist-grid');
  grid.innerHTML = '';
  state.playlists.forEach(pl => {
    const isLiked = pl.id === '__liked__';
    const item = document.createElement('div');
    item.className = 'playlist-item' + (isLiked ? ' liked-songs' : '');
    item.dataset.id = pl.id;
    if (isLiked) {
      item.innerHTML = `
        <div class="liked-songs-art">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="currentColor"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
        </div>
        <div class="playlist-item-info">
          <div class="playlist-item-name">Liked Songs</div>
          <div class="playlist-item-count">${pl.track_count} tracks</div>
        </div>`;
    } else {
      item.innerHTML = `
        <img src="${pl.image_url || ''}" alt="${esc(pl.name)}" onerror="this.style.opacity=0" />
        <div class="playlist-item-info">
          <div class="playlist-item-name">${esc(pl.name)}</div>
          <div class="playlist-item-count">${pl.track_count} tracks</div>
        </div>`;
    }
    item.addEventListener('click', () => selectPlaylist(pl));
    grid.appendChild(item);
  });
}

async function selectPlaylist(pl) {
  const item = $('playlist-grid').querySelector(`[data-id="${pl.id}"]`);
  if (item) {
    item.classList.add('importing');
    item.querySelector('.playlist-item-count').textContent = 'Importing…';
  }
  try {
    const result = await api('POST', `/api/playlists/${pl.id}/import`);
    state.activePlaylist = pl;
    await loadDuel();
  } catch (e) {
    alert('Failed to import playlist: ' + e.message);
    if (item) {
      item.classList.remove('importing');
      item.querySelector('.playlist-item-count').textContent = pl.track_count + ' tracks';
    }
  }
}

// ── Duel ──────────────────────────────────────────────────────────────────────
async function loadDuel() {
  try {
    const duel = await api('GET', `/api/playlists/${state.activePlaylist.id}/duel`);
    state.duel = duel;
    renderDuel();
    showScreen('duel');
  } catch (e) {
    alert('Could not load duel: ' + e.message);
  }
}

function renderDuel() {
  const { track_a, track_b, duel_count } = state.duel;
  $('duel-count').textContent = duel_count;
  $('playlist-title').textContent = state.activePlaylist.name;

  setTrack('a', track_a);
  setTrack('b', track_b);

  const arena = $('duel-arena');
  arena.classList.remove('transitioning');
  $('card-a').classList.remove('winner', 'loser');
  $('card-b').classList.remove('winner', 'loser');
}

function setTrack(side, track) {
  $('img-' + side).src = track.image_url || '';
  $('name-' + side).textContent = track.name;
  $('artist-' + side).textContent = track.artist;
  $('album-' + side).textContent = track.album;
}

async function vote(winnerSide) {
  const arena = $('duel-arena');
  if (arena.classList.contains('transitioning')) return;
  arena.classList.add('transitioning');

  const loserSide = winnerSide === 'a' ? 'b' : 'a';
  const winnerCard = $('card-' + winnerSide);
  const loserCard = $('card-' + loserSide);
  winnerCard.classList.add('winner');
  loserCard.classList.add('loser');

  const winnerId = state.duel['track_' + winnerSide].id;
  const loserId  = state.duel['track_' + loserSide].id;

  try {
    await api('POST', '/api/duel', { winner_id: winnerId, loser_id: loserId });
  } catch (e) {
    console.error('Duel submit failed:', e);
  }

  setTimeout(async () => {
    await loadDuel();
  }, 350);
}

$('card-a').addEventListener('click', () => vote('a'));
$('card-b').addEventListener('click', () => vote('b'));

$('skip-btn').addEventListener('click', async () => {
  const arena = $('duel-arena');
  if (arena.classList.contains('transitioning')) return;
  await api('POST', '/api/duel/skip', {});
  await loadDuel();
});

$('duel-back-btn').addEventListener('click', () => showScreen('playlist'));

// ── Leaderboard ───────────────────────────────────────────────────────────────
$('leaderboard-btn').addEventListener('click', loadLeaderboard);
$('lb-back-btn').addEventListener('click', () => showScreen('duel'));

async function loadLeaderboard() {
  try {
    const data = await api('GET', `/api/playlists/${state.activePlaylist.id}/leaderboard`);
    renderLeaderboard(data);
    showScreen('leaderboard');
  } catch (e) {
    alert('Could not load leaderboard: ' + e.message);
  }
}

function renderLeaderboard({ tracks, duel_count }) {
  $('lb-playlist-title').textContent = state.activePlaylist.name;
  $('lb-duel-count').textContent = duel_count;
  $('lb-track-count').textContent = tracks.length;

  const list = $('lb-list');
  list.innerHTML = '';
  tracks.forEach(t => {
    const total = t.wins + t.losses;
    const winPct = total ? Math.round((t.wins / total) * 100) : 0;
    const row = document.createElement('div');
    row.className = 'lb-row';
    row.innerHTML = `
      <div class="lb-rank">${rankIcon(t.rank)}</div>
      <img class="lb-thumb" src="${t.image_url || ''}" alt="" onerror="this.style.opacity=0" />
      <div class="lb-info">
        <div class="lb-track-name">${esc(t.name)}</div>
        <div class="lb-track-artist">${esc(t.artist)}</div>
      </div>
      <div class="lb-elo">${Math.round(t.elo)}</div>
      <div class="lb-record">${t.wins}W / ${t.losses}L</div>`;
    list.appendChild(row);
  });
}

function rankIcon(rank) {
  if (rank === 1) return '🥇';
  if (rank === 2) return '🥈';
  if (rank === 3) return '🥉';
  return rank;
}

// ── Export ────────────────────────────────────────────────────────────────────
$('export-btn').addEventListener('click', () => {
  $('export-modal').classList.remove('hidden');
  $('export-result').classList.add('hidden');
  $('export-result').innerHTML = '';
});
$('export-cancel').addEventListener('click', () => $('export-modal').classList.add('hidden'));
$('export-confirm').addEventListener('click', async () => {
  const name = $('export-name').value.trim() || 'Music Rank Top Tracks';
  const top_n = parseInt($('export-n').value) || 20;
  $('export-confirm').disabled = true;
  $('export-confirm').textContent = 'Creating…';
  try {
    const result = await api('POST', `/api/playlists/${state.activePlaylist.id}/export`, { name, top_n });
    const el = $('export-result');
    el.innerHTML = `Playlist created! <a href="${result.url}" target="_blank">Open in Spotify →</a>`;
    el.classList.remove('hidden');
  } catch (e) {
    alert('Export failed: ' + e.message);
  } finally {
    $('export-confirm').disabled = false;
    $('export-confirm').textContent = 'Create Playlist';
  }
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function esc(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Init ──────────────────────────────────────────────────────────────────────
boot();
