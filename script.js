async function searchPlaces() {
    const city = document.getElementById("locationInput").value.trim();
    const placesContainer = document.getElementById("placesContainer");
    const loading = document.getElementById("loading");

    placesContainer.innerHTML = "";

    if (!city) {
        loading.innerText = "Please enter a city or place.";
        return;
    }

    loading.innerText = "Fetching places from Wikipedia...";

    try {
        const response = await fetch(
            `/api/places?city=${encodeURIComponent(city)}`
        );

        if (!response.ok) {
            throw new Error("Backend error");
        }

        const data = await response.json();
        loading.innerText = "";

        if (!Array.isArray(data) || data.length === 0) {
            placesContainer.innerHTML = "<p>No places found.</p>";
            return;
        }

        data.forEach((place) => {
            const card = document.createElement("div");
            card.classList.add("place-card");

            card.innerHTML = `
                <img src="${place.img || 'https://via.placeholder.com/400x250?text=No+Image'}" alt="${place.name}">
                <h3>${place.name}</h3>
                <p>${place.shortDesc || "No description available."}</p>
                <button onclick="viewDetails('${place.id}')">View Details</button>
            `;

            placesContainer.appendChild(card);
        });

    } catch (error) {
        console.error(error);
        loading.innerText = "Cannot connect to backend.";
    }
}

function quickSearch(city) {
    document.getElementById("locationInput").value = city;
    searchPlaces();
}

async function viewDetails(id) {
    const container = document.getElementById("placesContainer");
    const loading = document.getElementById("loading");

    loading.innerText = "Fetching details from Wikipedia...";

    try {
        const response = await fetch(
            `/api/place/${encodeURIComponent(id)}`
        );

        if (!response.ok) {
            throw new Error("Failed");
        }

        const place = await response.json();
        loading.innerText = "";

        container.innerHTML = `
            <div class="detail-view" style="padding:20px;text-align:center;">
                <button onclick="searchPlaces()">← Back</button>

                <img src="${place.img || 'https://via.placeholder.com/500x300?text=No+Image'}"
                     style="width:100%;max-width:500px;margin:20px 0;">

                <h2>${place.name}</h2>
                <p><strong>About:</strong> ${place.fullDesc || "No details available."}</p>
                <p><strong>Description:</strong> ${place.shortDesc || "Not available"}</p>
                <p><strong>Timings:</strong> ${place.timings || "Not available"}</p>
                <p><strong>Rating:</strong> ${place.rating || "Not available"}</p>
                <p><strong>Phone:</strong> ${place.phone || "Not available"}</p>
                <p><strong>Website:</strong> ${
                    place.website && place.website !== "Not available"
                        ? `<a href="${place.website}" target="_blank">Open article</a>`
                        : "Not available"
                }</p>
            </div>
        `;

    } catch (error) {
        console.error(error);
        container.innerHTML = "<p>Could not fetch details.</p>";
    }
}