from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.config_loader import get_agronomic_config
from app.providers.factory import get_satellite_provider, get_weather_provider
from app.schemas.analysis import (
    AnalysisListResponse,
    AnalysisRequest,
    AnalysisResponse,
    SatelliteTimeseriesResponse,
    WeatherResponse,
)
from app.services import analysis as analysis_service
from app.services.fields import get_field_or_404
from app.settings import get_settings

router = APIRouter(prefix="/api/fields/{field_id}", tags=["analyses"])


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run a deterministic water-balance analysis for a field (fixture data only)",
)
def analyze_field(
    field_id: int, payload: AnalysisRequest, db: Session = Depends(get_db)
) -> AnalysisResponse:
    return analysis_service.analyze_field(db, field_id, payload.analysis_date)


@router.get("/analyses", response_model=AnalysisListResponse)
def list_analyses(
    field_id: int,
    limit: int | None = Query(default=None, ge=1, description="Defaults to DEFAULT_LIST_LIMIT"),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> AnalysisListResponse:
    settings = get_settings()
    effective_limit = min(limit or settings.default_list_limit, settings.max_list_limit)
    return analysis_service.list_analyses(db, field_id, limit=effective_limit, offset=offset)


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(
    field_id: int, analysis_id: int, db: Session = Depends(get_db)
) -> AnalysisResponse:
    return analysis_service.get_analysis_response(db, field_id, analysis_id)


@router.get(
    "/satellite-timeseries",
    response_model=SatelliteTimeseriesResponse,
    summary="Fixture-mode Sentinel-2-style index time series (DEMO / FIXTURE DATA)",
)
def get_satellite_timeseries(
    field_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> SatelliteTimeseriesResponse:
    field = get_field_or_404(db, field_id)
    settings = get_settings()
    config = get_agronomic_config()

    resolved_end = end_date or date.today()
    resolved_start = start_date or (
        resolved_end - timedelta(days=config.water_balance_defaults.satellite.lookback_days)
    )

    provider = get_satellite_provider()
    series = provider.get_index_timeseries_for_range(
        field.geojson_polygon, resolved_start, resolved_end
    )
    return SatelliteTimeseriesResponse(
        field_id=field_id,
        data_mode=settings.data_mode.value,
        provider=series.provider,
        source=series.source,
        retrieved_at=series.retrieved_at,
        cache_hit=series.cache_hit,
        rejected_acquisitions=[r.model_dump(mode="json") for r in series.rejected_acquisitions],
        observations=[obs.model_dump(mode="json") for obs in series.observations],
    )


@router.get(
    "/weather",
    response_model=WeatherResponse,
    summary="Fixture-mode weather history + forecast (DEMO / FIXTURE DATA)",
)
def get_weather(
    field_id: int,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> WeatherResponse:
    field = get_field_or_404(db, field_id)
    settings = get_settings()
    config = get_agronomic_config()

    as_of = date.today()
    resolved_start = start_date or (
        as_of - timedelta(days=config.water_balance_defaults.satellite.lookback_days)
    )
    forecast_window_days = -(-config.recommendation_defaults.forecast_rain.window_hours // 24)
    resolved_end = end_date or (as_of + timedelta(days=forecast_window_days))

    provider = get_weather_provider()
    series = provider.get_daily_series_for_range(
        field.centroid_latitude, field.centroid_longitude, resolved_start, resolved_end, as_of=as_of
    )
    return WeatherResponse(
        field_id=field_id,
        data_mode=settings.data_mode.value,
        provider=series.provider,
        source=series.source,
        retrieved_at=series.retrieved_at,
        cache_hit=series.cache_hit,
        coverage=series.coverage.model_dump(mode="json") if series.coverage else None,
        timezone=series.timezone,
        days=[day.model_dump(mode="json") for day in series.days],
    )
