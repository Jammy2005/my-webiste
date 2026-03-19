async function sendMessage() {
    const messageInput = document.getElementById("messageInput");
    const chatBox = document.getElementById("chatBox");

    const message = messageInput.value;

    // show user message
    const userMessage = document.createElement("p");
    userMessage.innerText = "You: " + message;
    chatBox.appendChild(userMessage);

    // call backend
    const res = await fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ message: message })
    });

    const data = await res.json();

    // show bot response DIRECTLY
    const botMessage = document.createElement("p");
    botMessage.innerText = data.response;
    chatBox.appendChild(botMessage);

    messageInput.value = "";
}