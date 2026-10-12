// L'admin : programmer, modifier, annuler des spectacles, gérer les inscrits
// d'un atelier, ajouter des artistes. Le navigateur ne vérifie presque rien :
// les règles vivent sur le serveur, et sa réponse s'affiche telle quelle.

const form = document.getElementById("performance-form");
const formError = document.getElementById("form-error");
const state = {
  artists: [],
  editing: null, // le spectacle en cours de modification, ou null
  participantsOf: null, // l'id de l'atelier ouvert dans la fenêtre des inscrits
  dayFilter: "",
};

// ----- Les listes (salles, artistes, jours) -----

async function loadVenuesAndDays() {
  const [festival, venues] = await Promise.all([api("/api/festival"), api("/api/venues")]);
  const venueSelect = document.getElementById("venue");
  for (const venue of venues) {
    venueSelect.add(new Option(`${venue.name} (${venue.capacity} places)`, venue.slug));
  }
  // Le début possible : du premier jour 06:00 au lendemain du dernier jour 05:59.
  const start = document.getElementById("start");
  start.min = `${festival.first_day}T06:00`;
  const after = new Date(`${festival.last_day}T12:00`);
  after.setDate(after.getDate() + 1);
  start.max = `${after.toISOString().slice(0, 10)}T05:59`;
  start.value = `${festival.first_day}T20:00`;

  const dayFilter = document.getElementById("day-filter");
  for (const day of festival.days) {
    dayFilter.add(new Option(formatDay(day), day));
  }
  dayFilter.addEventListener("change", () => {
    state.dayFilter = dayFilter.value;
    showSchedule();
  });
}

async function loadArtists() {
  state.artists = await api("/api/artists");
  for (const select of document.querySelectorAll(".artist-select")) {
    const previous = select.value;
    select.innerHTML = state.artists
      .map((a) => `<option value="${esc(a.slug)}">${esc(a.name)}</option>`)
      .join("");
    if (previous) select.value = previous;
  }
  const checked = new Set(selectedActs());
  document.getElementById("acts").innerHTML = state.artists
    .map(
      (a) => `<label><input type="checkbox" name="acts" value="${esc(a.slug)}"
        ${checked.has(a.slug) ? "checked" : ""}> ${esc(a.name)}</label>`
    )
    .join("");
  document.getElementById("artist-count").textContent =
    `${state.artists.length} artistes au festival.`;
}

function selectedActs() {
  return [...form.querySelectorAll('input[name="acts"]:checked')].map((box) => box.value);
}

// ----- Le formulaire : un seul pour créer et pour modifier -----

// N'affiche que les champs du type choisi.
function showKindFields() {
  const kind = form.kind.value;
  for (const fieldset of form.querySelectorAll("fieldset[data-kind]")) {
    fieldset.hidden = fieldset.dataset.kind !== kind;
  }
}

// Le corps JSON envoyé à l'API (voir PerformanceIn dans API.md).
function formBody() {
  const kind = form.kind.value;
  const body = {
    kind,
    title: form.title.value,
    venue: form.venue.value,
    start: form.start.value,
    duration_minutes: Number(form.duration_minutes.value),
    description: form.description.value,
  };
  if (kind === "solo") {
    body.artist = form.artist.value;
    body.min_age = Number(form.min_age.value || 0);
  } else if (kind === "lineup") {
    body.host = form.host.value;
    body.acts = selectedActs();
  } else {
    body.teacher = form.teacher.value;
    body.max_participants = Number(form.max_participants.value);
    // En modification, on garde les inscrits.
    body.participants = state.editing?.participants ?? [];
  }
  return body;
}

function showFormError(message) {
  formError.textContent = message;
  formError.hidden = !message;
}

function resetForm() {
  const start = form.start.value;
  form.reset();
  form.start.value = start;
  state.editing = null;
  document.getElementById("form-title").textContent = "Programmer un spectacle";
  document.getElementById("submit-button").textContent = "Programmer";
  document.getElementById("cancel-edit").hidden = true;
  document.getElementById("form-section").classList.remove("editing");
  showFormError("");
  showKindFields();
}

