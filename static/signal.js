let lineChart, pieChart, refreshTimer;
const apiBase = '/api';

async function fetchSignalInfo() {
  const res = await fetch(`${apiBase}/junctions`);
  const data = await res.json();
  return data.find(d => d.id === JID);
}

async function fetchTrafficLog(limit=50) {
  const res = await fetch(`${apiBase}/traffic_log?junction_id=${JID}&limit=${limit}`);
  const data = await res.json();
  return data;
}

function renderLineChart(labels, values) {
  const ctx = document.getElementById('lineChart').getContext('2d');
  if(lineChart) { lineChart.data.labels = labels; lineChart.data.datasets[0].data = values; lineChart.update(); return; }
  lineChart = new Chart(ctx, {
    type:'line',
    data:{ labels: labels, datasets:[{ label:'Vehicles', data: values, fill:false, borderColor:'rgb(75,192,192)' }]},
    options:{ responsive:true, scales:{ y:{ beginAtZero:true } } }
  });
}

function renderPieChart(counts) {
  const ctx = document.getElementById('pieChart').getContext('2d');
  const labels = ['Cars','Bikes','Buses+Trucks'];
  if(pieChart) { pieChart.data.datasets[0].data = counts; pieChart.update(); return; }
  pieChart = new Chart(ctx, {
    type:'pie',
    data:{ labels, datasets:[{ data: counts }]},
    options:{ responsive:true }
  });
}

async function refreshAll() {
  const info = await fetchSignalInfo();
  if(info) {
    document.getElementById('signalName').innerText = info.name + " (Signal ID: " + info.id + ")";
  }
  const logs = await fetchTrafficLog(50);
  // logs are newest first; reverse for chronological
  const recent = logs.slice().reverse();
  const labels = recent.map(r => new Date(r.timestamp).toLocaleTimeString());
  const values = recent.map(r => r.cars);
  renderLineChart(labels, values);

  // simulate vehicle type distribution from latest counts
  const latest = recent[recent.length-1] || {cars:0};
  const total = latest.cars || 0;
  const cars = Math.round(total * 0.7);
  const bikes = Math.round(total * 0.25);
  const buses = Math.max(0, total - cars - bikes);
  renderPieChart([cars, bikes, buses]);
}

function setAutoRefresh() {
  clearInterval(refreshTimer);
  const val = parseInt(document.getElementById('refreshInterval').value) * 1000;
  refreshTimer = setInterval(refreshAll, val);
}

document.addEventListener('DOMContentLoaded', async ()=>{
  await refreshAll();
  document.getElementById('refreshInterval').addEventListener('change', ()=>{ setAutoRefresh(); });
  document.getElementById('exportCsv').addEventListener('click', ()=>{ window.location = `/api/junction/${JID}/export`; });
  document.getElementById('manualGreen').addEventListener('click', ()=>{ setSignal('GREEN'); });
  document.getElementById('manualRed').addEventListener('click', ()=>{ setSignal('RED'); });
  setAutoRefresh();
});

async function setSignal(sig) {
  await fetch(`/api/junction/${JID}/signal`, {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({signal: sig})
  });
  // refresh after manual set
  await refreshAll();
}
