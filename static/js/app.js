document.addEventListener('DOMContentLoaded', () => {
  const input = document.querySelector('#id_files');
  const preview = document.querySelector('#file-preview');
  if (input && preview) {
    input.addEventListener('change', () => {
      preview.innerHTML = '';
      Array.from(input.files).forEach(file => {
        const item = document.createElement('div');
        item.className = 'preview-file';
        item.innerHTML = `<span class="file-icon"><i data-lucide="file"></i></span><span>${file.name}</span><small>${(file.size / 1024 / 1024).toFixed(2)} MB</small>`;
        preview.appendChild(item);
      });
      if (window.lucide) lucide.createIcons();
    });
  }

  document.querySelectorAll('.sheet-tab').forEach(tab => tab.addEventListener('click', () => {
    document.querySelectorAll('.sheet-tab').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.sheet-page').forEach(item => item.classList.add('hidden'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.page)?.classList.remove('hidden');
  }));

  const editorForm = document.querySelector('#editor-form');
  if (editorForm && window.initialPayload) {
    editorForm.addEventListener('submit', () => {
      const payload = structuredClone(window.initialPayload);
      document.querySelectorAll('.editor-table').forEach(table => {
        const page = Number(table.dataset.pageIndex);
        const tableIndex = Number(table.dataset.tableIndex);
        table.querySelectorAll('[data-kind="header"]').forEach(cell => { payload.pages[page].tables[tableIndex].headers[Number(cell.dataset.colIndex)].value = cell.innerText.trim() || null; });
        table.querySelectorAll('[data-kind="cell"]').forEach(cell => {
          const value = cell.innerText.trim() || null;
          payload.pages[page].tables[tableIndex].rows[Number(cell.dataset.rowIndex)][Number(cell.dataset.colIndex)].value = value;
          if (cell.dataset.fieldId && Array.isArray(payload.template_fields)) {
            const field = payload.template_fields.find(item => item.field_id === cell.dataset.fieldId);
            if (field) field.value = value;
          }
        });
      });
      document.querySelector('#payload').value = JSON.stringify(payload);
      const indicator = document.querySelector('#save-indicator');
      if (indicator) indicator.innerHTML = '<i data-lucide="loader-circle"></i> Salvando';
    });
  }
});
