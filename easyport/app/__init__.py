import os
import random
import time
import sys
from datetime import datetime
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash
from flask_cors import CORS
from dotenv import load_dotenv
import httpx
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
  LoginManager,
  login_user,
  login_required,
  logout_user,
  current_user,
  UserMixin,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from .schemas import RidesRequest, RidesResponse, RideOption
from .cache import TTLCache
from .providers import demo_quotes
import logging
try:
  from flask_wtf import CSRFProtect  # type: ignore
except Exception:
  class CSRFProtect:  # type: ignore
    def __init__(self, app=None):
      pass
    def init_app(self, app):
      pass
try:
  from flask_limiter import Limiter  # type: ignore
  from flask_limiter.util import get_remote_address  # type: ignore
except Exception:
  def get_remote_address():  # type: ignore
    return None
  class Limiter:  # type: ignore
    def __init__(self, key_func=None, app=None, default_limits=None):
      pass
    def limit(self, rule):
      def decorator(f):
        return f
      return decorator
try:
  import structlog  # type: ignore
  _HAS_STRUCTLOG = True
except Exception:
  _HAS_STRUCTLOG = False
  class _SimpleLogger:
    def __init__(self):
      logging.basicConfig(level=logging.INFO)
      self._log = logging.getLogger("easyport")
    def info(self, *args, **kwargs):
      self._log.info(str(args[0]) + " " + str({k: kwargs[k] for k in kwargs}))
    def error(self, *args, **kwargs):
      self._log.error(str(args[0]) + " " + str({k: kwargs[k] for k in kwargs}))
  class structlog:  # type: ignore
    @staticmethod
    def configure(processors=None):
      return None
    @staticmethod
    def get_logger():
      return _SimpleLogger()
try:
  from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST  # type: ignore
except Exception:
  class _NoopMetric:
    def labels(self, *args, **kwargs):
      return self
    def inc(self, *args, **kwargs):
      return None
    def observe(self, *args, **kwargs):
      return None
  def Counter(*args, **kwargs):  # type: ignore
    return _NoopMetric()
  def Histogram(*args, **kwargs):  # type: ignore
    return _NoopMetric()
  def generate_latest():  # type: ignore
    return b""
  CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"  # type: ignore


load_dotenv()


