(() => {
  const socket = io({ transports: ["websocket", "polling"] });
  const contactList = document.getElementById("contact-list");
  const searchInput = document.getElementById("user-search");
  const messageList = document.getElementById("message-list");
  const welcomePanel = document.getElementById("welcome-panel");
  const conversationPanel = document.getElementById("conversation-panel");
  const activeContact = document.getElementById("active-contact");
  const messageForm = document.getElementById("message-form");
  const messageInput = document.getElementById("message-input");
  const messageError = document.getElementById("message-error");
  let contacts = [];
  let selected = null;
  let lastQuery = "";
  let searchTimer = null;

  const escapeHTML = (value) => String(value ?? "").replace(/[&<>"']/g, c => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
  }[c]));
  const initials = (name) => String(name || "?").trim().split(/\s+/).slice(0,2).map(s => s[0] || "").join("").toUpperCase();
  const avatarClass = (id) => ["av-a","av-b","av-c","av-d","av-e"][Math.abs(Number(id)||0)%5];
  const shortTime = (iso) => {
    if (!iso) return "";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"});
  };
  function renderContacts() {
    document.getElementById("contact-count").textContent = contacts.length;
    if (!contacts.length) {
      contactList.innerHTML = '<div class="empty-contacts">No people found.<br><small>Ask someone to create an account.</small></div>';
      return;
    }
    contactList.innerHTML = contacts.map(u => `
      <button class="contact-item ${selected && selected.id === u.id ? "selected" : ""}" data-id="${u.id}">
        <span class="avatar ${avatarClass(u.id)}">${escapeHTML(initials(u.name))}</span>
        <span class="contact-info"><b>${escapeHTML(u.name)}</b><small>${escapeHTML(u.email)}</small></span>
        <span class="contact-dot" title="Account"></span>
      </button>`).join("");
    contactList.querySelectorAll(".contact-item").forEach(el => el.addEventListener("click", () => {
      const person = contacts.find(c => c.id === Number(el.dataset.id));
      if (person) openChat(person);
    }));
  }
  async function loadContacts(query="") {
    lastQuery = query;
    try {
      const response = await fetch(`/api/users?q=${encodeURIComponent(query)}`);
      if (!response.ok) throw new Error("Could not load contacts.");
      contacts = await response.json();
      renderContacts();
    } catch (err) {
      contactList.innerHTML = '<div class="empty-contacts">Could not load people. Refresh the page.</div>';
    }
  }
  function showError(text) {
    messageError.textContent = text;
    messageError.classList.remove("hidden");
    setTimeout(() => messageError.classList.add("hidden"), 4000);
  }
  function openChat(person) {
    selected = person;
    welcomePanel.classList.add("hidden");
    conversationPanel.classList.remove("hidden");
    const cls = avatarClass(person.id);
    activeContact.innerHTML = `<span class="avatar ${cls}">${escapeHTML(initials(person.name))}</span><div><h2>${escapeHTML(person.name)}</h2><p><span class="live-dot"></span> PulseChat member</p></div>`;
    renderContacts();
    messageList.innerHTML = '<div class="loading-messages">Opening conversation…</div>';
    socket.emit("open_conversation", {user_id: person.id});
    fetch(`/api/messages/${person.id}`)
      .then(r => r.ok ? r.json() : Promise.reject(new Error("Could not load messages.")))
      .then(messages => {
        if (!selected || selected.id !== person.id) return;
        messageList.innerHTML = "";
        messages.forEach(addMessage);
        scrollToBottom();
      })
      .catch(() => showError("Could not load this conversation. Please try again."));
  }
  function addMessage(m) {
    if (!selected || (m.sender_id !== selected.id && m.recipient_id !== selected.id)) return;
    if (messageList.querySelector(`[data-message-id="${m.id}"]`)) return;
    const mine = Number(m.sender_id) === Number(window.CURRENT_USER_ID);
    const item = document.createElement("div");
    item.className = `message-row ${mine ? "mine" : "theirs"}`;
    item.dataset.messageId = m.id;
    item.innerHTML = `<div class="message-content">${mine ? "" : `<span class="message-author">${escapeHTML(m.sender_name || selected.name)}</span>`}<div class="message-bubble">${escapeHTML(m.body).replace(/\n/g, "<br>")}</div><time>${escapeHTML(shortTime(m.created_at))}${mine ? " · You" : ""}</time></div>`;
    messageList.appendChild(item);
  }
  function scrollToBottom() { messageList.scrollTop = messageList.scrollHeight; }
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadContacts(searchInput.value.trim()), 180);
  });
  messageInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      messageForm.requestSubmit();
    }
  });
  messageInput.addEventListener("input", () => {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 120)}px`;
  });
  messageForm.addEventListener("submit", e => {
    e.preventDefault();
    const body = messageInput.value.trim();
    if (!selected) return showError("Choose a contact before sending a message.");
    if (!body) return;
    if (body.length > 2000) return showError("Messages are limited to 2,000 characters.");
    socket.emit("send_message", {recipient_id: selected.id, body});
    messageInput.value = "";
    messageInput.style.height = "auto";
    messageInput.focus();
  });
  socket.on("new_message", message => {
    if (selected && (Number(message.sender_id) === selected.id || Number(message.recipient_id) === selected.id)) {
      addMessage(message);
      scrollToBottom();
    }
  });
  socket.on("message_error", data => showError(data.error || "Message could not be sent."));
  socket.on("conversation_update", data => {
    if (data.other_id === selected?.id) return;
    // Refresh contact list so users can re-open a conversation after activity.
    loadContacts(lastQuery);
  });
  socket.on("connect_error", () => showError("Live connection failed. Check your connection and refresh."));
  document.getElementById("my-avatar").textContent = initials(window.CURRENT_USER_NAME);
  loadContacts();
})();
