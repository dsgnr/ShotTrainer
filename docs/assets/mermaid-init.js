// Initialise mermaid once the library is loaded. Mkdocs-material's
// instant-navigation feature swaps page content without a full reload,
// so mermaid runs again on each navigation event.
(function () {
  function run() {
    if (window.mermaid) {
      window.mermaid.initialize({ startOnLoad: false, theme: "dark" });
      window.mermaid.run({ querySelector: "pre.mermaid" });
    }
  }

  if (document.readyState !== "loading") {
    run();
  } else {
    document.addEventListener("DOMContentLoaded", run);
  }

  // Mkdocs-material instant navigation hook.
  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(run);
  }
})();
