
document.addEventListener("DOMContentLoaded", function () {
    const chatWindow = document.getElementById("angelChatWindow");
    const toggleButton = document.getElementById("angelChatToggle");
    const closeButton = document.getElementById("angelChatClose");
    const messages = document.getElementById("angelChatMessages");
    const options = document.getElementById("angelChatOptions");

    if (!chatWindow || !toggleButton || !closeButton ||
        !messages || !options) {
        return;
    }

    let chatStarted = false;
    let history = [];
    let currentMenu = "home";
    let supportActive = false;
    let supportReference = null;
    let supportTimer = null;
    let supportStatus = null;
    let lastMessageId = 0;
    let pollingInProgress = false;

    const mainMenu = {
        message: "Hi! How can I help you today?",
        options: [
            { label: "Track my luggage", next: "tracking" },
            { label: "Luggage registration", next: "registration" },
            { label: "Lost or delayed luggage", next: "missing" },
            { label: "Account and login help", next: "account" },
            { label: "Speak to a live agent", next: "liveAgent" }
        ]
    };

    const menus = {
        tracking: {
            message: "What do you need help with?",
            options: [
                {
                    label: "How do I track my luggage?",
                    answer: "Enter your ANGEL tracking ID in the Track Your Luggage box on the homepage, then select Search. Make sure the tracking ID is entered correctly."
                },
                {
                    label: "Where can I find my tracking ID?",
                    answer: "Your tracking ID should be provided when your luggage is registered in ANGEL. If you do not have it, contact the staff member or airport team who registered your luggage."
                },
                {
                    label: "My tracking ID is not working",
                    answer: "Double-check the ID for typing errors and try again. If it still cannot be found, the record may need to be checked by an ANGEL staff member."
                },
                {
                    label: "My luggage status has not changed",
                    answer: "The latest location may not have been recorded yet. If your luggage remains at the same status for an unusually long time, ask airport staff to investigate."
                }
            ]
        },

        registration: {
            message: "What would you like to know about registration?",
            options: [
                {
                    label: "How is luggage registered?",
                    answer: "Luggage is registered by an authorised ANGEL employee through the luggage registration system. The employee enters the required details and creates a tracking record."
                },
                {
                    label: "How do I get a tracking ID?",
                    answer: "A tracking ID is generated as part of the luggage registration process. Ask the staff member who registered your luggage if you have not received yours."
                },
                {
                    label: "My luggage details are incorrect",
                    answer: "Please contact an authorised ANGEL staff member and provide your tracking ID and the details that need correction. Do not share your password."
                }
            ]
        },

        missing: {
            message: "I'm sorry you're having trouble with your luggage. What happened?",
            options: [
                {
                    label: "My luggage is missing",
                    answer: "Report the missing luggage to the airline or airport baggage service desk as soon as possible. Keep your baggage tag and any reference numbers. An ANGEL staff member can also help check the recorded tracking information."
                },
                {
                    label: "My luggage is delayed",
                    answer: "Contact your airline's baggage service desk to report the delay and obtain a reference number. You can also check the latest recorded status using your ANGEL tracking ID."
                },
                {
                    label: "The location looks incorrect",
                    answer: "The recorded location may need to be verified by staff. Keep your tracking ID handy and request that an ANGEL employee check the latest update."
                },
                {
                    label: "I need urgent assistance",
                    next: "liveAgent"
                }
            ]
        },

        account: {
            message: "Let's see if I can help with your account.",
            options: [
                {
                    label: "I cannot log in",
                    answer: "Check that your username and password are correct and that you are using the correct ANGEL login page. If the issue continues, contact your system administrator."
                },
                {
                    label: "I forgot my password",
                    answer: "Please contact your ANGEL administrator or authorised supervisor to request a password reset. Never share your existing password with anyone."
                },
                {
                    label: "My account is disabled",
                    answer: "An authorised administrator or supervisor may need to review your account status. Contact them for assistance."
                },
                {
                    label: "I need more help",
                    next: "liveAgent"
                }
            ]
        },

        liveAgent: {
            message: "I'll help you connect with the ANGEL support team. Please enter your luggage tracking ID to begin.",
            options: [
                { label: "Start live support", action: "startSupport" },
                { label: "Back to main menu", next: "home" }
            ]
        }
    };

    function addMessage(text, sender) {
        const message = document.createElement("div");
        message.className = "angel-chat-message " + sender;
        message.textContent = text;
        messages.appendChild(message);
        messages.scrollTop = messages.scrollHeight;
    }

    function addInput(placeholder, buttonLabel, onSubmit, inputType = "text") {
        const form = document.createElement("form");
        form.className = "angel-chat-input-form";

        const input = document.createElement("input");
        input.type = inputType;
        input.placeholder = placeholder;
        input.required = true;
        input.maxLength = 2000;
        input.autocomplete = "off";
        input.className = "angel-chat-text-input";

        const button = document.createElement("button");
        button.type = "submit";
        button.className = "angel-chat-option";
        button.textContent = buttonLabel;

        form.append(input, button);
        options.replaceChildren(form);

        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            const value = input.value.trim();

            if (!value) return;

            input.disabled = true;
            button.disabled = true;

            try {
                await onSubmit(value, input, button);
            } catch (error) {
                addMessage(error.message || "Something went wrong. Please try again.", "bot");
                input.disabled = false;
                button.disabled = false;
            }
        });

        input.focus();
    }

    function renderOptions(menu) {
        options.replaceChildren();

        menu.options.forEach(function (option) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "angel-chat-option";
            button.textContent = option.label;

            button.addEventListener("click", function () {
                addMessage(option.label, "user");

                if (option.action === "startSupport") {
                    startSupportForm();
                    return;
                }

                if (option.next === "home") {
                    showMenu("home");
                    return;
                }

                if (option.next) {
                    history.push(currentMenu);
                    showMenu(option.next);
                    return;
                }

                if (option.answer) {
                    addMessage(option.answer, "bot");
                    renderFollowUpOptions();
                }
            });

            options.appendChild(button);
        });

        if (currentMenu !== "home") {
            const backButton = document.createElement("button");
            backButton.type = "button";
            backButton.className = "angel-chat-option";
            backButton.textContent = "← Back";

            backButton.addEventListener("click", function () {
                if (history.length > 0) {
                    showMenu(history.pop());
                } else {
                    showMenu("home");
                }
            });

            options.appendChild(backButton);

            const homeButton = document.createElement("button");
            homeButton.type = "button";
            homeButton.className = "angel-chat-option";
            homeButton.textContent = "Main menu";

            homeButton.addEventListener("click", function () {
                showMenu("home");
            });

            options.appendChild(homeButton);
        }
    }

    function renderFollowUpOptions() {
        options.replaceChildren();

        const helpfulButton = document.createElement("button");
        helpfulButton.type = "button";
        helpfulButton.className = "angel-chat-option";
        helpfulButton.textContent = "That solved my problem";

        helpfulButton.addEventListener("click", function () {
            addMessage("That solved my problem", "user");
            addMessage(
                "I'm glad I could help! Is there anything else I can assist you with?",
                "bot"
            );
            showMenu("home", false);
        });

        const agentButton = document.createElement("button");
        agentButton.type = "button";
        agentButton.className = "angel-chat-option";
        agentButton.textContent = "I still need help";

        agentButton.addEventListener("click", function () {
            addMessage("I still need help", "user");
            history.push(currentMenu);
            showMenu("liveAgent");
        });

        const homeButton = document.createElement("button");
        homeButton.type = "button";
        homeButton.className = "angel-chat-option";
        homeButton.textContent = "Main menu";

        homeButton.addEventListener("click", function () {
            showMenu("home");
        });

        options.append(helpfulButton, agentButton, homeButton);
    }

    function showMenu(name, addBotMessage = true) {
        stopSupportPolling();
        supportActive = false;
        currentMenu = name;

        const menu = name === "home" ? mainMenu : menus[name];

        if (!menu) {
            showMenu("home");
            return;
        }

        if (addBotMessage) {
            addMessage(menu.message, "bot");
        }

        renderOptions(menu);
    }

    function startSupportForm() {
        addMessage(
            "Please enter your luggage tracking ID. We'll use it to find your luggage record.",
            "bot"
        );

        addInput("Enter luggage tracking ID", "Continue", function (trackingId) {
            addMessage(trackingId, "user");
            askInitialMessage(trackingId.trim());
        });
    }

    function askInitialMessage(trackingId) {
        addMessage(
            "Briefly describe the issue so our support team knows how to help.",
            "bot"
        );

        addInput("Describe your issue...", "Request support", async function (initialMessage) {
            addMessage(initialMessage, "user");

            try {
                const response = await fetch("/support/start", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        tracking_id: trackingId,
                        message: initialMessage
                    })
                });

                const data = await response.json();

                if (!response.ok || !data.success) {
                    throw new Error(
                        data.message || data.error || "Unable to start a support request."
                    );
                }

                if (!data.reference) {
                    throw new Error("The server did not return a support reference.");
                }

                supportReference = data.reference;
                supportStatus = data.status || "Waiting";
                supportActive = true;
                lastMessageId = 0;

                addMessage(
                    "Your support request has been created! Reference: " +
                    supportReference + ". Status: " + supportStatus +
                    ". Keep this chat open while you wait for an employee.",
                    "bot"
                );

                showActiveSupportControls();

                await pollSupportMessages();
                supportTimer = setInterval(pollSupportMessages, 3000);
            } catch (error) {
                addMessage(
                    "I couldn't create your support request. " +
                    (error.message || "Please try again in a moment."),
                    "bot"
                );

                options.replaceChildren();

                const retryButton = document.createElement("button");
                retryButton.type = "button";
                retryButton.className = "angel-chat-option";
                retryButton.textContent = "Try again";
                retryButton.addEventListener("click", startSupportForm);
                options.appendChild(retryButton);

                const homeButton = document.createElement("button");
                homeButton.type = "button";
                homeButton.className = "angel-chat-option";
                homeButton.textContent = "Main menu";
                homeButton.addEventListener("click", function () {
                    showMenu("home");
                });
                options.appendChild(homeButton);
            }
        });
    }

   
