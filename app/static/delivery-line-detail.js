// L2/L4 交付线通用详情：只消费服务端受控投影，不读取原始资料。
(function () {
  'use strict';

  const root = document.querySelector('[data-delivery-detail]');
  if (!root) return;

  const lineId = document.body.dataset.deliveryLineId || '';
  const referencePattern = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$/;
  const evidenceTypes = new Set([
    'document', 'test_run', 'case_design', 'defect', 'technical_review', 'handoff', 'stage',
  ]);
  const statusLabels = {
    proposed: '拟议', confirmed: '已确认', superseded: '已替代', withdrawn: '已撤回',
    planned: '已规划', in_review: '评审中', approved: '已批准', implementation: '实施中',
    verified: '已核对', blocked: '已阻断', pending: '待核对', fixed: '已固定',
    inconsistent: '不一致', valid: '有效', stale: '待复核', missing: '待关联',
    unavailable: '暂不可查看', conflict: '待核对', provided: '已提供',
  };

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function safeText(value, fallback = '待关联') {
    return typeof value === 'string' && value.trim() ? value : fallback;
  }

  function safeReference(value) {
    return typeof value === 'string' && referencePattern.test(value) ? value : null;
  }

  function statusPill(value) {
    const status = safeText(value, '待核对');
    return el('span', `r3-status-pill delivery-status-${status}`, statusLabels[status] || status);
  }

  function warning(messages) {
    const block = el('div', 'safe-workspace-alert delivery-detail-alert');
    block.setAttribute('role', 'alert');
    block.append(el('strong', '', '请注意'));
    const list = el('ul');
    messages.forEach((message) => list.append(el('li', '', message)));
    block.append(list);
    return block;
  }

  function empty(text) {
    return el('p', 'delivery-detail-empty', text || '暂无已关联信息');
  }

  function section(title, id, content) {
    const block = el('section', 'delivery-detail-block');
    block.id = id;
    block.append(el('h3', '', title), content);
    return block;
  }

  function list(items, render, emptyText) {
    const wrap = el('div', 'delivery-detail-list');
    if (!Array.isArray(items) || !items.length) wrap.append(empty(emptyText));
    else items.forEach((item) => wrap.append(render(item)));
    return wrap;
  }

  function metaRow(label, value) {
    const row = el('div', 'delivery-detail-meta-row');
    row.append(el('dt', '', label), el('dd', '', safeText(value)));
    return row;
  }

  function refList(label, refs) {
    const values = Array.isArray(refs) ? refs.filter((value) => safeReference(value)) : [];
    return metaRow(label, values.length ? values.join('、') : '待关联');
  }

  function evidenceLink(item) {
    if (!item || !evidenceTypes.has(item.evidence_type) || !safeReference(item.evidence_id)) {
      return el('span', 'delivery-detail-unavailable', '证据暂不可查看');
    }
    const link = el('a', 'delivery-detail-link', `${safeText(item.evidence_type)} · ${item.evidence_id}`);
    const path = `/project-status/delivery-lines/${encodeURIComponent(lineId)}/evidence/${encodeURIComponent(item.evidence_type)}/${encodeURIComponent(item.evidence_id)}`;
    link.href = path;
    return link;
  }

  function summaryPanel(data) {
    const line = data.delivery_line || {};
    const panel = el('section', 'delivery-detail-summary');
    const heading = el('div', 'delivery-detail-summary-heading');
    heading.append(el('div', 'delivery-detail-kicker', safeText(line.delivery_line_id, '交付线')), el('h3', '', safeText(line.name)));
    heading.append(statusPill(line.delivery_status_label || line.delivery_status));
    panel.append(heading, el('p', 'delivery-detail-summary-copy', safeText(line.current_conclusion)));
    const meta = el('dl', 'delivery-detail-meta');
    meta.append(
      metaRow('当前候选', line.current_candidate_summary),
      metaRow('下一道门禁', line.next_gate_summary),
      metaRow('最近核对', line.verified_at),
      metaRow('产品验收', line.can_enter_product_acceptance === true ? '允许进入产品验收' : '暂不允许进入产品验收'),
      metaRow('受控试用', line.can_enter_controlled_trial === true ? '允许受控试用' : '暂不允许受控试用'),
    );
    panel.append(meta);
    return panel;
  }

  function revisionItem(item) {
    const article = el('article', 'delivery-detail-item');
    const title = el('h4', '', `${safeText(item.revision_label)} · ${safeText(item.revision_id)}`);
    article.append(title, statusPill(item.revision_status));
    const meta = el('dl', 'delivery-detail-meta');
    meta.append(
      metaRow('生效时间', item.effective_at),
      metaRow('核对状态', item.verification_state),
      metaRow('责任角色', item.owner_role),
      refList('变更引用', item.change_refs),
    );
    article.append(meta, el('p', '', safeText(item.change_summary)), el('p', '', safeText(item.scope_delta)));
    return article;
  }

  function solutionItem(item) {
    const article = el('article', 'delivery-detail-item');
    article.append(el('h4', '', `${safeText(item.title)} · ${safeText(item.technical_solution_id)}`), statusPill(item.solution_status));
    const meta = el('dl', 'delivery-detail-meta');
    meta.append(metaRow('方案类型', item.solution_type), metaRow('责任角色', item.owner_role), metaRow('核对状态', item.verification_state));
    article.append(meta, el('p', '', safeText(item.controlled_summary)), refList('候选交接', item.candidate_refs));
    return article;
  }

  function candidateItem(item) {
    const article = el('article', 'delivery-detail-item');
    article.append(el('h4', '', `${safeText(item.candidate_type)} · ${safeText(item.candidate_handoff_id)}`), statusPill(item.candidate_status));
    const handoffItems = Array.isArray(item.handoff_items) ? item.handoff_items : [];
    const listNode = el('ul', 'delivery-detail-sublist');
    if (!handoffItems.length) listNode.append(el('li', '', '交接项待关联'));
    handoffItems.forEach((handoff) => {
      const row = el('li', 'delivery-detail-subitem');
      row.append(el('strong', '', safeText(handoff.item_type)), el('span', '', safeText(handoff.safe_summary)), statusPill(handoff.status));
      listNode.append(row);
    });
    article.append(listNode);
    if (Array.isArray(item.missing_items) && item.missing_items.length) article.append(el('p', 'delivery-detail-warning-copy', `缺失项：${item.missing_items.join('、')}`));
    if (Array.isArray(item.conflict_items) && item.conflict_items.length) article.append(el('p', 'delivery-detail-warning-copy', `冲突项：${item.conflict_items.join('、')}`));
    return article;
  }

  function qualityItem(item) {
    const article = el('article', 'delivery-detail-item');
    article.append(el('h4', '', `${safeText(item.name)} · ${safeText(item.quality_requirement_id)}`), statusPill(item.status));
    article.append(el('p', '', safeText(item.readiness_summary)), el('p', 'delivery-detail-boundary', '质量追踪不等于产品验收或发布结论'));
    const id = safeReference(item.quality_requirement_id);
    if (id && safeReference(lineId)) {
      const link = el('a', 'delivery-detail-link', '查看质量详情');
      const url = new URL(`/project-status/tests/requirements/${encodeURIComponent(id)}`, window.location.origin);
      url.searchParams.set('line', lineId);
      url.searchParams.set('from', 'delivery-detail');
      url.hash = 'cases';
      link.href = url.pathname + url.search + url.hash;
      article.append(link);
    }
    return article;
  }

  function evidenceItem(item) {
    const article = el('article', 'delivery-detail-item');
    article.append(el('h4', '', safeText(item.safe_title)), statusPill(item.validity_state));
    article.append(el('p', '', safeText(item.safe_summary)), el('p', '', `来源角色：${safeText(item.source_role)}`));
    const link = evidenceLink(item);
    if (link.tagName === 'A') article.append(link);
    else article.append(link);
    return article;
  }

  function render(data) {
    root.replaceChildren();
    const line = data.delivery_line || {};
    root.append(summaryPanel(data));
    const messages = (Array.isArray(data.warnings) ? data.warnings : [])
      .map((item) => safeText(item && item.safe_message, '部分详情信息待核对'));
    if (messages.length) root.append(warning(messages));
    const sections = data.sections || {};
    const blocks = [
      section('需求版本', 'requirement-revisions', list(sections.requirement_revisions, revisionItem, '需求版本待关联')),
      section('技术方案', 'technical-solutions', list(sections.technical_solutions, solutionItem, '技术方案待关联')),
      section('候选交接', 'candidate-handoffs', list(sections.candidate_handoffs, candidateItem, '候选交接待关联')),
      section('质量追踪', 'quality-trace', list(sections.quality_trace, qualityItem, '质量对象待关联')),
      section('受控证据', 'controlled-evidence', list(sections.evidence, evidenceItem, '受控证据待关联')),
    ];
    blocks.forEach((block) => root.append(block));
    root.setAttribute('aria-busy', 'false');
    root.dataset.deliveryDetailState = safeText(data.state, 'incomplete');
    if (line.delivery_line_id !== lineId) root.append(warning(['详情关系与交付线不匹配，请重新选择']));
  }

  function fail() {
    root.replaceChildren(warning(['暂时无法加载交付线详情，请稍后重试']));
    root.setAttribute('aria-busy', 'false');
  }

  fetch(`/api/v1/project-status/delivery-lines/${encodeURIComponent(lineId)}/detail`, {
    headers: { Accept: 'application/json' }, cache: 'no-store',
  })
    .then((response) => {
      if (!response.ok) throw new Error('delivery detail unavailable');
      return response.json();
    })
    .then((body) => {
      if (!body || body.success !== true || !body.data) throw new Error('invalid delivery detail');
      render(body.data);
    })
    .catch(fail);
}());
