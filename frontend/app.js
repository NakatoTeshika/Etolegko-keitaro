"use strict";

const byId = (id) => document.getElementById(id);
const state = { campaignId: null, campaignName: "", streams: [], streamId: null, offers: [], busy: false };
const colors = ["#5418c4", "#7740dc", "#9763ef", "#b486ef", "#7037ad"];

function element(tag, className, value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = value;
  return node;
}

function button(label, action, className) {
  const node = element("button", className, label);
  node.type = "button";
  node.addEventListener("click", action);
  return node;
}

function notify(message, kind = "success") {
  byId("status").textContent = kind === "error" ? "" : message;
  byId("status").className = kind === "info" ? "notice info" : "notice";
  byId("error").textContent = kind === "error" ? message : "";

}

async function request(path, method = "GET", body) {
  const options = { method };
  if (body !== undefined) {
    options.headers = { "Content-Type": "application/json" };
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, options);
  } catch (_) {
    throw new Error("Не удалось связаться с сервером. Проверь, запущен ли FastAPI.");
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && data.detail;
    const fields = {name: "Название", geo: "Код страны", offer_id: "Оффер"};
    const validation = Array.isArray(detail) && detail.map((item) => {
      const field = (item.loc || []).slice(-1)[0];
      return (fields[field] || field || "Поле") + " — " + item.msg;
    }).join(". ");
    throw new Error(typeof detail === "string" ? detail : validation || "Ошибка сервера (HTTP " + response.status + ").");
  }
  if (data === null) throw new Error("Сервер вернул ответ без JSON.");
  return data;
}

async function run(pending, operation, success, report = notify) {
  if (state.busy) return;
  state.busy = true;
  const groups = document.querySelectorAll("fieldset");
  for (const group of groups) group.disabled = true;
  byId("refresh-offers").disabled = true;
  byId("create-submit").disabled = true;
  byId("close-create").disabled = true;
  report(pending, "info");
  try {
    await operation();
    report(typeof success === "function" ? success() : success);
  } catch (error) {
    report(error.message, "error");
  } finally {
    state.busy = false;
    for (const group of document.querySelectorAll("fieldset")) group.disabled = false;
    byId("refresh-offers").disabled = false;
    byId("create-submit").disabled = false;
    byId("close-create").disabled = false;
  }
}

function matchingOffers(query, excluded) {
  const term = query.trim().toLowerCase();
  return state.offers.filter((offer) =>
    (!excluded || !excluded.has(offer.id)) &&
    (offer.name.toLowerCase().includes(term) || String(offer.id).includes(term))
  );
}

function offerPicker(excluded) {
  const root = element("div", "offer-picker");
  const search = element("input");
  search.type = "search";
  search.placeholder = "Название или ID оффера";
  search.setAttribute("aria-label", "Поиск оффера");
  const select = element("select");
  select.setAttribute("aria-label", "Оффер из результатов поиска");
  function update() {
    const previous = select.value;
    const matches = matchingOffers(search.value, excluded);
    select.textContent = "";
    select.add(new Option(matches.length ? "Выбери оффер" : "Офферы не найдены", ""));
    for (const offer of matches) select.add(new Option(offer.name + " · #" + offer.id, offer.id));
    if (matches.some((offer) => String(offer.id) === previous)) select.value = previous;
  }
  search.addEventListener("input", update);
  root.append(search, select);
  update();
  return { root, select, update };
}

const createDialog = byId("create-dialog");

byId("open-create").addEventListener("click", () => createDialog.showModal());
byId("close-create").addEventListener("click", () => createDialog.close());
createDialog.addEventListener("cancel", (event) => {
  if (state.busy) event.preventDefault();
});

const createQuery = byId("create-offer-query");
const createResults = byId("create-offer-results");
let selectedOffer = null;

function reportCreate(message, kind = "success") {
  const status = byId("create-status");
  status.className = kind === "info" ? "notice info" : "notice";
  status.textContent = kind === "error" ? "" : message;
  if (kind === "success") {
    byId("create-form").reset();
    selectedOffer = null;
    createResults.hidden = true;
    createDialog.close();
    notify(message);
  }
  byId("create-error").textContent = kind === "error" ? message : "";
}

