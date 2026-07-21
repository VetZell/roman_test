const tg = window.Telegram?.WebApp;


/* --------------------------------------------------
   ЭЛЕМЕНТЫ ЭКРАНА АВТОРИЗАЦИИ
-------------------------------------------------- */

const cardElement =
    document.querySelector(".card");

const nameElement =
    document.getElementById("name");

const usernameElement =
    document.getElementById("username");

const avatarElement =
    document.getElementById("avatar");

const statusElement =
    document.getElementById("status");

const continueButton =
    document.getElementById("continue-button");


/* --------------------------------------------------
   ЭЛЕМЕНТЫ СПИСКА ПОЛЬЗОВАТЕЛЕЙ
-------------------------------------------------- */

const usersScreen =
    document.getElementById("users-screen");

const usersList =
    document.getElementById("users-list");

const backButton =
    document.getElementById("back-button");


/* --------------------------------------------------
   ЭЛЕМЕНТЫ ЧАТА
-------------------------------------------------- */

const chatScreen =
    document.getElementById("chat-screen");

const chatBackButton =
    document.getElementById("chat-back-button");

const chatAvatar =
    document.getElementById("chat-avatar");

const chatName =
    document.getElementById("chat-name");

const chatCode =
    document.getElementById("chat-code");

const messagesElement =
    document.getElementById("messages");

const messageInput =
    document.getElementById("message-input");

const sendButton =
    document.getElementById("send-button");


/* --------------------------------------------------
   СОСТОЯНИЕ ПРИЛОЖЕНИЯ
-------------------------------------------------- */

let currentUser = null;
let selectedUser = null;

let socket = null;
let reconnectTimer = null;

const renderedMessageIds =
    new Set();


/* --------------------------------------------------
   ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
-------------------------------------------------- */

function showError(message) {
    nameElement.textContent =
        "Ошибка авторизации";

    usernameElement.textContent =
        "Открой приложение через Telegram";

    statusElement.textContent =
        message;

    statusElement.className =
        "status error";

    continueButton.disabled = true;
}


function escapeHtml(value) {
    const element =
        document.createElement("div");

    element.textContent =
        value ?? "";

    return element.innerHTML;
}


function getFullName(user) {
    const fullName = [
        user?.first_name,
        user?.last_name
    ]
        .filter(Boolean)
        .join(" ");

    return fullName || "Пользователь";
}


function getUserSubtitle(user) {
    const code =
        user?.messenger_code || "";

    if (user?.username) {
        return `@${user.username} • ${code}`;
    }

    return code;
}


function getDefaultAvatar() {
    return "https://telegram.org/img/t_logo.png";
}


function vibrate(type = "light") {
    tg?.HapticFeedback?.impactOccurred(type);
}


function showAlert(message) {
    if (tg?.showAlert) {
        tg.showAlert(message);
        return;
    }

    alert(message);
}


/* --------------------------------------------------
   WEBSOCKET
-------------------------------------------------- */

function connectWebSocket() {
    if (!tg?.initData) {
        return;
    }

    if (
        socket &&
        (
            socket.readyState === WebSocket.OPEN ||
            socket.readyState === WebSocket.CONNECTING
        )
    ) {
        return;
    }

    const protocol =
        window.location.protocol === "https:"
            ? "wss:"
            : "ws:";

    const socketUrl =
        `${protocol}//${window.location.host}` +
        `/ws?init_data=` +
        encodeURIComponent(tg.initData);

    socket =
        new WebSocket(socketUrl);

    socket.addEventListener(
        "open",
        () => {
            console.log(
                "WebSocket подключён"
            );

            clearTimeout(
                reconnectTimer
            );
        }
    );

    socket.addEventListener(
        "message",
        (event) => {
            if (event.data === "ping") {
                if (
                    socket?.readyState ===
                    WebSocket.OPEN
                ) {
                    socket.send("pong");
                }

                return;
            }

            let data;

            try {
                data =
                    JSON.parse(event.data);
            } catch {
                return;
            }

            handleSocketEvent(data);
        }
    );

    socket.addEventListener(
        "close",
        () => {
            socket = null;

            clearTimeout(
                reconnectTimer
            );

            reconnectTimer =
                setTimeout(
                    connectWebSocket,
                    3000
                );
        }
    );

    socket.addEventListener(
        "error",
        () => {
            socket?.close();
        }
    );
}


function handleSocketEvent(data) {
    if (
        data.type !== "new_message" ||
        !data.message
    ) {
        return;
    }

    const message =
        data.message;

    if (
        renderedMessageIds.has(
            message.id
        )
    ) {
        return;
    }

    if (
        !selectedUser ||
        message.sender_id !== selectedUser.id
    ) {
        vibrate("medium");
        return;
    }

    addMessage(
        message.text,
        "other",
        message.id
    );

    vibrate("medium");
}


