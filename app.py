"""
File Concatenator Web Application

A Flask-based web application that concatenates Python codebases for Large
Language Model (LLM) processing. Intelligently filters and combines text files
from directories while excluding hidden files, binary files, and virtual environments.

Copyright (c) 2025 UT Health Science Center San Antonio STEM STAIRWAY Coding Team
Author: UT Health Science Center San Antonio STEM STAIRWAY Coding Team
Date: July 27, 2025
PEP 8 Compliant: Yes
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import gc

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import tempfile

# Load environment variables
load_dotenv()

# Configure logging
log_dir = os.environ.get('LOG_DIR', 'logs')
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add rotating file handler
file_handler = RotatingFileHandler(
    os.path.join(log_dir, 'file_concatenator.log'),
    maxBytes=10485760,  # 10MB
    backupCount=5
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(file_handler)


class FileProcessor:
    """
    Handles file processing operations including filtering, concatenation,
    and statistics collection with multithreading and memory optimization.
    """

    def __init__(self):
        """Initialize the FileProcessor with default settings."""
        self.excluded_dirs = {'.venv', '__pycache__', '.git', 'node_modules', 'venv', 'env'}
        self.included_extensions = {
            '.py', '.txt', '.md', '.html', '.css', '.js', '.java', '.json',
            '.xml', '.yaml', '.yml', '.cfg', '.conf', '.log', '.env',
            '.example', '.gitignore', '.dockerfile', '.sql', '.sh', '.bat'
        }
        self.stats = {
            'total_files': 0,
            'concatenated_files': 0,
            'skipped_files': 0,
            'errors': [],
            'binary_files': 0,
            'hidden_files': 0,
            'processed_size': 0
        }
        self.num_workers = int(os.environ.get('NUM_WORKERS', 8))
        self.chunk_size = int(os.environ.get('CHUNK_SIZE', 65536))  # 64KB chunks
        self.max_file_size = int(os.environ.get('MAX_FILE_SIZE', 10485760))  # 10MB
        self.progress_queue = queue.Queue()
        self.lock = threading.Lock()

    def is_hidden(self, path: Path) -> bool:
        """
        Check if a file or directory is hidden.

        Args:
            path (Path): Path object to check

        Returns:
            bool: True if the path is hidden, False otherwise
        """
        return path.name.startswith('.')

    def is_text_file(self, file_path: Path) -> bool:
        """
        Determine if a file should be included based on extension and content.

        Args:
            file_path (Path): Path to the file to check

        Returns:
            bool: True if the file should be included, False otherwise
        """
        try:
            # Check if file has an included extension
            file_extension = file_path.suffix.lower()
            file_name = file_path.name.lower()

            # Special cases for files without extensions or special names
            special_files = {
                'readme', 'license', 'dockerfile', 'makefile',
                '.env.example', '.gitignore', '.env'
            }

            # Check extension whitelist
            if file_extension in self.included_extensions:
                return True

            # Check special filenames
            if file_name in special_files or any(file_name.startswith(sf) for sf in special_files):
                return True

            # Check if it's a text file by content (fallback)
            try:
                with open(file_path, 'rb') as file:
                    chunk = file.read(1024)
                    if b'\x00' in chunk:  # Null bytes indicate binary
                        return False

                # Try to decode as UTF-8
                with open(file_path, 'r', encoding='utf-8') as file:
                    file.read(1024)
                    return True

            except (UnicodeDecodeError, PermissionError, OSError):
                return False

        except Exception:
            return False

    def should_exclude_directory(self, dir_path: Path) -> bool:
        """
        Check if a directory should be excluded from processing.
        Only excludes specific problematic directories.

        Args:
            dir_path (Path): Directory path to check

        Returns:
            bool: True if directory should be excluded, False otherwise
        """
        dir_name = dir_path.name.lower()

        # Only exclude specific problematic directories
        if dir_name in self.excluded_dirs:
            return True

        # Allow hidden directories that might contain important files
        # Only exclude specific hidden dirs like .git
        if self.is_hidden(dir_path) and dir_name in {'.git', '.svn', '.hg'}:
            return True

        return False

    def collect_files_with_info(self, root_directory: str) -> List[Dict[str, Any]]:
        """
        Recursively collect all non-excluded files with metadata.

        Args:
            root_directory (str): Root directory path to process

        Returns:
            List[Dict]: List of file info dictionaries
        """
        files_info = []
        root_path = Path(root_directory)

        logger.info(f"Starting file collection in: {root_directory}")

        if not root_path.exists():
            error_msg = f"Directory does not exist: {root_directory}"
            self.stats['errors'].append(error_msg)
            logger.error(error_msg)
            return files_info

        try:
            # Use rglob to recursively find all files
            logger.info(f"Scanning all files recursively in: {root_directory}")

            for file_path in root_path.rglob('*'):
                if file_path.is_file():
                    self.stats['total_files'] += 1

                    logger.debug(f"Processing file: {file_path}")

                    # Check if the file is in an excluded directory tree
                    skip_file = False
                    relative_to_root = file_path.relative_to(root_path)

                    # Check each part of the path for exclusions
                    for part in relative_to_root.parts[:-1]:  # Exclude the filename itself
                        if part.lower() in {name.lower() for name in self.excluded_dirs}:
                            skip_file = True
                            logger.debug(f"Skipping {file_path} due to excluded directory: {part}")
                            break
                        # Only exclude .git and similar VCS directories
                        if part.startswith('.') and part.lower() in {'.git', '.svn', '.hg'}:
                            skip_file = True
                            logger.debug(f"Skipping {file_path} due to VCS directory: {part}")
                            break

                    if skip_file:
                        self.stats['skipped_files'] += 1
                        continue

                    # Check if file itself is hidden (but allow important hidden files)
                    if self.is_hidden(file_path) and not file_path.name.lower() in {'.env', '.env.example', '.gitignore'}:
                        self.stats['hidden_files'] += 1
                        self.stats['skipped_files'] += 1
                        logger.debug(f"Skipping hidden file: {file_path}")
                        continue

                    # Check if file should be included based on extension/content
                    if not self.is_text_file(file_path):
                        self.stats['binary_files'] += 1
                        self.stats['skipped_files'] += 1
                        logger.debug(f"Skipping non-text file: {file_path}")
                        continue

                    # Get file info
                    try:
                        file_stat = file_path.stat()
                        relative_path = file_path.relative_to(root_path)

                        file_info = {
                            'path': str(file_path),
                            'relative_path': str(relative_path),
                            'name': file_path.name,
                            'size': file_stat.st_size,
                            'modified': datetime.fromtimestamp(file_stat.st_mtime).isoformat(),
                            'selected': True  # Default to selected
                        }
                        files_info.append(file_info)
                        logger.debug(f"Added file: {relative_path}")

                    except (OSError, PermissionError) as e:
                        error_msg = f"Error accessing {file_path}: {str(e)}"
                        self.stats['errors'].append(error_msg)
                        logger.warning(error_msg)

        except PermissionError as e:
            error_msg = f"Permission denied: {str(e)}"
            self.stats['errors'].append(error_msg)
            logger.error(error_msg)
        except Exception as e:
            error_msg = f"Error collecting files: {str(e)}"
            self.stats['errors'].append(error_msg)
            logger.error(error_msg)

        logger.info(f"Collected {len(files_info)} files from {root_directory}")
        return files_info

    def collect_files(self, root_directory: str) -> List[Path]:
        """
        Recursively collect all non-excluded files from the directory.

        Args:
            root_directory (str): Root directory path to process

        Returns:
            List[Path]: List of file paths to process
        """
        files_to_process = []
        root_path = Path(root_directory)

        if not root_path.exists():
            self.stats['errors'].append(f"Directory does not exist: {root_directory}")
            return files_to_process

        try:
            # Use rglob to recursively find all files
            for file_path in root_path.rglob('*'):
                if file_path.is_file():
                    self.stats['total_files'] += 1

                    # Check if the file is in an excluded directory tree
                    skip_file = False
                    relative_to_root = file_path.relative_to(root_path)

                    # Check each part of the path for exclusions
                    for part in relative_to_root.parts[:-1]:  # Exclude the filename itself
                        if part.lower() in {name.lower() for name in self.excluded_dirs}:
                            skip_file = True
                            break
                        # Only exclude .git and similar VCS directories
                        if part.startswith('.') and part.lower() in {'.git', '.svn', '.hg'}:
                            skip_file = True
                            break

                    if skip_file:
                        self.stats['skipped_files'] += 1
                        continue

                    # Check if file itself is hidden (but allow important hidden files)
                    if self.is_hidden(file_path) and not file_path.name.lower() in {'.env', '.env.example', '.gitignore'}:
                        self.stats['hidden_files'] += 1
                        self.stats['skipped_files'] += 1
                        continue

                    # Check if file should be included based on extension/content
                    if not self.is_text_file(file_path):
                        self.stats['binary_files'] += 1
                        self.stats['skipped_files'] += 1
                        continue

                    files_to_process.append(file_path)

        except PermissionError as e:
            self.stats['errors'].append(f"Permission denied: {str(e)}")
        except Exception as e:
            self.stats['errors'].append(f"Error collecting files: {str(e)}")

        return files_to_process

    def concatenate_files(self, files: List[Path], root_directory: str) -> str:
        """
        Concatenate all files with headers into a single string.

        Args:
            files (List[Path]): List of file paths to concatenate
            root_directory (str): Root directory for relative path calculation

        Returns:
            str: Concatenated content of all files
        """
        concatenated_content = []
        root_path = Path(root_directory)

        # Add header with metadata
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        header = f"""# Python Codebase Concatenation for LLM Processing
# Generated: {timestamp}
# Source Directory: {root_directory}
# Total Files Processed: {len(files)}
# Purpose: Prepared for Large Language Model analysis
# Copyright (c) 2025 UT Health Science Center San Antonio STEM STAIRWAY Coding Team
# ================================================

