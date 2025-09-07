let map;
let markers = {};
const cityCenter = [20.2961, 85.8245]; // Bhubaneswar
const defaultZoom = 13;

function centerToCity() {
  map.setView(cityCenter, defaultZoom);
}

function initMap() {
  map = L.map('map').setView(cityCenter, defaultZoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '© OpenStreetMap'
  }).addTo(map);
  loadJunctions();
  setInterval(loadJunctions, 3000);
  setupSearch();
}

async function loadJunctions() {
  try {
    const res = await fetch('/api/junctions');
    const data = await res.json();
    updateStats(data);
    updateMarkers(data);
    populateList(data);
  } catch (e) {
    console.error("Failed to fetch junctions", e);
  }
}

function updateStats(data) {
  document.getElementById('totalJ').innerText = data.length;
  let totalV = 0;
  let congested = 0;
  data.forEach(j => {
    totalV += j.current_cars || 0;
    if ((j.current_cars || 0) > 40) congested++;
  });
  document.getElementById('totalV').innerText = totalV;
  document.getElementById('congCount').innerText = congested;
}

function updateMarkers(data) {
  const existingIds = new Set(Object.keys(markers).map(k => parseInt(k)));
  data.forEach(j => {
    if (!j.lat || !j.lng) return;
    const id = j.id;
    const latlng = [j.lat, j.lng];
    const popupHtml = `
      <div class="marker-popup">
        <b>${j.name}</b><br>
        Cars: ${j.current_cars}<br>
        Signal: <span class="${j.signal === 'GREEN' ? 'badge-green' : 'badge-red'}">${j.signal}</span><br><br>
        <button onclick="setSignal(${id}, 'GREEN')" class="btn btn-sm btn-success">Set GREEN</button>
        <button onclick="setSignal(${id}, 'RED')" class="btn btn-sm btn-danger">Set RED</button>
      </div>
    `;
    if (markers[id]) {
      markers[id].setLatLng(latlng);
      markers[id].setPopupContent(popupHtml);
    } else {
      const m = L.marker(latlng).addTo(map);
      m.bindPopup(popupHtml);
      markers[id] = m;
    }
    existingIds.delete(id);
  });
  // remove markers not present
  existingIds.forEach(id => {
    map.removeLayer(markers[id]);
    delete markers[id];
  });
}

function populateList(data) {
  const ul = document.getElementById('junctionList');
  ul.innerHTML = '';
  data.forEach(j => {
    const li = document.createElement('li');
    li.className = 'list-group-item d-flex justify-content-between align-items-start';
    li.innerHTML = `<div><strong>${j.name}</strong><div class="small">Cars: ${j.current_cars} • ${j.signal}</div></div>`;
    li.onclick = () => {
      map.setView([j.lat, j.lng], 17);
      if (markers[j.id]) markers[j.id].openPopup();
    };
    ul.appendChild(li);
  });
}

async function setSignal(id, signal) {
  try {
    await fetch(`/api/junction/${id}/signal`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({signal: signal})
    });
    loadJunctions();
  } catch (e) {
    console.error("Failed to set signal", e);
  }
}

function setupSearch() {
  const input = document.getElementById('searchJ');
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    const items = document.querySelectorAll('#junctionList li');
    items.forEach(li => {
      const text = li.innerText.toLowerCase();
      li.style.display = text.includes(q) ? '' : 'none';
    });
  });
}

async function simulateAmbulance() {
  // pick a random junction near center to simulate ambulance location
  const keys = Object.keys(markers);
  if (keys.length === 0) return alert("No junctions loaded yet.");
  const randId = keys[Math.floor(Math.random() * keys.length)];
  const marker = markers[randId];
  const latlng = marker.getLatLng();
  try {
    await fetch('/api/emergency', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({type: 'ambulance', lat: latlng.lat, lng: latlng.lng, duration: 18})
    });
    alert("Ambulance simulated. Nearby signals preempted to GREEN for demo.");
    loadJunctions();
  } catch (e) {
    console.error("Failed to simulate ambulance", e);
  }
}

// Initialize map when script loads
window.addEventListener('DOMContentLoaded', initMap);
