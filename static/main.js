let map;
let markers = {};
let roadLayers = {};
const cityCenter = [20.2871, 85.8260];
const defaultZoom = 13;

function initMap() {
  map = L.map('map').setView(cityCenter, defaultZoom);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom:19, attribution:'© OpenStreetMap' }).addTo(map);
  loadAll();
  setInterval(loadAll, 4000);

  document.getElementById('addEventBtn').addEventListener('click', applyEvent);
}

async function loadAll() {
  await Promise.all([loadJunctions(), loadRoads()]);
  populateRoadsSelect();
}

async function loadJunctions() {
  const res = await fetch('/api/junctions');
  const data = await res.json();
  updateStats(data);
  updateMarkers(data);
  populateList(data);
}

function updateStats(data) {
  document.getElementById('totalJ').innerText = data.length;
  let totalV = 0, congested = 0;
  data.forEach(j => {
    totalV += j.current_cars || 0;
    if((j.current_cars || 0) > 40) congested++;
  });
  document.getElementById('totalV').innerText = totalV;
  document.getElementById('congCount').innerText = congested;
}

function getSignalIcon(state) {
  let color = state === "GREEN" ? "green" : state === "RED" ? "red" : "orange";
  return L.divIcon({
    html: `<div style="
      width:18px; height:18px;
      border-radius:50%;
      background:${color};
      border:2px solid #000;
    "></div>`,
    iconSize: [18, 18],
    className: ""
  });
}

function updateMarkers(data) {
  const existing = new Set(Object.keys(markers).map(k => parseInt(k)));
  data.forEach(j => {
    if(!j.lat || !j.lng) return;
    const id = j.id;
    const latlng = [j.lat, j.lng];

    const popupHtml = `
      <div>
        <b>${j.name}</b><br>
        Cars: ${j.current_cars}<br>
        Signal: <span style="color:${j.signal}">${j.signal}</span><br><br>
        <a href="/signal/${id}" class="btn btn-sm btn-primary">Open Details</a>
      </div>`;

    if(markers[id]) {
      markers[id].setLatLng(latlng);
      markers[id].setPopupContent(popupHtml);
      markers[id].setIcon(getSignalIcon(j.signal));
    } else {
      const m = L.marker(latlng, { icon: getSignalIcon(j.signal) }).addTo(map);
      m.bindPopup(popupHtml);
      markers[id] = m;
    }
    existing.delete(id);
  });
  existing.forEach(id => {
    map.removeLayer(markers[id]);
    delete markers[id];
  });
}

async function loadRoads() {
  const res = await fetch('/api/roads');
  const roads = await res.json();
  const existing = new Set(Object.keys(roadLayers).map(k=>parseInt(k)));
  roads.forEach(r => {
    const coords = r.coords.map(c => [c[0], c[1]]);
    let color = '#28a745'; // green
    if(r.status !== 'OPEN') color = '#6c757d'; // closed/construction
    else if (r.congestion >= 70) color = '#dc3545'; // red
    else if (r.congestion >= 40) color = 'gold';   // yellow

    if(roadLayers[r.id]) {
      roadLayers[r.id].setLatLngs(coords);
      roadLayers[r.id].setStyle({color: color, weight:4});
    } else {
      const p = L.polyline(coords, {color: color, weight:4}).addTo(map);
      p.bindTooltip(`${r.name} • ${r.status} • ${r.congestion}%`);
      roadLayers[r.id] = p;
      p.on('click', ()=> map.fitBounds(p.getBounds(), {padding:[40,40]}));
    }
    existing.delete(r.id);
  });
  existing.forEach(id => {
    map.removeLayer(roadLayers[id]);
    delete roadLayers[id];
  });
}

function populateList(data) {
  const ul = document.getElementById('junctionList');
  ul.innerHTML = '';
  data.forEach(j => {
    const li = document.createElement('li');
    li.className = 'list-group-item d-flex justify-content-between align-items-start';
    li.innerHTML = `
      <div>
        <strong>${j.name}</strong>
        <div class="small">Cars: ${j.current_cars} • ${j.signal}</div>
      </div>`;
    li.onclick = () => {
      map.setView([j.lat, j.lng], 17);
      if (markers[j.id]) markers[j.id].openPopup();
    };
    ul.appendChild(li);
  });
}

async function populateRoadsSelect() {
  const sel = document.getElementById('roadsSelect');
  if (!sel) return;
  const res = await fetch('/api/roads');
  const roads = await res.json();
  sel.innerHTML = '';
  roads.forEach(r => {
    const opt = document.createElement('option');
    opt.value = r.id;
    opt.text = `${r.name} (${r.status})`;
    sel.appendChild(opt);
  });
}

async function applyEvent() {
  const type = document.getElementById('eventType').value;
  const road_id = parseInt(document.getElementById('roadsSelect').value);
  const desc = document.getElementById('eventDesc').value || '';
  if(!road_id) return alert("Select a road");
  const res = await fetch('/api/event', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ road_id: road_id, type: type, description: desc })
  });
  const j = await res.json();
  if(j.error) return alert(j.error);
  alert("Event applied: " + JSON.stringify(j));
  loadAll();
}

function setupSearch(){
  const input = document.getElementById('searchJ');
  if(!input) return;
  input.addEventListener('input', ()=> {
    const q = input.value.toLowerCase();
    const items = document.querySelectorAll('#junctionList li');
    items.forEach(li=>{
      const text = li.innerText.toLowerCase();
      li.style.display = text.includes(q) ? '' : 'none';
    });
  });
}

window.addEventListener('DOMContentLoaded', ()=>{ initMap(); setupSearch(); });