"""
        concatenated_content.append(header)

        for file_path in sorted(files):
            try:
                # Calculate relative path from root directory
                relative_path = file_path.relative_to(root_path)

                # Create file header
                file_header = f"\n### {relative_path} ###\n"
                concatenated_content.append(file_header)

                # Read and append file content
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()
                    concatenated_content.append(content)
                    concatenated_content.append("\n\n")

                self.stats['concatenated_files'] += 1

            except Exception as e:
                error_msg = f"Error reading {file_path}: {str(e)}"
                self.stats['errors'].append(error_msg)
                concatenated_content.append(f"\n### ERROR: {relative_path} ###\n")
                concatenated_content.append(f"Could not read file: {str(e)}\n\n")

        return ''.join(concatenated_content)

    def read_file_chunk(self, file_path: Path, max_retries: int = 3) -> Optional[str]:
        """
        Read a single file with error handling and retries.

        Args:
            file_path (Path): Path to the file to read
            max_retries (int): Maximum number of retry attempts

        Returns:
            Optional[str]: File content or None if failed
        """
        for attempt in range(max_retries):
            try:
                # Check file size
                file_size = file_path.stat().st_size
                if file_size > self.max_file_size:
                    logger.warning(f"File {file_path} exceeds size limit, skipping")
                    return None

                # Read file in chunks for memory efficiency
                content_chunks = []
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    while True:
                        chunk = file.read(self.chunk_size)
                        if not chunk:
                            break
                        content_chunks.append(chunk)

                content = ''.join(content_chunks)

                # Update processed size
                with self.lock:
                    self.stats['processed_size'] += file_size

                logger.debug(f"Successfully read file: {file_path}")
                return content

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {file_path}: {str(e)}")
                if attempt == max_retries - 1:
                    error_msg = f"Failed to read {file_path} after {max_retries} attempts: {str(e)}"
                    with self.lock:
                        self.stats['errors'].append(error_msg)
                    logger.error(error_msg)
                    return None

        return None

    def process_file_batch(self, file_paths: List[Path], root_path: Path) -> List[str]:
        """
        Process a batch of files in parallel.

        Args:
            file_paths (List[Path]): List of file paths to process
            root_path (Path): Root directory path for relative paths

        Returns:
            List[str]: List of formatted file contents
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            # Submit file reading tasks
            future_to_path = {
                executor.submit(self.read_file_chunk, file_path): file_path
                for file_path in file_paths
            }

            # Collect results as they complete
            for future in as_completed(future_to_path):
                file_path = future_to_path[future]
                try:
                    content = future.result()
                    if content is not None:
                        # Calculate relative path
                        relative_path = file_path.relative_to(root_path)

                        # Format content with header
                        formatted_content = f"\n### {relative_path} ###\n{content}\n\n"
                        results.append((str(relative_path), formatted_content))

                        with self.lock:
                            self.stats['concatenated_files'] += 1
                    else:
                        with self.lock:
                            self.stats['skipped_files'] += 1

                except Exception as e:
                    error_msg = f"Error processing {file_path}: {str(e)}"
                    with self.lock:
                        self.stats['errors'].append(error_msg)
                    logger.error(error_msg)

        # Sort results by relative path for consistent output
        results.sort(key=lambda x: x[0])
        return [content for _, content in results]

    def concatenate_files_parallel(self, selected_files: List[Dict[str, Any]],
                                   root_directory: str) -> str:
        """
        Concatenate selected files using parallel processing and memory optimization.

        Args:
            selected_files (List[Dict]): List of selected file info dictionaries
            root_directory (str): Root directory for relative path calculation

        Returns:
            str: Concatenated content of all files
        """
        logger.info(f"Starting parallel concatenation of {len(selected_files)} files")

        root_path = Path(root_directory)

        # Add header with metadata
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        header = f"""# Python Codebase Concatenation for LLM Processing
# Generated: {timestamp}
# Source Directory: {root_directory}
# Total Files Selected: {len(selected_files)}
# Worker Threads: {self.num_workers}
# Purpose: Prepared for Large Language Model analysis
# Copyright (c) 2025 UT Health Science Center San Antonio STEM STAIRWAY Coding Team
# ================================================

"""

        # Convert to Path objects
        file_paths = [Path(file_info['path']) for file_info in selected_files]

        # Process files in batches to manage memory
        batch_size = max(1, len(file_paths) // self.num_workers)
        all_content = [header]

        for i in range(0, len(file_paths), batch_size):
            batch = file_paths[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} with {len(batch)} files")

            batch_content = self.process_file_batch(batch, root_path)
            all_content.extend(batch_content)

            # Force garbage collection after each batch
            gc.collect()

        logger.info("Parallel concatenation completed")
        return ''.join(all_content)

    def process_directory(self, directory_path: str) -> Tuple[str, Dict[str, Any]]:
        """
        Main processing function that handles the entire workflow.

        Args:
            directory_path (str): Path to the directory to process

        Returns:
            Tuple[str, Dict]: Concatenated content and statistics
        """
        # Reset stats for new processing
        self.stats = {
            'total_files': 0,
            'concatenated_files': 0,
            'skipped_files': 0,
            'errors': [],
            'binary_files': 0,
            'hidden_files': 0
        }

        # Collect and process files
        files_to_process = self.collect_files(directory_path)
        concatenated_content = self.concatenate_files(files_to_process, directory_path)

        return concatenated_content, self.stats


# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Global file processor instance
file_processor = FileProcessor()


@app.route('/')
def index():
    """
    Render the main application page.

    Returns:
        str: Rendered HTML template
    """
    return render_template('index.html')


@app.route('/list-files', methods=['POST'])
def list_files():
    """
    List files in a directory with metadata for selection.

    Returns:
        JSON: File listing with metadata
    """
    try:
        data = request.get_json()
        directory_path = data.get('directory_path', '')

        if not directory_path:
            return jsonify({
                'success': False,
                'error': 'Directory path is required'
            }), 400

        # Validate directory exists
        if not os.path.exists(directory_path):
            return jsonify({
                'success': False,
                'error': 'Directory does not exist'
            }), 400

        logger.info(f"Listing files in directory: {directory_path}")

        # Collect files with metadata
        files_info = file_processor.collect_files_with_info(directory_path)

        # Calculate total size
        total_size = sum(file_info['size'] for file_info in files_info)

        return jsonify({
            'success': True,
            'files': files_info,
            'stats': {
                'total_files': len(files_info),
                'total_size': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2)
            }
        })

    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'File listing error: {str(e)}'
        }), 500


