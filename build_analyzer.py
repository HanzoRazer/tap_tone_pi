#!/usr/bin/env python3
"""
Build script for Tap Tone Analyzer desktop application.

Usage:
    python build_analyzer.py          # Build for current platform
    python build_analyzer.py --onefile  # Single executable
    python build_analyzer.py --debug    # Debug build with console

Requirements:
    pip install pyinstaller
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def get_platform():
    """Get current platform name."""
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    else:
        return "linux"


def build_analyzer(onefile: bool = False, debug: bool = False):
    """Build the analyzer application."""
    project_root = Path(__file__).parent
    analyzer_dir = project_root / "analyzer"
    build_dir = project_root / "build"
    dist_dir = project_root / "dist"

    # Clean previous builds
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    # Base PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "TapToneAnalyzer",
        "--windowed",  # No console window
        "--noconfirm",  # Overwrite without asking
    ]

    # Platform-specific options
    platform = get_platform()

    if platform == "windows":
        # Windows icon
        icon_path = project_root / "assets" / "icon.ico"
        if icon_path.exists():
            cmd.extend(["--icon", str(icon_path)])

    elif platform == "macos":
        # macOS bundle options
        icon_path = project_root / "assets" / "icon.icns"
        if icon_path.exists():
            cmd.extend(["--icon", str(icon_path)])
        cmd.extend([
            "--osx-bundle-identifier", "com.taptonepi.analyzer"
        ])

    # Single file or directory
    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # Debug mode (show console)
    if debug:
        cmd.remove("--windowed")
        cmd.append("--console")

    # Hidden imports (Qt plugins that PyInstaller might miss)
    hidden_imports = [
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "matplotlib.backends.backend_qtagg",
        "scipy.signal",
        "scipy.fft",
    ]
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    # Data files
    # cmd.extend(["--add-data", f"assets{os.pathsep}assets"])

    # Entry point
    cmd.append(str(analyzer_dir / "app.py"))

    print(f"Building for {platform}...")
    print(f"Command: {' '.join(cmd)}")

    # Run PyInstaller
    result = subprocess.run(cmd, cwd=str(project_root))

    if result.returncode == 0:
        print(f"\n✓ Build successful!")
        print(f"  Output: {dist_dir}")

        if platform == "windows":
            exe_path = dist_dir / "TapToneAnalyzer" / "TapToneAnalyzer.exe"
            if onefile:
                exe_path = dist_dir / "TapToneAnalyzer.exe"
            print(f"  Executable: {exe_path}")

        elif platform == "macos":
            app_path = dist_dir / "TapToneAnalyzer.app"
            print(f"  Application: {app_path}")

        else:
            bin_path = dist_dir / "TapToneAnalyzer" / "TapToneAnalyzer"
            if onefile:
                bin_path = dist_dir / "TapToneAnalyzer"
            print(f"  Binary: {bin_path}")

    else:
        print(f"\n✗ Build failed with code {result.returncode}")
        sys.exit(1)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build Tap Tone Analyzer")
    parser.add_argument("--onefile", action="store_true",
                        help="Build as single executable")
    parser.add_argument("--debug", action="store_true",
                        help="Build with console for debugging")

    args = parser.parse_args()

    build_analyzer(onefile=args.onefile, debug=args.debug)


if __name__ == "__main__":
    main()
