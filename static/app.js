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
        const response = await fetch(
            "/api/auth/telegram",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    init_data: tg.initData
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

        currentUser = result.user;

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

        continueButton.disabled = false;

        sessionStorage.setItem(
            "telegram_user",
            JSON.stringify(currentUser)
        );

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
            () => openChatScreen(user)
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
        const response = await fetch(
            "/api/users",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    init_data: tg.initData
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

        renderUsers(result.users);

        cardElement.style.display =
            "none";

        chatScreen.style.display =
            "none";

        usersScreen.style.display =
            "block";

        vibrate();

    } catch (error) {
        alert(error.message);

    } finally {
        continueButton.disabled = false;

        continueButton.textContent =
            "💬 Перейти к чатам";
    }
}


/* --------------------------------------------------
   ОТКРЫТИЕ ЧАТА
-------------------------------------------------- */

async function openChatScreen(user) {
    selectedUser = user;

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

    usersScreen.style.display =
        "none";

    cardElement.style.display =
        "none";

    chatScreen.style.display =
        "block";

    messagesElement.innerHTML = `
        <div class="chat-empty">
            Загрузка сообщений...
        </div>
    `;

    vibrate();

    await loadMessages();

    messageInput.focus();
}

/* --------------------------------------------------
   ТЕСТОВЫЕ СООБЩЕНИЯ
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


function addMessage(text, sender = "me") {
    removeEmptyChatMessage();

    const message =
        document.createElement("div");

    message.className =
        `message ${sender}`;

    message.textContent =
        text;

    messagesElement.appendChild(
        message
    );

    messagesElement.scrollTop =
        messagesElement.scrollHeight;
}

async function loadMessages() {
    if (!selectedUser) {
        return;
    }

    try {
        const response = await fetch(
            "/api/messages",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    init_data: tg.initData,
                    user_id: selectedUser.id
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

        messagesElement.innerHTML = "";

        if (!result.messages.length) {
            messagesElement.innerHTML = `
                <div class="chat-empty">
                    Начните переписку с
                    <strong>
                        ${escapeHtml(
                            getFullName(selectedUser)
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
                );
            }
        );

    } catch (error) {
        messagesElement.innerHTML = `
            <div class="chat-empty">
                ${escapeHtml(error.message)}
            </div>
        `;
    }
}

async function sendMessage() {
    const text =
        messageInput.value.trim();

    if (!text || !selectedUser) {
        return;
    }

    sendButton.disabled = true;
    messageInput.disabled = true;

    try {
        const response = await fetch(
            "/api/messages/send",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    init_data: tg.initData,
                    receiver_id:
                        selectedUser.id,
                    text: text
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
        );

        messageInput.value = "";

        vibrate("medium");

    } catch (error) {
        alert(error.message);

    } finally {
        sendButton.disabled = false;
        messageInput.disabled = false;
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

        cardElement.style.display =
            "block";

        vibrate();
    }
);


chatBackButton.addEventListener(
    "click",
    () => {
        chatScreen.style.display =
            "none";

        usersScreen.style.display =
            "block";

        selectedUser = null;

        vibrate();
    }
);


/* --------------------------------------------------
   ОТПРАВКА СООБЩЕНИЯ
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
   ЗАПУСК
-------------------------------------------------- */

authorize();