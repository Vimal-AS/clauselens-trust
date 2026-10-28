/**
 * ClauseLens Trust - Risk Results View
 * Summary cards, filters, review tracking, PDF page preview with highlights, JSON/PDF export
 */

document.addEventListener('DOMContentLoaded', () => {
    let currentAnalysisId = null;
    let currentAnalysisData = null;
    let allFindings = [];
    let filteredFindings = [];

    // Filter elements
    const filterSeverity = document.getElementById('filterSeverity');
    const filterCategory = document.getElementById('filterCategory');
    const filterResultType = document.getElementById('filterResultType');
    const filterVerification = document.getElementById('filterVerification');
    const filterReviewStatus = document.getElementById('filterReviewStatus');
    const filterSearch = document.getElementById('filterSearch');
    const clearFiltersBtn = document.getElementById('clearFiltersBtn');

    // Counts & Stats
    const visibleCount = document.getElementById('visibleFindingsCount');
    const allFindingsCount = document.getElementById('allFindingsCount');
    const filteredFindingsCount = document.getElementById('filteredFindingsCount');
    const findingsList = document.getElementById('findingsList');
    const findingsEmptyState = document.getElementById('findingsEmptyState');
    const analysisSelect = document.getElementById('analysisSelect');

    // Exports
    const exportJsonBtn = document.getElementById('exportJsonBtn');
    const exportPdfBtn = document.getElementById('exportPdfBtn');

    // PDF Preview Modal
    const pdfPreviewModal = document.getElementById('pdfPreviewModal');
    const closePdfPreviewBtn = document.getElementById('closePdfPreviewBtn');
    const pdfPageImage = document.getElementById('pdfPageImage');
    const pdfPageSpinner = document.getElementById('pdfPageSpinner');
    const pdfPreviewTitle = document.getElementById('pdfPreviewTitle');

    closePdfPreviewBtn.addEventListener('click', () => {
        pdfPreviewModal.style.display = 'none';
        pdfPageImage.src = '';
    });

    // Detect if analysis_id is in URL path: /results/<id>
    const pathParts = window.location.pathname.split('/').filter(Boolean);
    if (pathParts.length > 1 && pathParts[0] === 'results') {
        currentAnalysisId = pathParts[1];
    }

    // Init analyses dropdown
    loadAnalysesDropdown();

    function loadAnalysesDropdown() {
        fetch('/api/analyses')
            .then(res => res.json())
            .then(data => {
                const analyses = data.analyses || [];
                analysisSelect.innerHTML = '';

                if (analyses.length === 0) {
                    analysisSelect.innerHTML = '<option value="">No analyses available</option>';
                    return;
                }

                analyses.forEach(a => {
                    const opt = document.createElement('option');
                    opt.value = a.id;
                    const dateStr = a.completed_at ? new Date(a.completed_at).toLocaleDateString() : '';
                    opt.textContent = `${a.original_filename} (${dateStr})`;
                    if (a.id === currentAnalysisId) {
                        opt.selected = true;
                    }
                    analysisSelect.appendChild(opt);
                });

                if (!currentAnalysisId && analyses.length > 0) {
                    currentAnalysisId = analyses[0].id;
                }

                if (currentAnalysisId) {
                    loadAnalysisDetail(currentAnalysisId);
                }
            })
            .catch(() => {});
    }

    analysisSelect.addEventListener('change', () => {
        currentAnalysisId = analysisSelect.value;
        if (currentAnalysisId) {
            history.pushState(null, '', `/results/${currentAnalysisId}`);
            loadAnalysisDetail(currentAnalysisId);
        }
    });

    function loadAnalysisDetail(analysisId) {
        fetch(`/api/analyses/${analysisId}`)
            .then(res => {
                if (!res.ok) throw new Error('Analysis not found.');
                return res.json();
            })
            .then(data => {
                currentAnalysisData = data;
                allFindings = data.findings || [];

                // Update Header
                const a = data.analysis;
                document.getElementById('resultsDocTitle').textContent = a.original_filename;
                const fileTypeLabel = a.file_type === 'images' ? `IMAGES (${a.total_pages || 0} Files)` : a.file_type.toUpperCase();
                document.getElementById('resultsDocSubtitle').textContent = `Format: ${fileTypeLabel} • Analyzed ${new Date(a.completed_at || a.created_at).toLocaleString()}`;
                
                const sampleBadge = document.getElementById('sampleDocBadge');
                sampleBadge.style.display = a.is_sample ? 'inline-block' : 'none';

                // Display warnings if any
                const warningsAlert = document.getElementById('analysisWarningsAlert');
                const warningsList = document.getElementById('analysisWarningsList');
                const warnings = data.warnings || (data.analysis && data.analysis.warnings) || [];
                if (warningsAlert && warningsList) {
                    if (warnings.length > 0) {
                        warningsList.innerHTML = warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('');
                        warningsAlert.style.display = 'flex';
                    } else {
                        warningsAlert.style.display = 'none';
                        warningsList.innerHTML = '';
                    }
                }

                // Populate Summary Cards
                updateSummaryCards(data.summary);

                // Apply initial filters
                applyFilters();
            })
            .catch(err => {
                showToast(err.message, 'error');
            });
    }

    function updateSummaryCards(s) {
        document.getElementById('statTotal').textContent = s.total_findings || 0;
        document.getElementById('statHigh').textContent = s.high || 0;
        document.getElementById('statMedium').textContent = s.medium || 0;
        document.getElementById('statLow').textContent = s.low || 0;
        document.getElementById('statConflicts').textContent = s.conflicts || 0;
        document.getElementById('statMatches').textContent = s.matches || 0;
        document.getElementById('statUncertain').textContent = s.uncertain || 0;
        document.getElementById('statNotFound').textContent = s.not_found || 0;

        allFindingsCount.textContent = s.total_findings || 0;
    }

    // Filter event listeners
    [filterSeverity, filterCategory, filterResultType, filterVerification, filterReviewStatus].forEach(el => {
        el.addEventListener('change', applyFilters);
    });
    filterSearch.addEventListener('input', applyFilters);

    clearFiltersBtn.addEventListener('click', () => {
        filterSeverity.value = 'all';
        filterCategory.value = 'all';
        filterResultType.value = 'all';
        filterVerification.value = 'all';
        filterReviewStatus.value = 'all';
        filterSearch.value = '';
        applyFilters();
    });

    function applyFilters() {
        const sev = filterSeverity.value;
        const cat = filterCategory.value;
        const rt = filterResultType.value;
        const ver = filterVerification.value;
        const rev = filterReviewStatus.value;
        const q = filterSearch.value.trim().toLowerCase();

        filteredFindings = allFindings.filter(f => {
            if (sev !== 'all' && f.severity !== sev) return false;
            if (cat !== 'all' && f.category !== cat) return false;
            if (rt !== 'all' && f.result_type !== rt) return false;
            if (ver !== 'all' && f.verification_status !== ver) return false;
            if (rev !== 'all' && f.review_status !== rev) return false;

            if (q) {
                const quoteText = (f.evidence_quote || '').toLowerCase();
                const clauseText = (f.clause_title || '').toLowerCase();
                const expText = (f.explanation || '').toLowerCase();
                if (!quoteText.includes(q) && !clauseText.includes(q) && !expText.includes(q)) {
                    return false;
                }
            }

            return true;
        });

        visibleCount.textContent = filteredFindings.length;
        filteredFindingsCount.textContent = filteredFindings.length;

        // Update active stat card highlight
        document.querySelectorAll('.stat-card').forEach(c => c.classList.remove('active-filter'));
        if (sev === 'high') {
            document.querySelector('.stat-card[data-card="high"]')?.classList.add('active-filter');
        } else if (sev === 'medium') {
            document.querySelector('.stat-card[data-card="medium"]')?.classList.add('active-filter');
        } else if (sev === 'low') {
            document.querySelector('.stat-card[data-card="low"]')?.classList.add('active-filter');
        }
        if (rt === 'conflict') {
            document.querySelector('.stat-card[data-card="conflicts"]')?.classList.add('active-filter');
        } else if (rt === 'match') {
            document.querySelector('.stat-card[data-card="matches"]')?.classList.add('active-filter');
        } else if (rt === 'uncertain') {
            document.querySelector('.stat-card[data-card="uncertain"]')?.classList.add('active-filter');
        } else if (rt === 'not_found') {
            document.querySelector('.stat-card[data-card="notfound"]')?.classList.add('active-filter');
        }

        renderFindings(filteredFindings);
    }

    // Stat card quick click-to-filter
    document.querySelectorAll('.stat-card').forEach(card => {
        card.addEventListener('click', () => {
            const type = card.getAttribute('data-card');
            if (!type) return;
            if (type === 'total') {
                filterSeverity.value = 'all';
                filterResultType.value = 'all';
            } else if (type === 'high' || type === 'medium' || type === 'low') {
                filterSeverity.value = (filterSeverity.value === type) ? 'all' : type;
            } else if (type === 'conflicts') {
                filterResultType.value = (filterResultType.value === 'conflict') ? 'all' : 'conflict';
            } else if (type === 'matches') {
                filterResultType.value = (filterResultType.value === 'match') ? 'all' : 'match';
            } else if (type === 'uncertain') {
                filterResultType.value = (filterResultType.value === 'uncertain') ? 'all' : 'uncertain';
            } else if (type === 'notfound') {
                filterResultType.value = (filterResultType.value === 'not_found') ? 'all' : 'not_found';
            }
            applyFilters();
        });
    });

    function renderFindings(findings) {
        findingsList.innerHTML = '';

        if (findings.length === 0) {
            findingsEmptyState.style.display = 'block';
            return;
        }

        findingsEmptyState.style.display = 'none';

        findings.forEach(f => {
            const card = document.createElement('div');
            const sevClass = f.severity ? `severity-${f.severity}` : 'severity-low';
            card.className = `finding-card ${sevClass}`;

            const isImageContract = currentAnalysisData && currentAnalysisData.analysis && currentAnalysisData.analysis.file_type === 'images';
            const locationStr = isImageContract
                ? (f.paragraph_reference || (f.page_number ? `Image ${f.page_number}` : 'Location: not available'))
                : (f.line_reference 
                    ? f.line_reference 
                    : (f.page_number ? `Page ${f.page_number}` : (f.paragraph_reference ? f.paragraph_reference : 'Location: not available')));

            const hasPage = (!!f.page_number && currentAnalysisData && currentAnalysisData.analysis.file_type === 'pdf') ||
                            (isImageContract && !!f.page_number);

            card.innerHTML = `
                <div class="finding-header" data-id="${f.id}">
                    <div class="finding-title-left">
                        <span class="risk-id-tag">${escapeHtml(f.risk_id)}</span>
                        ${f.severity ? `<span class="badge-pill badge-${f.severity}">${f.severity.toUpperCase()}</span>` : ''}
                        <span class="badge-pill badge-${f.result_type}">${f.result_type.replace('_', ' ').toUpperCase()}</span>
                        <span class="badge-pill badge-${f.verification_status}">${f.verification_status.replace(/_/g, ' ')}</span>
                        <span class="finding-title-text">${escapeHtml(f.category.toUpperCase())}${f.clause_title ? ` — ${escapeHtml(f.clause_title)}` : ''}</span>
                    </div>
                    <div class="finding-header-right">
                        <span class="badge-pill">${f.review_status.replace('_', ' ')}</span>
                        <span class="toggle-icon">▼</span>
                    </div>
                </div>
                <div class="finding-body">
                    <div class="comparison-grid">
                        <div class="comparison-box">
                            <div class="comparison-box-title">Policy Expected</div>
                            <div class="comparison-box-content">${escapeHtml(f.policy_expected || 'Standard policy')}</div>
                        </div>
                        <div class="comparison-box">
                            <div class="comparison-box-title">Condition Detected</div>
                            <div class="comparison-box-content">${escapeHtml(f.condition_detected || 'Clause detected')}</div>
                        </div>
                    </div>

                    ${f.evidence_quote ? `
                        <div class="evidence-quote-box">
                            <div class="evidence-header">
                                <span class="evidence-label">Exact Contract Evidence:</span>
                                <span class="evidence-location">${escapeHtml(locationStr)}</span>
                            </div>
                            <div class="evidence-text">"${escapeHtml(f.evidence_quote)}"</div>
                        </div>
                    ` : `
                        <div class="evidence-quote-box">
                            <div class="evidence-header"><span class="evidence-label">Evidence:</span></div>
                            <div class="evidence-text text-muted">No explicit matching clause text found in the contract.</div>
                        </div>
                    `}

                    <div class="action-impact-grid">
                        <div class="narrative-item">
                            <strong>Plain-English Explanation:</strong>
                            <p>${escapeHtml(f.explanation || '')}</p>
                        </div>
                        <div class="narrative-item">
                            <strong>Potential Risk Impact:</strong>
                            <p>${escapeHtml(f.potential_impact || '')}</p>
                        </div>
                    </div>

                    <div class="narrative-item mt-2">
                        <strong>Suggested Neutral Next Action:</strong>
                        <p>${escapeHtml(f.suggested_action || '')}</p>
                    </div>

                    <div class="review-tracking-bar">
                        <div class="review-controls">
                            <label class="form-label-xs">Review Status:</label>
                            <select class="form-control form-control-sm review-status-select" data-id="${f.id}">
                                <option value="not_reviewed" ${f.review_status === 'not_reviewed' ? 'selected' : ''}>Not Reviewed</option>
                                <option value="reviewed" ${f.review_status === 'reviewed' ? 'selected' : ''}>Reviewed</option>
                                <option value="needs_attention" ${f.review_status === 'needs_attention' ? 'selected' : ''}>Needs Attention</option>
                            </select>
                            <input type="text" class="form-control form-control-sm review-note-input" data-id="${f.id}" placeholder="Add review note..." value="${escapeHtml(f.review_note || '')}">
                            <button type="button" class="btn btn-sm btn-outline save-review-btn" data-id="${f.id}">Save Note</button>
                        </div>
                        <div>
                            ${hasPage ? `<button type="button" class="btn btn-sm btn-ghost view-page-btn" data-page="${f.page_number}" data-finding="${f.id}"><svg class="btn-svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg> ${isImageContract ? 'View Source Image' : 'View Page Highlight'}</button>` : ''}
                        </div>
                    </div>
                </div>
            `;

            findingsList.appendChild(card);
        });

        // Attach finding accordion toggle with smooth icon rotation
        document.querySelectorAll('.finding-header').forEach(header => {
            header.addEventListener('click', (e) => {
                if (e.target.closest('button') || e.target.closest('select') || e.target.closest('input')) return;
                const body = header.nextElementSibling;
                const icon = header.querySelector('.toggle-icon');
                const isHidden = body.style.display === 'none';
                if (isHidden) {
                    body.style.display = 'block';
                    if (icon) icon.classList.add('rotated');
                } else {
                    body.style.display = 'none';
                    if (icon) icon.classList.remove('rotated');
                }
            });
        });

        // Review Status change & note saving
        document.querySelectorAll('.save-review-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                const sel = document.querySelector(`.review-status-select[data-id="${id}"]`);
                const inp = document.querySelector(`.review-note-input[data-id="${id}"]`);
                saveReviewStatus(id, sel.value, inp.value);
            });
        });

        // View Page Highlight
        document.querySelectorAll('.view-page-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const page = btn.getAttribute('data-page');
                const findingId = btn.getAttribute('data-finding');
                openPdfPageModal(page, findingId);
            });
        });
    }

    function saveReviewStatus(findingId, status, note) {
        fetch(`/api/findings/${findingId}/review`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ review_status: status, review_note: note })
        })
        .then(async res => {
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to update review status.');
            return data;
        })
        .then(() => {
            showToast('Review status updated.', 'success');
            // Update in local array
            const found = allFindings.find(f => f.id == findingId);
            if (found) {
                found.review_status = status;
                found.review_note = note;
            }
        })
        .catch(err => {
            showToast(err.message, 'error');
        });
    }

    function openPdfPageModal(pageNum, findingId) {
        if (!currentAnalysisId) return;
        pdfPreviewModal.style.display = 'flex';
        pdfPageSpinner.style.display = 'block';
        pdfPageImage.style.display = 'none';

        const isImageContract = currentAnalysisData && currentAnalysisData.analysis && currentAnalysisData.analysis.file_type === 'images';
        pdfPreviewTitle.textContent = isImageContract 
            ? `Document Evidence Preview — Image ${pageNum}` 
            : `Document Evidence Preview — Page ${pageNum}`;

        const imgUrl = `/api/analyses/${currentAnalysisId}/page/${pageNum}.png?finding_id=${findingId}`;
        pdfPageImage.onload = () => {
            pdfPageSpinner.style.display = 'none';
            pdfPageImage.style.display = 'block';
        };
        pdfPageImage.onerror = () => {
            pdfPageSpinner.style.display = 'none';
            showToast('Failed to load page image preview.', 'error');
            pdfPreviewModal.style.display = 'none';
        };
        pdfPageImage.src = imgUrl;
    }

    // Export Handlers
    function getExportQuery() {
        const scope = document.querySelector('input[name="exportScope"]:checked').value;
        if (scope === 'all') {
            return '';
        }
        // Build filtered query string
        const params = new URLSearchParams();
        if (filterSeverity.value !== 'all') params.append('severity', filterSeverity.value);
        if (filterCategory.value !== 'all') params.append('category', filterCategory.value);
        if (filterResultType.value !== 'all') params.append('result_type', filterResultType.value);
        if (filterVerification.value !== 'all') params.append('verification', filterVerification.value);
        if (filterReviewStatus.value !== 'all') params.append('review', filterReviewStatus.value);
        if (filterSearch.value.trim()) params.append('search', filterSearch.value.trim());
        const qs = params.toString();
        return qs ? `?${qs}` : '';
    }

    const downloadSourceDocBtn = document.getElementById('downloadSourceDocBtn');
    if (downloadSourceDocBtn) {
        downloadSourceDocBtn.addEventListener('click', () => {
            if (!currentAnalysisId) return;
            window.open(`/api/analyses/${currentAnalysisId}/source-file`, '_blank');
        });
    }

    exportJsonBtn.addEventListener('click', () => {
        if (!currentAnalysisId) return;
        const qs = getExportQuery();
        window.open(`/api/analyses/${currentAnalysisId}/export.json${qs}`, '_blank');
    });

    exportPdfBtn.addEventListener('click', () => {
        if (!currentAnalysisId) return;
        const qs = getExportQuery();
        window.open(`/api/analyses/${currentAnalysisId}/export.pdf${qs}`, '_blank');
    });

    // Plain Text View Modal
    const viewPlainTextBtn = document.getElementById('viewPlainTextBtn');
    const plainTextModal = document.getElementById('plainTextModal');
    const closePlainTextBtn = document.getElementById('closePlainTextBtn');
    const copyPlainTextBtn = document.getElementById('copyPlainTextBtn');
    const plainTextContent = document.getElementById('plainTextContent');
    const plainTextDocTitle = document.getElementById('plainTextDocTitle');
    const plainTextDocStats = document.getElementById('plainTextDocStats');
    const plainTextFilter = document.getElementById('plainTextFilter');
    let rawDocumentText = '';

    if (viewPlainTextBtn) {
        viewPlainTextBtn.addEventListener('click', () => {
            if (!currentAnalysisId) return;
            plainTextModal.style.display = 'flex';
            plainTextContent.textContent = 'Loading extracted document text...';
            plainTextFilter.value = '';

            fetch(`/api/analyses/${currentAnalysisId}/text`)
                .then(async res => {
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.error || 'Failed to retrieve plain text.');
                    return data;
                })
                .then(data => {
                    rawDocumentText = data.full_text || '';
                    plainTextDocTitle.textContent = `${data.filename} — Raw Plain Text`;
                    const locationUnit = data.total_pages 
                        ? (data.file_type === 'images' ? `${data.total_pages} Images` : `${data.total_pages} Pages`) 
                        : `${data.total_paragraphs || 0} Paragraphs`;
                    plainTextDocStats.textContent = `${data.file_type.toUpperCase()} • ${locationUnit} • ${data.word_count.toLocaleString()} Words • ${data.character_count.toLocaleString()} Characters`;
                    plainTextContent.textContent = rawDocumentText;
                })
                .catch(err => {
                    plainTextContent.textContent = `Error: ${err.message}`;
                });
        });
    }

    if (closePlainTextBtn) {
        closePlainTextBtn.addEventListener('click', () => {
            plainTextModal.style.display = 'none';
        });
    }

    if (copyPlainTextBtn) {
        copyPlainTextBtn.addEventListener('click', () => {
            if (!rawDocumentText) return;
            navigator.clipboard.writeText(rawDocumentText)
                .then(() => {
                    showToast('Document text copied to clipboard.', 'success');
                })
                .catch(() => {
                    showToast('Failed to copy to clipboard.', 'error');
                });
        });
    }

    if (plainTextFilter) {
        plainTextFilter.addEventListener('input', () => {
            const query = plainTextFilter.value.trim();
            if (!query) {
                plainTextContent.textContent = rawDocumentText;
                return;
            }
            // Highlight query occurrences in pre block safely
            const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
            const safeText = escapeHtml(rawDocumentText);
            const highlighted = safeText.replace(regex, '<mark class="text-highlight">$1</mark>');
            plainTextContent.innerHTML = highlighted;
        });
    }

    function escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

});
