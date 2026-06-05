window.togglePasteContent = () => {
  const contentDiv = document.querySelector(".paste-content");
  if (!window.pasteContentJSON) {
    alert("No paste content available!");
    return;
  }

  if (typeof window.showingHTMLOnly === "undefined") {
    window.showingHTMLOnly = false;
  }

  if (!window.showingHTMLOnly) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(window.pasteContentJSON, "text/html");
    doc
      .querySelectorAll("[style]")
      .forEach((el) => el.removeAttribute("style"));
    Array.from(doc.querySelectorAll("style")).forEach((styleEl) =>
      styleEl.remove(),
    );
    const htmlContent = Array.from(doc.body.childNodes)
      .map((node) => node.outerHTML || node.textContent)
      .join("");

    contentDiv.innerHTML = htmlContent;
    contentDiv.style.transform = "";
    contentDiv.style.zoom = "";
    contentDiv.style.transition = "";
    window.showingHTMLOnly = true;
  } else {
    if (window.originalContent !== undefined) {
      contentDiv.innerHTML = window.originalContent;
    }

    contentDiv.style.transform = "";
    contentDiv.style.zoom = "";
    contentDiv.style.transition = "";
    window.showingHTMLOnly = false;
  }
};

document.addEventListener("DOMContentLoaded", () => {
  const contentElement = document.querySelector(".paste-content");
  if (contentElement) {
    window.originalContent = contentElement.innerHTML;
  }

  const toggleBtn = document.getElementById("toggleButton");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      window.togglePasteContent();
    });
  }
});
