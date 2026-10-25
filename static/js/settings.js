/**
 * ClauseLens Trust - Settings Page
 * Theme selection, language, privacy, and data deletion
 */

document.addEventListener('DOMContentLoaded', () => {
    const themeRadios = document.querySelectorAll('input[name="themeSelection"]');
    const languageSelect = document.getElementById('languageSelect');
    const keepFilesToggle = document.getElementById('keepUploadedFilesToggle');
    const defaultSeverityFilter = document.getElementById('defaultSeverityFilter');
    const defaultCategoryFilter = document.getElementById('defaultCategoryFilter');
    const saveSettingsBtn = document.getElementById('saveSettingsBtn');
    const restoreSettingsBtn = document.getElementById('restoreDefaultSettingsBtn');
    const deleteAllDataBtn = document.getElementById('deleteAllDataBtn');

    loadSettings();

    // Theme radio change updates theme instantly
    themeRadios.forEach(radio => {
        radio.addEventListener('change', () => {
            applyTheme(radio.value);
        });
    });

    function loadSettings() {
        fetch('/api/settings')
            .then(res => res.json())
            .then(data => {
                const s = data.settings || {};
                
                // Theme
                const themeVal = s.theme || 'light';
                const matchedRadio = document.querySelector(`input[name="themeSelection"][value="${themeVal}"]`);
                if (matchedRadio) matchedRadio.checked = true;

                // Language
                if (s.language && languageSelect) {
                    languageSelect.value = s.language;
                }

                // Keep files
                if (keepFilesToggle) {
                    keepFilesToggle.checked = s.keep_uploaded_files === 'true';
                }

                // Default filters
                if (s.default_severity_filter && defaultSeverityFilter) {
                    defaultSeverityFilter.value = s.default_severity_filter;
                }
                if (s.default_category_filter && defaultCategoryFilter) {
                    defaultCategoryFilter.value = s.default_category_filter;
                }
            })
            .catch(() => {});
    }

    saveSettingsBtn.addEventListener('click', () => {
        const selectedTheme = document.querySelector('input[name="themeSelection"]:checked').value;
        const selectedLanguage = languageSelect.value;
        const keepFiles = keepFilesToggle.checked ? 'true' : 'false';
        const defSev = defaultSeverityFilter.value;
        const defCat = defaultCategoryFilter.value;

        const updatedSettings = {
            theme: selectedTheme,
            language: selectedLanguage,
            keep_uploaded_files: keepFiles,
            default_severity_filter: defSev,
            default_category_filter: defCat
        };

        fetch('/api/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ settings: updatedSettings })
        })
        .then(async res => {
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to save settings.');
            return data;
        })
        .then(() => {
            applyTheme(selectedTheme);
            showToast('Settings saved successfully.', 'success');
        })
        .catch(err => {
            showToast(err.message, 'error');
        });
    });

    restoreSettingsBtn.addEventListener('click', () => {
        if (!confirm('Restore all settings to their default values?')) return;

        fetch('/api/settings/restore-defaults', { method: 'POST' })
            .then(async res => {
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Failed to restore defaults.');
                return data;
            })
            .then(() => {
                showToast('Default settings restored.', 'success');
                loadSettings();
                applyTheme('light');
            })
            .catch(err => {
                showToast(err.message, 'error');
            });
    });

    deleteAllDataBtn.addEventListener('click', () => {
        const confirmed = confirm('WARNING: Are you sure you want to permanently delete all uploaded files, analyses, findings, and review notes? This action cannot be undone.');
        if (!confirmed) return;

        fetch('/api/settings/delete-data', { method: 'POST' })
            .then(async res => {
                const data = await res.json();
                if (!res.ok) throw new Error(data.error || 'Failed to delete data.');
                return data;
            })
            .then(() => {
                showToast('All analysis data and files have been permanently deleted.', 'info');
            })
            .catch(err => {
                showToast(err.message, 'error');
            });
    });
});
