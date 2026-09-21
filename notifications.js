document.addEventListener("DOMContentLoaded", () => {

    const notification = document.querySelector(".notification");

    if (!notification) return;

    // Create notification badge
    const badge = document.createElement("span");
    badge.className = "notification-badge";
    badge.textContent = "3";

    notification.style.position = "relative";
    notification.appendChild(badge);


    // Create notification panel
    const panel = document.createElement("div");
    panel.className = "notification-panel";

    panel.innerHTML = `
        <div class="notification-header">
            <strong>🔔 Alert Center</strong>
            <button id="markRead">Mark all read</button>
        </div>

        <div class="notification-list">

            <div class="notification-item critical">
                <div class="notification-icon">🔴</div>
                <div>
                    <strong>Critical Anomaly</strong>
                    <p>Component PWR-1042 requires attention.</p>
                    <small>2 minutes ago</small>
                </div>
            </div>

            <div class="notification-item warning">
                <div class="notification-icon">🟠</div>
                <div>
                    <strong>Drift Warning</strong>
                    <p>Component PWR-1038 shows predicted drift.</p>
                    <small>15 minutes ago</small>
                </div>
            </div>

            <div class="notification-item success">
                <div class="notification-icon">🟢</div>
                <div>
                    <strong>Screening Completed</strong>
                    <p>128 components screened successfully.</p>
                    <small>1 hour ago</small>
                </div>
            </div>

        </div>
    `;

    document.body.appendChild(panel);


    // Open / close notification panel
    notification.addEventListener("click", (event) => {

        event.stopPropagation();

        panel.classList.toggle("show");

    });


    // Prevent panel click from closing itself
    panel.addEventListener("click", (event) => {
        event.stopPropagation();
    });


    // Mark all notifications as read
    document.getElementById("markRead").addEventListener("click", () => {

        badge.style.display = "none";

    });


    // Close when clicking outside
    document.addEventListener("click", () => {

        panel.classList.remove("show");

    });

});