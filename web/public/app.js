// La page d'accueil : dates, « sur scène maintenant », programme par jour
// (filtrable par salle) et grille des artistes.
//
// ?at=2027-06-11T21:00 dans l'adresse remplace l'heure actuelle, comme dans
// l'API : pratique pour voir le festival « en direct » avant juin 2027.

const params = new URLSearchParams(location.search);
const at = params.get("at");

const state = { day: null, venue: "" };

// La journée de festival d'un moment : on recule de 6 heures (comme le serveur).
function festivalDayOf(moment) {
  const date = new Date(`${moment.slice(0, 16)}`);
  date.setHours(date.getHours() - 6);
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

async function showFestival() {
  const festival = await api("/api/festival");
  // L'année est affichée à part, en italique : on la retire du nom.
  document.getElementById("festival-name").textContent = festival.name.replace(/\s*\d{4}$/, "");
  document.getElementById("festival-dates").textContent =
    `Du ${formatDay(festival.first_day)} au ${formatDay(festival.last_day)} 2027`;

  // Le jour affiché : celui de ?day=, sinon celui de ?at=, sinon le premier.
  const wanted = params.get("day") || (at ? festivalDayOf(at) : null);
  state.day = festival.days.includes(wanted) ? wanted : festival.days[0];

  const tabs = document.getElementById("day-tabs");
  tabs.innerHTML = festival.days
    .map(
      (day) =>
        `<button class="tab" role="tab" data-day="${day}">${esc(formatDay(day, "short"))}</button>`
    )
    .join("");
  tabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-day]");
    if (!button) return;
    state.day = button.dataset.day;
    showProgramme();
  });
}

async function showVenues() {
  const venues = await api("/api/venues");
  const select = document.getElementById("venue-filter");
  for (const venue of venues) {
    select.add(new Option(`${venue.name} (${venue.capacity} places)`, venue.slug));
  }
  select.addEventListener("change", () => {
    state.venue = select.value;
    showProgramme();
  });
}

async function showProgramme() {
  for (const tab of document.querySelectorAll("#day-tabs .tab")) {
    tab.setAttribute("aria-selected", String(tab.dataset.day === state.day));
  }
  const query = new URLSearchParams({ day: state.day });
  if (state.venue) query.set("venue", state.venue);
  const performances = await api(`/api/programme?${query}`);
  const box = document.getElementById("programme-cards");
  box.innerHTML = performances.length
    ? performances.map((p) => performanceCard(p)).join("")
    : `<div class="empty">Aucun spectacle dans cette salle ce jour-là.</div>`;
}

async function showNow() {
  const now = await api(at ? `/api/now?at=${encodeURIComponent(at)}` : "/api/now");
  const playing = document.getElementById("now-playing");
  playing.innerHTML = now.now_playing.length
    ? now.now_playing
        .map(
          (p) => `<div class="now-item">${esc(p.title)}
            <span class="muted">· ${esc(p.venue_name)}, jusqu'à ${formatTime(p.end)}</span></div>`
        )
        .join("")
    : `<div class="muted">Rien sur scène en ce moment.</div>`;
  document.getElementById("up-next").innerHTML = now.up_next.length
    ? now.up_next
        .map(
          (p) => `<li><time>${esc(formatDay(p.festival_day, "short"))} ${formatTime(p.start)}</time>
            ${esc(p.title)} · ${esc(p.venue_name)}</li>`
        )
        .join("")
    : `<li>Le festival est terminé. À l'année prochaine !</li>`;
}

async function showArtists() {
  const artists = await api("/api/artists");
  document.getElementById("artist-grid").innerHTML = artists
    .map(
      (a) => `<a class="artist" href="artist.html?slug=${encodeURIComponent(a.slug)}">
          ${avatarHtml(a)}<strong>${esc(a.name)}</strong></a>`
    )
    .join("");
}

async function start() {
  try {
    await Promise.all([showFestival(), showVenues()]);
    await Promise.all([showProgramme(), showNow(), showArtists()]);
  } catch (error) {
    document.querySelector("main").insertAdjacentHTML(
      "afterbegin",
      `<div class="error-box">Le programme n'a pas pu être chargé : ${esc(error.message)}</div>`
    );
  }
  // Sans ?at=, « sur scène maintenant » se met à jour chaque minute.
  if (!at) setInterval(showNow, 60_000);
}

start();
