import os
import sys
from flask import Flask, render_template, jsonify, request, send_from_directory
from dotenv import load_dotenv

load_dotenv()

from database import init_db, seed_default_policies, seed_default_settings

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-me')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('UPLOAD_MAX_SIZE_MB', 50)) * 1024 * 1024
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['REPORTS_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')

# Ensure directories exist
for folder in [app.config['UPLOAD_FOLDER'], app.config['REPORTS_FOLDER'], 'database']:
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), folder) if folder == 'database' else folder, exist_ok=True)

# Initialize database safely
try:
    init_db()
    seed_default_policies()
    seed_default_settings()
except Exception as e:
    app.logger.warning(f"Database init warning (can happen in concurrent workers): {e}")

# Import and register blueprints
from services.api_policies import policies_bp
from services.api_contracts import contracts_bp
from services.api_analyses import analyses_bp
from services.api_settings import settings_bp
from services.api_findings import findings_bp

app.register_blueprint(policies_bp)
app.register_blueprint(contracts_bp)
app.register_blueprint(analyses_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(findings_bp)


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/policies')
def policies_page():
    return render_template('policies.html')


@app.route('/results')
def results_page():
    return render_template('results.html')


@app.route('/results/<analysis_id>')
def results_detail_page(analysis_id):
    return render_template('results.html', analysis_id=analysis_id)


@app.route('/settings')
def settings_page():
    return render_template('settings.html')


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok', 'app': 'ClauseLens Trust'})


@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': f'File too large. Maximum size is {app.config["MAX_CONTENT_LENGTH"] // (1024*1024)} MB.'}), 413


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint not found.'}), 404
    return render_template('home.html'), 404


@app.errorhandler(500)
def server_error(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'An internal error occurred. Please try again.'}), 500
    return render_template('home.html'), 500


if __name__ == '__main__':
    print("=" * 60)
    print("  ClauseLens Trust - Contract Risk Review")
    print("  Running at http://127.0.0.1:5000")
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5000, debug=os.environ.get('FLASK_DEBUG', '0') == '1')
