
document.addEventListener("DOMContentLoaded", () => {

    const nav = document.querySelector(".angel-nav");

    if (!nav) return;

    const buttons = nav.querySelectorAll("[data-menu]");
    const menus = nav.querySelectorAll(".angel-mega-menu");

    let activeButton = null;

    function closeMenus() {

        menus.forEach(menu => {
            menu.hidden = true;
        });

        buttons.forEach(button => {
            button.setAttribute("aria-expanded", "false");
        });

        nav.classList.remove("menu-open");

        activeButton = null;
    }

    buttons.forEach(button => {

        const menuId = button.dataset.menu;
        const menu = document.getElementById(menuId);

        if (!menu) return;

        button.setAttribute("aria-controls", menuId);

        button.addEventListener("click", () => {

            const isOpen =
                button.getAttribute("aria-expanded") === "true";

            closeMenus();

            if (!isOpen) {

                menu.hidden = false;

                button.setAttribute("aria-expanded", "true");

                nav.classList.add("menu-open");

                activeButton = button;
            }

        });

    });

    // Close when clicking outside the navigation

    document.addEventListener("click", event => {

        if (!nav.contains(event.target)) {
            closeMenus();
        }

    });

    // Close when pressing Escape

    document.addEventListener("keydown", event => {

        if (event.key === "Escape" && activeButton) {

            const previousButton = activeButton;

            closeMenus();

            previousButton.focus();
        }

    });

    // Close after selecting a menu link

    menus.forEach(menu => {

        menu.querySelectorAll("a").forEach(link => {

            link.addEventListener("click", closeMenus);

        });

    });

});

/* =========================================
   PREMIUM FLOATING SUPPORT MENU
   ========================================= */

document.addEventListener("DOMContentLoaded", function () {

    const supportToggle = document.getElementById("angelSupportToggle");
    const supportMenu = document.getElementById("angelSupportMenu");
    const supportClose = document.getElementById("angelSupportClose");
    const openAssistant = document.getElementById("angelOpenAssistant");
    const originalChatToggle = document.getElementById("angelChatToggle");
    const chatWindow = document.getElementById("angelChatWindow");

    if (!supportToggle || !supportMenu || !supportClose ||
        !openAssistant || !originalChatToggle || !chatWindow) {
        return;
    }

    function showSupportMenu() {
        supportMenu.hidden = false;
        supportToggle.setAttribute("aria-expanded", "true");
    }

    function hideSupportMenu() {
        supportMenu.hidden = true;
        supportToggle.setAttribute("aria-expanded", "false");
    }

    supportToggle.addEventListener("click", function () {

        if (chatWindow.classList.contains("angel-chat-open")) {
            originalChatToggle.click();
            supportToggle.focus();
            return;
        }

        if (supportMenu.hidden) {
            showSupportMenu();
        } else {
            hideSupportMenu();
        }

    });

    supportClose.addEventListener("click", function () {
        hideSupportMenu();
        supportToggle.focus();
    });

    openAssistant.addEventListener("click", function () {

        hideSupportMenu();

        if (!chatWindow.classList.contains("angel-chat-open")) {
            originalChatToggle.click();
        }

    });

    document.addEventListener("click", function (event) {

        if (!supportMenu.contains(event.target) &&
            !supportToggle.contains(event.target)) {
            hideSupportMenu();
        }

    });

    document.addEventListener("keydown", function (event) {

        if (event.key === "Escape" && !supportMenu.hidden) {
            hideSupportMenu();
            supportToggle.focus();
        }

    });

});

// Open ANGEL Assistant from the support page
document.addEventListener("DOMContentLoaded", function () {

    const params = new URLSearchParams(window.location.search);

    if (params.get("assistant") === "open") {

        const chatToggle = document.getElementById("angelChatToggle");
        const chatWindow = document.getElementById("angelChatWindow");

        if (chatToggle && chatWindow &&
            !chatWindow.classList.contains("angel-chat-open")) {

            chatToggle.click();

        }

    }

});

/* HOMEPAGE VIDEO PLAY / PAUSE */

document.addEventListener("DOMContentLoaded", function () {
    const video = document.querySelector(".angel-hero-video");
    const button = document.getElementById("angelVideoControl");

    if (!video || !button) return;

    const icon = button.querySelector("i");
    const reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    );

    function updateButton() {
        icon.className = video.paused
            ? "bi bi-play-fill"
            : "bi bi-pause-fill";

        button.setAttribute(
            "aria-label",
            video.paused
                ? "Play background video"
                : "Pause background video"
        );
    }

    button.addEventListener("click", function () {
        if (video.paused) {
            video.play().catch(updateButton);
        } else {
            video.pause();
        }
    });

    video.addEventListener("play", updateButton);
    video.addEventListener("pause", updateButton);

    if (reducedMotion.matches) {
        video.pause();
    }

    reducedMotion.addEventListener("change", function (event) {
        if (event.matches) video.pause();
    });

    updateButton();
});