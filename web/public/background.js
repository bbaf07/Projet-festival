// Le fond animé : des clés de sol qui apparaissent et disparaissent.
// Reprise de l'animation de fond du projet précédent (des loupes), en
// JavaScript simple : chaque clé a sa place, sa taille, sa rotation, sa durée
// et son intensité, tirées une fois pour toutes.

(function () {
  // Générateur pseudo-aléatoire déterministe (mulberry32) : la même graine
  // donne toujours la même disposition, d'une page à l'autre.
  function mulberry32(seed) {
    return function random() {
      seed |= 0;
      seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const COUNT = 30;
  const random = mulberry32(1337);

  const layer = document.createElement("div");
  layer.className = "bg-clefs";
  layer.setAttribute("aria-hidden", "true");

  for (let index = 0; index < COUNT; index++) {
    const clef = document.createElement("span");
    clef.className = "bg-clef";
    clef.textContent = "𝄞"; // U+1D11E, la clé de sol
    const size = 22 + random() * 52;
    clef.style.top = `${random() * 100}%`;
    clef.style.left = `${random() * 100}%`;
    clef.style.fontSize = `${size}px`;
    clef.style.transform = `rotate(${-30 + random() * 60}deg)`;
    clef.style.animationDuration = `${2.2 + random() * 2.6}s`;
    clef.style.animationDelay = `${random() * 2.5}s`;
    clef.style.setProperty("--peak", String(0.1 + random() * 0.16));
    layer.append(clef);
  }

  document.body.prepend(layer);
})();