function renderCreateResults() {
  const matches = matchingOffers(createQuery.value);
  createResults.textContent = "";

  for (const offer of matches) {
    const choice = button(offer.name + " · #" + offer.id, () => {
      selectedOffer = offer;
      createQuery.value = offer.name + " · #" + offer.id;
      createQuery.removeAttribute("aria-invalid");
      createQuery.focus();
      createResults.hidden = true;
    });
    createResults.append(choice);
  }

  if (!matches.length) {
    createResults.append(element("p", "muted", "Офферы не найдены."));
  }

  createResults.hidden = false;
}

createResults.addEventListener("mousedown", (event) => {
  if (event.target.closest("button")) event.preventDefault();
});

createQuery.addEventListener("focus", () => {
  if (!selectedOffer) renderCreateResults();
});
createQuery.addEventListener("input", () => {
  selectedOffer = null;
  renderCreateResults();
});
byId("create-picker").addEventListener("focusout", (event) => {
  if (!event.currentTarget.contains(event.relatedTarget)) createResults.hidden = true;
});
byId("create-picker").addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (!createResults.hidden) {
      event.preventDefault();
      createQuery.focus();
      createResults.hidden = true;
    }
  }
  if (event.key === "ArrowDown" && event.target === createQuery) {
    event.preventDefault();
    if (createResults.hidden) renderCreateResults();
    const first = createResults.querySelector("button");
    if (first) first.focus();
  } else if ((event.key === "ArrowDown" || event.key === "ArrowUp") &&
      createResults.contains(event.target)) {
    event.preventDefault();
    const next = event.key === "ArrowDown"
      ? event.target.nextElementSibling
      : event.target.previousElementSibling || createQuery;
    if (next) next.focus();
  }
});

function replaceStreams(streams) {
  state.streams = streams;
  if (!streams.some((stream) => stream.id === state.streamId)) {
    const first = streams.find((stream) => stream.offers.length) || streams[0];
    state.streamId = first ? first.id : null;
  }
  renderEditor();
}

function renderEditor() {
  const editor = byId("editor");
  const previousList = editor.querySelector(".offer-list");
  const previousScroll = previousList &&
    previousList.dataset.streamId === String(state.streamId)
    ? previousList.scrollTop : 0;
  editor.textContent = "";
  byId("campaign-caption").textContent = state.campaignId
    ? (state.campaignName ? state.campaignName + " · " : "") + "#" + state.campaignId
    : "Выбери кампанию по ID";

  const stream = state.streams.find((item) => item.id === state.streamId);
  if (!stream) {
    editor.className = "panel empty";
    editor.textContent = state.campaignId ? "Нет загруженных потоков для этой кампании." : "Импортируй потоки кампании, чтобы начать редактирование.";
    return;
  }

  editor.className = "";
  const controls = element("fieldset");
  controls.disabled = state.busy;
  const columns = element("div", "columns");
  const panel = element("section", "panel");
  const tabs = element("div", "tabs");
  tabs.setAttribute("aria-label", "Потоки кампании");
  for (const item of state.streams) {
    const tab = button(item.name, () => {
      state.streamId = item.id;
      renderEditor();
      const current = byId("editor").querySelector('.tabs button[aria-pressed="true"]');
      if (current) current.focus();
    });
    tab.setAttribute("aria-pressed", String(item.id === stream.id));
    tabs.append(tab);
  }
  panel.append(tabs, element("h2", "", stream.name),
    element("p", "muted section-head", "Поток #" + stream.id));
  if (stream.offers.length) {
    const tableHead = element("div", "offer-row offer-table-head");
    tableHead.append(element("span", "", "Оффер"), element("span", "", "Доля трафика"),
      element("span", "", "Действия"));
    panel.append(tableHead);
  }
  const offerList = element("div", "offer-list");
  offerList.dataset.streamId = stream.id;
  for (const offer of stream.offers) offerList.append(renderOffer(stream, offer));
  panel.append(offerList);
  if (stream.offers.length) panel.append(renderAdd(stream));
  else panel.append(element("p", "empty", "В этом потоке нет привязанных офферов."));

  const side = element("div", "stack");
  const details = element("section", "panel");
  details.append(element("h2", "", "Состояние потока"),
    element("p", "", stream.has_draft ? "Есть неопубликованные изменения" : "Опубликовано"),
    element("p", "muted", "Активных офферов: " + stream.offers.filter((item) => !item.removed).length));
  side.append(renderAllocation(stream), details);
  columns.append(panel, side);
  controls.append(columns);
  const draft = element("div", stream.has_draft ? "draft" : "draft published");
  if (stream.has_draft) {
    const actions = element("div", "actions");
    actions.append(button("Отменить черновик", () => edit(stream, "/cancel", "POST", undefined, "Черновик отменён.")),
      button("Опубликовать в Keitaro", () => edit(stream, "/push", "POST", undefined, "Изменения опубликованы."), "primary"));
    draft.append(element("strong", "", "Неопубликованные изменения"), actions);
  } else {
    draft.append(element("strong", "", "Все изменения опубликованы"));
  }
  controls.append(draft);
  editor.append(controls);
  offerList.scrollTop = previousScroll;
}

