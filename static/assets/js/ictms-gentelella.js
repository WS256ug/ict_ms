document.addEventListener("DOMContentLoaded", () => {
  const body = document.body;
  const menuToggle = document.getElementById("menu_toggle");
  const overlay = document.getElementById("sidebar-overlay");
  const sidebarLinks = document.querySelectorAll(".side-menu a");
  const counters = document.querySelectorAll(".js-counter");
  const mobileQuery = window.matchMedia("(max-width: 991.98px)");

  const closeMobileSidebar = () => {
    body.classList.remove("sidebar-open");
  };

  const handleToggle = () => {
    if (mobileQuery.matches) {
      body.classList.toggle("sidebar-open");
      return;
    }
    body.classList.toggle("sidebar-collapsed");
  };

  const syncLayout = () => {
    if (!mobileQuery.matches) {
      body.classList.remove("sidebar-open");
    }
  };

  const animateCounter = (element) => {
    const target = Number.parseInt(element.dataset.counterTarget || "0", 10);
    if (!Number.isFinite(target) || target < 1) {
      element.textContent = "0";
      return;
    }

    const duration = 1000;
    const startTime = performance.now();

    const render = (timestamp) => {
      const progress = Math.min((timestamp - startTime) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      element.textContent = new Intl.NumberFormat().format(Math.round(target * eased));
      if (progress < 1) {
        window.requestAnimationFrame(render);
      }
    };

    window.requestAnimationFrame(render);
  };

  if (menuToggle) {
    menuToggle.addEventListener("click", handleToggle);
  }

  if (overlay) {
    overlay.addEventListener("click", closeMobileSidebar);
  }

  sidebarLinks.forEach((link) => {
    link.addEventListener("click", () => {
      if (mobileQuery.matches) {
        closeMobileSidebar();
      }
    });
  });

  mobileQuery.addEventListener("change", syncLayout);
  syncLayout();

  const observer = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }
        animateCounter(entry.target);
        obs.unobserve(entry.target);
      });
    },
    { threshold: 0.45 }
  );

  counters.forEach((counter) => observer.observe(counter));
});
