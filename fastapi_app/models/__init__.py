"""
FastAPI数据模型
"""

from .auth import PasswordResetConfirm, PasswordResetRequest, TokenResponse, UserInfo, UserLogin, UserRegister
from .common import APIResponse
from .flights import (
    FlightAirport,
    FlightCarrier,
    FlightLeg,
    FlightLegFormatted,
    FlightPrice,
    FlightResult,
    FlightSearchRequest,
    FlightSearchResponse,
    MaxStops,
    MonitorDataResponse,
    MonitorFlightData,
    PassengerInfo,
    SeatClass,
    SortBy,
    TripType,
)

__all__ = [
    'UserInfo',
    'UserLogin',
    'UserRegister',
    'TokenResponse',
    'PasswordResetRequest',
    'PasswordResetConfirm',
    'APIResponse',
    'FlightSearchRequest',
    'FlightSearchResponse',
    'FlightResult',
    'FlightLeg',
    'FlightLegFormatted',
    'FlightPrice',
    'FlightCarrier',
    'FlightAirport',
    'PassengerInfo',
    'MonitorFlightData',
    'MonitorDataResponse',
    'SeatClass',
    'TripType',
    'SortBy',
    'MaxStops',
]