function renderOffer(stream, offer) {
  const row = element("div", offer.removed ? "offer-row removed" : "offer-row");
  const title = element("div", "offer-name");
  title.append(element("strong", "", offer.name),
    element("div", "muted", "#" + offer.id + (offer.removed ? " · удалён" : offer.pinned ? " · закреплён" : "")));
  const share = element("div", "share");
  const meter = element("div", "meter");
  meter.setAttribute("aria-hidden", "true");
  const fill = element("span");
  fill.style.width = offer.share + "%";
  meter.append(fill);
  share.append(element("strong", "", offer.share + "%"), meter);

  const actions = element("div", "actions");
  const path = "/offers/" + offer.id;
  if (!offer.removed) {
    actions.append(button(offer.pinned ? "Открепить" : "Закрепить", () =>
      edit(stream, path + "/pin", "PATCH", {pinned: !offer.pinned}, offer.pinned ? "Доля откреплена." : "Доля закреплена.")));
  }
  actions.append(button(offer.removed ? "Восстановить" : "Удалить", () =>
    edit(stream, path, "PATCH", {active: offer.removed}, offer.removed ? "Оффер восстановлен." : "Оффер удалён из черновика.")));
  row.append(title, share, actions);
  return row;
}

function renderAdd(stream) {
  const form = element("form", "add-row");
  const picker = offerPicker(new Set(stream.offers.map((offer) => offer.id)));
  const add = element("button", "", "Добавить оффер");
  add.type = "submit";
  form.append(picker.root, add);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!picker.select.value) {
      notify("Выбери оффер для добавления.", "error");
      picker.select.focus();
      return;
    }
    edit(stream, "/offers/" + picker.select.value, "POST", undefined, "Оффер добавлен в черновик.");
  });
  return form;
}

function renderAllocation(stream) {
  const panel = element("section", "panel");
  const active = stream.offers.filter((offer) => !offer.removed);
  panel.append(element("h2", "", "Распределение трафика"));
  if (!active.length) {
    panel.append(element("p", "muted", "Нет активных офферов."));
    return panel;
  }
  const bar = element("div", "allocation");
  bar.setAttribute("aria-hidden", "true");
  const legend = element("ul", "legend");
  active.forEach((offer, index) => {
    const color = colors[index % colors.length];
    const segment = element("span");
    segment.style.width = offer.share + "%";
    segment.style.backgroundColor = color;
    if (offer.share >= 12) segment.textContent = offer.share + "%";
    bar.append(segment);
    const item = element("li");
    const dot = element("span", "dot");
    dot.style.backgroundColor = color;
    item.append(dot, element("span", "", offer.name + " — " + offer.share + "%"));
    legend.append(item);
  });
  panel.append(bar, legend);
  return panel;
}

