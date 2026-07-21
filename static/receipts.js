/* --------------------------------------------------
   СТАТУСЫ СООБЩЕНИЙ: ✓ ДОСТАВЛЕНО / ✓✓ ПРОЧИТАНО
-------------------------------------------------- */

const messageReceiptCache = new Map();
const originalFetchForReceipts = window.fetch.bind(window);

window.fetch = async (...args) => {
    const response = await originalFetchForReceipts(...args);

    try {
        const clone = response.clone();
        const data = await clone.json();

        if (Array.isArray(data?.messages)) {
            data.messages.forEach((message) => {
                messageReceiptCache.set(Number(message.id), message);
            });
        }

        if (data?.message?.id) {
            messageReceiptCache.set(Number(data.message.id), data.message);
        }
    } catch {
        // Ответ не JSON — ничего не делаем.
    }

    return response;
};

function getReceiptState(message) {
    if (message?.is_read) {
        return {
            className: "read",
            text: "✓✓",
            title: "Прочитано",
        };
    }

    if (message?.is_delivered) {
        return {
            className: "delivered",
            text: "✓",
            title: "Доставлено",
        };
    }

    return {
        className: "sent",
        text: "✓",
        title: "Отправлено",
    };
}

function renderMessageReceipt(messageElement, message) {
    if (!messageElement || !messageElement.classList.contains("me")) {
        return;
    }

    let receipt = messageElement.querySelector(".message-receipt");

    if (!receipt) {
        receipt = document.createElement("span");
        receipt.className = "message-receipt";
        messageElement.appendChild(receipt);
    }

    const state = getReceiptState(message);
    receipt.className = `message-receipt ${state.className}`;
    receipt.textContent = state.text;
    receipt.title = state.title;
}

function updateMessageReceipts(messageIds, state) {
    (messageIds || []).forEach((messageId) => {
        const numericId = Number(messageId);
        const previous = messageReceiptCache.get(numericId) || { id: numericId };
        const updated = {
            ...previous,
            is_delivered: state === "delivered" || state === "read" || previous.is_delivered,
            is_read: state === "read" || previous.is_read,
        };

        messageReceiptCache.set(numericId, updated);

        const element = messagesElement.querySelector(
            `[data-message-id="${numericId}"]`,
        );

        renderMessageReceipt(element, updated);
    });
}

const originalAddMessageForReceipts = addMessage;

addMessage = function addMessageWithReceipt(
    text,
    sender = "me",
    messageId = null,
) {
    originalAddMessageForReceipts(text, sender, messageId);

    if (sender !== "me" || messageId === null) {
        return;
    }

    const element = messagesElement.querySelector(
        `[data-message-id="${Number(messageId)}"]`,
    );

    const message = messageReceiptCache.get(Number(messageId)) || {
        id: Number(messageId),
        is_delivered: false,
        is_read: false,
    };

    renderMessageReceipt(element, message);
};

const originalHandleSocketEventForReceipts = handleSocketEvent;

handleSocketEvent = function handleSocketEventWithReceipts(data) {
    if (data?.type === "new_message" && data.message?.id) {
        messageReceiptCache.set(Number(data.message.id), data.message);
    }

    if (data?.type === "messages_delivered") {
        updateMessageReceipts(data.message_ids, "delivered");
        return;
    }

    if (data?.type === "messages_read") {
        updateMessageReceipts(data.message_ids, "read");
        return;
    }

    originalHandleSocketEventForReceipts(data);
};
