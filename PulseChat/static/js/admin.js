(() => {
  const errorBox = document.getElementById("admin-error");
  let people = [];
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const date = iso => {
    if (!iso) return "—";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString([], {month:"short",day:"numeric",hour:"2-digit",minute:"2-digit"});
  };
  function showError(message) { errorBox.textContent = message; errorBox.classList.remove("hidden"); }
  async function load() {
    try {
      const r = await fetch("/api/admin/stats");
      if (!r.ok) throw new Error("Could not load dashboard data. Sign in again and refresh.");
      const data = await r.json();
      document.getElementById("stat-users").textContent = data.users.toLocaleString();
      document.getElementById("stat-messages").textContent = data.messages.toLocaleString();
      document.getElementById("stat-today").textContent = data.today_messages.toLocaleString();
      document.getElementById("stat-admins").textContent = data.admins.toLocaleString();
      document.getElementById("last-updated").textContent = "Updated " + new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
      const recent = document.getElementById("recent-messages");
      recent.innerHTML = data.recent.length ? data.recent.map(m => `<tr><td><div class="table-person"><span class="tiny-avatar">${esc((m.sender_name||"?")[0])}</span><b>${esc(m.sender_name)}</b></div></td><td><span class="message-preview">${esc(m.body)}</span></td><td>${esc(m.recipient_name)}</td><td class="time-cell">${esc(date(m.created_at))}</td></tr>`).join("") : '<tr><td colspan="4" class="table-empty">No messages yet. Activity will appear here.</td></tr>';
      people = data.people;
      document.getElementById("people-count").textContent = `${people.length} ACCOUNTS`;
      renderPeople();
    } catch (e) { showError(e.message || "Dashboard could not load."); }
  }
  function renderPeople() {
    const query = (document.getElementById("admin-search").value || "").toLowerCase().trim();
    const filtered = people.filter(p => `${p.name} ${p.email} ${p.role}`.toLowerCase().includes(query));
    document.getElementById("people-list").innerHTML = filtered.length ? filtered.map(p => `
      <tr><td><div class="person-cell"><span class="tiny-avatar">${esc((p.name||"?")[0])}</span><div><b>${esc(p.name)}</b><small>${esc(p.email)}</small></div></div></td>
      <td><span class="role-tag ${p.role === "admin" ? "role-admin" : ""}">${esc(p.role)}</span></td>
      <td>${p.role === "user" ? `<button class="delete-user" data-id="${p.id}" title="Delete user" aria-label="Delete ${esc(p.name)}">×</button>` : ""}</td></tr>`).join("") : '<tr><td colspan="3" class="table-empty">No matching accounts.</td></tr>';
    document.querySelectorAll(".delete-user").forEach(button => button.addEventListener("click", async () => {
      const person = people.find(p => p.id === Number(button.dataset.id));
      if (!person || !confirm(`Delete ${person.name}'s account and message history? This cannot be undone.`)) return;
      try {
        const r = await fetch(`/api/admin/users/${person.id}/delete`, {method:"POST"});
        const data = await r.json();
        if (!r.ok) throw new Error(data.error || "Could not delete account.");
        await load();
      } catch (e) { showError(e.message); }
    }));
  }
  document.getElementById("admin-search").addEventListener("input", renderPeople);
  load();
})();
