from fastapi import APIRouter

from app.domain.config_loader import get_agronomic_config

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/options")
def get_options() -> dict:
    config = get_agronomic_config()
    return {
        "methodology_version": config.water_balance_defaults.methodology_version,
        "crops": {
            key: {"label_uz": profile.label_uz} for key, profile in config.crops.crops.items()
        },
        "soils": {
            key: {"label_uz": profile.label_uz} for key, profile in config.soils.soils.items()
        },
        "irrigation_methods": {
            key: {"label_uz": profile.label_uz}
            for key, profile in config.irrigation_methods.irrigation_methods.items()
        },
    }
