function logout() {
    document.cookie = "session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    console.log("Logout. Session cookie eaten");
    location.href = "/login.html";
}

function newPlayer() {
    document.cookie = "session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    console.log("Go to New Player. Session cookie eaten");
    location.href = "/new.html";
}

function cleanHome() {
    document.cookie= "session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    console.log("Go home with no cookies. Session cookie eaten");
    location.href = "/home.html";
}

function login(sessionId) {
    console.log("Change Session. sessionId = " + sessionId);
    console.log(sessionId.replace(":", "=") + "; max-age=" + (60 * 60 * 24 * 365 * 2));
    document.cookie = sessionId.replace(":", "=") + "; max-age=" + (60 * 60 * 24 * 365 * 2);
    location.href = "/home.html";
}

function changeSession(sessionId) { // cookieCrumble
    console.log("Change Session. sessionId = " + sessionId);
    console.log(sessionId.replace(":", "=") + "; max-age=" + (60 * 60 * 24 * 365 * 2));
    document.cookie = sessionId.replace(":", "=") + "; max-age=" + (60 * 60 * 24 * 365 * 2);
    location.reload();
}