/**
 * ClauseLens Trust - Policy Management
 * Built-in and Custom Policy CRUD with Unsaved Changes Detection
 */

document.addEventListener('DOMContentLoaded', () => {
    let originalPoliciesState = null;
    let hasUnsavedChanges = false;
    let builtInPolicies = [];
    let customPolicies = [];

    const saveBtn = document.getElementById('savePoliciesBtn');
    const restoreDefaultsBtn = document.getElementById('restoreDefaultsBtn');
    const unsavedWarningBar = document.getElementById('unsavedWarningBar');

    // Custom Policy Modal controls
    const openAddCustomModalBtn = document.getElementById('openAddCustomModalBtn');
    const customPolicyModal = document.getElementById('customPolicyModal');
    const closeCustomModalBtn = document.getElementById('closeCustomModalBtn');
    const cancelCustomModalBtn = document.getElementById('cancelCustomModalBtn');
    const saveCustomPolicyBtn = document.getElementById('saveCustomPolicyBtn');
    const customMatchType = document.getElementById('custom_match_type');
    const customMaxValueGroup = document.getElementById('customMaxValueGroup');

    loadPolicies();

    // Listen for changes to mark unsaved
    const inputs = document.querySelectorAll('.policy-card input, .policy-card select');
    inputs.forEach(input => {
        input.addEventListener('change', markUnsaved);
        input.addEventListener('input', markUnsaved);
    });

    window.addEventListener('beforeunload', (e) => {
        if (hasUnsavedChanges) {
            e.preventDefault();
            e.returnValue = 'You have unsaved policy changes. Are you sure you want to leave?';
        }
    });

    function markUnsaved() {
        hasUnsavedChanges = true;
        unsavedWarningBar.style.display = 'block';
    }

    function markSaved() {
        hasUnsavedChanges = false;
        unsavedWarningBar.style.display = 'none';
    }

    // Custom Match Type change
    customMatchType.addEventListener('change', () => {
        if (customMatchType.value === 'number_max') {
            customMaxValueGroup.style.display = 'block';
        } else {
            customMaxValueGroup.style.display = 'none';
        }
    });

    // Custom Modal Open / Close
    openAddCustomModalBtn.addEventListener('click', () => {
        resetCustomModal();
        customPolicyModal.style.display = 'flex';
    });

    function closeCustomModal() {
        customPolicyModal.style.display = 'none';
    }

    closeCustomModalBtn.addEventListener('click', closeCustomModal);
    cancelCustomModalBtn.addEventListener('click', closeCustomModal);

    function resetCustomModal() {
        document.getElementById('custom_name').value = '';
        document.getElementById('custom_description').value = '';
        document.getElementById('custom_match_type').value = 'must_not_contain';
        document.getElementById('custom_severity').value = 'medium';
        document.getElementById('custom_keywords').value = '';
        document.getElementById('custom_max_value').value = '';
        document.getElementById('custom_expected').value = '';
        customMaxValueGroup.style.display = 'none';
    }

    function loadPolicies() {
        fetch('/api/policies')
            .then(res => res.json())
            .then(data => {
                const policies = data.policies || [];
                builtInPolicies = policies.filter(p => !p.is_custom);
                customPolicies = policies.filter(p => p.is_custom);

                populateBuiltInPolicies(builtInPolicies);
                renderCustomPolicies(customPolicies);
                markSaved();
            })
            .catch(() => {
                showToast('Failed to load policies.', 'error');
            });
    }

    function populateBuiltInPolicies(policies) {
        policies.forEach(p => {
            const config = p.config || {};
            const enabled = p.enabled;

            if (p.category === 'payment') {
                document.getElementById('policy_payment_enabled').checked = enabled;
                if (config.max_payment_days) {
                    document.getElementById('policy_payment_max_days').value = config.max_payment_days;
                }
            } else if (p.category === 'renewal') {
                document.getElementById('policy_renewal_enabled').checked = enabled;
                document.getElementById('policy_renewal_auto_allowed').checked = !!config.auto_renewal_allowed;
                if (config.max_renewal_term_months) {
                    document.getElementById('policy_renewal_max_term').value = config.max_renewal_term_months;
                }
                if (config.min_cancellation_notice_days) {
                    document.getElementById('policy_renewal_min_notice').value = config.min_cancellation_notice_days;
                }
            } else if (p.category === 'liability') {
                document.getElementById('policy_liability_enabled').checked = enabled;
                document.getElementById('policy_liability_unlimited_allowed').checked = !!config.unlimited_liability_allowed;
                document.getElementById('policy_liability_require_cap').checked = config.require_liability_cap !== false;
            } else if (p.category === 'termination') {
                document.getElementById('policy_termination_enabled').checked = enabled;
                if (config.min_notice_days) {
                    document.getElementById('policy_termination_min_notice').value = config.min_notice_days;
                }
                document.getElementById('policy_termination_flag_onesided').checked = config.flag_one_sided_termination !== false;
            } else if (p.category === 'jurisdiction') {
                document.getElementById('policy_jurisdiction_enabled').checked = enabled;
                if (config.preferred_jurisdiction) {
                    document.getElementById('policy_jurisdiction_preferred').value = config.preferred_jurisdiction;
                }
                if (config.accepted_jurisdictions) {
                    document.getElementById('policy_jurisdiction_accepted').value = config.accepted_jurisdictions.join(', ');
                }
            }
        });
    }

    function renderCustomPolicies(policies) {
        const list = document.getElementById('customPoliciesList');
        const empty = document.getElementById('noCustomPolicies');

        if (policies.length === 0) {
            empty.style.display = 'block';
            list.innerHTML = '';
            list.appendChild(empty);
            return;
        }

        empty.style.display = 'none';
        list.innerHTML = '';

        policies.forEach(p => {
            const config = p.config || {};
            const item = document.createElement('div');
            item.className = 'custom-rule-item';
            
            const matchDesc = config.match_type === 'must_not_contain' 
                ? 'Must NOT Contain' 
                : (config.match_type === 'must_contain' ? 'Must Contain' : `Number Max (${config.max_value})`);

            item.innerHTML = `
                <div>
                    <div class="custom-rule-title">
                        ${escapeHtml(p.name)} 
                        <span class="badge-pill badge-${config.severity || 'medium'}">${(config.severity || 'medium').toUpperCase()}</span>
                    </div>
                    <div class="custom-rule-meta">
                        Type: <strong>${matchDesc}</strong> • Keywords: <code>${escapeHtml(config.keywords || '')}</code>
                        ${config.description ? ` • ${escapeHtml(config.description)}` : ''}
                    </div>
                </div>
                <div>
                    <button type="button" class="btn btn-sm btn-ghost btn-danger-text delete-custom-btn" data-id="${p.id}">Delete</button>
                </div>
            `;
            list.appendChild(item);
        });

        // Attach delete listeners
        document.querySelectorAll('.delete-custom-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.getAttribute('data-id');
                if (confirm('Delete this custom policy rule?')) {
                    deleteCustomPolicy(id);
                }
            });
        });
    }

    // Save Policies
    saveBtn.addEventListener('click', () => {
        // Collect form data
        const maxPaymentDays = parseInt(document.getElementById('policy_payment_max_days').value, 10);
        if (isNaN(maxPaymentDays) || maxPaymentDays <= 0) {
            showToast('Max payment days must be a positive number.', 'error');
            return;
        }

        const maxRenewalTerm = parseInt(document.getElementById('policy_renewal_max_term').value, 10);
        const minRenewalNotice = parseInt(document.getElementById('policy_renewal_min_notice').value, 10);
        if (isNaN(maxRenewalTerm) || maxRenewalTerm <= 0 || isNaN(minRenewalNotice) || minRenewalNotice <= 0) {
            showToast('Renewal term and notice days must be positive numbers.', 'error');
            return;
        }

        const minTerminationNotice = parseInt(document.getElementById('policy_termination_min_notice').value, 10);
        if (isNaN(minTerminationNotice) || minTerminationNotice <= 0) {
            showToast('Termination notice days must be a positive number.', 'error');
            return;
        }

        const preferredJurisdiction = document.getElementById('policy_jurisdiction_preferred').value.trim();
        if (!preferredJurisdiction) {
            showToast('Preferred jurisdiction cannot be empty.', 'error');
            return;
        }

        const acceptedRaw = document.getElementById('policy_jurisdiction_accepted').value;
        const acceptedJurisdictions = acceptedRaw.split(',').map(s => s.trim()).filter(Boolean);

        // Build policies array to send
        const updatedPolicies = builtInPolicies.map(p => {
            if (p.category === 'payment') {
                return {
                    id: p.id,
                    name: p.name,
                    category: 'payment',
                    enabled: document.getElementById('policy_payment_enabled').checked,
                    config: { max_payment_days: maxPaymentDays }
                };
            } else if (p.category === 'renewal') {
                return {
                    id: p.id,
                    name: p.name,
                    category: 'renewal',
                    enabled: document.getElementById('policy_renewal_enabled').checked,
                    config: {
                        auto_renewal_allowed: document.getElementById('policy_renewal_auto_allowed').checked,
                        max_renewal_term_months: maxRenewalTerm,
                        min_cancellation_notice_days: minRenewalNotice
                    }
                };
            } else if (p.category === 'liability') {
                return {
                    id: p.id,
                    name: p.name,
                    category: 'liability',
                    enabled: document.getElementById('policy_liability_enabled').checked,
                    config: {
                        unlimited_liability_allowed: document.getElementById('policy_liability_unlimited_allowed').checked,
                        require_liability_cap: document.getElementById('policy_liability_require_cap').checked
                    }
                };
            } else if (p.category === 'termination') {
                return {
                    id: p.id,
                    name: p.name,
                    category: 'termination',
                    enabled: document.getElementById('policy_termination_enabled').checked,
                    config: {
                        min_notice_days: minTerminationNotice,
                        flag_one_sided_termination: document.getElementById('policy_termination_flag_onesided').checked
                    }
                };
            } else if (p.category === 'jurisdiction') {
                return {
                    id: p.id,
                    name: p.name,
                    category: 'jurisdiction',
                    enabled: document.getElementById('policy_jurisdiction_enabled').checked,
                    config: {
                        preferred_jurisdiction: preferredJurisdiction,
                        accepted_jurisdictions: acceptedJurisdictions.length > 0 ? acceptedJurisdictions : [preferredJurisdiction]
                    }
                };
            }
            return p;
        });

        fetch('/api/policies', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ policies: updatedPolicies })
        })
        .then(async res => {
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to save policies.');
            return data;
        })
        .then(() => {
            showToast('Policies saved successfully.', 'success');
            markSaved();
            loadPolicies();
        })
        .catch(err => {
            showToast(err.message, 'error');
        });
    });

    // Restore Defaults
    restoreDefaultsBtn.addEventListener('click', () => {
        if (!confirm('Are you sure you want to restore built-in policies to their default values?')) {
            return;
        }

        fetch('/api/policies/restore-defaults', { method: 'POST' })
            .then(async res => {
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Failed to restore defaults.');
                return data;
            })
            .then(() => {
                showToast('Default policies restored.', 'success');
                markSaved();
                loadPolicies();
            })
            .catch(err => {
                showToast(err.message, 'error');
            });
    });

    // Save Custom Policy
    saveCustomPolicyBtn.addEventListener('click', () => {
        const name = document.getElementById('custom_name').value.trim();
        const description = document.getElementById('custom_description').value.trim();
        const matchType = document.getElementById('custom_match_type').value;
        const severity = document.getElementById('custom_severity').value;
        const keywords = document.getElementById('custom_keywords').value.trim();
        const maxValRaw = document.getElementById('custom_max_value').value;
        const expected = document.getElementById('custom_expected').value.trim();

        if (!name) {
            showToast('Policy name is required.', 'error');
            return;
        }
        if (!keywords) {
            showToast('At least one keyword is required.', 'error');
            return;
        }

        const config = {
            match_type: matchType,
            keywords: keywords,
            severity: severity,
            description: description,
            expected_condition: expected
        };

        if (matchType === 'number_max') {
            const maxVal = parseFloat(maxValRaw);
            if (isNaN(maxVal)) {
                showToast('Valid numeric maximum is required for Number Max type.', 'error');
                return;
            }
            config.max_value = maxVal;
        }

        fetch('/api/policies/custom', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name, config: config, enabled: true })
        })
        .then(async res => {
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to create custom policy.');
            return data;
        })
        .then(() => {
            closeCustomModal();
            showToast('Custom policy created.', 'success');
            loadPolicies();
        })
        .catch(err => {
            showToast(err.message, 'error');
        });
    });

    function deleteCustomPolicy(id) {
        fetch(`/api/policies/custom/${id}`, { method: 'DELETE' })
            .then(async res => {
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Failed to delete policy.');
                return data;
            })
            .then(() => {
                showToast('Custom policy deleted.', 'info');
                loadPolicies();
            })
            .catch(err => {
                showToast(err.message, 'error');
            });
    }
});
