/**
 * ClauseLens Trust - Contract Upload & Analysis Workflow
 */

document.addEventListener('DOMContentLoaded', () => {
    let currentUploadedFile = null; // { uuid_name, original_filename, file_type, file_size, is_sample }

    const uploadZone = document.getElementById('uploadZone');
    const uploadZoneIdle = document.getElementById('uploadZoneIdle');
    const uploadZoneSelected = document.getElementById('uploadZoneSelected');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    const replaceFileBtn = document.getElementById('replaceFileBtn');
    const removeFileBtn = document.getElementById('removeFileBtn');
    const analyseBtn = document.getElementById('analyseBtn');
    const demoContractBtn = document.getElementById('demoContractBtn');
    const uploadError = document.getElementById('uploadError');
    const uploadErrorMsg = document.getElementById('uploadErrorMsg');
    const analysisStatusBox = document.getElementById('analysisStatusBox');
    const statusStageText = document.getElementById('statusStageText');
    const selectedFileName = document.getElementById('selectedFileName');
    const selectedFileMeta = document.getElementById('selectedFileMeta');
    const fileIconBadge = document.getElementById('fileIconBadge');

    // Load recent analyses on home load
    loadRecentAnalyses();

    // File selection triggers
    browseBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    uploadZone.addEventListener('click', () => {
        if (!currentUploadedFile) {
            fileInput.click();
        }
    });

    replaceFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
    });

    removeFileBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        resetUploadState();
    });

    // Drag and drop handlers
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadZone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            uploadZone.classList.remove('dragover');
        });
    });

    uploadZone.addEventListener('drop', (e) => {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            handleFilesSelected(files);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files.length > 0) {
            handleFilesSelected(fileInput.files);
        }
    });

    function hideError() {
        uploadError.style.display = 'none';
        uploadErrorMsg.textContent = '';
    }

    function showError(msg) {
        uploadError.style.display = 'flex';
        uploadErrorMsg.textContent = msg;
    }

    function resetUploadState() {
        currentUploadedFile = null;
        fileInput.value = '';
        uploadZoneIdle.style.display = 'block';
        uploadZoneSelected.style.display = 'none';
        analyseBtn.disabled = true;
        hideError();
    }

    function handleFilesSelected(fileList) {
        hideError();
        const files = Array.from(fileList);
        if (files.length === 0) return;

        const imgExts = ['jpg', 'jpeg', 'png'];
        const docExts = ['pdf', 'docx'];

        // Determine if all are images, single document, or mixed
        const allImages = files.every(f => {
            const ext = f.name.split('.').pop().toLowerCase();
            return imgExts.includes(ext);
        });

        const allDocs = files.every(f => {
            const ext = f.name.split('.').pop().toLowerCase();
            return docExts.includes(ext);
        });

        if (allDocs) {
            if (files.length > 1) {
                showError('Please upload one PDF or DOCX contract document at a time (or multiple images).');
                return;
            }
            const file = files[0];
            const maxSize = 50 * 1024 * 1024;
            if (file.size > maxSize) {
                showError('File exceeds 50 MB limit. Please select a smaller contract.');
                return;
            }
            uploadFileToServer(file);
            return;
        }

        if (allImages) {
            const maxImageCount = 20;
            if (files.length > maxImageCount) {
                showError(`Maximum of ${maxImageCount} images allowed per upload. You selected ${files.length} images.`);
                return;
            }

            const maxFileSize = 50 * 1024 * 1024;
            for (const img of files) {
                if (img.size > maxFileSize) {
                    showError(`Image "${img.name}" exceeds 50 MB limit (${(img.size / (1024 * 1024)).toFixed(1)} MB).`);
                    return;
                }
            }

            const maxBatchSize = 100 * 1024 * 1024;
            const totalSize = files.reduce((acc, f) => acc + f.size, 0);
            if (totalSize > maxBatchSize) {
                showError(`Total image batch exceeds 100 MB limit (${(totalSize / (1024 * 1024)).toFixed(1)} MB).`);
                return;
            }

            uploadImagesToServer(files);
            return;
        }

        // Mixed or unsupported extensions
        showError('Unsupported file type or mixed formats. Please upload either a single contract document (.pdf, .docx) or multiple contract page images (.jpg, .jpeg, .png).');
    }

    function uploadImagesToServer(files) {
        const formData = new FormData();
        files.forEach(f => {
            formData.append('images', f, f.name);
        });

        analyseBtn.disabled = true;
        analysisStatusBox.style.display = 'block';
        statusStageText.textContent = `Uploading and validating ${files.length} images...`;

        fetch('/api/contracts/upload-images', {
            method: 'POST',
            body: formData
        })
        .then(async (res) => {
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || 'Upload failed.');
            }
            return data;
        })
        .then((data) => {
            currentUploadedFile = data.file;
            selectedFileName.textContent = currentUploadedFile.original_filename;
            const sizeMb = (currentUploadedFile.file_size / (1024 * 1024)).toFixed(2);
            selectedFileMeta.textContent = `IMAGES • ${currentUploadedFile.total_images || files.length} Images • ${sizeMb} MB`;
            fileIconBadge.className = 'file-icon file-icon-docx';

            uploadZoneIdle.style.display = 'none';
            uploadZoneSelected.style.display = 'flex';
            analyseBtn.disabled = false;
            analysisStatusBox.style.display = 'none';
            hideError();
        })
        .catch((err) => {
            analysisStatusBox.style.display = 'none';
            resetUploadState();
            showError(err.message);
        });
    }

    function uploadFileToServer(file) {
        const formData = new FormData();
        formData.append('file', file);

        analyseBtn.disabled = true;
        analysisStatusBox.style.display = 'block';
        statusStageText.textContent = 'Uploading and validating file...';

        fetch('/api/contracts/upload', {
            method: 'POST',
            body: formData
        })
        .then(async (res) => {
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || 'Upload failed.');
            }
            return data;
        })
        .then((data) => {
            currentUploadedFile = data.file;
            selectedFileName.textContent = currentUploadedFile.original_filename;
            const sizeMb = (currentUploadedFile.file_size / (1024 * 1024)).toFixed(2);
            selectedFileMeta.textContent = `${currentUploadedFile.file_type.toUpperCase()} • ${sizeMb} MB`;
            fileIconBadge.className = `file-icon file-icon-${currentUploadedFile.file_type}`;

            uploadZoneIdle.style.display = 'none';
            uploadZoneSelected.style.display = 'flex';
            analyseBtn.disabled = false;
            analysisStatusBox.style.display = 'none';
            hideError();
        })
        .catch((err) => {
            analysisStatusBox.style.display = 'none';
            resetUploadState();
            showError(err.message);
        });
    }

    // Demo contracts selection modal
    const demoContractsModal = document.getElementById('demoContractsModal');
    const closeDemoModalBtn = document.getElementById('closeDemoModalBtn');
    const demoCardsList = document.getElementById('demoCardsList');

    if (closeDemoModalBtn) {
        closeDemoModalBtn.addEventListener('click', () => {
            demoContractsModal.style.display = 'none';
        });
    }

    // Demo contract button opens picker modal
    demoContractBtn.addEventListener('click', () => {
        hideError();
        demoContractsModal.style.display = 'flex';
        loadDemoList();
    });

    function loadDemoList() {
        fetch('/api/contracts/demo-list')
            .then(res => res.json())
            .then(data => {
                const demos = data.demos || [];
                renderDemoCards(demos);
            })
            .catch(() => {
                demoCardsList.innerHTML = '<p class="text-danger text-center">Failed to load demo list.</p>';
            });
    }

    function renderDemoCards(demos) {
        demoCardsList.innerHTML = '';
        demos.forEach(d => {
            const card = document.createElement('div');
            card.className = 'demo-choice-card';

            const badgeClass = d.risk_badge.toLowerCase().includes('high') 
                ? 'badge-high' 
                : (d.risk_badge.toLowerCase().includes('medium') ? 'badge-medium' : 'badge-match');

            card.innerHTML = `
                <div class="demo-card-left">
                    <div class="demo-doc-type-icon ${d.file_type}">
                        ${d.file_type.toUpperCase()}
                    </div>
                    <div class="demo-card-info">
                        <div class="demo-card-header">
                            <span class="demo-card-title">${escapeHtml(d.title)}</span>
                            <span class="badge-pill ${badgeClass}">${escapeHtml(d.risk_badge)}</span>
                        </div>
                        <p class="demo-card-desc">${escapeHtml(d.description)}</p>
                        <span class="demo-card-conflicts">${escapeHtml(d.conflicts_summary)}</span>
                    </div>
                </div>
                <div class="demo-card-actions">
                    <button type="button" class="btn btn-sm btn-primary select-demo-btn" data-id="${d.id}">
                        Open
                    </button>
                </div>
            `;
            demoCardsList.appendChild(card);
        });

        document.querySelectorAll('.select-demo-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const demoId = btn.getAttribute('data-id');
                demoContractsModal.style.display = 'none';
                loadSelectedDemo(demoId, false);
            });
        });
    }

    function loadSelectedDemo(demoId, autoAnalyse = false) {
        hideError();
        analyseBtn.disabled = true;
        analysisStatusBox.style.display = 'block';
        statusStageText.textContent = 'Loading selected sample contract...';

        fetch('/api/contracts/demo', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ demo_id: demoId })
        })
        .then(async (res) => {
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to load demo contract.');
            return data;
        })
        .then((data) => {
            currentUploadedFile = data.file;
            selectedFileName.textContent = currentUploadedFile.original_filename;
            const sizeMb = (currentUploadedFile.file_size / (1024 * 1024)).toFixed(2);
            selectedFileMeta.textContent = `${currentUploadedFile.file_type.toUpperCase()} • ${sizeMb} MB (Sample Document)`;
            if (fileIconBadge) {
                fileIconBadge.className = `file-icon file-icon-${currentUploadedFile.file_type}`;
            }

            uploadZoneIdle.style.display = 'none';
            uploadZoneSelected.style.display = 'flex';
            analyseBtn.disabled = false;
            
            if (autoAnalyse) {
                // Immediately start contract analysis
                runContractAnalysis();
            } else {
                analysisStatusBox.style.display = 'none';
                showToast(`Loaded sample contract: ${data.file.title || data.file.original_filename}`, 'info');
            }
        })
        .catch((err) => {
            analysisStatusBox.style.display = 'none';
            showError(err.message);
        });
    }

    function runContractAnalysis() {
        if (!currentUploadedFile) return;

        analyseBtn.disabled = true;
        analysisStatusBox.style.display = 'block';
        statusStageText.textContent = 'Extracting text and document locations...';

        const timer = setTimeout(() => {
            statusStageText.textContent = 'Checking contract clauses against your policies...';
        }, 600);

        const timer2 = setTimeout(() => {
            statusStageText.textContent = 'Verifying quote evidence against document sources...';
        }, 1200);

        fetch('/api/contracts/analyse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentUploadedFile)
        })
        .then(async (res) => {
            clearTimeout(timer);
            clearTimeout(timer2);
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.error || 'Analysis failed.');
            }
            return data;
        })
        .then((data) => {
            analysisStatusBox.style.display = 'none';
            showToast('Analysis completed successfully!', 'success');
            // Navigate directly to results page for this analysis
            window.location.href = `/results/${data.analysis_id}`;
        })
        .catch((err) => {
            clearTimeout(timer);
            clearTimeout(timer2);
            analysisStatusBox.style.display = 'none';
            analyseBtn.disabled = false;
            showError(err.message);
        });
    }

    // Analyse Button
    analyseBtn.addEventListener('click', () => {
        runContractAnalysis();
    });

    // Recent Analyses & Latest Summary
    function loadRecentAnalyses() {
        fetch('/api/analyses')
            .then(res => res.json())
            .then(data => {
                const analyses = data.analyses || [];
                renderRecentTable(analyses);
                if (analyses.length > 0) {
                    loadLatestSummary(analyses[0].id);
                }
            })
            .catch(() => {});
    }

    function renderRecentTable(analyses) {
        const countSpan = document.getElementById('recentAnalysesCount');
        const emptyState = document.getElementById('recentAnalysesEmpty');
        const tableWrapper = document.getElementById('recentTableWrapper');
        const tableBody = document.getElementById('recentTableBody');

        countSpan.textContent = `${analyses.length} saved`;

        if (analyses.length === 0) {
            emptyState.style.display = 'block';
            tableWrapper.style.display = 'none';
            return;
        }

        emptyState.style.display = 'none';
        tableWrapper.style.display = 'block';
        tableBody.innerHTML = '';

        analyses.slice(0, 5).forEach(a => {
            const tr = document.createElement('tr');
            const dateStr = a.completed_at ? new Date(a.completed_at).toLocaleDateString() : new Date(a.created_at).toLocaleDateString();
            const badge = a.is_sample ? ' <span class="card-badge">Sample</span>' : '';
            
            tr.innerHTML = `
                <td><strong>${escapeHtml(a.original_filename)}</strong>${badge}</td>
                <td><span class="card-badge">${a.file_type.toUpperCase()}</span></td>
                <td>${dateStr}</td>
                <td><span class="badge-pill badge-match">${escapeHtml(a.status)}</span></td>
                <td><a href="/results/${a.id}" class="btn btn-sm btn-outline">View Report →</a></td>
            `;
            tableBody.appendChild(tr);
        });
    }

    function loadLatestSummary(latestId) {
        fetch(`/api/analyses/${latestId}`)
            .then(res => res.json())
            .then(data => {
                const empty = document.getElementById('latestSummaryEmpty');
                const details = document.getElementById('latestAnalysisDetails');
                const title = document.getElementById('latestDocTitle');
                const time = document.getElementById('latestDocTime');
                const viewBtn = document.getElementById('viewLatestBtn');
                const badge = document.getElementById('latestAnalysisBadge');
                const grid = document.getElementById('latestStatsGrid');

                empty.style.display = 'none';
                details.style.display = 'block';

                const a = data.analysis;
                const s = data.summary;

                title.textContent = a.original_filename;
                time.textContent = `Analyzed ${new Date(a.completed_at || a.created_at).toLocaleString()}`;
                viewBtn.href = `/results/${a.id}`;

                badge.innerHTML = a.is_sample ? '<span class="sample-badge">Sample Document</span>' : '';

                grid.innerHTML = `
                    <div class="stat-card stat-conflict">
                        <div class="stat-number">${s.conflicts}</div>
                        <div class="stat-label">Conflicts</div>
                    </div>
                    <div class="stat-card stat-high">
                        <div class="stat-number">${s.high}</div>
                        <div class="stat-label">High Priority</div>
                    </div>
                    <div class="stat-card stat-match">
                        <div class="stat-number">${s.matches}</div>
                        <div class="stat-label">Matches</div>
                    </div>
                    <div class="stat-card stat-uncertain">
                        <div class="stat-number">${s.uncertain}</div>
                        <div class="stat-label">Uncertain</div>
                    </div>
                `;
            })
            .catch(() => {});
    }
});
