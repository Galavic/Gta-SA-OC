// Social profiles supplied by the user. Missing platforms are omitted per person.
export const contributors = {
  lauta: {
    name: "lauta",
    avatar: "https://avatars.githubusercontent.com/u/265983493?v=4&s=192",
    socials: {
      x: { href: "https://x.com/LautaTWT", label: "@LautaTWT" },
      github: { href: "https://github.com/machinebreak", label: "machinebreak" },
      discordGroup: { href: "https://discord.gg/7hbqkDmKHA", label: "Join the community" },
      whatsapp: { href: "https://whatsapp.com/channel/0029VbDpnc1545uwf4F6ju0Z", label: "Follow the channel" },
    },
  },
  Galavic: {
    name: "Galavic",
    avatar: "https://avatars.githubusercontent.com/u/203557097?v=4&s=192",
    socials: {
      x: { href: "https://x.com/ga_lavic", label: "@ga_lavic" },
      github: { href: "https://github.com/Galavic", label: "Galavic" },
    },
  },
};

export function installContributorCards(openModal) {
  const modal = document.getElementById("contributor-card");
  const fields = [...modal.querySelectorAll("[data-social]")];
  for (const button of document.querySelectorAll("[data-contributor]")) {
    button.addEventListener("click", () => {
      const selected = contributors[button.dataset.contributor];
      if (!selected) return;
      document.getElementById("contributor-name").textContent = selected.name;
      document.getElementById("contributor-avatar").src = selected.avatar;
      for (const field of fields) {
        const social = selected.socials[field.dataset.social];
        field.hidden = !social;
        field.querySelector(".social-value").textContent = social?.label || "";
        if (social) field.href = social.href;
        else field.removeAttribute("href");
      }
      openModal("contributor-card");
    });
  }
}
