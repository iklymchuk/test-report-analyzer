# Dashboard configuration

# API Configuration
DEFAULT_API_URL = "http://localhost:8000"
API_TIMEOUT = 10  # seconds

# UI Configuration
PAGE_TITLE = "Test Report Analyzer"
PAGE_ICON = "📊"
LAYOUT = "wide"

# Chart colors
COLORS = {
    'primary': '#007bff',
    'success': '#28a745',
    'warning': '#ffc107',
    'danger': '#dc3545',
    'info': '#17a2b8',
    'secondary': '#6c757d'
}

# Thresholds
THRESHOLDS = {
    'health_score': {
        'excellent': 80,
        'good': 60,
        'fair': 40
    },
    'flakiness': {
        'critical': 0.5,
        'high': 0.3,
        'medium': 0.15
    },
    'slow_test': {
        'default': 5.0,  # seconds
        'min': 0.5,
        'max': 30.0
    }
}

# Display limits
DISPLAY_LIMITS = {
    'recent_runs': 20,
    'flaky_tests': 50,
    'slow_tests': 50,
    'clusters': 10,
    'chart_items': 15
}

# Cache TTL (seconds)
CACHE_TTL = {
    'health': 60,
    'stats': 30,
    'runs': 60,
    'tests': 300
}

# Feature flags
FEATURES = {
    'ai_insights': True,
    'export_reports': True,
    'real_time_updates': False
}
