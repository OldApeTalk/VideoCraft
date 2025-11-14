#!/usr/bin/env python3
"""
PyInstaller build script for VideoCraft project.
This script packages the entire project into a standalone executable.

Requirements:
- Install PyInstaller: pip install pyinstaller
- Ensure all dependencies in requirements.txt are installed

Usage:
python build_exe.py
"""

import os
import sys
import PyInstaller.__main__

def build_exe():
    # Get the absolute path to the main script
    main_script = os.path.join(os.path.dirname(__file__), 'src', 'VideoCraft.py')

    # PyInstaller arguments
    args = [
        main_script,  # Main script
        '--onefile',  # Create a single executable file
        '--name=VideoCraft',  # Name of the executable
        '--windowed',  # Prevent console window from appearing (for GUI apps)
        '--clean',  # Clean cache and temporary files
        '--noconfirm',  # Replace output directory without confirmation
        # Collect all submodules for complex libraries
        '--collect-all=yt_dlp',
        '--collect-all=deepl',
        # Add data files if needed (e.g., config files, assets)
        '--add-data=src;src',  # Include src folder so sub-scripts can be accessed
        # Hidden imports for dependencies that might not be auto-detected
        '--hidden-import=yt_dlp',
        '--hidden-import=requests',
        '--hidden-import=srt',
        '--hidden-import=ffmpeg',
        '--hidden-import=deepl',
        '--hidden-import=urllib.parse',
        '--hidden-import=threading',
        '--hidden-import=re',
        '--hidden-import=math',
    ]

    # Run PyInstaller
    PyInstaller.__main__.run(args)

if __name__ == "__main__":
    print("Building VideoCraft executable with PyInstaller...")
    build_exe()
    print("Build completed. Check the 'dist' folder for the executable.")