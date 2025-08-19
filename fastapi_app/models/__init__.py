"""
FastAPI数据模型
"""

from .auth import UserInfo, UserLogin, UserRegister, TokenResponse, PasswordResetRequest, PasswordResetConfirm
from .common import APIResponse
from .flights import (
    FlightSearchRequest, FlightSearchResponse, FlightResult, FlightLeg, FlightLegFormatted,
    FlightPrice, FlightCarrier, FlightAirport, PassengerInfo, MonitorFlightData,
    MonitorDataResponse, SeatClass, TripType, SortBy, MaxStops
)

__all__ = [
    'UserInfo', 'UserLogin', 'UserRegister', 'TokenResponse', 'PasswordResetRequest', 'PasswordResetConfirm',
    'APIResponse',
    'FlightSearchRequest', 'FlightSearchResponse', 'FlightResult', 'FlightLeg', 'FlightLegFormatted',
    'FlightPrice', 'FlightCarrier', 'FlightAirport', 'PassengerInfo', 'MonitorFlightData',
    'MonitorDataResponse', 'SeatClass', 'TripType', 'SortBy', 'MaxStops'
]
