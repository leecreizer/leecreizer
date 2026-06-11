// data-dialog 버튼 → <dialog> 폼을 data-* 값으로 채워 열기
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-dialog]");
  if (!btn) return;
  const dialog = document.getElementById(btn.dataset.dialog);
  if (!dialog) return;
  const form = dialog.querySelector("form");
  form.reset();

  const isEdit = Boolean(btn.dataset.id);
  const title = dialog.querySelector("h3");
  if (title) {
    title.textContent = isEdit
      ? (title.dataset.titleEdit || title.textContent)
      : (title.dataset.titleNew || title.textContent);
  }

  for (const [key, value] of Object.entries(btn.dataset)) {
    if (key === "dialog") continue;
    const fields = form.querySelectorAll(`[name="${key}"]`);
    if (!fields.length) continue;
    if (fields.length > 1 || (fields[0].type === "checkbox" && key.endsWith("_ids"))) {
      // 다중 체크박스 (예: channel_ids="1,2")
      const values = value.split(",").map((v) => v.trim());
      fields.forEach((f) => { f.checked = values.includes(f.value); });
    } else {
      const field = fields[0];
      if (field.type === "checkbox") {
        field.checked = value === "1" || value === "true";
      } else {
        field.value = value;
      }
    }
  }
  dialog.showModal();
});

// dialog 바깥(backdrop) 클릭 시 닫기
document.querySelectorAll("dialog").forEach((dialog) => {
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) dialog.close();
  });
});