def setup_logging(app):
  """Configure application logging for production."""
  if not app.debug:
    # Production logging setup
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
      logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
      )
    )
    handler.setLevel(getattr(logging, app.config.get('LOG_LEVEL', 'INFO')))
    app.logger.addHandler(handler)
    app.logger.setLevel(getattr(logging, app.config.get('LOG_LEVEL', 'INFO')))
    
    # Remove default Flask handler to avoid duplicate logs
    app.logger.handlers = [handler]
  else:
    # Development logging
    logging.basicConfig(
      level=logging.DEBUG,
      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def create_app(config=None):
  # Load environment variables
  load_dotenv()
  
  # Import config here to avoid circular imports
  if config is None:
    from config import get_config
    config = get_config()
  
  # Create Flask app instance
  base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
  app = Flask(
    __name__,
    static_folder=os.path.join(base_dir, 'static'),
    template_folder=os.path.join(base_dir, 'templates')
  )
  
  # Load configuration
  app.config.from_object(config)
  
  # Configure proxy handling for Railway deployment
  app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
  
  # Setup logging
  setup_logging(app)
  
  # Initialize CORS
  CORS(app, resources={
    r"/api/*": {
      "origins": "*",
      "methods": ["GET", "POST", "OPTIONS"],
      "allow_headers": ["Content-Type", "Authorization"]
    }
  })

  # Initialize database
  db = SQLAlchemy(app)
  
  # Initialize login manager
  login_manager = LoginManager(app)
  login_manager.login_view = 'login'
  login_manager.login_message = 'Please log in to access this page.'
  login_manager.login_message_category = 'info'
  
  # Initialize CSRF protection
  csrf = CSRFProtect(app)

  # Initialize rate limiting with better configuration
  limiter = Limiter(
    get_remote_address, 
    app=app, 
    default_limits=["100 per minute"],
    storage_uri=app.config.get('RATELIMIT_STORAGE_URL', 'memory://')
  ) 

  # Structured logging
  structlog.configure(
    processors=[
      structlog.processors.TimeStamper(fmt="iso"),
      structlog.processors.add_log_level,
      structlog.processors.JSONRenderer()
    ]
  )
  log = structlog.get_logger()
  # Initialize caches with configuration
  geocode_cache = TTLCache(
    default_ttl_seconds=app.config.get('GEOCODE_CACHE_TIMEOUT', 3600), 
    max_items=5000
  )
  quotes_cache = TTLCache(
    default_ttl_seconds=app.config.get('QUOTES_CACHE_TIMEOUT', 60), 
    max_items=5000
  )

  # Prometheus metrics
  HTTP_REQUESTS = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
  HTTP_LATENCY = Histogram('http_request_latency_seconds', 'Latency of HTTP requests', ['endpoint'])

  class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
      self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
      return check_password_hash(self.password_hash, password)



  @login_manager.user_loader
  def load_user(user_id):
    return User.query.get(int(user_id))

  # Initialize database tables
  with app.app_context():
    try:
      db.create_all()
      app.logger.info("Database tables created successfully")
    except Exception as e:
      app.logger.error(f"Error creating database tables: {str(e)}")
      if not app.debug:
        # In production, we might want to fail fast
        raise

  # -----------------------------
  # Helpers
  # -----------------------------
  def normalize_ride(app_name: str, app_icon: str, vehicle_type: str, price: int,
                     eta_minutes: int, distance_km: float, surge: bool,
                     rating: float, deep_link: str, recommended: bool):
    return {
      "app": app_name,
      "appIcon": app_icon,
      "vehicleType": vehicle_type,
      "price": int(price),
      "estimatedTime": int(eta_minutes),
      "distance": float(distance_km),
      "surge": bool(surge),
      "rating": float(rating),
      "deepLink": deep_link,
      "recommended": bool(recommended),
    }

  async def geocode(address: str):
    """Minimal geocoding via OpenStreetMap Nominatim (no key, rate-limited)."""
    if not address:
      return None
    cached = geocode_cache.get(address.strip().lower())
    if cached is not None:
      return cached
    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": app.config.get('NOMINATIM_USER_AGENT', 'easyport/1.0')}
    params = {"q": address, "format": "json", "limit": 1}
    try:
      async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not data:
          return None
        first = data[0]
        coords = {"lat": float(first["lat"]), "lng": float(first["lon"]) }
        geocode_cache.set(address.strip().lower(), coords, ttl_seconds=app.config.get('GEOCODE_CACHE_TIMEOUT', 3600))
        return coords
    except Exception as e:
      app.logger.error(f"Geocoding error for '{address}': {str(e)}")
      return None

  # -----------------------------
  # Provider clients (placeholders; implement once you have access)
  # -----------------------------
  async def uber_quotes(src: dict, dst: dict, passengers: int):
    # TODO: Implement OAuth2 and pricing/ETA endpoints once approved
    # Return empty list until credentials/approval in place
    return []

  async def ola_quotes(src: dict, dst: dict, passengers: int):
    return []

  async def rapido_quotes(src: dict, dst: dict, passengers: int):
    return []

  async def indrive_quotes(src: dict, dst: dict, passengers: int):
    return []

  async def meru_quotes(src: dict, dst: dict, passengers: int):
    return []

  def generate_mock_ride_data(source, destination, passengers):
    base_price = random.uniform(100, 300)
    multiplier = 1.2 if passengers and int(passengers) > 1 else 1.0

    def rnd(val):
      return int(round(val))

    # Enhanced ride data with detailed categories and accessibility features
    rides = [
      {
        "id": 1,
        "app": "Uber",
        "appIcon": "🚗",
        "vehicleType": "UberGo",
        "vehicleCategory": "Economy",
        "price": rnd(base_price * multiplier * random.uniform(0.9, 1.1)),
        "estimatedTime": rnd(random.uniform(15, 35)),
        "distance": rnd(random.uniform(5, 20)),
        "deepLink": "uber://",
        "rating": 4.5,
        "surge": random.random() > 0.7,
        "features": ["AC", "Music", "Professional Driver"],
        "accessibility": ["Standard Access"],
        "maxPassengers": 4,
        "cancellationFee": rnd(20 + random.uniform(-5, 5)),
      },
      {
        "id": 2,
        "app": "Uber",
        "appIcon": "♿",
        "vehicleType": "UberWAV",
        "vehicleCategory": "Accessible",
        "price": rnd(base_price * multiplier * 1.1 * random.uniform(0.9, 1.1)),
        "estimatedTime": rnd(random.uniform(20, 40)),
        "distance": rnd(random.uniform(5, 20)),
        "deepLink": "uber://",
        "rating": 4.7,
        "surge": random.random() > 0.8,
        "features": ["AC", "Wheelchair Accessible", "Trained Driver"],
        "accessibility": ["Wheelchair Accessible", "Mobility Aid Friendly"],
        "maxPassengers": 3,
        "cancellationFee": rnd(25 + random.uniform(-5, 5)),
      },
      {
        "id": 3,
        "app": "Ola",
        "appIcon": "🚕",
        "vehicleType": "Mini",
        "vehicleCategory": "Economy",
        "price": rnd(base_price * multiplier * random.uniform(0.85, 1.15)),
        "estimatedTime": rnd(random.uniform(12, 37)),
        "distance": rnd(random.uniform(4, 22)),
        "deepLink": "olacabs://",
        "rating": 4.3,
        "surge": random.random() > 0.8,
        "features": ["AC", "Cashless", "24/7 Support"],
        "accessibility": ["Standard Access"],
        "maxPassengers": 4,
        "cancellationFee": rnd(15 + random.uniform(-3, 3)),
      },
      {
        "id": 4,
        "app": "Ola",
        "appIcon": "🚗",
        "vehicleType": "Prime Sedan",
        "vehicleCategory": "Premium",
        "price": rnd(base_price * multiplier * 1.4 * random.uniform(0.9, 1.1)),
        "estimatedTime": rnd(random.uniform(15, 30)),
        "distance": rnd(random.uniform(4, 22)),
        "deepLink": "olacabs://",
        "rating": 4.6,
        "surge": random.random() > 0.7,
        "features": ["AC", "Premium Interior", "Top Rated Driver"],
        "accessibility": ["Standard Access", "Extra Legroom"],
        "maxPassengers": 4,
        "cancellationFee": rnd(30 + random.uniform(-5, 5)),
      },
      {
        "id": 5,
        "app": "Rapido",
        "appIcon": "🛵",
        "vehicleType": "Bike",
        "vehicleCategory": "Two-Wheeler",
        "price": rnd(base_price * multiplier * 0.6 * random.uniform(0.9, 1.1)),
        "estimatedTime": rnd(random.uniform(8, 23)),
        "distance": rnd(random.uniform(3, 15)),
        "deepLink": "rapido://",
        "rating": 4.2,
        "surge": random.random() > 0.9,
        "features": ["Quick", "Affordable", "Traffic Friendly"],
        "accessibility": ["Standard Access"],
        "maxPassengers": 1,
        "cancellationFee": rnd(10 + random.uniform(-2, 2)),
      },
      {
        "id": 6,
        "app": "Rapido",
        "appIcon": "🛺",
        "vehicleType": "Auto",
        "vehicleCategory": "Three-Wheeler",
        "price": rnd(base_price * multiplier * 0.8 * random.uniform(0.9, 1.1)),
        "estimatedTime": rnd(random.uniform(12, 28)),
        "distance": rnd(random.uniform(3, 15)),
        "deepLink": "rapido://",
        "rating": 4.0,
        "surge": random.random() > 0.85,
        "features": ["Open Air", "Local Experience", "Economical"],
        "accessibility": ["Standard Access", "Easy Entry"],
        "maxPassengers": 3,
        "cancellationFee": rnd(8 + random.uniform(-2, 2)),
      },
      {
        "id": 7,
        "app": "Meru",
        "appIcon": "🚙",
        "vehicleType": "Sedan",
        "vehicleCategory": "Premium",
        "price": rnd(base_price * multiplier * 1.1 * random.uniform(0.9, 1.1)),
        "estimatedTime": rnd(random.uniform(18, 40)),
        "distance": rnd(random.uniform(6, 22)),
        "deepLink": "meru://",
        "rating": 4.4,
        "surge": False,
        "features": ["Premium", "AC", "Professional Service"],
        "accessibility": ["Standard Access", "Extra Legroom"],
        "maxPassengers": 4,
        "cancellationFee": rnd(25 + random.uniform(-5, 5)),
      },
      {
        "id": 8,
        "app": "InDrive",
        "appIcon": "🚐",
        "vehicleType": "SUV",
        "vehicleCategory": "Large",
        "price": rnd(base_price * multiplier * 1.3 * random.uniform(0.9, 1.1)),
        "estimatedTime": rnd(random.uniform(20, 45)),
        "distance": rnd(random.uniform(7, 25)),
        "deepLink": "indrive://",
        "rating": 4.1,
        "surge": random.random() > 0.6,
        "features": ["Spacious", "Group Travel", "Luggage Space"],
        "accessibility": ["Standard Access", "Wheelchair Storage"],
        "maxPassengers": 7,
        "cancellationFee": rnd(35 + random.uniform(-5, 8)),
      },
      {
        "id": 9,
        "app": "InDrive",
        "appIcon": "🚗",
        "vehicleType": "Comfort",
        "vehicleCategory": "Premium",
        "price": rnd(base_price * multiplier * 1.2 * random.uniform(0.9, 1.1)),
        "estimatedTime": rnd(random.uniform(15, 35)),
        "distance": rnd(random.uniform(7, 25)),
        "deepLink": "indrive://",
        "rating": 4.3,
        "surge": random.random() > 0.7,
        "features": ["Comfort", "AC", "Quality Vehicle"],
        "accessibility": ["Standard Access"],
        "maxPassengers": 4,
        "cancellationFee": rnd(20 + random.uniform(-3, 5)),
      },
    ]

    # Exclude single-seat bike options for groups larger than 1
    try:
      if int(passengers) > 1:
        rides = [r for r in rides if (r.get("vehicleType", "").lower() != "bike")]
    except Exception:
      pass

    return {
      "source": source,
      "destination": destination,
      "passengers": passengers,
      "timestamp": datetime.utcnow().isoformat() + "Z",
      "rides": rides,
    }

  # -----------------------------
  # Error Handlers
  # -----------------------------
  @app.errorhandler(404)
  def not_found_error(error):
    return render_template('index.html', error="Page not found"), 404

  @app.errorhandler(500)
  def internal_error(error):
    db.session.rollback()
    app.logger.error(f"Internal server error: {str(error)}")
    return render_template('index.html', error="Internal server error"), 500

  @app.errorhandler(429)
  def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded", "message": str(e.description)}), 429

  @app.errorhandler(413)
  def request_entity_too_large(error):
    return jsonify({"error": "Request too large"}), 413

  # -----------------------------
  # API Routes
  # -----------------------------
  @app.route('/api/health', methods=['GET'])
  def health():
    """Comprehensive health check endpoint for monitoring."""
    try:
      # Check database connection
      db_status = "ok"
      try:
        db.session.execute(db.text('SELECT 1'))
        db.session.commit()
      except Exception as e:
        db_status = f"error: {str(e)}"
      
      # Check cache functionality
      cache_status = "ok"
      try:
        test_key = "health_check_test"
        geocode_cache.set(test_key, "test_value", ttl_seconds=1)
        cached_value = geocode_cache.get(test_key)
        if cached_value != "test_value":
          cache_status = "error: cache not working"
      except Exception as e:
        cache_status = f"error: {str(e)}"
      
      health_data = {
        "status": "OK" if db_status == "ok" and cache_status == "ok" else "DEGRADED",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "environment": app.config.get('FLASK_ENV', 'unknown'),
        "checks": {
          "database": db_status,
          "cache": cache_status,
          "provider_api": "enabled" if app.config.get('PROVIDER_API_ENABLED') else "disabled"
        }
      }
      
      status_code = 200 if health_data["status"] == "OK" else 503
      return jsonify(health_data), status_code
      
    except Exception as e:
      return jsonify({
        "status": "ERROR",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "error": str(e)
      }), 500

  @app.route('/api/geocode', methods=['GET'])
  def api_geocode():
    try:
      q = (request.args.get('q') or '').strip()
      if not q:
        return jsonify({"results": []})
      # Simple pass-through to OSM with caching via the async helper
      import asyncio
      coords = asyncio.run(geocode(q))
      if not coords:
        return jsonify({"results": []})
      return jsonify({"results": [{"label": q, "lat": coords["lat"], "lng": coords["lng"]}]})
    except Exception as exc:
      return jsonify({"results": [], "error": str(exc)}), 500

  @csrf.exempt
  @app.route('/api/rides', methods=['POST'])
  @limiter.limit("30/minute")
  def rides():
    try:
      start_ts = time.time()
      parsed = RidesRequest.model_validate((request.get_json(silent=True) or {}))
      source = parsed.source
      destination = parsed.destination
      passengers = int(parsed.passengers)

      # cache key (works for mock and real providers)
      cache_key = f"{source}|{destination}|{passengers}"
      cached_quotes = quotes_cache.get(cache_key)
      if cached_quotes is not None:
        return jsonify(RidesResponse.model_validate(cached_quotes).model_dump())

      if not app.config['PROVIDER_API_ENABLED']:
        # Simulate API delay
        time.sleep(0.5)  # Reduced for better UX in production
        response_payload = generate_mock_ride_data(source, destination, passengers)
        quotes_cache.set(cache_key, response_payload, ttl_seconds=app.config.get('QUOTES_CACHE_TIMEOUT', 60))
        resp = RidesResponse.model_validate(response_payload).model_dump()
        
        HTTP_LATENCY.labels('/api/rides').observe(time.time() - start_ts)
        HTTP_REQUESTS.labels('POST', '/api/rides', '200').inc()
        log.info("rides_mock", source=source, destination=destination, passengers=passengers)
        return jsonify(resp)

      # Use async provider aggregation when feature-flag enabled
      async def assemble():
        src, dst = await asyncio.gather(geocode(source), geocode(destination))
        if not src or not dst:
          # Fallback to mock if geocoding fails
          return generate_mock_ride_data(source, destination, passengers)
        results = await asyncio.gather(
          uber_quotes(src, dst, passengers),
          ola_quotes(src, dst, passengers),
          rapido_quotes(src, dst, passengers),
          indrive_quotes(src, dst, passengers),
          meru_quotes(src, dst, passengers),
          demo_quotes(src, dst, passengers),
        )
        rides = [r for sub in results for r in sub]
        payload = {
          "source": source,
          "destination": destination,
          "passengers": passengers,
          "timestamp": datetime.utcnow().isoformat() + "Z",
          "rides": rides if rides else generate_mock_ride_data(source, destination, passengers)["rides"],
        }
        return RidesResponse.model_validate(payload).model_dump()

      import asyncio
      assembled = asyncio.run(assemble())
      quotes_cache.set(cache_key, assembled, ttl_seconds=app.config.get('QUOTES_CACHE_TIMEOUT', 60))
      
      HTTP_LATENCY.labels('/api/rides').observe(time.time() - start_ts)
      HTTP_REQUESTS.labels('POST', '/api/rides', '200').inc()
      log.info("rides_real", source=source, destination=destination, passengers=passengers, provider_enabled=True)
      return jsonify(assembled)
    except Exception as exc:
      HTTP_REQUESTS.labels('POST', '/api/rides', '500').inc()
      log.error("rides_error", error=str(exc))
      return jsonify({"error": "Failed to fetch ride data", "details": str(exc)}), 500



  @app.route('/metrics', methods=['GET'])
  def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

  # -----------------------------
  # Static and SPA Routes
  # -----------------------------
  @app.route('/')
  def index():
    return render_template('index.html', user=current_user if current_user.is_authenticated else None)

  @app.route('/book')
  def book():
    deep_link = request.args.get('dl', '')
    web_url = request.args.get('web', '')
    label = request.args.get('label', 'Ride')
    s = request.args.get('s', '')
    t = request.args.get('t', '')
    
    return render_template('book.html', deep_link=deep_link, web_url=web_url, label=label, s=s, t=t)





  # -----------------------------
  # Auth Routes
  # -----------------------------
  @app.route('/register', methods=['GET', 'POST'])
  def register():
    if request.method == 'POST':
      name = (request.form.get('name') or '').strip()
      email = (request.form.get('email') or '').strip().lower()
      password = request.form.get('password') or ''
      confirm = request.form.get('confirm') or ''

      if not name or not email or not password:
        flash('All fields are required', 'error')
        return redirect(url_for('register'))
      if password != confirm:
        flash('Passwords do not match', 'error')
        return redirect(url_for('register'))
      if User.query.filter_by(email=email).first():
        flash('Email already registered', 'error')
        return redirect(url_for('register'))

      user = User(name=name, email=email)
      user.set_password(password)
      db.session.add(user)
      db.session.commit()
      login_user(user)
      return redirect(url_for('index'))

    return render_template('register.html')

  @app.route('/login', methods=['GET', 'POST'])
  def login():
    if request.method == 'POST':
      email = (request.form.get('email') or '').strip().lower()
      password = request.form.get('password') or ''
      user = User.query.filter_by(email=email).first()
      if not user or not user.check_password(password):
        flash('Invalid email or password', 'error')
        return redirect(url_for('login'))
      login_user(user, remember=True)
      next_url = request.args.get('next') or url_for('index')
      return redirect(next_url)
    return render_template('login.html')

  @app.route('/logout', methods=['POST', 'GET'])
  @login_required
  def logout():
    logout_user()
    return redirect(url_for('index'))

  # Remove the run method as it's not needed for production deployment
  # The app will be served by gunicorn in production
  
  return app