// Remplit le formulaire avec un spectacle existant, pour le modifier.
function editPerformance(performance) {
  resetForm();
  state.editing = performance;
  form.kind.value = performance.kind;
  form.title.value = performance.title;
  form.venue.value = performance.venue;
  form.start.value = performance.start;
  form.duration_minutes.value = performance.duration_minutes;
  form.description.value = performance.description;
  if (performance.kind === "solo") {
    form.artist.value = performance.artist;
    form.min_age.value = performance.min_age;
  } else if (performance.kind === "lineup") {
    form.host.value = performance.host;
    for (const box of form.querySelectorAll('input[name="acts"]')) {
      box.checked = performance.acts.includes(box.value);
    }
  } else {
    form.teacher.value = performance.teacher;
    form.max_participants.value = performance.max_participants;
  }
  showKindFields();
  document.getElementById("form-title").textContent = `Modifier « ${performance.title} »`;
  document.getElementById("submit-button").textContent = "Enregistrer les modifications";
  document.getElementById("cancel-edit").hidden = false;
  const section = document.getElementById("form-section");
  section.classList.add("editing");
  section.scrollIntoView({ behavior: "smooth" });
}

form.kind.addEventListener("change", showKindFields);
document.getElementById("cancel-edit").addEventListener("click", resetForm);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showFormError("");
  try {
    if (state.editing) {
      const id = state.editing.id;
      const saved = await api(`/api/performances/${encodeURIComponent(id)}`, {
        method: "PUT",
        body: formBody(),
      });
      toast(
        saved.id === id
          ? `« ${saved.title} » modifié.`
          : `« ${saved.title} » déplacé : son id est maintenant ${saved.id}.`
      );
    } else {
      const saved = await api("/api/performances", { method: "POST", body: formBody() });
      toast(`« ${saved.title} » programmé (${saved.id}).`);
    }
    resetForm();
    await showSchedule();
  } catch (error) {
    showFormError(error.message); // la phrase du serveur : quelle règle, pourquoi
  }
});

// ----- Le programme, jour par jour -----

async function showSchedule() {
  const query = state.dayFilter ? `?day=${state.dayFilter}` : "";
  const performances = await api(`/api/programme${query}`);
  const byDay = new Map();
  for (const p of performances) {
    if (!byDay.has(p.festival_day)) byDay.set(p.festival_day, []);
    byDay.get(p.festival_day).push(p);
  }
  const box = document.getElementById("schedule");
  if (!performances.length) {
    box.innerHTML = `<div class="empty">Aucun spectacle.</div>`;
    return;
  }
  box.innerHTML = [...byDay]
    .map(
      ([day, list]) => `
      <div class="day-block">
        <h3>${esc(formatDay(day))}</h3>
        <div class="table-wrap"><table>
          <thead><tr><th>Horaire</th><th>Spectacle</th><th>Salle</th><th>Sur scène</th><th></th></tr></thead>
          <tbody>${list.map(scheduleRow).join("")}</tbody>
        </table></div>
      </div>`
    )
    .join("");
  // On garde les objets pour les boutons (modifier a besoin de tout le spectacle).
  state.performances = new Map(performances.map((p) => [p.id, p]));
}

function scheduleRow(p) {
  const participants =
    p.kind === "workshop"
      ? `<button class="button ghost small" data-action="participants" data-id="${esc(p.id)}">Inscrits</button>`
      : "";
  return `<tr>
    <td class="time">${formatTime(p.start)}–${formatTime(p.end)}</td>
    <td><strong>${esc(p.title)}</strong> ${badgesHtml(p)}<div class="id">${esc(p.id)}</div></td>
    <td>${esc(p.venue_name)}</td>
    <td>${esc(p.summary)}</td>
    <td class="row-actions">
      ${participants}
      <button class="button ghost small" data-action="edit" data-id="${esc(p.id)}">Modifier</button>
      <button class="button danger small" data-action="cancel" data-id="${esc(p.id)}">Annuler</button>
    </td>
  </tr>`;
}

