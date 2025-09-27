import random
from typing import Dict, List


async def demo_quotes(src: Dict[str, float], dst: Dict[str, float], passengers: int) -> List[dict]:
  base = random.uniform(110, 240)
  multiplier = 1.15 if int(passengers) > 1 else 1.0

  def rnd(val):
    return int(round(val))

  # Simulate two vehicle classes from a demo provider
  quotes = [
    {
      "app": "DemoCab",
      "appIcon": "🚖",
      "vehicleType": "Economy",
      "price": rnd(base * multiplier * random.uniform(0.9, 1.05)),
      "estimatedTime": rnd(random.uniform(10, 28)),
      "distance": rnd(random.uniform(4, 18)),
      "deepLink": "democab://book",
      "rating": 4.2,
      "surge": random.random() > 0.75,
      "features": ["AC", "Digital Payment"],
      "recommended": int(passengers) <= 3,
    },
    {
      "app": "DemoCab",
      "appIcon": "🚖",
      "vehicleType": "Premium",
      "price": rnd(base * multiplier * 1.25 * random.uniform(0.95, 1.1)),
      "estimatedTime": rnd(random.uniform(12, 32)),
      "distance": rnd(random.uniform(4, 18)),
      "deepLink": "democab://book",
      "rating": 4.6,
      "surge": random.random() > 0.65,
      "features": ["AC", "Music", "Professional Driver"],
      "recommended": int(passengers) > 3,
    },
  ]

  # Filter bike-like options if passengers > 1 (not applicable here, but keep pattern)
  try:
    if int(passengers) > 1:
      quotes = [q for q in quotes if (q.get("vehicleType", "").lower() != "bike")]
  except Exception:
    pass

  return quotes


