#!/bin/bash
# Setup script for Test Report Analyzer

set -e  # Exit on error

echo "========================================="
echo "Test Report Analyzer - Setup"
echo "========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists. Removing old one..."
    rm -rf venv
fi

python3 -m venv venv
echo "✓ Virtual environment created"

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip
echo "✓ pip upgraded"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Initialize database
echo ""
echo "Initializing database..."
python init_db.py
echo "✓ Database initialized"

# Verify database
echo ""
echo "Verifying database..."
if [ -f "data/test_reports.db" ]; then
    DB_SIZE=$(ls -lh data/test_reports.db | awk '{print $5}')
    echo "✓ Database file created: data/test_reports.db ($DB_SIZE)"
    
    # Check schema
    TABLE_COUNT=$(sqlite3 data/test_reports.db "SELECT COUNT(*) FROM sqlite_master WHERE type='table';")
    echo "✓ Tables created: $TABLE_COUNT tables"
else
    echo "✗ Database file not found!"
    exit 1
fi

# Test with sample report
echo ""
echo "Testing with sample report..."
python ingest_report.py tests/fixtures/sample_report.xml \
    --project demo-project \
    --branch main \
    --commit abc123 \
    --init-db

echo ""
echo "========================================="
echo "Setup complete! ✓"
echo "========================================="
echo ""
echo "To activate the virtual environment:"
echo "  source venv/bin/activate"
echo ""
echo "To test the parser:"
echo "  python ingestion/junit_parser.py tests/fixtures/sample_report.xml"
echo ""
echo "To ingest a report:"
echo "  python ingest_report.py tests/fixtures/sample_report.xml --project my-app"
echo ""
echo "To check the database:"
echo "  sqlite3 data/test_reports.db"
echo "  sqlite> .tables"
echo "  sqlite> .schema test_runs"
echo "  sqlite> SELECT * FROM test_runs;"
echo ""
