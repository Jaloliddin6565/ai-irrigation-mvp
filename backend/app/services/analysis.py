"""Orchestrates one field analysis: crop stage -> water balance ->
initialization -> satellite qualification -> recommendation -> confidence
-> persistence.

Fixture-mode only in this phase (Phase 3): DATA_MODE=live is not wired up
yet — see docs/data_modes.md. This is a deterministic calculation
pipeline, not a trained AI model — see CLAUDE.md.

ANALYSIS_METHODOLOGY_VERSION versions this orchestration/calculation code
itself; the individual YAML config files carry their own
methodology_version for the agronomic VALUES, which is a separate concern
(see docs/methodology.md).
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models.analysis import Analysis
from app.db.models.enums import AnalysisDataMode, IrrigationMethod
from app.db.models.field import Field
from app.db.models.irrigation_event import IrrigationEvent
from app.domain.confidence import compute_confidence
from app.domain.config_loader import CropProfile, SoilProfile, get_agronomic_config
from app.domain.crop_stage import CropGrowthStage, determine_crop_stage
from app.domain.initialization import (
    InitializationMethod,
    IrrigationEventInput,
    determine_initialization,
)
from app.domain.irrigation_normalization import normalize_irrigation_event
from app.domain.messages import Message
from app.domain.recommendation import determine_recommendation
from app.domain.satellite_adjustment import (
    SatelliteObservationInput,
    determine_satellite_adjustment,
)
from app.domain.water_balance import (
    DailyInputs,
    clamp,
    compute_raw,
    compute_taw,
    run_daily_water_balance,
)
from app.providers.factory import get_satellite_provider, get_weather_provider
from app.repositories import analyses as analyses_repo
from app.schemas.analysis import (
    AnalysisListItem,
    AnalysisListResponse,
    AnalysisResponse,
    ConfidenceSchema,
    CropStageSummary,
    DailyWaterBalanceRowSchema,
    FieldSummary,
    InitializationSummary,
    MessageCode,
    RecommendationSchema,
    SatelliteSummary,
    WaterBalanceSummary,
    WeatherSummary,
)
from app.services.fields import get_field_or_404
from app.settings import get_settings

ANALYSIS_METHODOLOGY_VERSION = "0.3.0"


def _to_message_codes(messages: list[Message]) -> list[MessageCode]:
    return [MessageCode(code=m.code, params=m.params, text_en=m.text_en) for m in messages]


def _resolve_soil_water_params(field: Field, soil_profile: SoilProfile) -> tuple[float, float]:
    field_capacity = (
        field.field_capacity_override
        if field.field_capacity_override is not None
        else soil_profile.field_capacity
    )
    wilting_point = (
        field.wilting_point_override
        if field.wilting_point_override is not None
        else soil_profile.wilting_point
    )
    return field_capacity, wilting_point


def _taw_and_raw_at(
    d: date, field: Field, crop_profile: CropProfile, field_capacity: float, wilting_point: float
) -> tuple[float, float]:
    stage = determine_crop_stage(
        planting_date=field.planting_date,
        analysis_date=d,
        crop_profile=crop_profile,
        stage_override=field.crop_stage_override,
    )
    root_depth = (
        field.root_depth_override if field.root_depth_override is not None else stage.root_depth_m
    )
    taw = compute_taw(field_capacity, wilting_point, root_depth)
    raw = compute_raw(taw, stage.depletion_fraction)
    return taw, raw


def _field_summary(field: Field) -> FieldSummary:
    return FieldSummary(
        id=field.id,
        name=field.name,
        crop_type=field.crop_type.value,
        crop_variety=field.crop_variety,
        soil_texture=field.soil_texture.value,
        irrigation_method=field.irrigation_method.value,
        area_hectares=field.area_hectares,
        planting_date=field.planting_date,
        expected_harvest_date=field.expected_harvest_date,
        root_depth_override_m=field.root_depth_override,
        field_capacity_override=field.field_capacity_override,
        wilting_point_override=field.wilting_point_override,
    )


def get_analysis_or_404(db: Session, field_id: int, analysis_id: int) -> Analysis:
    analysis = analyses_repo.get_by_id_for_field(db, field_id, analysis_id)
    if analysis is None:
        raise AppError(
            code="analysis_not_found",
            message_uz=f"{analysis_id} identifikatorli tahlil topilmadi.",
            message_en=f"Analysis {analysis_id} not found for field {field_id}.",
            status_code=404,
        )
    return analysis


def list_analyses(db: Session, field_id: int, *, limit: int, offset: int) -> AnalysisListResponse:
    get_field_or_404(db, field_id)
    items, total = analyses_repo.list_for_field(db, field_id=field_id, limit=limit, offset=offset)
    return AnalysisListResponse(
        items=[
            AnalysisListItem(
                id=item.id,
                requested_at=item.requested_at,
                analysis_date=item.analysis_date,
                data_mode=item.data_mode.value,
                status=item.recommendation.get("status", "unknown")
                if item.recommendation
                else "unknown",
                confidence_category=item.confidence.get("category", "unknown")
                if item.confidence
                else "unknown",
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_analysis_response(db: Session, field_id: int, analysis_id: int) -> AnalysisResponse:
    analysis = get_analysis_or_404(db, field_id, analysis_id)
    return _response_from_orm(analysis)


def _response_from_orm(analysis: Analysis) -> AnalysisResponse:
    wb = analysis.water_balance_summary or {}
    water_balance_summary = WaterBalanceSummary(
        initialization=InitializationSummary.model_validate(wb["initialization"]),
        taw_mm=wb["taw_mm"],
        raw_mm=wb["raw_mm"],
        depletion_before_satellite_adjustment_mm=wb["depletion_before_satellite_adjustment_mm"],
        satellite_adjustment_mm=wb["satellite_adjustment_mm"],
        depletion_mm=wb["depletion_mm"],
        start_date=wb["start_date"],
        end_date=wb["end_date"],
        daily_rows=[DailyWaterBalanceRowSchema.model_validate(r) for r in wb.get("daily_rows", [])],
    )
    return AnalysisResponse(
        id=analysis.id,
        field_id=analysis.field_id,
        requested_at=analysis.requested_at,
        analysis_date=analysis.analysis_date,
        data_mode=analysis.data_mode.value,
        methodology_version=analysis.calculation_version,
        field_summary=FieldSummary.model_validate(wb["input_summary"]),
        crop_stage=CropStageSummary.model_validate(wb["crop_stage"]),
        weather_summary=WeatherSummary.model_validate(analysis.weather_summary),
        satellite_summary=SatelliteSummary.model_validate(analysis.satellite_summary),
        water_balance_summary=water_balance_summary,
        recommendation=RecommendationSchema.model_validate(analysis.recommendation),
        confidence=ConfidenceSchema.model_validate(analysis.confidence),
        warnings=analysis.warnings or [],
    )


def analyze_field(
    db: Session, field_id: int, requested_analysis_date: date | None
) -> AnalysisResponse:
    field = get_field_or_404(db, field_id)
    settings = get_settings()
    config = get_agronomic_config()
    wb_defaults = config.water_balance_defaults
    rec_defaults = config.recommendation_defaults

    analysis_date = requested_analysis_date or date.today()
    requested_at = datetime.now(UTC)

    crop_profile = config.crops.crops[field.crop_type]
    soil_profile = config.soils.soils[field.soil_texture]
    irrigation_profile = config.irrigation_methods.irrigation_methods[field.irrigation_method]

    field_capacity, wilting_point = _resolve_soil_water_params(field, soil_profile)

    crop_stage_result = determine_crop_stage(
        planting_date=field.planting_date,
        analysis_date=analysis_date,
        crop_profile=crop_profile,
        stage_override=field.crop_stage_override,
    )

    def taw_at(d: date) -> float:
        return _taw_and_raw_at(d, field, crop_profile, field_capacity, wilting_point)[0]

    def raw_at(d: date) -> float:
        return _taw_and_raw_at(d, field, crop_profile, field_capacity, wilting_point)[1]

    taw_mm_now, raw_mm_now = _taw_and_raw_at(
        analysis_date, field, crop_profile, field_capacity, wilting_point
    )

    max_anchor_age_days = wb_defaults.initialization.max_anchor_age_days
    lookback_days = max(wb_defaults.satellite.lookback_days, max_anchor_age_days)
    history_start = analysis_date - timedelta(days=lookback_days)
    forecast_window_days = -(-rec_defaults.forecast_rain.window_hours // 24)  # ceiling division
    weather_end = analysis_date + timedelta(days=forecast_window_days)

    irrigation_events_orm = list(
        db.scalars(
            select(IrrigationEvent)
            .where(IrrigationEvent.field_id == field_id)
            .order_by(IrrigationEvent.occurred_at)
        )
    )
    qualitative_map = wb_defaults.qualitative_irrigation_mm.model_dump()

    domain_irrigation_events = [
        IrrigationEventInput(
            occurred_at=event.occurred_at.date(),
            amount_mm=event.amount_mm,
            total_volume_m3=event.total_volume_m3,
            duration_minutes=event.duration_minutes,
            flow_rate_m3_hour=event.flow_rate_m3_hour,
            qualitative_amount=event.qualitative_amount.value if event.qualitative_amount else None,
        )
        for event in irrigation_events_orm
    ]

    # DATA_MODE-driven selection only — see app/providers/factory.py. Never
    # instantiate a concrete provider class here directly, so live mode can
    # never silently end up using fixture data.
    weather_provider = get_weather_provider()
    satellite_provider = get_satellite_provider()

    weather_series = weather_provider.get_daily_series_for_range(
        field.centroid_latitude,
        field.centroid_longitude,
        history_start,
        weather_end,
        as_of=analysis_date,
    )
    weather_by_date = {d.date: d for d in weather_series.days}
    weather_available_dates_past = [d for d in weather_by_date if d <= analysis_date]

    if weather_series.coverage and weather_series.coverage.missing_dates:
        past_missing = [d for d in weather_series.coverage.missing_dates if d <= analysis_date]
        if past_missing:
            all_warnings_weather_gap = (
                f"Weather data unavailable for {len(past_missing)} day(s) in the requested "
                f"range ({weather_series.provider}); those days are excluded from the water "
                "balance rather than assumed to be zero."
            )
        else:
            all_warnings_weather_gap = None
    else:
        all_warnings_weather_gap = None

    # Always use the field's real, complete polygon — never a centroid or
    # an arbitrary bounding box (fixture mode ignores this argument).
    satellite_series = satellite_provider.get_index_timeseries_for_range(
        field.geojson_polygon, history_start, analysis_date
    )
    sat_observation_inputs = [
        SatelliteObservationInput(
            acquisition_date=obs.acquisition_date,
            valid_pixel_ratio=obs.valid_pixel_ratio,
            ndmi_p50=obs.ndmi.p50,
            msi_p50=obs.msi.p50,
            ndvi_p50=obs.ndvi.p50,
        )
        for obs in satellite_series.observations
        # Provider-layer quality gate: corrupt/non-physical/cloud-blotted
        # observations never reach the domain trend-adjustment logic at
        # all. "stale"/"low_valid_pixel_ratio" observations ARE passed
        # through — the domain layer (satellite_adjustment.py) already has
        # its own, more nuanced freshness/pixel-ratio thresholds and is
        # designed to react to them (lower confidence, skip adjustment)
        # rather than being pre-filtered on the same two dimensions twice.
        if obs.quality_status
        not in {"cloud_contaminated", "no_data", "malformed_response", "non_finite_values"}
    ]

    init_result = determine_initialization(
        planting_date=field.planting_date,
        analysis_date=analysis_date,
        irrigation_events=domain_irrigation_events,
        field_area_hectares=field.area_hectares,
        qualitative_irrigation_mm=qualitative_map,
        irrigation_efficiency=irrigation_profile.efficiency,
        max_anchor_age_days=max_anchor_age_days,
        conservative_default_fraction_of_raw=wb_defaults.initialization.conservative_default_fraction_of_raw,
        weather_available_dates=weather_available_dates_past,
        taw_at=taw_at,
        raw_at=raw_at,
    )

    all_warnings: list[str] = list(crop_stage_result.warnings) + list(init_result.warnings)
    if all_warnings_weather_gap:
        all_warnings.append(all_warnings_weather_gap)

    forecast_precip_mm = 0.0
    daily_rows_schema: list[DailyWaterBalanceRowSchema] = []
    weather_days_covered = 0
    weather_days_missing = 0
    depletion_before_adjustment: float | None = None
    wb_start: date | None = None

    if init_result.method == InitializationMethod.INSUFFICIENT_DATA:
        satellite_result = determine_satellite_adjustment(
            analysis_date=analysis_date,
            observations=sat_observation_inputs,
            min_valid_observations_for_trend=wb_defaults.satellite.min_valid_observations_for_trend,
            max_observation_age_days_for_trend=wb_defaults.satellite.max_observation_age_days_for_trend,
            low_valid_pixel_ratio_threshold=wb_defaults.satellite.low_valid_pixel_ratio_threshold,
            trend_adjustment_cap_fraction_of_raw=wb_defaults.satellite.trend_adjustment_cap_fraction_of_raw,
            raw_mm=raw_mm_now,
        )
        adjusted_depletion = None
        weather_available_fraction = 0.0
    else:
        irrigation_mm_by_date: dict[date, float] = {}
        for domain_event in domain_irrigation_events:
            normalized = normalize_irrigation_event(
                amount_mm=domain_event.amount_mm,
                total_volume_m3=domain_event.total_volume_m3,
                duration_minutes=domain_event.duration_minutes,
                flow_rate_m3_hour=domain_event.flow_rate_m3_hour,
                qualitative_amount=domain_event.qualitative_amount,
                field_area_hectares=field.area_hectares,
                qualitative_irrigation_mm=qualitative_map,
            )
            all_warnings.extend(normalized.warnings)
            if normalized.depth_mm is not None:
                d = domain_event.occurred_at
                irrigation_mm_by_date[d] = irrigation_mm_by_date.get(d, 0.0) + normalized.depth_mm

        # Guaranteed by the method check above (only INSUFFICIENT_DATA leaves these unset).
        assert init_result.start_date is not None
        assert init_result.starting_depletion_mm is not None
        daily_inputs: dict[date, DailyInputs] = {}
        current = init_result.start_date
        while current <= analysis_date:
            weather_day = weather_by_date.get(current)
            daily_inputs[current] = DailyInputs(
                et0_mm=weather_day.et0_mm if weather_day else None,
                precipitation_mm=weather_day.precipitation_mm if weather_day else None,
                irrigation_mm=irrigation_mm_by_date.get(current, 0.0),
            )
            current += timedelta(days=1)

        wb_result = run_daily_water_balance(
            planting_date=field.planting_date,
            crop_profile=crop_profile,
            stage_override=field.crop_stage_override,
            field_capacity=field_capacity,
            wilting_point=wilting_point,
            root_depth_override_m=field.root_depth_override,
            irrigation_efficiency=irrigation_profile.efficiency,
            effective_precipitation_factor=wb_defaults.effective_precipitation_factor,
            start_date=init_result.start_date,
            end_date=analysis_date,
            initial_depletion_mm=init_result.starting_depletion_mm,
            daily_inputs=daily_inputs,
        )
        all_warnings.extend(wb_result.warnings)

        depletion_before_adjustment = wb_result.final_depletion_mm
        taw_mm_now = wb_result.final_taw_mm
        raw_mm_now = wb_result.final_raw_mm
        wb_start = init_result.start_date

        total_rows = len(wb_result.rows)
        missing_rows = sum(1 for row in wb_result.rows if row.is_missing_weather)
        weather_available_fraction = (total_rows - missing_rows) / total_rows if total_rows else 0.0
        weather_days_covered = total_rows - missing_rows
        weather_days_missing = missing_rows
        daily_rows_schema = [DailyWaterBalanceRowSchema(**vars(row)) for row in wb_result.rows]

        satellite_result = determine_satellite_adjustment(
            analysis_date=analysis_date,
            observations=sat_observation_inputs,
            min_valid_observations_for_trend=wb_defaults.satellite.min_valid_observations_for_trend,
            max_observation_age_days_for_trend=wb_defaults.satellite.max_observation_age_days_for_trend,
            low_valid_pixel_ratio_threshold=wb_defaults.satellite.low_valid_pixel_ratio_threshold,
            trend_adjustment_cap_fraction_of_raw=wb_defaults.satellite.trend_adjustment_cap_fraction_of_raw,
            raw_mm=raw_mm_now,
        )
        all_warnings.extend(satellite_result.warnings)

        adjusted_depletion = clamp(
            depletion_before_adjustment + satellite_result.adjustment_mm, 0.0, taw_mm_now
        )

        forecast_rows = [
            d
            for d in weather_series.days
            if d.is_forecast and d.date <= analysis_date + timedelta(days=forecast_window_days)
        ]
        forecast_precip_mm = sum(d.precipitation_mm for d in forecast_rows)

    confidence_result = compute_confidence(
        crop_variety_present=field.crop_variety is not None,
        expected_harvest_date_present=field.expected_harvest_date is not None,
        irrigation_method_known=field.irrigation_method != IrrigationMethod.UNKNOWN,
        notes_present=bool(field.notes),
        crop_stage_is_edge_case=crop_stage_result.stage
        in (CropGrowthStage.PRE_PLANTING, CropGrowthStage.POST_SEASON),
        crop_profile_uncertainty_factor=crop_profile.uncertainty_factor,
        soil_profile_uncertainty_factor=soil_profile.uncertainty_factor,
        soil_requires_field_survey=soil_profile.requires_field_survey,
        initialization=init_result,
        weather_available_fraction=weather_available_fraction,
        satellite=satellite_result,
        max_observation_age_days_for_trend=wb_defaults.satellite.max_observation_age_days_for_trend,
        min_valid_observations_for_trend=wb_defaults.satellite.min_valid_observations_for_trend,
        weights=config.confidence_weights.weights,
        high_threshold=config.confidence_weights.thresholds.high,
        medium_threshold=config.confidence_weights.thresholds.medium,
        cap_irrigation_amount_unknown=config.confidence_weights.caps.max_score_if_irrigation_amount_unknown,
        cap_soil_unknown=config.confidence_weights.caps.max_score_if_soil_unknown,
        cap_initialization_weak=config.confidence_weights.caps.max_score_if_initialization_weak,
        cap_satellite_stale_or_low_quality=(
            config.confidence_weights.caps.max_score_if_satellite_stale_or_low_quality
        ),
        cap_weather_missing=config.confidence_weights.caps.max_score_if_weather_missing,
    )

    recommendation_result = determine_recommendation(
        analysis_date=analysis_date,
        depletion_mm=adjusted_depletion,
        taw_mm=taw_mm_now,
        raw_mm=raw_mm_now,
        irrigation_efficiency=irrigation_profile.efficiency,
        practical_min_mm=crop_profile.practical_application_mm.min,
        practical_max_mm=crop_profile.practical_application_mm.max,
        field_area_hectares=field.area_hectares,
        forecast_precipitation_mm=forecast_precip_mm,
        forecast_window_hours=rec_defaults.forecast_rain.window_hours,
        confidence_category=confidence_result.category,
        monitor_depletion_raw_ratio=rec_defaults.status_thresholds.monitor_depletion_raw_ratio,
        irrigate_soon_depletion_raw_ratio=rec_defaults.status_thresholds.irrigate_soon_depletion_raw_ratio,
        irrigate_now_depletion_raw_ratio=rec_defaults.status_thresholds.irrigate_now_depletion_raw_ratio,
        forecast_rain_delay_threshold_mm=rec_defaults.forecast_rain.delay_threshold_mm,
        min_replacement_fraction=rec_defaults.recommended_range.min_replacement_fraction,
        max_replacement_fraction=rec_defaults.recommended_range.max_replacement_fraction,
        uncertainty_range_padding_fraction_medium=rec_defaults.uncertainty_range_padding_fraction_medium,
        uncertainty_range_padding_fraction_low=rec_defaults.uncertainty_range_padding_fraction_low,
        extra_reasons=satellite_result.reasons,
    )
    all_warnings.extend(recommendation_result.warnings)

    field_summary_schema = _field_summary(field)
    crop_stage_schema = CropStageSummary(
        days_after_planting=crop_stage_result.days_after_planting,
        stage=crop_stage_result.stage.value,
        kc=crop_stage_result.kc,
        root_depth_m=crop_stage_result.root_depth_m,
        depletion_fraction=crop_stage_result.depletion_fraction,
        stage_overridden=crop_stage_result.stage_overridden,
        assumptions=crop_stage_result.assumptions,
        warnings=crop_stage_result.warnings,
    )
    initialization_schema = InitializationSummary(
        method=init_result.method.value,
        start_date=init_result.start_date,
        starting_depletion_mm=init_result.starting_depletion_mm,
        uncertainty=init_result.uncertainty,
        warnings=init_result.warnings,
        warning_codes=_to_message_codes(init_result.warning_codes),
    )
    weather_summary_schema = WeatherSummary(
        data_mode=settings.data_mode.value,
        start_date=history_start,
        end_date=weather_end,
        days_covered=weather_days_covered,
        days_missing=weather_days_missing,
        total_et0_mm=sum(row.et0_mm for row in daily_rows_schema),
        total_precipitation_mm=sum(row.precipitation_mm for row in daily_rows_schema),
        forecast_precipitation_mm=forecast_precip_mm,
        forecast_window_hours=rec_defaults.forecast_rain.window_hours,
        provider=weather_series.provider,
        source=weather_series.source,
        retrieved_at=weather_series.retrieved_at,
        cache_hit=weather_series.cache_hit,
        missing_dates=weather_series.coverage.missing_dates if weather_series.coverage else [],
        coverage_ratio=weather_series.coverage.coverage_ratio if weather_series.coverage else 1.0,
        completeness_status=(
            weather_series.coverage.completeness_status if weather_series.coverage else "complete"
        ),
    )
    satellite_summary_schema = SatelliteSummary(
        data_mode=settings.data_mode.value,
        observations_considered=len(sat_observation_inputs),
        valid_observations_used=satellite_result.valid_observations_used,
        latest_observation_date=satellite_result.latest_observation_date,
        latest_observation_age_days=satellite_result.latest_observation_age_days,
        latest_valid_pixel_ratio=satellite_result.latest_valid_pixel_ratio,
        data_quality=satellite_result.data_quality.value,
        adjustment_applied=satellite_result.applied,
        adjustment_mm=satellite_result.adjustment_mm,
        reasons=satellite_result.reasons,
        provider=satellite_series.provider,
        source=satellite_series.source,
        retrieved_at=satellite_series.retrieved_at,
        cache_hit=satellite_series.cache_hit,
        rejected_acquisitions_count=len(satellite_series.rejected_acquisitions),
    )
    water_balance_summary_schema = WaterBalanceSummary(
        initialization=initialization_schema,
        taw_mm=taw_mm_now,
        raw_mm=raw_mm_now,
        depletion_before_satellite_adjustment_mm=depletion_before_adjustment,
        satellite_adjustment_mm=satellite_result.adjustment_mm,
        depletion_mm=adjusted_depletion,
        start_date=wb_start,
        end_date=analysis_date,
        daily_rows=daily_rows_schema,
    )
    recommendation_schema = RecommendationSchema(
        status=recommendation_result.status.value,
        depletion_mm=recommendation_result.depletion_mm,
        base_gross_mm=recommendation_result.base_gross_mm,
        recommended_min_mm=recommendation_result.recommended_min_mm,
        recommended_max_mm=recommendation_result.recommended_max_mm,
        recommended_min_m3_per_ha=recommendation_result.recommended_min_m3_per_ha,
        recommended_max_m3_per_ha=recommendation_result.recommended_max_m3_per_ha,
        total_min_volume_m3=recommendation_result.total_min_volume_m3,
        total_max_volume_m3=recommendation_result.total_max_volume_m3,
        window_start_date=recommendation_result.window.start_date
        if recommendation_result.window
        else None,
        window_end_date=recommendation_result.window.end_date
        if recommendation_result.window
        else None,
        reasons=recommendation_result.reasons,
        warnings=recommendation_result.warnings,
        reason_codes=_to_message_codes(recommendation_result.reason_codes),
        warning_codes=_to_message_codes(recommendation_result.warning_codes),
    )
    confidence_schema = ConfidenceSchema(
        score=confidence_result.score,
        category=confidence_result.category,
        factor_scores=confidence_result.factor_scores.as_dict(),
        weights=confidence_result.weights,
        triggered_caps=confidence_result.triggered_caps,
        strong_factors=confidence_result.strong_factors,
        weak_factors=confidence_result.weak_factors,
    )

    # Deduplicate warnings while preserving order.
    deduped_warnings = list(dict.fromkeys(all_warnings))

    analysis = Analysis(
        field_id=field.id,
        requested_at=requested_at,
        analysis_date=analysis_date,
        data_mode=AnalysisDataMode(settings.data_mode.value),
        satellite_summary=satellite_summary_schema.model_dump(mode="json"),
        weather_summary=weather_summary_schema.model_dump(mode="json"),
        water_balance_summary={
            "input_summary": field_summary_schema.model_dump(mode="json"),
            "crop_stage": crop_stage_schema.model_dump(mode="json"),
            "initialization": initialization_schema.model_dump(mode="json"),
            "taw_mm": taw_mm_now,
            "raw_mm": raw_mm_now,
            "depletion_before_satellite_adjustment_mm": depletion_before_adjustment,
            "satellite_adjustment_mm": satellite_result.adjustment_mm,
            "depletion_mm": adjusted_depletion,
            "start_date": wb_start.isoformat() if wb_start else None,
            "end_date": analysis_date.isoformat(),
            "daily_rows": [row.model_dump(mode="json") for row in daily_rows_schema],
        },
        recommendation=recommendation_schema.model_dump(mode="json"),
        confidence=confidence_schema.model_dump(mode="json"),
        warnings=deduped_warnings,
        calculation_version=ANALYSIS_METHODOLOGY_VERSION,
    )
    analyses_repo.create(db, analysis)
    db.commit()
    db.refresh(analysis)

    return AnalysisResponse(
        id=analysis.id,
        field_id=analysis.field_id,
        requested_at=analysis.requested_at,
        analysis_date=analysis.analysis_date,
        data_mode=analysis.data_mode.value,
        methodology_version=analysis.calculation_version,
        field_summary=field_summary_schema,
        crop_stage=crop_stage_schema,
        weather_summary=weather_summary_schema,
        satellite_summary=satellite_summary_schema,
        water_balance_summary=water_balance_summary_schema,
        recommendation=recommendation_schema,
        confidence=confidence_schema,
        warnings=deduped_warnings,
    )
