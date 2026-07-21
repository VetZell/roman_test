const tg = window.Telegram?.WebApp;

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

const usersScreen =
    document.getElementById("users-screen");

const usersList =
    document.getElementById("users-list");

const backButton =
    document.getElementById("back-button");


let currentUser = null;


/* --------------------------------------------------
   ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
-------------------------------------------------- */

function showError(message) {
    nameElement.textContent =
        "Ошибка авторизации";

    usernameElement.textContent =
        "Открой приложение через Telegram";

    statusElement.textContent = message;

    statusElement.className =
        "status error";

    continueButton.disabled = true;
}


function escapeHtml(value) {
    const element =
        document.createElement("div");

    element.textContent = value || "";

    return element.innerHTML;
}


function getFullName(user) {
    const fullName = [
        user.first_name,
        user.last_name
    ]
        .filter(Boolean)
        .join(" ");

    return fullName || "Пользователь";
}


function getUserSubtitle(user) {
    if (user.username) {
        return (
            `@${user.username} • ` +
            `${user.messenger_code}`
        );
    }

    return user.messenger_code;
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

    const initData = tg.initData;

    if (!initData) {
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
                    init_data: initData
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

        const fullName =
            getFullName(currentUser);

        nameElement.textContent =
            fullName;

        usernameElement.textContent =
            getUserSubtitle(currentUser);

        if (currentUser.photo_url) {
            avatarElement.src =
                currentUser.photo_url;
        }

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
                Попроси другого человека открыть
                Roman Messenger через Telegram.
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
            "https://telegram.org/img/t_logo.png";

        const subtitle =
            getUserSubtitle(user);

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
                    ${escapeHtml(subtitle)}
                </div>
            </div>

            <div class="user-arrow">
                ›
            </div>
        `;

        userElement.addEventListener(
            "click",
            () => {
                selectUser(user);
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

        usersScreen.style.display =
            "block";

    } catch (error) {
        alert(error.message);

    } finally {
        continueButton.disabled = false;

        continueButton.textContent =
            "💬 Перейти к чатам";
    }
}


/* --------------------------------------------------
   ВЫБОР ПОЛЬЗОВАТЕЛЯ
-------------------------------------------------- */

function selectUser(user) {
    tg.HapticFeedback?.impactOccurred(
        "light"
    );

    sessionStorage.setItem(
        "selected_user",
        JSON.stringify(user)
    );

    alert(
        "Выбран пользователь:\n\n" +
        getFullName(user) +
        "\n" +
        getUserSubtitle(user) +
        "\n\nСледующим шагом откроем чат."
    );
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
    }
);


/* --------------------------------------------------
   ЗАПУСК
-------------------------------------------------- */

authorize();