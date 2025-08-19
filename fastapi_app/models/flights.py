"""
FastAPI版本的航班数据模型
基于Pydantic模型，适配原有数据结构
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator


class SeatClass(str, Enum):
    """座位等级枚举"""
    ECONOMY = "ECONOMY"
    PREMIUM_ECONOMY = "PREMIUM_ECONOMY"
    BUSINESS = "BUSINESS"
    FIRST = "FIRST"


class TripType(str, Enum):
    """行程类型枚举"""
    ONE_WAY = "ONE_WAY"
    ROUND_TRIP = "ROUND_TRIP"


class SortBy(str, Enum):
    """排序方式枚举"""
    BEST = "BEST"
    CHEAPEST = "CHEAPEST"
    DURATION = "DURATION"
    DEPARTURE_TIME = "DEPARTURE_TIME"
    ARRIVAL_TIME = "ARRIVAL_TIME"
    TOP_FLIGHTS = "TOP_FLIGHTS"


class MaxStops(str, Enum):
    """最大中转次数枚举"""
    ANY = "ANY"
    NON_STOP = "NON_STOP"
    ONE_STOP_OR_FEWER = "ONE_STOP_OR_FEWER"
    TWO_OR_FEWER_STOPS = "TWO_OR_FEWER_STOPS"


class PassengerInfo(BaseModel):
    """乘客信息"""
    adults: int = Field(default=1, ge=1, le=9, description="成人数量")
    children: int = Field(default=0, ge=0, le=8, description="儿童数量(2-11岁)")
    infants_in_seat: int = Field(default=0, ge=0, le=8, description="婴儿占座数量(0-2岁)")
    infants_on_lap: int = Field(default=0, ge=0, le=8, description="婴儿怀抱数量(0-2岁)")
    
    @property
    def total_passengers(self) -> int:
        """总乘客数"""
        return self.adults + self.children + self.infants_in_seat + self.infants_on_lap


class FlightSearchRequest(BaseModel):
    """航班搜索请求"""
    departure_code: str = Field(..., min_length=3, max_length=3, description="出发机场代码")
    destination_code: str = Field(..., min_length=3, max_length=3, description="目的地机场代码")
    depart_date: str = Field(..., description="出发日期(YYYY-MM-DD)")
    return_date: Optional[str] = Field(None, description="返程日期(YYYY-MM-DD)")
    passengers: PassengerInfo = Field(default_factory=PassengerInfo, description="乘客信息")
    seat_class: SeatClass = Field(default=SeatClass.ECONOMY, description="座位等级")
    max_stops: MaxStops = Field(default=MaxStops.ANY, description="最大中转次数")
    sort_by: SortBy = Field(default=SortBy.CHEAPEST, description="排序方式")
    
    @validator('departure_code', 'destination_code')
    def validate_airport_codes(cls, v):
        """验证机场代码格式"""
        if not v.isalpha() or len(v) != 3:
            raise ValueError('机场代码必须是3位字母')
        return v.upper()
    
    @validator('depart_date', 'return_date')
    def validate_dates(cls, v):
        """验证日期格式"""
        if v is None:
            return v
        try:
            datetime.strptime(v, '%Y-%m-%d')
            return v
        except ValueError:
            raise ValueError('日期格式必须是YYYY-MM-DD')
    
    @property
    def trip_type(self) -> TripType:
        """根据是否有返程日期确定行程类型"""
        return TripType.ROUND_TRIP if self.return_date else TripType.ONE_WAY


class FlightLeg(BaseModel):
    """航段信息"""
    airline_code: str = Field(..., description="航空公司代码")
    airline_name: str = Field(..., description="航空公司名称")
    flight_number: str = Field(..., description="航班号")
    departure_airport: str = Field(..., description="出发机场代码")
    arrival_airport: str = Field(..., description="到达机场代码")
    departure_time: datetime = Field(..., description="出发时间")
    arrival_time: datetime = Field(..., description="到达时间")
    duration_minutes: int = Field(..., ge=0, description="飞行时长(分钟)")
    aircraft_type: Optional[str] = Field(None, description="机型")
    
    @property
    def duration_formatted(self) -> str:
        """格式化的飞行时长"""
        hours = self.duration_minutes // 60
        minutes = self.duration_minutes % 60
        return f"{hours}h {minutes}m"


class FlightPrice(BaseModel):
    """航班价格信息"""
    amount: float = Field(..., ge=0, description="价格金额")
    currency: str = Field(default="USD", description="货币代码")
    formatted: str = Field(..., description="格式化价格显示")


class FlightCarrier(BaseModel):
    """航空公司信息"""
    name: str = Field(..., description="航空公司名称")
    logoUrl: str = Field(default="", description="航空公司Logo URL")


class FlightAirport(BaseModel):
    """机场信息"""
    city: str = Field(..., description="城市名称")
    displayCode: str = Field(..., description="机场代码")


class FlightLegFormatted(BaseModel):
    """格式化的航段信息（前端兼容格式）"""
    departure: str = Field(..., description="出发时间ISO格式")
    arrival: str = Field(..., description="到达时间ISO格式")
    durationInMinutes: int = Field(..., description="飞行时长(分钟)")
    origin: FlightAirport = Field(..., description="出发机场信息")
    destination: FlightAirport = Field(..., description="到达机场信息")
    carriers: Dict[str, List[FlightCarrier]] = Field(..., description="航空公司信息")
    flightNumber: str = Field(..., description="航班号")


class FlightResult(BaseModel):
    """航班搜索结果"""
    price: FlightPrice = Field(..., description="价格信息")
    legs: List[FlightLegFormatted] = Field(default_factory=list, description="航段列表")
    stops: int = Field(default=0, ge=0, description="中转次数")
    isDirect: bool = Field(default=True, description="是否直飞")
    stopsText: str = Field(default="直飞", description="中转次数文本")
    layovers: List[Dict[str, Any]] = Field(default_factory=list, description="中转信息")
    duration: str = Field(..., description="总飞行时长")
    airline: str = Field(..., description="主要航空公司")
    flightNumber: str = Field(..., description="主要航班号")
    departureTime: str = Field(..., description="出发时间(HH:MM)")
    arrivalTime: str = Field(..., description="到达时间(HH:MM)")
    departureDateTime: Optional[str] = Field(None, description="出发时间ISO格式")
    arrivalDateTime: Optional[str] = Field(None, description="到达时间ISO格式")
    bookingUrl: str = Field(default="", description="预订链接")
    source: str = Field(default="smart-flights", description="数据源")


class FlightSearchResponse(BaseModel):
    """航班搜索响应"""
    success: bool = Field(..., description="搜索是否成功")
    data: Dict[str, List[FlightResult]] = Field(..., description="搜索结果数据")
    flights: List[FlightResult] = Field(default_factory=list, description="航班列表(向后兼容)")
    search_info: Dict[str, Any] = Field(..., description="搜索信息")
    source: str = Field(default="smart-flights", description="数据源")
    search_time: str = Field(..., description="搜索时间")
    total_count: int = Field(default=0, description="结果总数")
    message: Optional[str] = Field(None, description="响应消息")
    error: Optional[str] = Field(None, description="错误信息")


class MonitorFlightData(BaseModel):
    """监控页面航班数据"""
    destination: str = Field(..., description="目的地名称")
    code: str = Field(..., description="目的地代码")
    country: str = Field(..., description="国家")
    price: int = Field(..., description="价格")
    currency: str = Field(default="CNY", description="货币")
    departDate: str = Field(..., description="出发日期")
    returnDate: str = Field(default="", description="返程日期")
    image: str = Field(..., description="目的地图片URL")
    heat: int = Field(..., description="热度值")
    tags: str = Field(default="", description="标签")
    bookingUrl: str = Field(default="", description="预订链接")
    visaStatus: Optional[str] = Field(None, description="签证状态")
    popularity: int = Field(..., description="热度百分比")
    attractions: List[str] = Field(default_factory=list, description="景点列表")


class MonitorDataResponse(BaseModel):
    """监控数据响应"""
    success: bool = Field(..., description="请求是否成功")
    flights: List[MonitorFlightData] = Field(default_factory=list, description="航班数据")
    stats: Dict[str, Any] = Field(..., description="统计信息")
    city_name: str = Field(..., description="城市名称")
    city_flag: str = Field(..., description="城市旗帜emoji")
    error: Optional[str] = Field(None, description="错误信息")


class APIResponse(BaseModel):
    """通用API响应格式"""
    success: bool = Field(..., description="请求是否成功")
    message: str = Field(..., description="响应消息")
    data: Optional[Any] = Field(None, description="响应数据")
    error: Optional[str] = Field(None, description="错误信息")
