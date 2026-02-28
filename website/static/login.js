async function handleLogin() {
    const userField = document.getElementById('username').value;
    const passField = document.getElementById('password').value;

    const response = await fetch('/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: userField, password: passField })
    });

    if (response.ok) {
        // The server set a cookie, now we can go to the chat
        window.location.href = "/chat";
    } else {
        alert("Login failed! Check your username/password.");
    }
}