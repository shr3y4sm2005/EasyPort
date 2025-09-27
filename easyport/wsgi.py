import os
import sys
from app import create_app
from config import get_config

# Create application instance with proper configuration
config = get_config()
app = create_app(config)

if __name__ == '__main__':
    # This is only used for local development
    # In production, gunicorn will handle the WSGI app
    port = config.PORT
    debug = config.DEBUG
    
    print(f"Starting EasyPort on port {port} (debug={debug})")
    app.run(
        host='0.0.0.0', 
        port=port, 
        debug=debug,
        use_reloader=debug,
        threaded=True
    )