/* --------------------------------------------------
   TELEGRAM-АВТОРИЗАЦИЯ
-------------------------------------------------- */

async function authorize() {
    if (!tg) {
        showError(
            "Telegram WebApp SDK недоступен."
        );

        return;
    }

    tg.ready();
    tg.expand();

    if (!tg.initData) {
        showError(
            "Данные Telegram не получены. " +
            "Открой Mini App кнопкой внутри бота."
        );

        return;
    }

    try {
        const response =
            await fetch(
                "/api/auth/telegram",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        init_data:
                            tg.initData
                    })
                }
            );

        const result =
            await response.json();

        if (!response.ok || !result.ok) {
            throw new Error(
                result.detail ||
                "Авторизация не выполнена"
            );
        }

        currentUser =
            result.user;

        nameElement.textContent =
            getFullName(currentUser);

        usernameElement.textContent =
            getUserSubtitle(currentUser);

        avatarElement.src =
            currentUser.photo_url ||
            getDefaultAvatar();

        statusElement.textContent =
            "✓ Личность подтверждена Telegram";

        statusElement.className =
            "status success";

        continueButton.disabled =
            false;

        sessionStorage.setItem(
            "telegram_user",
            JSON.stringify(currentUser)
        );

        connectWebSocket();

    } catch (error) {
        showError(error.message);
    }
}


/* --------------------------------------------------
   СПИСОК ПОЛЬЗОВАТЕЛЕЙ
-------------------------------------------------- */

function renderUsers(users) {
    usersList.innerHTML = "";

    if (!users.length) {
        usersList.innerHTML = `
            <div class="empty-users">
                Пока других пользователей нет.
                <br><br>
                Открой Roman Messenger
                со второго Telegram-аккаунта.
            </div>
        `;

        return;
    }

    users.forEach((user) => {
        const userElement =
            document.createElement("div");

        userElement.className =
            "user-card";

        const avatar =
            user.photo_url ||
            getDefaultAvatar();

        userElement.innerHTML = `
            <img
                class="user-avatar"
                src="${escapeHtml(avatar)}"
                alt="Аватар"
            >

            <div class="user-info">
                <div class="user-name">
                    ${escapeHtml(
                        getFullName(user)
                    )}
                </div>

                <div class="user-code">
                    ${escapeHtml(
                        getUserSubtitle(user)
                    )}
                </div>
            </div>

            <div class="user-arrow">
                ›
            </div>
        `;

        userElement.addEventListener(
            "click",
            () => {
                openChatScreen(user);
            }
        );

        usersList.appendChild(
            userElement
        );
    });
}


async function openUsersScreen() {
    continueButton.disabled = true;

    continueButton.textContent =
        "Загрузка пользователей...";

    try {
        const response =
            await fetch(
                "/api/users",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        init_data:
                            tg.initData
                    })
                }
            );

        const result =
            await response.json();

        if (!response.ok || !result.ok) {
            throw new Error(
                result.detail ||
                "Не удалось загрузить пользователей"
            );
        }

        renderUsers(
            result.users
        );

        cardElement.style.display =
            "none";

        chatScreen.style.display =
            "none";

        usersScreen.style.display =
            "block";

        vibrate();

    } catch (error) {
        showAlert(error.message);

    } finally {
        continueButton.disabled =
            false;

        continueButton.textContent =
            "💬 Перейти к чатам";
    }
}


/* --------------------------------------------------
   ОТКРЫТИЕ ЧАТА
-------------------------------------------------- */

async function openChatScreen(user) {
    selectedUser =
        user;

    sessionStorage.setItem(
        "selected_user",
        JSON.stringify(user)
    );

    chatName.textContent =
        getFullName(user);

    chatCode.textContent =
        getUserSubtitle(user);

    chatAvatar.src =
        user.photo_url ||
        getDefaultAvatar();

    cardElement.style.display =
        "none";

    usersScreen.style.display =
        "none";

    chatScreen.style.display =
        "block";

    messagesElement.innerHTML = `
        <div class="chat-empty">
            Загрузка сообщений...
        </div>
    `;

    renderedMessageIds.clear();

    vibrate();

    await loadMessages();

    messageInput.focus();
}


/* --------------------------------------------------
   ЗАГРУЗКА СООБЩЕНИЙ
-------------------------------------------------- */

