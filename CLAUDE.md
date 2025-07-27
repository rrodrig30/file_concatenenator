# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a File Concatenator Web Application project that's designed to be implemented as a Flask-based web service. The project currently contains only the design specifications and implementation instructions in `instructions.md`.

## Project Status

The File Concatenator Web Application is fully implemented and functional. The application:
- Allows users to select a directory and concatenate all text files within it
- Excludes hidden files, binary files, and virtual environment directories
- Provides a professional web UI with real-time feedback
- Offers download functionality for concatenated files
- Uses environment variables for configuration
- Follows PEP 8 coding standards

## Implementation Requirements

Based on the specifications in `instructions.md`, the implementation requires:

### Technology Stack
- **Backend**: Flask (Python 3.8+)
- **Frontend**: HTML5, CSS3, Bootstrap 5, JavaScript
- **Dependencies**: Flask, Werkzeug

### Project Structure (to be created)
```
file_concatenator/
├── app.py              # Main Flask application
├── templates/
│   └── index.html      # Web interface
├── requirements.txt    # Python dependencies
```

### Key Components to Implement

1. **FileProcessor Class** (`app.py`): Core logic for file operations
   - File filtering (hidden, binary, excluded directories)
   - Recursive file collection
   - Content concatenation with headers

2. **Flask Routes**:
   - `/` - Main interface
   - `/process` - Directory processing endpoint
   - `/download` - File download endpoint

3. **Web Interface** (`templates/index.html`):
   - Directory input form
   - Processing statistics display
   - Content preview
   - Download functionality

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the Flask application
python app.py

# The application will run on http://localhost:5000

# Run linting (optional)
pip install flake8
flake8 app.py --max-line-length=88 --extend-ignore=E501
```

## Implementation Notes

- The specifications include complete code implementations in `instructions.md`
- All code should follow PEP 8 guidelines
- The application excludes: `.venv`, `__pycache__`, `.git`, `node_modules`, hidden files, and binary files
- Error handling and user feedback are emphasized in the design