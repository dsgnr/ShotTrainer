// Load mermaid only on pages with a diagram. Instant navigation swaps page
// content without a full reload, so diagrams are rendered on each navigation.
(function () {
  const SRC = "https://unpkg.com/mermaid@10.9.3/dist/mermaid.min.js";
  let loading = null;

  function load() {
    if (window.mermaid) return Promise.resolve();
    loading ??= new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = SRC;
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
    return loading;
  }

  function run() {
    if (!document.querySelector("pre.mermaid")) return;
    load().then(() => {
      window.mermaid.initialize({ startOnLoad: false, theme: "dark" });
      window.mermaid.run({ querySelector: "pre.mermaid" });
    });
  }

  if (document.readyState !== "loading") {
    run();
  } else {
    document.addEventListener("DOMContentLoaded", run);
  }

  if (window.document$ && typeof window.document$.subscribe === "function") {
    window.document$.subscribe(run);
  }
})();