@app.route('/process', methods=['POST'])
def process_directory():
    """
    Process the directory and return concatenated content with statistics.

    Returns:
        JSON: Processing results and statistics
    """
    try:
        data = request.get_json()
        directory_path = data.get('directory_path', '')
        selected_files = data.get('selected_files', [])
        use_parallel = data.get('use_parallel', True)

        if not directory_path:
            return jsonify({
                'success': False,
                'error': 'Directory path is required'
            }), 400

        if not selected_files:
            return jsonify({
                'success': False,
                'error': 'No files selected for processing'
            }), 400

        # Validate directory exists
        if not os.path.exists(directory_path):
            return jsonify({
                'success': False,
                'error': 'Directory does not exist'
            }), 400

        logger.info(f"Processing {len(selected_files)} selected files from {directory_path}")

        # Reset stats for new processing
        file_processor.stats = {
            'total_files': 0,
            'concatenated_files': 0,
            'skipped_files': 0,
            'errors': [],
            'binary_files': 0,
            'hidden_files': 0,
            'processed_size': 0
        }

        # Process the selected files
        if use_parallel:
            content = file_processor.concatenate_files_parallel(selected_files, directory_path)
        else:
            # Fallback to sequential processing
            file_paths = [Path(file_info['path']) for file_info in selected_files]
            content = file_processor.concatenate_files(file_paths, directory_path)

        # Store content in temporary file
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', delete=False, suffix='.txt', encoding='utf-8'
        )
        temp_file.write(content)
        temp_file.close()

        # Add processing metadata to stats
        stats = file_processor.stats.copy()
        stats['selected_files'] = len(selected_files)
        stats['processing_method'] = 'parallel' if use_parallel else 'sequential'
        stats['worker_threads'] = file_processor.num_workers if use_parallel else 1

        logger.info(f"Processing completed. Stats: {stats}")

        return jsonify({
            'success': True,
            'stats': stats,
            'temp_file': temp_file.name,
            'content_preview': content[:1000] + '...' if len(content) > 1000 else content
        })

    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Processing error: {str(e)}'
        }), 500


