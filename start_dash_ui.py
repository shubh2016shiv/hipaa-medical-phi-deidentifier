#!/usr/bin/env python3
"""
DEID Patients - Dash UI Launcher

Simple launcher script for the professional Dash UI.
This script handles dependency checking and starts the web application.

Usage:
    python start_dash_ui.py

Requirements:
    - Python 3.7+
    - Required packages listed in requirements_dash.txt
"""

import sys
import subprocess
import importlib.util
import os

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 7):
        print("❌ Error: Python 3.7 or higher is required")
        print(f"   Current version: {sys.version}")
        return False
    return True

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = ['dash', 'plotly', 'pandas']
    missing_packages = []
    
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n💡 Install missing packages with:")
        print("   pip install -r requirements_dash.txt")
        return False
    
    return True

def install_dependencies():
    """Install required dependencies"""
    try:
        print("📦 Installing required dependencies...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements_dash.txt'])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def start_dash_ui():
    """Start the Dash UI application"""
    try:
        print("🚀 Starting DEID Patients Dash UI...")
        print("=" * 50)
        print("🏥 DEID Patients - Professional Clinical Data De-identification")
        print("👥 Target Audience: Clinicians and AI professionals")
        print("🔒 Focus: HIPAA-compliant clinical data de-identification")
        print("=" * 50)
        print("🔗 Application will be available at: http://localhost:8050")
        print("⏹️  Press Ctrl+C to stop the application")
        print("=" * 50)
        
        # Import and run the Dash app
        from dash_ui import app
        app.run_server(debug=False, host='0.0.0.0', port=8050)
        
    except ImportError as e:
        print(f"❌ Failed to import dash_ui module: {e}")
        print("   Make sure dash_ui.py is in the current directory")
        return False
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
        return True
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        return False

def main():
    """Main launcher function"""
    print("🏥 DEID Patients - Dash UI Launcher")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Check dependencies
    if not check_dependencies():
        print("\n🤔 Would you like to install missing dependencies? (y/n): ", end="")
        try:
            response = input().lower().strip()
            if response in ['y', 'yes']:
                if not install_dependencies():
                    sys.exit(1)
            else:
                print("❌ Cannot start without required dependencies")
                sys.exit(1)
        except KeyboardInterrupt:
            print("\n👋 Installation cancelled by user")
            sys.exit(1)
    
    # Start the application
    if not start_dash_ui():
        sys.exit(1)

if __name__ == '__main__':
    main()


