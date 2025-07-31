# File Concatenator Web Application

A Flask-based web application that concatenates Python codebases for Large Language Model (LLM) processing. Intelligently filters and combines text files from directories while excluding hidden files, binary files, and virtual environments.

## 🔥 **Copyright © 2025 UT Health Science Center San Antonio STEM STAIRWAY Coding Team** 🔥

## Features

- **Web-based Interface**: Professional UI built with Bootstrap 5
- **Directory Browser**: Interactive directory navigation with modal interface
  - Browse local directories visually
  - Breadcrumb navigation for easy path tracking
  - Security restrictions to prevent unauthorized access
- **File Selection Interface**: Choose specific files to process
  - Individual file selection with checkboxes
  - Select All / Deselect All functionality
  - Real-time file size and count display
  - Default: all files selected
- **Smart File Filtering**: Includes all relevant development files:
  - **Programming Languages**: .py, .java, .js, .html, .css, .sql, .sh, .bat
  - **Documentation**: .md, .txt, README files
  - **Configuration**: .json, .xml, .yaml, .yml, .cfg, .conf, .env, .env.example
  - **Logs and Templates**: .log files, template directories
  - **Special Files**: .gitignore, Dockerfile, Makefile
  - **Excludes**: Binary files, .venv, __pycache__, .git, node_modules
- **Performance Optimization**:
  - Multithreaded file processing (configurable worker count, default 8)
  - Memory-efficient chunked file reading
  - Batch processing for large file sets
  - Automatic garbage collection
- **Comprehensive Logging**: Rotating log files with detailed processing information
- **Error Mitigation**: Retry mechanisms and graceful failure handling
- **Real-time Statistics**: Enhanced metrics including processing method, data volume, and performance
- **Download Functionality**: Generate and download concatenated files
- **Secure File Handling**: Proper validation and secure filename handling

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd file_concatenator
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Usage

1. Run the application:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

3. Enter a directory path in the input field or use the Browse button
4. Click "List Files" to see available files in the directory
5. Select/deselect individual files or use "Select All"/"Deselect All"
6. Click "Process Selected" to concatenate chosen files
7. Review the enhanced statistics including processing metrics
8. Download the concatenated file

## Configuration

The application uses environment variables for configuration. See `.env.example` for available options:

- `FLASK_HOST`: Host to bind the server (default: 0.0.0.0)
- `FLASK_PORT`: Port to run the server (default: 5000)
- `FLASK_DEBUG`: Enable debug mode (default: False)
- `SECRET_KEY`: Flask secret key for sessions
- `ALLOWED_BROWSE_PATHS`: Comma-separated list of allowed base paths for directory browsing (default: user's home directory)
- `NUM_WORKERS`: Number of worker threads for parallel processing (default: 8)
- `CHUNK_SIZE`: File reading chunk size in bytes (default: 65536)
- `MAX_FILE_SIZE`: Maximum individual file size in bytes (default: 10485760)
- `LOG_DIR`: Directory for log files (default: logs)

## Project Structure

```
file_concatenator/
├── app.py              # Main Flask application
├── templates/
│   └── index.html      # Web interface
├── requirements.txt    # Python dependencies
├── .env               # Environment configuration
├── .env.example       # Example configuration
├── .gitignore         # Git ignore file
└── README.md          # This file
```

## API Endpoints

- `GET /` - Main web interface
- `POST /list-files` - List files in directory with metadata
- `POST /process` - Process selected files and return statistics
- `POST /browse` - Browse directory structure
- `POST /download` - Download concatenated file

## Security Notes

- The application validates all directory paths
- Filenames are sanitized before download
- Temporary files are cleaned up after download
- No user data is stored permanently

## Development

To run in development mode with auto-reload:

```bash
FLASK_DEBUG=True python app.py
```

## License

**🔥 Copyright © 2025 UT Health Science Center San Antonio STEM STAIRWAY Coding Team 🔥**

This project is provided as-is for educational and professional use.