(() => {
    const escapeHtml = (value) => String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');

    const tableMarkup = (headers, rows, emptyText = 'Sem dados para este período.') => {
        if (!rows.length) return `<p class="report-empty">${escapeHtml(emptyText)}</p>`;
        return `<div class="report-table-wrap"><table><thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    };

    const getFilters = () => Array.from(document.querySelectorAll('.master-filter-field')).map((field) => {
        const label = field.querySelector('.master-filter-label')?.textContent.trim() || 'Filtro';
        const select = field.querySelector('select');
        const value = select?.selectedOptions[0]?.textContent.trim() || 'Todos';
        return { label, value };
    });

    const getMetrics = () => Array.from(document.querySelectorAll('.metric-card')).map((card) => ({
        value: card.querySelector('h3')?.textContent.trim() || '—',
        label: card.querySelector('.text-muted')?.textContent.trim() || 'Indicador'
    }));

    const getChartData = (canvasId, title) => {
        const canvas = document.getElementById(canvasId);
        const chart = canvas && window.Chart?.getChart ? window.Chart.getChart(canvas) : null;
        if (!chart) return { title, headers: [], rows: [] };
        const labels = chart.data.labels || [];
        const datasets = chart.data.datasets || [];
        return {
            title,
            headers: ['Referência', ...datasets.map((dataset) => dataset.label || 'Valor')],
            rows: labels.map((label, index) => [label, ...datasets.map((dataset) => dataset.data[index] ?? '—')])
        };
    };

    const getHeatmapData = () => Array.from(document.querySelectorAll('.master-heat-day')).map((day) => {
        const description = day.getAttribute('title') || day.textContent.trim();
        const parts = description.split(' - ');
        return [parts[0] || description, parts.slice(1).join(' - ') || '0 acessos'];
    });

    const getStudentData = () => {
        const table = document.getElementById('studentsReportTable');
        if (!table) return { headers: [], rows: [] };
        const headers = Array.from(table.querySelectorAll('thead th')).map((cell) => cell.textContent.trim());
        const rows = Array.from(table.querySelectorAll('tbody tr')).map((row) => Array.from(row.querySelectorAll('td')).map((cell) => cell.textContent.replace(/\s+/g, ' ').trim()));
        return { headers, rows };
    };

    const buildReport = (button) => {
        const filters = getFilters();
        const metrics = getMetrics();
        const charts = [
            getChartData('bnccChart', 'Domínio de habilidades BNCC'),
            getChartData('engagementChart', 'Evolução do engajamento'),
            getChartData('sevenDaysChart', 'Tempo médio diário — últimos 7 dias')
        ];
        const heatmap = getHeatmapData();
        const students = getStudentData();
        const generatedAt = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'long', timeStyle: 'short' }).format(new Date());
        const logoUrl = new URL(button.dataset.logo, window.location.href).href;
        const reportWindow = window.open('', '_blank');

        if (!reportWindow) {
            window.alert('O navegador bloqueou a janela do relatório. Permita pop-ups para o MundoKaizo e tente novamente.');
            return;
        }

        const chartSections = charts.map((chart) => `<section class="report-section"><h2>${escapeHtml(chart.title)}</h2>${tableMarkup(chart.headers, chart.rows)}</section>`).join('');
        const filterCards = filters.map((filter) => `<div><span>${escapeHtml(filter.label)}</span><strong>${escapeHtml(filter.value)}</strong></div>`).join('');
        const metricCards = metrics.map((metric) => `<div><strong>${escapeHtml(metric.value)}</strong><span>${escapeHtml(metric.label)}</span></div>`).join('');

        reportWindow.document.open();
        reportWindow.document.write(`<!DOCTYPE html><html lang="pt-br"><head><meta charset="UTF-8"><title>Relatório Gerencial - MundoKaizo</title><style>
            @page { size:A4; margin:14mm; }
            * { box-sizing:border-box; }
            body { margin:0; color:#0a2b49; font-family:Arial,'Segoe UI',sans-serif; font-size:10px; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
            .report-toolbar { position:sticky; top:0; z-index:5; padding:10px; display:flex; justify-content:flex-end; background:#eef5f8; }
            .report-toolbar button { padding:10px 16px; border:0; border-radius:9px; background:#278fc4; color:#fff; font-weight:700; cursor:pointer; }
            .report-page { max-width:900px; margin:0 auto; }
            .report-header { padding-bottom:15px; display:flex; align-items:center; justify-content:space-between; gap:20px; border-bottom:2px solid #278fc4; }
            .report-brand { display:flex; align-items:center; gap:12px; }
            .report-brand img { width:58px; height:58px; object-fit:contain; }
            .report-brand h1 { margin:0; font-size:21px; line-height:1; }
            .report-brand p,.report-meta { margin:5px 0 0; color:#637b8d; }
            .report-meta { text-align:right; line-height:1.5; }
            .report-filters { margin-top:15px; padding:11px; display:grid; grid-template-columns:repeat(3,1fr); gap:8px; border:1px solid #dce8ef; border-radius:12px; background:#f5f9fb; }
            .report-filters div { min-width:0; }
            .report-filters span,.report-metrics span { display:block; color:#6b8191; font-size:7px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; }
            .report-filters strong { display:block; margin-top:3px; overflow-wrap:anywhere; font-size:9px; }
            .report-metrics { margin-top:12px; display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }
            .report-metrics div { padding:12px; border:1px solid #dce8ef; border-radius:11px; background:#fff; }
            .report-metrics strong { display:block; margin-bottom:4px; color:#147dac; font-size:18px; }
            .report-section { margin-top:18px; break-inside:avoid; }
            .report-section.students { break-inside:auto; }
            .report-section h2 { margin:0 0 8px; padding-bottom:6px; border-bottom:1px solid #dce8ef; font-size:12px; }
            .report-table-wrap { overflow:hidden; border:1px solid #dce8ef; border-radius:9px; }
            table { width:100%; border-collapse:collapse; }
            th { padding:7px 8px; background:#edf6fa; color:#4e697b; font-size:7px; letter-spacing:.04em; text-align:left; text-transform:uppercase; }
            td { padding:7px 8px; border-top:1px solid #e7eef2; font-size:8px; vertical-align:top; }
            tbody tr:nth-child(even) { background:#fafcfd; }
            .report-empty { padding:16px; border:1px dashed #cedce5; border-radius:9px; color:#718696; text-align:center; }
            .report-footer { margin-top:20px; padding-top:9px; display:flex; justify-content:space-between; border-top:1px solid #dce8ef; color:#718696; font-size:7px; }
            @media print { .report-toolbar { display:none; } .report-page { max-width:none; } thead { display:table-header-group; } tr { break-inside:avoid; } }
        </style></head><body><div class="report-toolbar"><button type="button" onclick="window.print()">Salvar como PDF</button></div><main class="report-page">
            <header class="report-header"><div class="report-brand"><img src="${escapeHtml(logoUrl)}" alt="MundoKaizo"><div><h1>Relatório Gerencial</h1><p>Cidades, escolas, turmas e resultados</p></div></div><div class="report-meta"><strong>MundoKaizo</strong><br>Gerado em ${escapeHtml(generatedAt)}</div></header>
            <section class="report-filters">${filterCards}</section>
            <section class="report-metrics">${metricCards}</section>
            ${chartSections}
            <section class="report-section"><h2>Acessos da rede — últimos 30 dias</h2>${tableMarkup(['Data', 'Acessos'], heatmap)}</section>
            <section class="report-section students"><h2>Detalhamento de alunos — filtro atual</h2>${tableMarkup(students.headers, students.rows, 'Nenhum aluno encontrado para o filtro atual.')}</section>
            <footer class="report-footer"><span>MundoKaizo · Aprender é uma aventura</span><span>Relatório gerencial</span></footer>
        </main><script>window.addEventListener('load',()=>setTimeout(()=>window.print(),350));<\/script></body></html>`);
        reportWindow.document.close();
        reportWindow.opener = null;
    };

    const enhanceSelect = (select) => {
        const wrapper = document.createElement('div');
        wrapper.className = 'master-custom-select';
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);
        select.classList.add('master-native-select');

        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'master-select-trigger';
        trigger.setAttribute('aria-haspopup', 'listbox');
        trigger.setAttribute('aria-expanded', 'false');
        trigger.innerHTML = `<span></span><i class="fa-solid fa-chevron-down" aria-hidden="true"></i>`;

        const menu = document.createElement('div');
        menu.className = 'master-select-menu';
        menu.setAttribute('role', 'listbox');
        menu.tabIndex = -1;

        const options = Array.from(select.options);
        const sync = () => {
            trigger.querySelector('span').textContent = select.selectedOptions[0]?.textContent || '';
            menu.querySelectorAll('[role="option"]').forEach((option, index) => option.setAttribute('aria-selected', String(options[index].selected)));
        };
        const close = () => { wrapper.classList.remove('is-open'); trigger.setAttribute('aria-expanded', 'false'); };
        const open = () => { document.querySelectorAll('.master-custom-select.is-open').forEach((item) => item !== wrapper && item.classList.remove('is-open')); wrapper.classList.add('is-open'); trigger.setAttribute('aria-expanded', 'true'); };

        options.forEach((option, index) => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'master-select-option';
            item.setAttribute('role', 'option');
            item.textContent = option.textContent;
            item.addEventListener('click', () => {
                select.selectedIndex = index;
                sync();
                close();
                select.dispatchEvent(new Event('change', { bubbles: true }));
            });
            menu.appendChild(item);
        });

        trigger.addEventListener('click', () => wrapper.classList.contains('is-open') ? close() : open());
        trigger.addEventListener('keydown', (event) => {
            if (!['ArrowDown', 'ArrowUp', 'Home', 'End', 'Escape'].includes(event.key)) return;
            event.preventDefault();
            if (event.key === 'Escape') return close();
            open();
            const items = Array.from(menu.querySelectorAll('.master-select-option'));
            const selected = Math.max(0, select.selectedIndex);
            const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : event.key === 'ArrowUp' ? Math.max(0, selected - 1) : Math.min(items.length - 1, selected + 1);
            items[next]?.focus();
        });
        menu.addEventListener('keydown', (event) => { if (event.key === 'Escape') { close(); trigger.focus(); } });
        wrapper.append(trigger, menu);
        sync();
    };

    document.querySelectorAll('.master-filter-select').forEach(enhanceSelect);
    document.addEventListener('click', (event) => {
        if (!event.target.closest('.master-custom-select')) document.querySelectorAll('.master-custom-select.is-open').forEach((item) => item.classList.remove('is-open'));
    });
    document.getElementById('createPdfButton')?.addEventListener('click', (event) => buildReport(event.currentTarget));
})();