@app.route('/browse', methods=['POST'])
def browse_directory():
    """
    Browse directories and return subdirectories and path info.

    Returns:
        JSON: Directory listing with navigation info
    """
    try:
        data = request.get_json()
        current_path = data.get('path', '')

        # If no path provided, start with home directory
        if not current_path:
            current_path = os.path.expanduser('~')

        # Resolve and validate path
        current_path = os.path.abspath(current_path)

        # Security: Prevent directory traversal attacks
        # Get allowed base paths from environment or use safe defaults
        allowed_bases = os.environ.get('ALLOWED_BROWSE_PATHS', '').split(',')
        if not allowed_bases or allowed_bases == ['']:
            # Default to user's home directory if no restrictions set
            allowed_bases = [os.path.expanduser('~')]

        # Check if current path is within allowed bases
        path_allowed = False
        for base in allowed_bases:
            base = os.path.abspath(base.strip())
            if current_path.startswith(base):
                path_allowed = True
                break

        if not path_allowed:
            # If path not in allowed bases, default to first allowed base
            current_path = os.path.abspath(allowed_bases[0].strip())

        # Security check - ensure path exists and is readable
        if not os.path.exists(current_path):
            return jsonify({
                'success': False,
                'error': 'Path does not exist'
            }), 404

        if not os.access(current_path, os.R_OK):
            return jsonify({
                'success': False,
                'error': 'Permission denied'
            }), 403

        # Get parent directory (if not at root)
        parent_path = None
        if current_path != os.path.dirname(current_path):
            parent_path = os.path.dirname(current_path)

        # List directories only (not files)
        directories = []
        try:
            for item in sorted(os.listdir(current_path)):
                item_path = os.path.join(current_path, item)
                if os.path.isdir(item_path):
                    # Check if accessible
                    if os.access(item_path, os.R_OK):
                        directories.append({
                            'name': item,
                            'path': item_path,
                            'hidden': item.startswith('.')
                        })
        except PermissionError:
            # If we can't list the directory contents
            pass

        # Get path components for breadcrumb
        path_components = []
        temp_path = current_path
        while temp_path and temp_path != os.path.dirname(temp_path):
            path_components.append({
                'name': os.path.basename(temp_path) or temp_path,
                'path': temp_path
            })
            temp_path = os.path.dirname(temp_path)
        path_components.reverse()

        return jsonify({
            'success': True,
            'current_path': current_path,
            'parent_path': parent_path,
            'directories': directories,
            'path_components': path_components
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Browse error: {str(e)}'
        }), 500


@app.route('/download', methods=['POST'])
def download_file():
    """
    Generate and serve the concatenated file for download.

    Returns:
        File: Downloadable concatenated file
    """
    try:
        data = request.get_json()
        temp_file_path = data.get('temp_file', '')
        filename = data.get('filename', 'concatenated_files.txt')

        # Secure the filename
        filename = secure_filename(filename)
        if not filename.endswith('.txt'):
            filename += '.txt'

        if not os.path.exists(temp_file_path):
            return jsonify({
                'success': False,
                'error': 'Temporary file not found'
            }), 404

        # Send file and clean up
        def remove_file(response):
            try:
                os.unlink(temp_file_path)
            except OSError:
                pass
            return response

        return send_file(
            temp_file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Download error: {str(e)}'
        }), 500


if __name__ == '__main__':
    # Get configuration from environment variables
    host = os.environ.get('FLASK_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    app.run(debug=debug, host=host, port=port)