function edit(stream, suffix, method, body, success) {
  const path = "/campaigns/" + state.campaignId + "/streams/" + stream.id + suffix;
  run("Сохраняем изменения…", async () => {
    replaceStreams(await request(path, method, body));
  }, success);
}

function renderCatalog() {
  const list = byId("catalog-list");
  list.textContent = "";
  const matches = matchingOffers(byId("catalog-query").value);
  if (!matches.length) list.append(element("p", "empty", "Офферы не найдены."));
  for (const offer of matches) list.append(element("div", "catalog-item", offer.name + " · #" + offer.id));
}

async function loadOffers() {
  state.offers = await request("/offers");
  if (!createResults.hidden) renderCreateResults();
  renderCatalog();
  if (state.streams.length) renderEditor();
}

function showSection(offers) {
  byId("workspace").hidden = offers;
  byId("catalog").hidden = !offers;
  byId("nav-streams").setAttribute("aria-pressed", String(!offers));
  byId("nav-offers").setAttribute("aria-pressed", String(offers));
}

byId("nav-streams").addEventListener("click", () => showSection(false));
byId("nav-offers").addEventListener("click", () => showSection(true));
byId("refresh-offers").addEventListener("click", () =>
  run("Загружаем каталог…", loadOffers, "Каталог обновлён."));
byId("catalog-query").addEventListener("input", renderCatalog);

byId("load-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (state.busy) return;
  const input = byId("campaign-id");
  const id = Number(input.value.trim());
  if (!/^\d+$/.test(input.value.trim()) || !Number.isSafeInteger(id) || id < 1) {
    notify("Введи положительный числовой ID кампании.", "error");
    input.focus();
    return;
  }
  const local = event.submitter && event.submitter.value === "local";
  const path = "/campaigns/" + id + (local ? "/streams" : "/fetch");
  run("Загружаем потоки…", async () => {
    const streams = await request(path, local ? "GET" : "POST");
    if (state.campaignId !== id) {
      state.campaignName = "";
      state.streamId = null;
    }
    state.campaignId = id;
    replaceStreams(streams);
  }, () => "Загружено потоков: " + state.streams.length + ".");
});

byId("create-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (state.busy) return;
  const fields = event.currentTarget.elements;
  const name = fields.namedItem("name");
  const geo = fields.namedItem("geo");
  const body = {name: name.value.trim(), geo: geo.value.trim().toUpperCase(), offer_id: selectedOffer ? Number(selectedOffer.id) : 0};
  for (const field of [name, geo, createQuery]) field.removeAttribute("aria-invalid");
  const validOffer = Number.isSafeInteger(body.offer_id) && body.offer_id > 0;
  if (!body.name || !/^[A-Z]{2}$/.test(body.geo) || !validOffer) {
    const invalid = !body.name ? name : !/^[A-Z]{2}$/.test(body.geo) ? geo : createQuery;
    invalid.setAttribute("aria-invalid", "true");
    reportCreate(invalid === name ? "Введи название кампании." : invalid === geo ? "Введи двухбуквенный код страны, например MX." : "Выбери оффер из результатов поиска.", "error");
    invalid.focus();
    return;
  }
  run("Создаём кампанию…", async () => {
    const campaign = await request("/campaigns", "POST", body);
    if (!campaign || !Number.isSafeInteger(campaign.id) || campaign.id < 1) {
      throw new Error("Сервер не вернул ID кампании. Проверь список кампаний в Keitaro перед повторной отправкой.");
    }
    byId("campaign-id").value = campaign.id;
    state.campaignId = campaign.id;
    state.campaignName = campaign.name;
    state.streamId = null;
    replaceStreams([]);
  }, () => "Кампания #" + state.campaignId + " создана. Теперь импортируй её потоки.", reportCreate);
});

byId("create-submit").disabled = false;
loadOffers().catch((error) => {
  notify(error.message, "error");
  reportCreate(error.message, "error");
});