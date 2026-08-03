import pytest
from pydantic import ValidationError

from app.schemas.farmer import FarmerCreate


def test_valid_farmer_create() -> None:
    farmer = FarmerCreate(
        full_name="Aliyev Vali",
        phone="+998901234567",
        region="Toshkent viloyati",
        district="Zangiota tumani",
    )
    assert farmer.phone == "+998901234567"
    assert farmer.preferred_language == "uz"


@pytest.mark.parametrize(
    "phone",
    ["12345", "not-a-phone", "+998", "0901234567890123456", "++998901234567"],
)
def test_rejects_invalid_phone(phone: str) -> None:
    with pytest.raises(ValidationError):
        FarmerCreate(full_name="Aliyev Vali", phone=phone, region="Xorazm", district="Yakkabog'")


def test_rejects_invalid_email() -> None:
    with pytest.raises(ValidationError):
        FarmerCreate(
            full_name="Aliyev Vali",
            phone="+998901234567",
            email="not-an-email",
            region="Xorazm",
            district="Yakkabog'",
        )


def test_accepts_valid_email() -> None:
    farmer = FarmerCreate(
        full_name="Aliyev Vali",
        phone="+998901234567",
        email="farmer@example.com",
        region="Xorazm",
        district="Yakkabog'",
    )
    assert farmer.email == "farmer@example.com"


@pytest.mark.parametrize("blank", ["", "   "])
def test_rejects_blank_full_name(blank: str) -> None:
    with pytest.raises(ValidationError):
        FarmerCreate(full_name=blank, phone="+998901234567", region="Xorazm", district="Yakkabog'")
