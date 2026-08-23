// R3 轻量监控前端：四个页面、四张固定信息卡与受控证据详情投影。
// 只消费服务端 R3 受控投影；全部内容经 textContent 渲染，证据链接仅允许
// /api/v1/project-status/dashboard/r3/evidence/{type}/{id} 白名单。
(function () {
  'use strict';
  if (typeof window.dashboardElement !== 'function') return;

  const FACT_TYPE_LABELS = {
    completed: '已完成',
    in_progress: '进行中',
    next_action: '下一步',
    blocked: '阻断',
    candidate: '组合候选',
  };
  const FACT_STATUS_LABELS = {
    verified: '已核对',
    pending_check: '待核对',
    stale: '待复核',
  };
  const EVIDENCE_TYPE_LABELS = {
    document: '文档',
    test_run: '测试运行',
    case_design: '用例设计',
    defect: '缺陷',
    technical_review: '技术评审',
    handoff: '交接',
    stage: '阶段',
  };
  const EVIDENCE_STATUS_LABELS = {
    valid: '有效',
    stale: '待复核',
    missing: '暂不可查看',
  };
  const CANDIDATE_FIELD_LABELS = {
    backend_candidate: '服务端候选',
    frontend_candidate: '前端候选',
    migration_summary: '迁移说明',
    startup_handoff_ref: '启动交接编号',
  };
  const OWNER_WORKSPACE_ROUTES = {
    development: 'development',
    frontend: 'frontend',
    testing: 'testing',
  };

  const COPY_LOAD_FAILURE = '交付信息暂未加载，当前不展示任何通过或准出结论。请刷新重试。';
  const COPY_FIELD_MISSING = '当前信息待补齐';
  const COPY_DATE_MISSING = '核对日期待补录';
  const COPY_EVIDENCE_UNAVAILABLE = '证据暂不可查看';
  const COPY_NO_FACTS = '当前无此类事实';
  const COPY_PENDING_PLACEHOLDER = '待提供';
  const COPY_ALL_LINES = '全部交付线';
  const COPY_UNFILTERED = '未筛选交付线';
  const COPY_DETAIL_FAILURE = '证据详情暂未加载，请稍后重试。';

  const LINE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;
  const EVIDENCE_HREF_PATTERN =
    /^\/api\/v1\/project-status\/dashboard\/r3\/evidence\/(document|test_run|case_design|defect|technical_review|handoff|stage)\/[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;

  function el(tag, className, text) {
    return window.dashboardElement(tag, className, text);
  }

  function textOr(value, fallback) {
    return typeof value === 'string' && value.trim() ? value : fallback;
  }

  function r3LineFromUrl() {
    const line = new URLSearchParams(window.location.search).get('line');
    return line && LINE_ID_PATTERN.test(line) ? line : null;
  }

  function r3LineHref(href, line) {
    if (!line) return href;
    const url = new URL(href, window.location.origin);
    url.searchParams.set('line', line);
    return url.pathname + url.search + url.hash;
  }

  function r3EvidenceHref(type, id) {
    return `/api/v1/project-status/dashboard/r3/evidence/${encodeURIComponent(type)}/${encodeURIComponent(id)}`;
  }

  function r3EvidenceHrefAllowed(type, id) {
    return (
      typeof type === 'string' &&
      typeof id === 'string' &&
      EVIDENCE_HREF_PATTERN.test(r3EvidenceHref(type, id))
    );
  }

  function r3MetaRow(label, value) {
    const row = el('div', 'r3-meta-row');
    row.append(el('dt', '', label), el('dd', '', value));
    return row;
  }

  function r3StatusPill(value, kind) {
    return el('span', `r3-status-pill r3-status-${kind || 'neutral'}`, value);
  }

  function r3FactTypeBadge(factType) {
    return el(
      'span',
      `r3-fact-type r3-type-${factType}`,
      FACT_TYPE_LABELS[factType] || COPY_FIELD_MISSING,
    );
  }

  function r3EmptyState() {
    return el('p', 'r3-empty', COPY_NO_FACTS);
  }

  function r3WarningBlock(warnings) {
    const section = el('section', 'safe-workspace-alert r3-alert');
    section.setAttribute('role', 'alert');
    section.append(el('strong', '', '交付监控提示'));
    const list = el('ul');
    warnings.forEach((warning) => {
      list.append(el('li', '', textOr(warning && warning.safe_message, COPY_FIELD_MISSING)));
    });
    section.append(list);
    return section;
  }

  function r3LoadFailure(target) {
    const panel = el('div', 'r3-load-failure');
    const message = el('p', '', COPY_LOAD_FAILURE);
    message.setAttribute('role', 'alert');
    const refresh = el('button', 'safe-workspace-retry', '刷新重试');
    refresh.type = 'button';
    refresh.addEventListener('click', () => window.location.reload());
    const back = el('a', 'r3-action-link', '返回项目总览');
    back.href = r3LineHref('/project-status', r3LineFromUrl());
    panel.append(message, refresh, back);
    target.replaceChildren(panel);
    target.setAttribute('aria-busy', 'false');
  }

  function r3SyncNavLine(line) {
    document
      .querySelectorAll('.console-subnav a[href^="/project-status/workspaces"]')
      .forEach((link) => {
        link.href = r3LineHref(link.getAttribute('href') || link.href, line);
      });
    document.querySelectorAll('[data-r3-back-overview]').forEach((link) => {
      link.href = r3LineHref('/project-status', line);
    });
  }

  function r3BuildControls(view) {
    const currentLine = r3LineFromUrl();
    const controls = el('div', 'r3-controls');

    const selectorWrap = el('div', 'r3-line-selector');
    const label = el('label', '', '交付线');
    label.htmlFor = 'r3-line-select';
    const select = el('select');
    select.id = 'r3-line-select';
    const allOption = el('option', '', COPY_ALL_LINES);
    allOption.value = '';
    select.append(allOption);
    (Array.isArray(view.line_options) ? view.line_options : []).forEach((option) => {
      const node = el('option', '', textOr(option && option.label, COPY_FIELD_MISSING));
      node.value = option && option.id ? option.id : '';
      if (node.value) select.append(node);
    });
    const options = Array.from(select.options).map((option) => option.value);
    select.value = currentLine && options.includes(currentLine) ? currentLine : '';
    select.addEventListener('change', () => {
      const next = select.value;
      const url = new URL(window.location.href);
      if (next) url.searchParams.set('line', next);
      else url.searchParams.delete('line');
      window.history.pushState({}, '', url.pathname + url.search);
      window.scrollTo(0, 0);
      r3SyncNavLine(next || null);
      loadR3Workspace();
    });
    selectorWrap.append(label, select);

    const state = el('dl', 'r3-current-state');
    const conclusionItems = Array.isArray(view.cards && view.cards.conclusion && view.cards.conclusion.items)
      ? view.cards.conclusion.items
      : [];
    const selectedConclusion = currentLine
      ? conclusionItems.find((item) => item && item.delivery_line_id === currentLine) || null
      : null;
    state.append(
      r3MetaRow(
        '当前交付状态',
        selectedConclusion
          ? textOr(selectedConclusion.delivery_status_label, COPY_FIELD_MISSING)
          : COPY_ALL_LINES,
      ),
      r3MetaRow(
        '最近核对时间',
        selectedConclusion
          ? textOr(selectedConclusion.verified_at, COPY_DATE_MISSING)
          : COPY_UNFILTERED,
      ),
    );

    const back = el('a', 'r3-back-overview', '返回项目总览');
    back.href = r3LineHref('/project-status', currentLine);
    back.setAttribute('data-r3-back-overview', '');

    controls.append(selectorWrap, state, back);
    return controls;
  }

  function r3Card(title, cardKey) {
    const section = el('section', 'r3-card');
    section.setAttribute('aria-labelledby', `r3-card-${cardKey}-title`);
    section.setAttribute('data-r3-card', cardKey);
    section.append(el('h3', 'r3-card-title', title));
    const body = el('div', 'r3-card-body');
    section.append(body);
    return { section, body };
  }

  function r3LineDocumentEvidence(view, lineId) {
    const facts = []
      .concat(view.cards.progress.facts || [])
      .concat(view.cards.gates_and_blockers.facts || []);
    for (const fact of facts) {
      if (!fact || fact.delivery_line_id !== lineId) continue;
      const ref = (fact.evidence_refs || []).find((item) => item && item.type === 'document');
      if (ref) return ref;
    }
    return null;
  }

  function r3ConclusionItem(view, line) {
    const article = el('article', 'r3-conclusion-item');
    const heading = el('header', 'r3-item-heading');
    const title = el('div');
    title.append(el('h4', '', textOr(line.name, COPY_FIELD_MISSING)));
    title.append(el('p', 'r3-scope-summary', textOr(line.scope_summary, COPY_FIELD_MISSING)));
    heading.append(
      title,
      r3StatusPill(textOr(line.delivery_status_label, COPY_FIELD_MISSING), 'line'),
    );
    article.append(heading);

    article.append(el('p', 'r3-conclusion', textOr(line.current_conclusion, COPY_FIELD_MISSING)));
    article.append(
      r3MetaRow('当前候选', textOr(line.current_candidate_summary, COPY_FIELD_MISSING)),
    );
    article.append(
      r3MetaRow(
        '产品验收',
        line.can_enter_product_acceptance ? '允许进入产品验收' : '暂不允许进入产品验收',
      ),
    );
    article.append(
      r3MetaRow('受控试用', line.can_enter_controlled_trial ? '允许受控试用' : '暂不允许受控试用'),
    );
    article.append(r3MetaRow('下一道门禁', textOr(line.next_gate_summary, COPY_FIELD_MISSING)));
    article.append(r3MetaRow('最近核对时间', textOr(line.verified_at, COPY_DATE_MISSING)));

    const actions = el('div', 'r3-item-actions');
    const overviewLink = el('a', 'r3-action-link', '查看项目总览');
    overviewLink.href = r3LineHref('/project-status', line.delivery_line_id);
    actions.append(overviewLink);
    const documentRef = r3LineDocumentEvidence(view, line.delivery_line_id);
    if (documentRef) {
      const evidenceItems = view.cards && view.cards.checked_evidence
        ? view.cards.checked_evidence.items || []
        : [];
      const evidenceItem = evidenceItems.find(
        (item) => item && item.type === documentRef.type && item.id === documentRef.id,
      );
      const docButton = el('button', 'r3-action-link', '查看关联文档');
      docButton.type = 'button';
      if (
        evidenceItem &&
        evidenceItem.available === true &&
        r3EvidenceHrefAllowed(documentRef.type, documentRef.id)
      ) {
        docButton.dataset.r3EvidenceType = documentRef.type;
        docButton.dataset.r3EvidenceId = documentRef.id;
        docButton.addEventListener('click', () => {
          openR3EvidenceDetail(documentRef.type, documentRef.id, docButton, view);
        });
      } else {
        docButton.disabled = true;
        docButton.textContent = textOr(
          evidenceItem && evidenceItem.unavailable_reason,
          COPY_EVIDENCE_UNAVAILABLE,
        );
      }
      actions.append(docButton);
    }
    article.append(actions);
    return article;
  }

  function r3ConclusionCard(view) {
    const { section, body } = r3Card('当前交付结论', 'conclusion');
    const items = Array.isArray(view.cards && view.cards.conclusion && view.cards.conclusion.items)
      ? view.cards.conclusion.items
      : [];
    if (!items.length) body.append(r3EmptyState());
    items.forEach((line) => body.append(r3ConclusionItem(view, line)));
    return section;
  }

  function r3EvidenceActionButtons(fact, view) {
    const actions = el('div', 'r3-item-actions');
    const availableRef = (fact.evidence_refs || []).find(
      (ref) =>
        ref &&
        r3EvidenceHrefAllowed(ref.type, ref.id) &&
        view.cards.checked_evidence.items.some(
          (item) => item && item.type === ref.type && item.id === ref.id && item.available === true,
        ),
    );
    if (availableRef) {
      const evidenceButton = el('button', 'r3-action-link', '查看事项证据');
      evidenceButton.type = 'button';
      evidenceButton.dataset.r3EvidenceType = availableRef.type;
      evidenceButton.dataset.r3EvidenceId = availableRef.id;
      evidenceButton.addEventListener('click', () => {
        openR3EvidenceDetail(availableRef.type, availableRef.id, evidenceButton, view);
      });
      actions.append(evidenceButton);
    }
    const ownerRoute = OWNER_WORKSPACE_ROUTES[fact.owner_role];
    if (ownerRoute) {
      const workspaceLink = el('a', 'r3-action-link', '查看责任工作区');
      workspaceLink.href = r3LineHref(
        `/project-status/workspaces/${ownerRoute}`,
        r3LineFromUrl() || fact.delivery_line_id,
      );
      actions.append(workspaceLink);
    }
    return actions;
  }

  function r3FactRow(fact, view) {
    const row = el('li', 'r3-fact-row');
    const heading = el('header', 'r3-item-heading');
    heading.append(
      r3FactTypeBadge(fact.fact_type),
      r3StatusPill(
        FACT_STATUS_LABELS[fact.status] || COPY_FIELD_MISSING,
        fact.status === 'verified' ? 'verified' : fact.status,
      ),
    );
    row.append(heading);
    row.append(el('p', 'r3-fact-summary', textOr(fact.summary, COPY_FIELD_MISSING)));
    row.append(
      el(
        'small',
        'r3-fact-meta',
        `责任角色：${textOr(fact.owner_role_label, COPY_FIELD_MISSING)} · 最近核对：${textOr(fact.verified_at, COPY_DATE_MISSING)}`,
      ),
    );
    row.append(r3EvidenceActionButtons(fact, view));
    return row;
  }

  function r3ProgressCard(view) {
    const { section, body } = r3Card('进度与责任', 'progress');
    const facts = Array.isArray(view.cards && view.cards.progress && view.cards.progress.facts)
      ? view.cards.progress.facts
      : [];
    if (!facts.length) {
      body.append(r3EmptyState());
      return section;
    }
    const list = el('ul', 'r3-fact-list');
    facts.forEach((fact) => list.append(r3FactRow(fact, view)));
    body.append(list);
    return section;
  }

  function r3CandidateGroup(fact, view) {
    const group = el('article', 'r3-candidate-group');
    group.setAttribute('data-r3-candidate', fact.fact_id);
    const heading = el('header', 'r3-item-heading');
    heading.append(
      r3FactTypeBadge('candidate'),
      r3StatusPill(
        FACT_STATUS_LABELS[fact.status] || COPY_FIELD_MISSING,
        fact.status === 'verified' ? 'verified' : fact.status,
      ),
    );
    group.append(heading);

    const fields = el('dl', 'r3-candidate-fields');
    [
      ['backend_candidate', '服务端候选'],
      ['frontend_candidate', '前端候选'],
      ['migration_summary', '迁移说明'],
      ['startup_handoff_ref', '启动交接编号'],
    ].forEach(([key, label]) => {
      fields.append(r3MetaRow(label, textOr(fact[key], COPY_PENDING_PLACEHOLDER)));
    });
    const candidateStatus = textOr(fact.candidate_status_label, COPY_FIELD_MISSING);
    const statusRow = r3MetaRow('候选状态', candidateStatus);
    statusRow.classList.add('r3-candidate-status-row');
    fields.append(statusRow);
    group.append(fields);

    if (Array.isArray(fact.missing_fields) && fact.missing_fields.length) {
      group.append(
        el(
          'p',
          'r3-candidate-note',
          `待补齐：${fact.missing_fields
            .map((key) => CANDIDATE_FIELD_LABELS[key] || key)
            .join('、')}`,
        ),
      );
    }
    if (Array.isArray(fact.conflict_sources) && fact.conflict_sources.length) {
      group.append(
        el('p', 'r3-candidate-note r3-candidate-conflict', `冲突来源：${fact.conflict_sources.join('；')}`),
      );
    }
    group.append(el('p', 'r3-fact-summary', textOr(fact.summary, COPY_FIELD_MISSING)));
    group.append(r3EvidenceActionButtons(fact, view));
    return group;
  }

  function r3GatesCard(view) {
    const { section, body } = r3Card('门禁与阻断', 'gates');
    const facts = Array.isArray(
      view.cards && view.cards.gates_and_blockers && view.cards.gates_and_blockers.facts,
    )
      ? view.cards.gates_and_blockers.facts
      : [];
    if (!facts.length) {
      body.append(r3EmptyState());
      return section;
    }
    const list = el('ul', 'r3-fact-list');
    facts.forEach((fact) => {
      if (fact.fact_type === 'candidate') list.append(r3CandidateGroup(fact, view));
      else list.append(r3FactRow(fact, view));
    });
    body.append(list);
    return section;
  }

  function r3EvidenceItem(item, view) {
    const row = el('li', 'r3-evidence-item');
    const titleText = textOr(item.title, textOr(item.id, COPY_FIELD_MISSING));
    row.append(
      r3StatusPill(
        EVIDENCE_STATUS_LABELS[item.status] || COPY_FIELD_MISSING,
        item.status === 'valid' ? 'verified' : item.status,
      ),
    );
    if (item.available === true && r3EvidenceHrefAllowed(item.type, item.id)) {
      const link = el('button', 'r3-evidence-link', titleText);
      link.type = 'button';
      link.dataset.r3EvidenceType = item.type;
      link.dataset.r3EvidenceId = item.id;
      link.addEventListener('click', () => {
        openR3EvidenceDetail(item.type, item.id, link, view);
      });
      row.append(link);
    } else {
      row.append(el('strong', 'r3-evidence-title', titleText));
      const blocked = el('button', 'r3-evidence-link', textOr(item.unavailable_reason, COPY_EVIDENCE_UNAVAILABLE));
      blocked.type = 'button';
      blocked.disabled = true;
      row.append(blocked);
    }
    row.append(el('p', 'r3-evidence-summary', textOr(item.safe_summary, COPY_FIELD_MISSING)));
    row.append(
      el(
        'small',
        'r3-fact-meta',
        `类型：${EVIDENCE_TYPE_LABELS[item.type] || COPY_FIELD_MISSING} · 编号：${textOr(item.id, COPY_FIELD_MISSING)} · 责任角色：${textOr(item.owner_role_label, COPY_FIELD_MISSING)} · 核对：${textOr(item.verified_at, COPY_DATE_MISSING)}`,
      ),
    );
    return row;
  }

  function r3EvidenceCard(view) {
    const { section, body } = r3Card('已核对证据', 'evidence');
    const items = Array.isArray(
      view.cards && view.cards.checked_evidence && view.cards.checked_evidence.items,
    )
      ? view.cards.checked_evidence.items
      : [];
    if (!items.length) {
      body.append(r3EmptyState());
      return section;
    }
    const list = el('ul', 'r3-evidence-list');
    items.forEach((item) => list.append(r3EvidenceItem(item, view)));
    body.append(list);
    return section;
  }

  function r3RenderWorkspace(view) {
    const target = document.querySelector('[data-r3-workspace]');
    if (!target) return;
    target.replaceChildren();
    target.setAttribute('aria-busy', 'false');

    target.append(r3BuildControls(view));
    const warnings = Array.isArray(view.warnings) ? view.warnings : [];
    if (warnings.length) target.append(r3WarningBlock(warnings));

    const grid = el('div', 'r3-card-grid');
    grid.append(
      r3ConclusionCard(view),
      r3ProgressCard(view),
      r3GatesCard(view),
      r3EvidenceCard(view),
    );
    target.append(grid);
  }

  function closeR3EvidenceDialog(overlay, sourceButton) {
    if (overlay && overlay.parentNode) overlay.parentNode.removeChild(overlay);
    if (sourceButton && document.contains(sourceButton)) {
      sourceButton.focus({ preventScroll: true });
      sourceButton.scrollIntoView({ block: 'nearest' });
    }
  }

  function openR3EvidenceDetail(type, id, sourceButton, view) {
    if (!r3EvidenceHrefAllowed(type, id)) return;
    const overlay = el('div', 'r3-dialog-overlay');
    const dialog = el('section', 'r3-dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'r3-dialog-title');
    const dialogTitle = el('h3', 'r3-dialog-title', '证据详情（受控投影）');
    dialogTitle.id = 'r3-dialog-title';
    dialog.append(dialogTitle);
    const body = el('div', 'r3-dialog-body');
    dialog.append(body);
    const actions = el('div', 'r3-dialog-actions');
    const closeButton = el('button', 'r3-dialog-close', '返回原工作区');
    closeButton.type = 'button';
    actions.append(closeButton);
    dialog.append(actions);
    overlay.append(dialog);
    document.body.append(overlay);

    const finish = () => closeR3EvidenceDialog(overlay, sourceButton);
    closeButton.addEventListener('click', finish);
    overlay.addEventListener('click', (event) => {
      if (event.target === overlay) finish();
    });
    overlay.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') finish();
      if (event.key === 'Tab') {
        event.preventDefault();
        closeButton.focus();
      }
    });
    closeButton.focus();

    fetch(r3EvidenceHref(type, id), { cache: 'no-store' })
      .then((response) => {
        if (!response.ok) throw new Error('r3 evidence detail request failed');
        return response.json();
      })
      .then((payload) => {
        if (!payload || !payload.success || !payload.data) {
          throw new Error('r3 evidence projection invalid');
        }
        const detail = payload.data;
        const lineLabel = view.selected_line
          ? textOr(view.selected_line.label, COPY_FIELD_MISSING)
          : COPY_ALL_LINES;
        const fields = el('dl', 'r3-dialog-fields');
        fields.append(
          r3MetaRow('标题', textOr(detail.title, COPY_FIELD_MISSING)),
          r3MetaRow('稳定编号', textOr(detail.id, COPY_FIELD_MISSING)),
          r3MetaRow('类型', EVIDENCE_TYPE_LABELS[detail.type] || COPY_FIELD_MISSING),
          r3MetaRow('状态', textOr(detail.status, COPY_FIELD_MISSING)),
          r3MetaRow('责任角色', textOr(detail.owner_role_label, COPY_FIELD_MISSING)),
          r3MetaRow('核对日期', textOr(detail.verified_at, COPY_DATE_MISSING)),
          r3MetaRow('受控摘要', textOr(detail.safe_summary, COPY_FIELD_MISSING)),
          r3MetaRow(
            '关联证据编号',
            Array.isArray(detail.related_evidence_ids) && detail.related_evidence_ids.length
              ? detail.related_evidence_ids.join('、')
              : COPY_FIELD_MISSING,
          ),
          r3MetaRow('当前交付线', lineLabel),
        );
        if (detail.available === false) {
          const notice = el('p', 'r3-dialog-notice', textOr(detail.unavailable_reason, COPY_EVIDENCE_UNAVAILABLE));
          notice.setAttribute('role', 'alert');
          body.append(notice);
        }
        body.append(fields);
      })
      .catch(() => {
        body.replaceChildren();
        const failure = el('p', 'r3-dialog-notice', COPY_DETAIL_FAILURE);
        failure.setAttribute('role', 'alert');
        body.append(failure);
      });
  }

  async function loadR3Workspace() {
    const target = document.querySelector('[data-r3-workspace]');
    if (!target) return;
    const workspaceId = target.dataset.r3Workspace;
    if (!workspaceId) return;
    target.setAttribute('aria-busy', 'true');
    const line = r3LineFromUrl();
    const endpoint =
      `/api/v1/project-status/dashboard/r3/workspaces/${encodeURIComponent(workspaceId)}` +
      (line ? `?line=${encodeURIComponent(line)}` : '');
    try {
      const response = await fetch(endpoint, { cache: 'no-store' });
      if (!response.ok) throw new Error('r3 workspace request failed');
      const payload = await response.json();
      if (!payload || !payload.success || !payload.data) {
        throw new Error('r3 workspace projection invalid');
      }
      r3RenderWorkspace(payload.data);
    } catch (error) {
      r3LoadFailure(target);
    }
  }

  function focusDeliveryLineFromUrl() {
    const line = r3LineFromUrl();
    if (!line) return;
    const card = document.getElementById(`delivery-line-${line}`);
    if (!card) return;
    card.classList.add('r3-line-focused');
    card.setAttribute('tabindex', '-1');
    card.scrollIntoView({ block: 'start' });
    card.focus({ preventScroll: true });
    const workspaceEntry = document.querySelector('.safe-workspace-entry a');
    if (workspaceEntry) {
      workspaceEntry.href = r3LineHref(
        workspaceEntry.getAttribute('href') || workspaceEntry.href,
        line,
      );
    }
  }

  const r3Target = document.querySelector('[data-r3-workspace]');
  if (r3Target) {
    if ('scrollRestoration' in window.history) window.history.scrollRestoration = 'manual';
    window.scrollTo(0, 0);
    r3SyncNavLine(r3LineFromUrl());
    loadR3Workspace();
  } else {
    const lineFromUrl = r3LineFromUrl();
    const deliveryContent = document.querySelector('[data-delivery-lines-content]');
    if (deliveryContent && lineFromUrl) {
      const observer = new MutationObserver(() => {
        if (document.getElementById(`delivery-line-${lineFromUrl}`)) {
          focusDeliveryLineFromUrl();
          observer.disconnect();
        }
      });
      observer.observe(deliveryContent, { childList: true, subtree: true });
      focusDeliveryLineFromUrl();
    }
  }
})();