function showActiveSupportControls() {

        if (!supportActive) return;

        options.replaceChildren();

        addInput("Type your message...", "Send", async function (message, input, button) {
            if (!supportReference) {
                throw new Error("Your support reference is missing. Please start a support request again.");
            }

            const response = await fetch("/support/send", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    reference: supportReference,
                    message: message
                })
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(
                    data.message || data.error || "Message could not be sent."
                );
            }

            addMessage(message, "user");
            input.value = "";
            input.disabled = false;
            button.disabled = false;
            input.focus();

            await pollSupportMessages();
        });

        const refreshButton = document.createElement("button");
        refreshButton.type = "button";
        refreshButton.className = "angel-chat-option";
        refreshButton.textContent = "Check for replies";
        refreshButton.addEventListener("click", pollSupportMessages);
        options.appendChild(refreshButton);

        const homeButton = document.createElement("button");
        homeButton.type = "button";
        homeButton.className = "angel-chat-option";
        homeButton.textContent = "Main menu";
        homeButton.addEventListener("click", function () {
            showMenu("home");
        });
        options.appendChild(homeButton);
    }

    async function pollSupportMessages() {
        if (!supportActive || !supportReference || pollingInProgress) return;

        pollingInProgress = true;

        try {
            const url = "/support/messages?reference=" +
                encodeURIComponent(supportReference);

            const response = await fetch(url, {
                method: "GET",
                cache: "no-store",
                credentials: "same-origin"
            });

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(
                    data.message || data.error || "Could not check support messages."
                );
            }

            if (data.status && data.status !== supportStatus) {
                supportStatus = data.status;
                addMessage("Support status: " + supportStatus, "bot");
            }

            (data.messages || []).forEach(function (message) {
                const messageId = Number(message.id) || 0;

                if (messageId > lastMessageId) {
                    lastMessageId = messageId;

                    if (message.sender_type === "employee") {
                        addMessage(message.message, "bot");
                    } else if (message.sender_type === "system") {
                        addMessage(message.message, "bot");
                    }
                }
            });

            if (supportStatus === "Resolved") {
                stopSupportPolling();
                supportActive = false;

                addMessage(
                    "This support conversation has been resolved. If you need more help, you can start a new request.",
                    "bot"
                );

                options.replaceChildren();

                const newRequestButton = document.createElement("button");
                newRequestButton.type = "button";
                newRequestButton.className = "angel-chat-option";
                newRequestButton.textContent = "Start another support request";
                newRequestButton.addEventListener("click", function () {
                    showMenu("liveAgent");
                });
                options.appendChild(newRequestButton);
            }
        } catch (error) {
            addMessage(
                "I couldn't refresh your support messages: " +
                (error.message || "Please try again."),
                "bot"
            );

            // Stop this polling attempt from repeatedly filling the chat with errors.
            stopSupportPolling();
            supportActive = false;

            const retryButton = document.createElement("button");
            retryButton.type = "button";
            retryButton.className = "angel-chat-option";
            retryButton.textContent = "Reconnect to support";

            retryButton.addEventListener("click", function () {
                supportActive = true;
                showActiveSupportControls();
                pollSupportMessages();
                if (!supportTimer) {
                    supportTimer = setInterval(pollSupportMessages, 3000);
                }
            });

            options.appendChild(retryButton);
        } finally {
            pollingInProgress = false;
        }
    }

    function stopSupportPolling() {
        if (supportTimer) {
            clearInterval(supportTimer);
            supportTimer = null;
        }
    }

    function openChat() {
        chatWindow.classList.add("angel-chat-open");
        chatWindow.setAttribute("aria-hidden", "false");
        toggleButton.setAttribute("aria-expanded", "true");

        if (!chatStarted) {
            chatStarted = true;
            showMenu("home");
        }
    }

    // ANGEL Support information popup
const supportInfoToggle = document.getElementById("supportInfoToggle");
const supportPopup = document.getElementById("supportPopup");
const openAngelSupport = document.getElementById("openAngelSupport");

if (supportInfoToggle && supportPopup) {
    supportInfoToggle.addEventListener("click", function (event) {
        event.preventDefault();
        supportPopup.hidden = !supportPopup.hidden;
    });
}

if (openAngelSupport && supportPopup) {
    openAngelSupport.addEventListener("click", function (event) {
        event.preventDefault();
        supportPopup.hidden = true;
        openChat();
    });
}

    function closeChat() {
        chatWindow.classList.remove("angel-chat-open");
        chatWindow.setAttribute("aria-hidden", "true");
        toggleButton.setAttribute("aria-expanded", "false");
        toggleButton.focus();
    }

    toggleButton.addEventListener("click", function () {
        if (chatWindow.classList.contains("angel-chat-open")) {
            closeChat();
        } else {
            openChat();
        }
    });

    closeButton.addEventListener("click", closeChat);

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" &&
            chatWindow.classList.contains("angel-chat-open")) {
            closeChat();
        }
    });
});
