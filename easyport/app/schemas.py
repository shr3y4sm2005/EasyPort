from pydantic import BaseModel, Field, conint, confloat
from typing import List, Optional


class RidesRequest(BaseModel):
  source: str = Field(min_length=1)
  destination: str = Field(min_length=1)
  passengers: conint(ge=1, le=6) = 1


class RideOption(BaseModel):
  id: Optional[int]
  app: str
  appIcon: Optional[str]
  vehicleType: str
  vehicleCategory: Optional[str] = None
  price: conint(ge=0)
  estimatedTime: conint(ge=0)
  distance: confloat(ge=0)
  deepLink: Optional[str] = None
  rating: Optional[confloat(ge=0, le=5)] = None
  surge: Optional[bool] = None
  features: Optional[List[str]] = None
  accessibility: Optional[List[str]] = None
  maxPassengers: Optional[int] = None
  cancellationFee: Optional[int] = None


class RidesResponse(BaseModel):
  source: Optional[str]
  destination: Optional[str]
  passengers: Optional[int]
  timestamp: str
  rides: List[RideOption]


