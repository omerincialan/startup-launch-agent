const views = ['startView', 'loadingView', 'decisionView', 'resultsView'];
const appState = { projectId: '', state: null };
let loadingTimer;

function showView(id) {
  views.forEach(view => document.getElementById(view).classList.toggle('hidden', view !== id));
  document.getElementById('errorBox').classList.add('hidden');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showError(message) {
  const box = document.getElementById('errorBox');
  box.textContent = message;
  box.classList.remove('hidden');
}

function setStatus(text, busy = false) {
  document.querySelector('#statusPill span').textContent = text;
  document.querySelector('#statusPill i').style.background = busy ? '#c9f45b' : '#176b48';
}

function updatePhases(current) {
  const order = ['research', 'discovery', 'hypothesis_selection', 'positioning_generation', 'positioning_evaluation', 'validation_planning', 'roadmap_planning', 'validation_ready'];
  const index = Math.max(0, order.indexOf(current));
  document.querySelectorAll('.phases li').forEach((item, i) => {
    item.classList.toggle('active', i === index);
    item.classList.toggle('done', i < index);
  });
}

async function request(url, options = {}) {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
  return data;
}

function escapeHtml(value) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}

function renderMarkdown(value = '') {
  const lines = escapeHtml(value).split('\n');
  const output = [];
  let inList = false;
  const inline = text => text
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>');

  for (const line of lines) {
    const bullet = line.match(/^\s*[-*]\s+(.+)/);
    if (bullet) {
      if (!inList) { output.push('<ul>'); inList = true; }
      output.push(`<li>${inline(bullet[1])}</li>`);
      continue;
    }
    if (inList) { output.push('</ul>'); inList = false; }
    if (/^###\s+/.test(line)) output.push(`<h3>${inline(line.replace(/^###\s+/, ''))}</h3>`);
    else if (/^##\s+/.test(line)) output.push(`<h2>${inline(line.replace(/^##\s+/, ''))}</h2>`);
    else if (/^#\s+/.test(line)) output.push(`<h1>${inline(line.replace(/^#\s+/, ''))}</h1>`);
    else if (/^---+$/.test(line.trim())) output.push('<hr>');
    else if (line.trim()) output.push(`<p>${inline(line)}</p>`);
  }
  if (inList) output.push('</ul>');
  return output.join('');
}

function beginLoading(resuming = false) {
  showView('loadingView');
  const titles = resuming
    ? ['Building your validation strategy…', 'Defining success and rejection signals…', 'Prioritizing your first 30 days…']
    : ['Understanding your target users…', 'Finding expensive, repeated problems…', 'Creating three directions to compare…'];
  let index = 0;
  document.getElementById('loadingTitle').textContent = titles[0];
  clearInterval(loadingTimer);
  loadingTimer = setInterval(() => {
    index = (index + 1) % titles.length;
    document.getElementById('loadingTitle').textContent = titles[index];
    document.querySelectorAll('.loading-steps span').forEach((item, i) => item.classList.toggle('on', i === index));
  }, 5000);
}

function consume(data) {
  appState.state = data.state;
  updatePhases(data.state.current_phase);
  clearInterval(loadingTimer);
  if (data.decision) {
    document.getElementById('hypotheses').innerHTML = renderMarkdown(data.decision.hypotheses);
    showView('decisionView');
    setStatus('Your decision');
  } else if (data.state.status === 'completed') {
    document.getElementById('artifact').textContent = `Saved locally: ${data.artifact || 'artifacts/'}`;
    showResult('roadmap');
    showView('resultsView');
    setStatus('Roadmap ready');
  }
}

document.getElementById('projectId').value = `startup-${new Date().toISOString().slice(0, 19).replaceAll(':', '').replace('T', '-')}`;
const ideaInput = document.getElementById('idea');
ideaInput.addEventListener('input', () => {
  document.getElementById('ideaCount').textContent = `${ideaInput.value.length} / 600`;
});
document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => {
  ideaInput.value = button.dataset.example;
  ideaInput.dispatchEvent(new Event('input'));
  ideaInput.focus();
}));

document.getElementById('startForm').addEventListener('submit', async event => {
  event.preventDefault();
  appState.projectId = document.getElementById('projectId').value.trim();
  beginLoading(false);
  setStatus('Agent working', true);
  updatePhases('research');
  try {
    const data = await request('/api/projects', {
      method: 'POST',
      body: JSON.stringify({ idea: ideaInput.value.trim(), project_id: appState.projectId })
    });
    consume(data);
  } catch (error) {
    clearInterval(loadingTimer);
    showView('startView');
    setStatus('Needs attention');
    showError(error.message);
  }
});

document.querySelectorAll('.choice').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('.choice').forEach(item => item.classList.remove('selected'));
  button.classList.add('selected');
  document.getElementById('choice').value = button.dataset.choice;
}));

document.getElementById('decisionForm').addEventListener('submit', async event => {
  event.preventDefault();
  beginLoading(true);
  setStatus('Agent working', true);
  updatePhases('validation_planning');
  try {
    const data = await request(`/api/projects/${appState.projectId}/resume`, {
      method: 'POST', body: JSON.stringify({ choice: document.getElementById('choice').value })
    });
    consume(data);
  } catch (error) {
    clearInterval(loadingTimer);
    showView('decisionView');
    setStatus('Needs attention');
    showError(error.message);
  }
});

function showResult(tab) {
  const positioningHistory = (appState.state.positioning_attempts || []).map(attempt => {
    const evaluation = attempt.evaluation;
    const position = attempt.positioning;
    const dimensions = Object.entries(evaluation.dimensions || {})
      .map(([name, score]) => `- **${name.replaceAll('_', ' ')}:** ${score}/10`)
      .join('\n');
    return `## Iteration ${attempt.iteration} — ${evaluation.score}/10${evaluation.passed ? ' ✓ PASS' : ''}\n\n` +
      `### ${position.headline}\n\n${position.statement}\n\n` +
      `${dimensions}\n\n**Evaluator feedback:**\n${(evaluation.feedback || []).map(item => `- ${item}`).join('\n')}`;
  }).join('\n\n---\n\n');
  const content = {
    roadmap: appState.state.thirty_day_roadmap,
    positioning: positioningHistory || 'No positioning iterations were saved.',
    validation: appState.state.validation_plan,
    research: `${appState.state.research_plan}\n\n${appState.state.research_findings}`
  };
  document.getElementById('resultDocument').innerHTML = renderMarkdown(content[tab]);
  document.querySelectorAll('.tab').forEach(item => item.classList.toggle('active', item.dataset.tab === tab));
}

document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => showResult(button.dataset.tab)));
document.getElementById('newProject').addEventListener('click', () => location.reload());
document.getElementById('showResume').addEventListener('click', () => document.getElementById('resumeForm').classList.toggle('hidden'));
document.getElementById('resumeForm').addEventListener('submit', async event => {
  event.preventDefault();
  appState.projectId = document.getElementById('resumeId').value.trim();
  beginLoading(false);
  setStatus('Loading project', true);
  try {
    const data = await request(`/api/projects/${appState.projectId}`);
    consume(data);
  } catch (error) {
    clearInterval(loadingTimer);
    showView('startView');
    setStatus('Needs attention');
    showError(error.message);
  }
});
