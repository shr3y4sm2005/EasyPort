#!/usr/bin/env python3
"""
EasyPort Startup Script
Handles both development and production startup with proper configuration.
"""

import os
import sys
from pathlib import Path

def main():
    """Main startup function."""
    # Add the current directory to the Python path
    current_dir = Path(__file__).parent.absolute()
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    # Import after adding to path
    from app import create_app
    from config import get_config
    
    # Get configuration
    config = get_config()
    
    # Create application
    app = create_app(config)
    
    # Determine startup mode
    env = os.environ.get('FLASK_ENV', 'development').lower()
    
    if env == 'production':
        print("EasyPort starting in PRODUCTION mode")
        print("Use gunicorn or another WSGI server for production deployment")
        return app
    else:
        print(f"EasyPort starting in DEVELOPMENT mode on port {config.PORT}")
        app.run(
            host='0.0.0.0',
            port=config.PORT,
            debug=config.DEBUG,
            use_reloader=True,
            threaded=True
        )

if __name__ == '__main__':
    main()