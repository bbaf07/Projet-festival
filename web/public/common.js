// Outils partagés par le site et l'admin : appeler l'API, afficher les dates,
// fabriquer du HTML sans risque (tout texte venant de l'API est échappé).

// Appelle l'API. Si la réponse est une erreur, lève une Error avec la phrase
// de l'API ({"detail": "..."}), pour l'afficher telle quelle.
async function api(path, options = {}) {
  const init = { ...options, headers: { ...(options.headers || {}) } };
  if (init.body !== undefined && typeof init.body !== "string") {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(init.body);
  }
  const response = await fetch(path, init);
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(errorMessage(data, response.status));
  }
  return data;
}

// Le "detail" d'une erreur : une phrase (nos règles) ou une liste (FastAPI).
function errorMessage(data, status) {
  if (!data || data.detail === undefined) return `Erreur ${status}`;
  if (typeof data.detail === "string") return data.detail;
  return data.detail
    .map((item) => `${item.loc.slice(1).join(".")} : ${item.msg}`)
    .join(" ; ");
}

// Échappe un texte avant de l'insérer dans du HTML.
function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// "2027-06-11" -> "vendredi 11 juin" (midi : évite les surprises de fuseau).
function formatDay(day, style = "long") {
  const date = new Date(`${day}T12:00`);
  const options =
    style === "short"
      ? { weekday: "short", day: "numeric", month: "short" }
      : { weekday: "long", day: "numeric", month: "long" };
  return new Intl.DateTimeFormat("fr-FR", options).format(date);
}

// "2027-06-11T21:30" -> "21:30"
function formatTime(moment) {
  return moment.slice(11, 16);
}

// Les initiales d'un nom, pour un avatar sans photo : "Léa Fontaine" -> "LF".
function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");
}

// L'avatar d'un artiste : sa photo s'il en a une, sinon ses initiales.
function avatarHtml(artist) {
  if (artist.photo_url) {
    return `<img class="avatar" src="${esc(artist.photo_url)}" alt="">`;
  }
  return `<div class="avatar" aria-hidden="true">${esc(initials(artist.name))}</div>`;
}

const KIND_LABELS = { solo: "Solo", lineup: "Plateau", workshop: "Atelier" };

// Les badges d'un spectacle : type, âge minimum, places restantes.
function badgesHtml(performance) {
  const badges = [`<span class="badge">${KIND_LABELS[performance.kind] || esc(performance.kind)}</span>`];
  if (performance.min_age) {
    badges.push(`<span class="badge age">${performance.min_age}+</span>`);
  }
  if (performance.places_left !== undefined) {
    badges.push(
      performance.places_left > 0
        ? `<span class="badge places">${performance.places_left} place(s) restante(s)</span>`
        : `<span class="badge full">Complet</span>`
    );
  }
  return `<div class="badges">${badges.join("")}</div>`;
}

// Les noms des artistes d'un spectacle, chacun vers sa page.
function artistLinks(performance, prefix = "") {
  return performance.artists
    .map((a) => `<a href="${prefix}artist.html?slug=${encodeURIComponent(a.slug)}">${esc(a.name)}</a>`)
    .join(", ");
}

// La carte d'un spectacle dans le programme.
function performanceCard(performance, { showDay = false } = {}) {
  const day = showDay ? `${esc(formatDay(performance.festival_day, "short"))} · ` : "";
  const description = performance.description
    ? `<p class="description">${esc(performance.description)}</p>`
    : "";
  return `
    <article class="card kind-${esc(performance.kind)}">
      <div class="time">${day}${formatTime(performance.start)} – ${formatTime(performance.end)}</div>
      <h3>${esc(performance.title)}</h3>
      <div class="venue">${esc(performance.venue_name)}</div>
      <p class="summary">${artistLinks(performance)}</p>
      ${description}
      ${badgesHtml(performance)}
    </article>`;
}

// Un message en bas de l'écran, qui disparaît tout seul.
function toast(message, isError = false) {
  let box = document.getElementById("toast");
  if (!box) {
    box = document.createElement("div");
    box.id = "toast";
    box.setAttribute("role", "status");
    document.body.append(box);
  }
  box.textContent = message;
  box.className = isError ? "error" : "";
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (box.hidden = true), isError ? 6000 : 3000);
}
