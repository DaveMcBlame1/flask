console.log("index.js loaded");

// List of available themes
const themes = ['HomeBrew', 'DarkMode', 'LightModeHB', 'LightMode', 'default']; // Add more themes as needed

// Function to preload themes
function preloadThemes() {
    const head = document.head;
    themes.forEach(theme => {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = `/static/themes/${theme}.css`;
        link.id = `${theme.toLowerCase()}-theme`;
        link.disabled = true; // Disable by default
        head.appendChild(link);
    });
}

// Function to set the theme
function setTheme(themeName) {
    themes.forEach(theme => {
        const themeLink = document.getElementById(`${theme.toLowerCase()}-theme`);
        themeLink.disabled = theme !== themeName;
    });

    // Save the selected theme to localStorage
    localStorage.setItem('selectedTheme', themeName);
}

// Function to scroll to the bottom of the chatbox
function scrollToBottom() {
    const chatbox = document.getElementById('chatbox');
    if (chatbox) {
        chatbox.scrollTop = chatbox.scrollHeight;
    }
}

// Load the saved theme and scroll to the bottom when the page loads
window.onload = function() {
    preloadThemes(); // Preload all themes

    const savedTheme = localStorage.getItem('selectedTheme');
    if (savedTheme) {
        setTheme(savedTheme);
    } else {
        setTheme('default'); // Default theme
    }

    scrollToBottom(); // Scroll to the bottom of the chatbox
};