async function loadMessages() {
    if (!selectedUser) {
        return;
    }

    try {
        const response =
            await fetch(
                "/api/messages",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        init_data:
                            tg.initData,

                        user_id:
                            selectedUser.id
                    })
                }
            );

        const result =
            await response.json();

        if (!response.ok || !result.ok) {
            throw new Error(
                result.detail ||
                "Не удалось загрузить сообщения"
            );
        }

        renderedMessageIds.clear();

        messagesElement.innerHTML =
            "";

        if (!result.messages.length) {
            messagesElement.innerHTML = `
                <div class="chat-empty">
                    Начните переписку с
                    <strong>
                        ${escapeHtml(
                            getFullName(
                                selectedUser
                            )
                        )}
                    </strong>
                </div>
            `;

            return;
        }

        result.messages.forEach(
            (message) => {
                const sender =
                    message.sender_id ===
                    currentUser.id
                        ? "me"
                        : "other";

                addMessage(
                    message.text,
                    sender,
                    message.id
                );
            }
        );

        messagesElement.scrollTop =
            messagesElement.scrollHeight;

    } catch (error) {
        messagesElement.innerHTML = `
            <div class="chat-empty">
                ${escapeHtml(
                    error.message
                )}
            </div>
        `;
    }
}


/* --------------------------------------------------
   ОТОБРАЖЕНИЕ СООБЩЕНИЙ
-------------------------------------------------- */

function removeEmptyChatMessage() {
    const emptyMessage =
        messagesElement.querySelector(
            ".chat-empty"
        );

    if (emptyMessage) {
        emptyMessage.remove();
    }
}


function addMessage(
    text,
    sender = "me",
    messageId = null
) {
    if (
        messageId !== null &&
        renderedMessageIds.has(
            messageId
        )
    ) {
        return;
    }

    removeEmptyChatMessage();

    const messageElement =
        document.createElement("div");

    messageElement.className =
        `message ${sender}`;

    messageElement.textContent =
        text;

    if (messageId !== null) {
        renderedMessageIds.add(
            messageId
        );

        messageElement.dataset.messageId =
            String(messageId);
    }

    messagesElement.appendChild(
        messageElement
    );

    messagesElement.scrollTop =
        messagesElement.scrollHeight;
}


/* --------------------------------------------------
   ОТПРАВКА СООБЩЕНИЯ
-------------------------------------------------- */

async function sendMessage() {
    const text =
        messageInput.value.trim();

    if (!text || !selectedUser) {
        return;
    }

    sendButton.disabled =
        true;

    messageInput.disabled =
        true;

    try {
        const response =
            await fetch(
                "/api/messages/send",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        init_data:
                            tg.initData,

                        receiver_id:
                            selectedUser.id,

                        text:
                            text
                    })
                }
            );

        const result =
            await response.json();

        if (!response.ok || !result.ok) {
            throw new Error(
                result.detail ||
                "Не удалось отправить сообщение"
            );
        }

        addMessage(
            result.message.text,
            "me",
            result.message.id
        );

        messageInput.value =
            "";

        vibrate("medium");

    } catch (error) {
        showAlert(error.message);

    } finally {
        sendButton.disabled =
            false;

        messageInput.disabled =
            false;

        messageInput.focus();
    }
}


/* --------------------------------------------------
   НАВИГАЦИЯ
-------------------------------------------------- */

continueButton.addEventListener(
    "click",
    openUsersScreen
);


backButton.addEventListener(
    "click",
    () => {
        usersScreen.style.display =
            "none";

        chatScreen.style.display =
            "none";

        cardElement.style.display =
            "block";

        selectedUser =
            null;

        vibrate();
    }
);


chatBackButton.addEventListener(
    "click",
    () => {
        chatScreen.style.display =
            "none";

        cardElement.style.display =
            "none";

        usersScreen.style.display =
            "block";

        selectedUser =
            null;

        renderedMessageIds.clear();

        vibrate();
    }
);


/* --------------------------------------------------
   ОБРАБОТЧИКИ ОТПРАВКИ
-------------------------------------------------- */

sendButton.addEventListener(
    "click",
    sendMessage
);


messageInput.addEventListener(
    "keydown",
    (event) => {
        if (event.key === "Enter") {
            event.preventDefault();

            sendMessage();
        }
    }
);


/* --------------------------------------------------
   ЖИЗНЕННЫЙ ЦИКЛ
-------------------------------------------------- */

document.addEventListener(
    "visibilitychange",
    () => {
        if (
            document.visibilityState ===
            "visible"
        ) {
            connectWebSocket();

            if (selectedUser) {
                loadMessages();
            }
        }
    }
);


window.addEventListener(
    "beforeunload",
    () => {
        clearTimeout(
            reconnectTimer
        );

        socket?.close();
    }
);


/* --------------------------------------------------
   ЗАПУСК
-------------------------------------------------- */

authorize();