document.getElementById("schedule").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  const performance = state.performances.get(button.dataset.id);
  if (button.dataset.action === "edit") {
    editPerformance(performance);
  } else if (button.dataset.action === "participants") {
    openParticipants(performance.id);
  } else if (button.dataset.action === "cancel") {
    if (!confirm(`Annuler « ${performance.title} » ? Le spectacle sera supprimé du programme.`)) {
      return;
    }
    try {
      await api(`/api/performances/${encodeURIComponent(performance.id)}`, { method: "DELETE" });
      toast(`« ${performance.title} » annulé.`);
      if (state.editing?.id === performance.id) resetForm();
      await showSchedule();
    } catch (error) {
      toast(error.message, true);
    }
  }
});

// ----- Les inscrits d'un atelier -----

const dialog = document.getElementById("participants-dialog");

// Dans la fenêtre, les erreurs s'affichent dedans (le toast serait derrière).
function showParticipantsError(message) {
  const box = document.getElementById("participants-error");
  box.textContent = message;
  box.hidden = !message;
}

async function openParticipants(id) {
  state.participantsOf = id;
  showParticipantsError("");
  await showParticipants();
  if (!dialog.open) dialog.showModal();
}

async function showParticipants() {
  const workshop = await api(`/api/performances/${encodeURIComponent(state.participantsOf)}`);
  document.getElementById("participants-title").textContent = `Inscrits · ${workshop.title}`;
  document.getElementById("participants-places").textContent =
    `${workshop.participants.length} inscrit(s), ${workshop.places_left} place(s) restante(s) sur ${workshop.capacity}.`;
  document.getElementById("participants-list").innerHTML = workshop.participants.length
    ? workshop.participants
        .map(
          (name) => `<li>${esc(name)}
            <button class="button danger small" data-name="${esc(name)}">Retirer</button></li>`
        )
        .join("")
    : `<li class="muted">Personne pour l'instant.</li>`;
}

document.getElementById("participant-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = event.target.name;
  showParticipantsError("");
  try {
    await api(`/api/performances/${encodeURIComponent(state.participantsOf)}/participants`, {
      method: "POST",
      body: { name: input.value },
    });
    toast(`${input.value} est inscrit(e).`);
    input.value = "";
    await Promise.all([showParticipants(), showSchedule()]);
  } catch (error) {
    showParticipantsError(error.message);
  }
});

document.getElementById("participants-list").addEventListener("click", async (event) => {
  const button = event.target.closest("[data-name]");
  if (!button) return;
  const name = button.dataset.name;
  showParticipantsError("");
  try {
    await api(
      `/api/performances/${encodeURIComponent(state.participantsOf)}/participants/${encodeURIComponent(name)}`,
      { method: "DELETE" }
    );
    toast(`${name} est désinscrit(e).`);
    await Promise.all([showParticipants(), showSchedule()]);
  } catch (error) {
    showParticipantsError(error.message);
  }
});

// ----- Ajouter un artiste -----

document.getElementById("artist-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const artistForm = event.target;
  try {
    const artist = await api("/api/artists", {
      method: "POST",
      body: {
        name: artistForm.name.value,
        bio: artistForm.bio.value,
        photo_url: artistForm.photo_url.value,
      },
    });
    toast(`${artist.name} ajouté(e) (${artist.slug}).`);
    artistForm.reset();
    await loadArtists();
  } catch (error) {
    toast(error.message, true);
  }
});

// ----- Démarrage -----

async function start() {
  try {
    await Promise.all([loadVenuesAndDays(), loadArtists()]);
    showKindFields();
    await showSchedule();
  } catch (error) {
    document.querySelector("main").insertAdjacentHTML(
      "afterbegin",
      `<div class="error-box">L'admin n'a pas pu se charger : ${esc(error.message)}</div>`
    );
  }
}

start();
