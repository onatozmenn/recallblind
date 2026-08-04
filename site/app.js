(() => {
  const data = window.RECLUME_DATA;
  const chart = document.querySelector("#bar-chart");
  const title = document.querySelector("#metric-title");
  const direction = document.querySelector("#metric-direction");
  const description = document.querySelector("#metric-description");
  const tabs = [...document.querySelectorAll(".metric-tab")];
  const tableBody = document.querySelector("#leaderboard-body");

  const format = (value) => `${value.toFixed(value % 1 === 0 ? 1 : 2)}%`;

  function renderMetric(key) {
    const metric = data.metrics[key];
    title.textContent = metric.title;
    direction.textContent = metric.direction;
    description.textContent = metric.description;
    chart.innerHTML = metric.models.map((model) => `
      <div class="chart-row">
        <span class="chart-label" title="${model.name}">${model.name}</span>
        <div class="chart-track" aria-hidden="true"><div class="chart-fill" style="--width:${model.value}%"></div></div>
        <strong class="chart-value">${format(model.value)}</strong>
      </div>
    `).join("");

    tabs.forEach((tab) => {
      const active = tab.dataset.metric === key;
      tab.classList.toggle("active", active);
      tab.setAttribute("aria-pressed", String(active));
    });
  }

  tableBody.innerHTML = data.leaderboard.map((row) => `
    <tr>
      <td>${row.model}<div class="model-note">${row.snapshot}</div></td>
      <td class="metric-cell">${format(row.usr)}</td>
      <td class="metric-cell">${format(row.bor)}</td>
      <td class="metric-cell">${format(row.repair)}</td>
      <td class="metric-cell">${format(row.ncs)}</td>
      <td><div class="model-note">${row.note}</div></td>
    </tr>
  `).join("");

  tabs.forEach((tab) => tab.addEventListener("click", () => renderMetric(tab.dataset.metric)));
  renderMetric("usr");
})();
