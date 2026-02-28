const content = document.getElementById("content");

/* LOGOUT */
function logout() {
    window.location.href = "../homepage/index.html";
}

/* ================= VOLUNTEERS ================= */
function loadVolunteers() {
    fetch("/api/db")
        .then(res => res.json())
        .then(data => {
            const volunteers = data.volunteers || [];

            let html = `
                <h2>Volunteer List</h2>
                <table>
                    <tr>
                        <th>Name</th>
                        <th>Phone</th>
                    </tr>
            `;

            volunteers.forEach(v => {
                html += `
                    <tr>
                        <td>${v.name}</td>
                        <td>${v.phone || "-"}</td>
                    </tr>
                `;
            });

            html += "</table>";
            content.innerHTML = html;
            content.style.display = "block";
        });
}

/* ================= TALUKS ================= */
function loadTaluks() {
    fetch("/api/taluk")
        .then(res => res.json())
        .then(data => {
            const taluks = data.taluks || [];

            let html = `
                <h2>Taluk List</h2>
                <table>
                    <tr>
                        <th>Taluk Name</th>
                        <th>Resources</th>
                    </tr>
            `;

            taluks.forEach(t => {
                html += `
                    <tr>
                        <td>${t.name}</td>
                        <td>
                            <span class="eye" onclick="viewResources('${t.name}')">👁</span>
                        </td>
                    </tr>
                `;
            });

            html += "</table>";
            content.innerHTML = html;
            content.style.display = "block";
        });
}

/* ================= RESOURCES ================= */
function viewResources(talukName) {
    fetch(`/api/resources?talukName=${talukName}`)
        .then(res => res.json())
        .then(data => {
            const r = data.resources || {};

            document.getElementById("resourceBody").innerHTML = `
                <p><b>Boats:</b> ${r.boats || 0}</p>
                <p><b>Rescue Vehicles:</b> ${r.rescue_vehicles || 0}</p>
                <p><b>Relief Camps:</b> ${r.relief_camps || 0}</p>
            `;

            document.getElementById("resourceModal").style.display = "flex";
        });
}

function closeModal() {
    document.getElementById("resourceModal").style.display = "none";
}
