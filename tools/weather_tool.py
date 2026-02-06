"""
OpenWeatherMap API Tool for AI Operations Assistant.
Provides current weather and forecast information.
"""

import time
from typing import Any, Dict, List

from .base import BaseTool, ToolResult, ToolAction, ToolParameter
from config import get_settings
from utils.cache import cached_api_call
from utils.logger import get_logger

logger = get_logger(__name__)


class WeatherTool(BaseTool):
    """Tool for fetching weather information from OpenWeatherMap."""
    
    BASE_URL = "https://api.openweathermap.org/data/2.5"
    
    @property
    def name(self) -> str:
        return "weather"
    
    @property
    def description(self) -> str:
        return "Get current weather conditions and forecasts for any city"
    
    @property
    def actions(self) -> List[ToolAction]:
        return [
            ToolAction(
                name="get_current_weather",
                description="Get current weather for a city",
                parameters=[
                    ToolParameter(name="city", type="string", description="City name (e.g., 'London', 'New York', 'Tokyo')"),
                    ToolParameter(name="units", type="string", description="Temperature units", required=False, default="metric", enum=["metric", "imperial", "kelvin"]),
                ]
            ),
            ToolAction(
                name="get_forecast",
                description="Get 5-day weather forecast for a city",
                parameters=[
                    ToolParameter(name="city", type="string", description="City name"),
                    ToolParameter(name="units", type="string", description="Temperature units", required=False, default="metric", enum=["metric", "imperial", "kelvin"]),
                ]
            ),
        ]
    
    def _get_unit_symbol(self, units: str) -> str:
        """Get temperature unit symbol."""
        return {"metric": "°C", "imperial": "°F", "kelvin": "K"}.get(units, "°C")
    
    async def execute(self, action: str, parameters: Dict[str, Any]) -> ToolResult:
        """Execute a weather API action."""
        start_time = time.time()
        
        try:
            if action == "get_current_weather":
                return await self._get_current_weather(start_time, **parameters)
            elif action == "get_forecast":
                return await self._get_forecast(start_time, **parameters)
            else:
                return self._timed_result(
                    start_time, False,
                    error=f"Unknown action: {action}. Available: {[a.name for a in self.actions]}"
                )
        except Exception as e:
            logger.error(f"Weather API error: {e}", extra={"action": action})
            return self._timed_result(start_time, False, error=str(e))
    
    @cached_api_call(ttl_seconds=600)  # Cache weather for 10 minutes
    async def _get_current_weather(
        self,
        start_time: float,
        city: str,
        units: str = "metric"
    ) -> ToolResult:
        """Get current weather for a city."""
        settings = get_settings()
        client = await self.get_http_client()
        
        url = f"{self.BASE_URL}/weather"
        params = {
            "q": city,
            "appid": settings.openweathermap_api_key,
            "units": units
        }
        
        response = await client.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        unit_symbol = self._get_unit_symbol(units)
        
        result = {
            "city": data["name"],
            "country": data["sys"]["country"],
            "temperature": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "temp_min": data["main"]["temp_min"],
            "temp_max": data["main"]["temp_max"],
            "unit": unit_symbol,
            "humidity": data["main"]["humidity"],
            "pressure": data["main"]["pressure"],
            "condition": data["weather"][0]["main"],
            "description": data["weather"][0]["description"],
            "wind_speed": data["wind"]["speed"],
            "wind_direction": data["wind"].get("deg", 0),
            "clouds": data["clouds"]["all"],
            "visibility": data.get("visibility", 0) / 1000,  # Convert to km
            "sunrise": data["sys"]["sunrise"],
            "sunset": data["sys"]["sunset"]
        }
        
        logger.info(f"Retrieved weather for {city}: {result['temperature']}{unit_symbol}")
        
        return self._timed_result(start_time, True, data=result)
    
    @cached_api_call(ttl_seconds=1800)  # Cache forecast for 30 minutes
    async def _get_forecast(
        self,
        start_time: float,
        city: str,
        units: str = "metric"
    ) -> ToolResult:
        """Get 5-day forecast for a city."""
        settings = get_settings()
        client = await self.get_http_client()
        
        url = f"{self.BASE_URL}/forecast"
        params = {
            "q": city,
            "appid": settings.openweathermap_api_key,
            "units": units
        }
        
        response = await client.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        unit_symbol = self._get_unit_symbol(units)
        
        # Extract daily forecasts (every 8 entries = 1 day, since data is 3-hourly)
        forecasts = []
        for item in data["list"][::8][:5]:  # Get one entry per day, max 5 days
            forecasts.append({
                "datetime": item["dt_txt"],
                "temperature": item["main"]["temp"],
                "feels_like": item["main"]["feels_like"],
                "humidity": item["main"]["humidity"],
                "condition": item["weather"][0]["main"],
                "description": item["weather"][0]["description"],
                "wind_speed": item["wind"]["speed"],
                "clouds": item["clouds"]["all"]
            })
        
        result = {
            "city": data["city"]["name"],
            "country": data["city"]["country"],
            "unit": unit_symbol,
            "forecast_days": len(forecasts),
            "forecasts": forecasts
        }
        
        return self._timed_result(start_time, True, data=result)
