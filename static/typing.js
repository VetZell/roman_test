/* --------------------------------------------------
   ИНДИКАТОР "ПЕЧАТАЕТ..."
-------------------------------------------------- */

let typingStopTimer = null;
let remoteTypingTimer = null;
let lastTypingSent = false;

function sendTypingStatus(isTyping) {
    if (
        !selectedUser ||
        !socket ||
        socket.readyState !== WebSocket.OPEN
    ) {
        return;
    }

    if (lastTypingSent === isTyping) {
        return;
    }

    lastTypingSent = isTyping;

    socket.send(
        JSON.stringify({
            type: "typing",
            receiver_id: selectedUser.id,
            is_typing: isTyping,
        }),
    );
}

function stopTyping() {
    clearTimeout(typingStopTimer);

    if (lastTypingSent) {
        sendTypingStatus(false);
    }
}

function showRemoteTyping(isTyping) {
    clearTimeout(remoteTypingTimer);

    if (!selectedUser) {
        return;
    }

    if (!isTyping) {
        updateChatHeaderStatus();
        return;
    }

    chatCode.innerHTML = `
        <span class="typing-status">
            печатает<span class="typing-dots">...</span>
        </span>
    `;

    remoteTypingTimer = setTimeout(
        updateChatHeaderStatus,
        3500,
    );
}

const originalHandleSocketEvent = handleSocketEvent;

handleSocketEvent = function handleSocketEventWithTyping(data) {
    if (data?.type === "typing") {
        if (
            selectedUser &&
            Number(data.user_id) === Number(selectedUser.id)
        ) {
            showRemoteTyping(Boolean(data.is_typing));
        }

        return;
    }

    originalHandleSocketEvent(data);
};

messageInput.addEventListener(
    "input",
    () => {
        clearTimeout(typingStopTimer);

        const hasText =
            messageInput.value.trim().length > 0;

        if (!hasText) {
            stopTyping();
            return;
        }

        sendTypingStatus(true);

        typingStopTimer = setTimeout(
            () => {
                sendTypingStatus(false);
            },
            1800,
        );
    },
);

sendButton.addEventListener(
    "click",
    stopTyping,
);

messageInput.addEventListener(
    "keydown",
    (event) => {
        if (event.key === "Enter") {
            stopTyping();
        }
    },
);

chatBackButton.addEventListener(
    "click",
    () => {
        stopTyping();
        clearTimeout(remoteTypingTimer);
    },
);

window.addEventListener(
    "beforeunload",
    stopTyping,
);
